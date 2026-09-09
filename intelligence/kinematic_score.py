"""Predictive kinematic threat model — a continuous alternative to the tiered
sector score in threat_score.py.

    S_total = ( alpha * exp(-lambda * d)
              + beta  * max(0, 1 / (TTB + epsilon))
              + gamma * ln(1 + L_t) ) * W_class * C_det

    d     shortest Euclidean distance (px) from the object's ground point to
          the border line
    TTB   time-to-breach in seconds: d / closing speed, +inf when not approaching
    L_t   dwell time in seconds
    W_class  class multiplier (vehicle > person > animal)
    C_det    detector confidence, 0..1

Why this shape rather than the additive tier model:
  - Proximity decays EXPONENTIALLY, so the last few metres at the fence carry
    far more weight than the same distance crossed out in the approach strip.
    A linear term would score those equally.
  - TTB is predictive rather than descriptive. Someone sprinting parallel to
    the fence has high speed but infinite TTB and contributes nothing; someone
    walking slowly straight at it has a short TTB and scores high. The tiered
    model's speed term could not tell those apart.
  - Loitering is logarithmic: the jump from 0s to 30s standing at the line
    matters much more than 300s to 330s, and ln saturates accordingly instead
    of growing without bound.
"""
import math

# Same tier boundaries as the tiered scorer, so alerting, the incident store
# and the dashboard read one consistent 0-100 scale whichever model is active.
GREEN_MAX = 30
YELLOW_MAX = 69


class KinematicThreatScore:
    """Result object, interface-compatible with ThreatScore where it counts:
    `.total`, `.tier`, `.override_reason` and `.breakdown()` are what the alert
    manager, incident store and overlay consume."""

    __slots__ = (
        "proximity", "ttb_term", "loiter_term", "class_multiplier", "confidence",
        "distance_px", "ttb_seconds", "dwell_seconds", "raw", "total", "tier",
        "override_reason",
    )

    OVERRIDE_MIN_TOTAL = 70.0

    def __init__(
        self,
        proximity: float,
        ttb_term: float,
        loiter_term: float,
        class_multiplier: float,
        confidence: float,
        distance_px: float,
        ttb_seconds: float,
        dwell_seconds: float,
        override_reason: "str | None" = None,
    ):
        self.proximity = proximity
        self.ttb_term = ttb_term
        self.loiter_term = loiter_term
        self.class_multiplier = class_multiplier
        self.confidence = confidence
        self.distance_px = distance_px
        self.ttb_seconds = ttb_seconds
        self.dwell_seconds = dwell_seconds

        self.raw = (proximity + ttb_term + loiter_term) * class_multiplier * confidence
        self.total = max(0.0, min(100.0, self.raw))

        if self.total <= GREEN_MAX:
            self.tier = "green"
        elif self.total <= YELLOW_MAX:
            self.tier = "yellow"
        else:
            self.tier = "red"

        self.override_reason = override_reason
        if override_reason is not None:
            self.tier = "red"
            self.total = max(self.total, self.OVERRIDE_MIN_TOTAL)

    def breakdown(self) -> str:
        """One-line "why", matching ThreatScore.breakdown()'s contract: only
        contributing terms, so a sentry reads the cause at a glance."""
        parts = [
            ("prox", self.proximity),
            ("ttb", self.ttb_term),
            ("loiter", self.loiter_term),
        ]
        summary = " + ".join(f"{n} {v:.1f}" for n, v in parts if v > 0.05) or "none"
        ttb = "never" if math.isinf(self.ttb_seconds) else f"{self.ttb_seconds:.1f}s"
        summary += (
            f" | d={self.distance_px:.0f}px TTB={ttb} dwell={self.dwell_seconds:.0f}s"
            f" xW{self.class_multiplier:g} xC{self.confidence:.2f}"
        )
        if self.raw > 100.0:
            summary += f" (raw {self.raw:.0f}, capped)"
        if self.override_reason is not None:
            summary += f"  [forced RED: {self.override_reason}]"
        return summary


class KinematicThreatScorer:
    """Evaluates the equation above against one camera's border line.

    With no border line drawn the model has no geometry to work from, so every
    detection scores 0 and stays Green. That is deliberate and mirrors the
    tiered model's behaviour without zones: better a silent system the operator
    notices is unconfigured than a confident-looking score built on nothing.
    """

    def __init__(
        self,
        border_store,
        alpha: float = 45.0,
        decay_lambda: float = 0.010,
        beta: float = 25.0,
        gamma: float = 5.0,
        epsilon: float = 1.0,
        class_weights: "dict | None" = None,
        nominal_fps: float = 20.0,
    ):
        self.border_store = border_store
        self.alpha = alpha
        self.decay_lambda = decay_lambda
        self.beta = beta
        self.gamma = gamma
        self.epsilon = epsilon
        self.class_weights = class_weights or {"vehicle": 1.5, "person": 1.0, "animal": 0.4}
        self.nominal_fps = nominal_fps

    def score(
        self,
        ground_point,
        category: str,
        confidence: float,
        direction=None,
        speed_px_per_frame: float = 0.0,
        dwell_seconds: float = 0.0,
        fps: "float | None" = None,
        override_reason: "str | None" = None,
    ) -> KinematicThreatScore:
        line = self.border_store.line
        weight = self.class_weights.get(category, 1.0)
        confidence = max(0.0, min(1.0, float(confidence)))

        if line is None:
            return KinematicThreatScore(
                0.0, 0.0, 0.0, weight, confidence,
                distance_px=math.inf, ttb_seconds=math.inf,
                dwell_seconds=dwell_seconds, override_reason=override_reason,
            )

        distance = line.distance_to(ground_point)

        # E_p — exponential proximity.
        proximity = self.alpha * math.exp(-self.decay_lambda * distance)

        # TTB — needs velocity in px/SECOND. The tracker reports a displacement
        # vector plus a px/frame magnitude, so rebuild the vector at unit length
        # and scale by speed and the measured frame rate. A cold/implausible fps
        # falls back to the nominal rate rather than producing a wild TTB.
        effective_fps = fps if (fps and fps > 1.0) else self.nominal_fps
        ttb = math.inf
        if direction is not None and speed_px_per_frame > 0.0:
            magnitude = math.hypot(direction[0], direction[1])
            if magnitude > 0.0:
                scale = speed_px_per_frame * effective_fps / magnitude
                velocity = (direction[0] * scale, direction[1] * scale)
                ttb = line.time_to_breach(ground_point, velocity)
        ttb_term = 0.0 if math.isinf(ttb) else self.beta * max(0.0, 1.0 / (ttb + self.epsilon))

        # L_t — logarithmic dwell.
        loiter_term = self.gamma * math.log1p(max(0.0, dwell_seconds))

        return KinematicThreatScore(
            proximity, ttb_term, loiter_term, weight, confidence,
            distance_px=distance, ttb_seconds=ttb, dwell_seconds=dwell_seconds,
            override_reason=override_reason,
        )

from intelligence.threat_rules import ThreatRulesDB

GREEN_MAX = 30
YELLOW_MAX = 69


class ThreatScore:
    __slots__ = (
        "sector_risk", "time_risk", "kinematics_risk", "class_confidence",
        "direction_risk", "loiter_risk", "group_risk", "total", "tier",
        "override_reason",
    )

    # A breach of the border line is a priority event whatever the clock says.
    # An additive score can't express that through weights alone without
    # distorting every other case, so it is an explicit override — the same
    # pattern the watchlist match already uses. The component breakdown is
    # still reported, so the escalation stays transparent rather than magic.
    OVERRIDE_MIN_TOTAL = 70.0

    def __init__(
        self,
        sector_risk: float,
        time_risk: float,
        kinematics_risk: float,
        class_confidence: float,
        direction_risk: float = 0.0,
        loiter_risk: float = 0.0,
        group_risk: float = 0.0,
        override_reason: "str | None" = None,
    ):
        self.sector_risk = sector_risk
        self.time_risk = time_risk
        self.kinematics_risk = kinematics_risk
        self.class_confidence = class_confidence
        self.direction_risk = direction_risk
        self.loiter_risk = loiter_risk
        self.group_risk = group_risk
        self.total = min(
            100.0,
            sector_risk + time_risk + kinematics_risk + class_confidence
            + direction_risk + loiter_risk + group_risk,
        )
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
        """One-line "why", for the log and the on-screen overlay. Only the
        components that actually contributed are listed, so a sentry reads the
        cause of a Red at a glance instead of seven mostly-zero numbers."""
        parts = [
            ("sector", self.sector_risk), ("time", self.time_risk),
            ("move", self.kinematics_risk), ("class", self.class_confidence),
            ("direction", self.direction_risk), ("loiter", self.loiter_risk),
            ("group", self.group_risk),
        ]
        summary = " + ".join(f"{n} {v:.0f}" for n, v in parts if v > 0) or "none"
        if self.override_reason is not None:
            summary += f"  [forced RED: {self.override_reason}]"
        return summary


class ThreatScorer:
    """Combines the offline rule lookups into one transparent 0-100 score:

        T = S_sector + T_time + K_kinematics + C_class
            + D_direction + L_loiter + G_group

    0-30 -> Green (log), 31-69 -> Yellow (warn+snapshot), 70-100 -> Red
    (priority). Deliberately transparent: a sentry sees *why* something scored
    Red — which component drove it — not just a black-box alert.

    The last three terms are what make this a *border* rule set rather than a
    generic intrusion alarm:
      - direction: crossing the line matters, and in both senses (inward is
        infiltration, outward is exfiltration/smuggling). Walking parallel to
        the fence scores lower but is not free — that is what reconnaissance
        along a fence looks like.
      - loiter: dwell time inside a zone, keyed on the Re-ID person_id so it
        survives the tracker losing and re-acquiring someone. Standing still
        at the fence is invisible to a speed-based rule.
      - group: several people at the line together is a different event from
        one person.
    """

    def __init__(self, rules: ThreatRulesDB):
        self.rules = rules

    def score(
        self,
        zone_tier: str,
        hour: int,
        speed_px_per_frame: float,
        category: str,
        zone_direction: "str | None" = None,
        dwell_seconds: float = 0.0,
        group_count: int = 1,
    ) -> ThreatScore:
        sector_risk = self.rules.get_sector_risk(zone_tier or "none")
        time_risk = self.rules.get_time_risk(hour)
        class_confidence = self.rules.get_class_confidence(category)
        kinematics_risk = self._kinematics_risk(speed_px_per_frame)

        # The border-specific terms apply to people inside a defined zone.
        # Outside any zone there is no border line to cross, loiter at, or
        # gather on, so charging for them would just re-create the alert flood
        # the old rule set produced on un-zoned footage.
        in_zone = bool(zone_tier) and zone_tier != "none"
        is_person = category == "person"
        direction_risk = self.rules.get_direction_risk(zone_direction) if in_zone else 0.0
        loiter_risk = (
            self._loiter_risk(dwell_seconds) if in_zone and is_person else 0.0
        )
        group_risk = (
            self.rules.get_group_risk(group_count) if in_zone and is_person else 0.0
        )

        return ThreatScore(
            sector_risk, time_risk, kinematics_risk, class_confidence,
            direction_risk, loiter_risk, group_risk,
            override_reason=self._crossing_override(zone_tier, zone_direction, category),
        )

    # Animals are deliberately exempt: livestock and strays cross a border line
    # constantly, and forcing every one of them to Red is exactly the false-alarm
    # source that gets a system switched off.
    CROSSING_DIRECTIONS = ("inward", "outward", "crossing")
    OVERRIDE_CATEGORIES = ("person", "vehicle")

    def _crossing_override(
        self, zone_tier: str, zone_direction: "str | None", category: str
    ) -> "str | None":
        if zone_tier != "red":
            return None
        if category not in self.OVERRIDE_CATEGORIES:
            return None
        if zone_direction not in self.CROSSING_DIRECTIONS:
            return None
        return f"{category} crossing the border line ({zone_direction})"

    def _kinematics_risk(self, speed: float) -> float:
        """U-curve: both near-stationary and running score high, an ordinary
        walking pace scores lowest.

            risk
             max |\                    /
                 | \                  /
               0 |  \________________/
                 +--|----|--------|--|----> speed
                  still walk_min walk_max fast

        The old rule was a straight line with "faster = worse", which scored a
        man lying still at the fence — the textbook infiltration posture — as
        zero risk.
        """
        config = self.rules.get_movement_config()
        still = config["still_speed_px_per_frame"]
        walk_min = config["walk_min_px_per_frame"]
        walk_max = config["walk_max_px_per_frame"]
        fast = config["fast_speed_px_per_frame"]
        max_risk = config["max_movement_risk"]

        if speed <= still:
            return max_risk
        if speed < walk_min:
            # Ramping down out of "stationary" into the walking band.
            fraction = (speed - still) / (walk_min - still)
            return (1.0 - fraction) * max_risk
        if speed <= walk_max:
            return 0.0
        if speed >= fast:
            return max_risk
        fraction = (speed - walk_max) / (fast - walk_max)
        return fraction * max_risk

    def _loiter_risk(self, dwell_seconds: float) -> float:
        config = self.rules.get_loiter_config()
        if dwell_seconds >= config["alert_seconds"]:
            return config["alert_risk"]
        if dwell_seconds >= config["warn_seconds"]:
            return config["warn_risk"]
        return 0.0

"""The border as a line vector, rather than a filled polygon.

The tiered zone model answers "which region is this in?". A border line answers
"how far from the line, and closing how fast?" — which is what the predictive
kinematic score needs. The two coexist: ZoneEngine still classifies sectors,
this supplies the continuous geometry.
"""
import json
import logging
import math
import os

log = logging.getLogger("ibvap.zones")


class BorderLine:
    """A finite border segment in camera pixel coordinates.

    Distance is measured to the SEGMENT, not the infinite line it lies on. A
    drawn border has ends; an object 500px beyond the end of the fence is far
    from the border even if it sits exactly on the line's mathematical
    extension, and an infinite-line distance would wrongly read that as zero.
    """

    __slots__ = ("p1", "p2")

    def __init__(self, p1, p2):
        self.p1 = (float(p1[0]), float(p1[1]))
        self.p2 = (float(p2[0]), float(p2[1]))

    # -- geometry -----------------------------------------------------------
    def _nearest_point(self, point):
        """Closest point on the segment, and the parameter t along it."""
        (x1, y1), (x2, y2) = self.p1, self.p2
        vx, vy = x2 - x1, y2 - y1
        length_sq = vx * vx + vy * vy
        if length_sq == 0.0:
            return self.p1, 0.0
        wx, wy = point[0] - x1, point[1] - y1
        t = (wx * vx + wy * vy) / length_sq
        t = max(0.0, min(1.0, t))          # clamp: segment, not infinite line
        return (x1 + t * vx, y1 + t * vy), t

    def distance_to(self, point) -> float:
        """Shortest Euclidean distance in pixels — `d` in the threat equation."""
        nearest, _t = self._nearest_point(point)
        return math.hypot(point[0] - nearest[0], point[1] - nearest[1])

    def signed_side(self, point) -> float:
        """>0 one side, <0 the other, 0 on the line. Which side is "ours"
        depends on how the operator drew it; the sign is only used to detect
        that a track has changed sides, i.e. crossed."""
        (x1, y1), (x2, y2) = self.p1, self.p2
        return (x2 - x1) * (point[1] - y1) - (y2 - y1) * (point[0] - x1)

    def closing_speed(self, point, velocity) -> float:
        """Component of `velocity` pointing at the nearest point on the border.

        Positive means the gap is shrinking. This is the projection of the
        velocity onto the unit vector from the object toward the border — the
        rate of change of `distance_to`, which is exactly what Time-To-Breach
        divides by. Using raw speed instead would treat someone sprinting
        *parallel* to the fence as an imminent breach.
        """
        nearest, _t = self._nearest_point(point)
        dx, dy = nearest[0] - point[0], nearest[1] - point[1]
        distance = math.hypot(dx, dy)
        if distance == 0.0:
            return 0.0                      # already on the line
        return (velocity[0] * dx + velocity[1] * dy) / distance

    def time_to_breach(self, point, velocity) -> float:
        """Seconds until the object reaches the border at its current closing
        speed, or +inf when it is stationary or moving away.

        `velocity` must be in pixels per SECOND, so the result is in seconds.
        Infinity is the honest answer for "never at this rate"; the caller
        turns that into a zero contribution rather than a division by zero.
        """
        closing = self.closing_speed(point, velocity)
        if closing <= 0.0:
            return math.inf
        return self.distance_to(point) / closing

    # -- persistence --------------------------------------------------------
    def to_dict(self) -> dict:
        return {"p1": list(self.p1), "p2": list(self.p2)}

    @classmethod
    def from_dict(cls, data: dict) -> "BorderLine":
        return cls(data["p1"], data["p2"])

    def __repr__(self) -> str:
        return f"BorderLine({self.p1} -> {self.p2})"


class BorderLineStore:
    """Loads/saves one camera's border line as JSON, mirroring how ZoneEngine
    persists its polygons so both are drawn once and reloaded on start."""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.line: "BorderLine | None" = None
        self.load()

    def load(self) -> None:
        if not os.path.exists(self.config_path):
            return
        try:
            with open(self.config_path) as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            log.warning("Could not read border line %s: %s", self.config_path, e)
            return
        if data:
            self.line = BorderLine.from_dict(data)
            log.info("Loaded border line from %s: %s", self.config_path, self.line)

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.config_path) or ".", exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(self.line.to_dict() if self.line else {}, f, indent=2)

    def set_line(self, line: "BorderLine | None") -> None:
        self.line = line
        self.save()

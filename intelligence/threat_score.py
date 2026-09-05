from intelligence.threat_rules import ThreatRulesDB

GREEN_MAX = 30
YELLOW_MAX = 69


class ThreatScore:
    __slots__ = ("sector_risk", "time_risk", "kinematics_risk", "class_confidence", "total", "tier")

    def __init__(
        self, sector_risk: float, time_risk: float, kinematics_risk: float, class_confidence: float
    ):
        self.sector_risk = sector_risk
        self.time_risk = time_risk
        self.kinematics_risk = kinematics_risk
        self.class_confidence = class_confidence
        self.total = sector_risk + time_risk + kinematics_risk + class_confidence
        if self.total <= GREEN_MAX:
            self.tier = "green"
        elif self.total <= YELLOW_MAX:
            self.tier = "yellow"
        else:
            self.tier = "red"


class ThreatScorer:
    """Combines Phase 9's rule lookups into one transparent 0-100 score:

        T = S_sector + T_time + K_kinematics + C_class

    0-30 -> Green (log), 31-69 -> Yellow (warn+snapshot), 70-100 -> Red
    (priority). Deliberately transparent (roadmap's novelty pitch #2): a
    sentry sees *why* something scored Red — which component drove it — not
    just a black-box alert.
    """

    def __init__(self, rules: ThreatRulesDB):
        self.rules = rules

    def score(self, zone_tier: str, hour: int, speed_px_per_frame: float, category: str) -> ThreatScore:
        sector_risk = self.rules.get_sector_risk(zone_tier or "none")
        time_risk = self.rules.get_time_risk(hour)
        class_confidence = self.rules.get_class_confidence(category)
        kinematics_risk = self._kinematics_risk(speed_px_per_frame)
        return ThreatScore(sector_risk, time_risk, kinematics_risk, class_confidence)

    def _kinematics_risk(self, speed: float) -> float:
        config = self.rules.get_movement_config()
        slow = config["slow_speed_px_per_frame"]
        fast = config["fast_speed_px_per_frame"]
        max_risk = config["max_movement_risk"]

        if speed <= slow:
            return 0.0
        if speed >= fast:
            return max_risk
        fraction = (speed - slow) / (fast - slow)
        return fraction * max_risk

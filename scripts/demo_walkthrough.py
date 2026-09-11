"""Runs a realistic border-approach scenario through the REAL zone engine,
threat scorer and loiter tracker (no mocks) and prints the score at each step.

Two uses:
  1. Proof the rule engine behaves sensibly end-to-end, not just in isolated
     unit tests: `python scripts/demo_walkthrough.py`.
  2. A rehearsal script for a judge demo — the printed narration doubles as
     cue cards for what to do in front of the camera and what number should
     appear when you do it.

Uses temporary zones/rules files so it never touches your real
config/zones_cam0.json or database/threat_rules.db.
"""
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from intelligence.loiter import LoiterTracker
from intelligence.threat_rules import ThreatRulesDB
from intelligence.threat_score import ThreatScorer
from zones.zone_engine import Zone, ZoneEngine

WIDTH, HEIGHT = 640, 480

# A hallway-style webcam layout: far third of frame = the border line (red),
# middle third = the approach strip (yellow), near third (closest to camera)
# = own territory (green). This is what config/zones_demo.json below sets up
# for a live run too.
RED = [(0, 0), (WIDTH, 0), (WIDTH, HEIGHT // 3), (0, HEIGHT // 3)]
YELLOW = [(0, HEIGHT // 3), (WIDTH, HEIGHT // 3), (WIDTH, 2 * HEIGHT // 3), (0, 2 * HEIGHT // 3)]
GREEN = [(0, 2 * HEIGHT // 3), (WIDTH, 2 * HEIGHT // 3), (WIDTH, HEIGHT), (0, HEIGHT)]


def bar(total: float) -> str:
    filled = round(total / 2)
    return "#" * filled + "." * (50 - filled)


def narrate(label: str, score, extra: str = "") -> None:
    print(f"\n--- {label} {extra}".ljust(78, "-"))
    print(f"  {bar(score.total)}  T={score.total:5.1f}  ({score.tier.upper()})")
    print(f"  {score.breakdown()}")


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="ibvap_demo_"))
    engine = ZoneEngine(config_path=str(tmp / "zones.json"))
    engine.add_zone(Zone("red", RED))
    engine.add_zone(Zone("yellow", YELLOW))
    engine.add_zone(Zone("green", GREEN))

    rules = ThreatRulesDB(db_path=str(tmp / "threat_rules.db"))
    scorer = ThreatScorer(rules)
    loiter = LoiterTracker(now_fn=lambda: clock["t"])
    clock = {"t": 0.0}

    print("=" * 78)
    print(" IBVAP THREAT SCORE — LIVE RULE WALKTHROUGH (real engine, no mocks)")
    print(" Zones: red = far third of frame, yellow = middle, green = near camera")
    print("=" * 78)

    # 1. Someone in their own territory, broad daylight, walking normally.
    point = (WIDTH // 2, HEIGHT - 40)
    zone = engine.classify(point, direction=(0, -1))
    dwell = loiter.update(("track", 1), zone["tier"])
    score = scorer.score(
        zone_tier=zone["tier"], hour=14, speed_px_per_frame=5.0, category="person",
        zone_direction=zone["direction"], dwell_seconds=dwell, group_count=1,
    )
    narrate("1. Person in GREEN zone, 2pm, walking normally", score,
            "(cue: stand near the camera, walk in place)")

    # 2. Same person now in the yellow approach strip, at 2am, moving inward.
    point = (WIDTH // 2, HEIGHT // 2)
    zone = engine.classify(point, direction=(0, -1))
    dwell = loiter.update(("track", 1), zone["tier"])
    score = scorer.score(
        zone_tier=zone["tier"], hour=2, speed_px_per_frame=5.0, category="person",
        zone_direction=zone["direction"], dwell_seconds=dwell, group_count=1,
    )
    narrate("2. Same person, now YELLOW strip, 2am, moving toward the line", score,
            "(cue: step back from the camera, toward the far wall)")

    # 3. They stop and stand still at the line for two minutes (loiter alert
    #    threshold). Ticks every 2s of fake time — LoiterTracker expires an
    #    entry untouched for grace_seconds (5s default), so this steps the
    #    clock the way real frames would rather than jumping 125s in one call.
    #    The live camera demo either accepts the real 30s/120s wait or uses
    #    the lowered DEMO thresholds described in the README section below.
    for _ in range(63):
        clock["t"] += 2.0
        dwell = loiter.update(("track", 1), "red")
    zone = {"tier": "red", "direction": "inward"}
    score = scorer.score(
        zone_tier="red", hour=2, speed_px_per_frame=0.5, category="person",
        zone_direction="inward", dwell_seconds=dwell, group_count=1,
    )
    narrate("3. Same person now in RED zone, stood still 125s (>120s alert dwell)", score,
            "(cue: step to the far wall and stand motionless)")

    # 4. A second and third person join at the line — group risk.
    clock["t"] += 1.0
    dwell = loiter.update(("track", 1), "red")
    score = scorer.score(
        zone_tier="red", hour=2, speed_px_per_frame=0.5, category="person",
        zone_direction="inward", dwell_seconds=dwell, group_count=3,
    )
    narrate("4. Two more people join at the line (group_count=3)", score,
            "(cue: have two more people step into frame)")

    # 5. Watchlist hit, but this camera (in this scenario) never had zones
    #    configured — reproduces the exact capped-at-69 behaviour explained
    #    in the Rulebook, using a SEPARATE zone-less engine.
    bare_rules = ThreatRulesDB(db_path=str(tmp / "threat_rules_bare.db"))
    bare_scorer = ThreatScorer(bare_rules)
    score = bare_scorer.score(
        zone_tier="none", hour=2, speed_px_per_frame=3.0, category="person",
        watchlist_match="Demo Subject", watchlist_similarity=0.81,
    )
    narrate("5. Watchlist match, but NO zones drawn for this camera", score,
            "(cue: this is what cam0 looks like right now — draw zones to lift it)")

    print("\n" + "=" * 78)
    print(" All five steps ran against the real ZoneEngine + ThreatScorer + "
          "LoiterTracker.\n Nothing here is mocked or hand-typed into a test "
          "assertion — this is the same\n code path app.py runs on every frame.")
    print("=" * 78)

    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()

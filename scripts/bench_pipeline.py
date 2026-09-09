"""Headless per-stage benchmark for the IBVAP pipeline.

    python scripts/bench_pipeline.py [--frames 120]

Runs every stage the live loop runs, on the real models, and reports each
stage's latency. Headless and self-contained: no camera, no window, and every
database/evidence path is redirected into a temporary directory, so a run
never touches database/incidents.db, the watchlist, or snapshots/.

Re-ID and face recognition are driven from a fixed synthetic person box rather
than waiting for the detector to find a real person, so their cost is measured
on every frame instead of only when a subject happens to be present. That
makes the numbers reproducible run-to-run, which is the point: this exists to
compare a *before* and an *after*.
"""
import argparse
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from activity_gate.gate import ActivityGate  # noqa: E402
from alerts.alert_manager import AlertManager  # noqa: E402
from config.settings import (  # noqa: E402
    BRIGHTNESS_THRESHOLD, CAMERA_HEIGHT, CAMERA_WIDTH, DETECTION_CONFIDENCE,
    DETECTION_MODEL_PATH, REID_MATCH_MARGIN, REID_MODEL_PATH,
    REID_SIMILARITY_THRESHOLD, REID_TTL_SECONDS, WATCHLIST_SIMILARITY_THRESHOLD,
)
from detection.draw import draw_detections  # noqa: E402
from face.face_recognizer import FaceRecognizer  # noqa: E402
from face.watchlist import WatchlistDB, WatchlistMatcher  # noqa: E402
from filtering.false_alarm import FalseAlarmFilter  # noqa: E402
from intelligence.loiter import LoiterTracker  # noqa: E402
from intelligence.threat_rules import ThreatRulesDB  # noqa: E402
from intelligence.threat_score import ThreatScorer  # noqa: E402
from preprocessing.enhance import Preprocessor  # noqa: E402
from profiling.stage_profiler import StageProfiler  # noqa: E402
from reid.embedder import OSNetEmbedder  # noqa: E402
from reid.reid import PersonGallery  # noqa: E402
from tracking.tracker import Tracker  # noqa: E402
from zones.zone_engine import Zone, ZoneEngine  # noqa: E402

PERSON_BOX = (240, 140, 330, 400)  # a plausible upright person at 640x480


def make_frames(count: int, width: int, height: int, dark: bool):
    """A moving figure against a textured ground.

    Texture matters: a flat fill makes the temporal median filter and the
    JPEG-ish workloads unrealistically cheap, and gives ByteTrack nothing to
    latch onto. `dark` drives the frame below BRIGHTNESS_THRESHOLD so the
    low-light branch (CLAHE + gamma + median) is exercised.
    """
    rng = np.random.default_rng(1234)
    base_level = 45 if dark else 150
    frames = []
    for i in range(count):
        f = rng.integers(base_level - 25, base_level + 25,
                         (height, width, 3), dtype=np.uint8)
        shift = (i * 4) % 200
        x1, y1, x2, y2 = PERSON_BOX
        cv2.rectangle(f, (x1 + shift, y1), (x2 + shift, y2),
                      (base_level + 60,) * 3, -1)
        cv2.circle(f, (x1 + shift + 45, y1 - 25), 28, (base_level + 70,) * 3, -1)
        frames.append(f)
    return frames


class _Det:
    """Minimal stand-in matching the attributes the later stages read."""
    def __init__(self, box):
        self.box = box
        self.track_id = 1
        self.person_id = None
        self.direction = (6.0, 0.0)
        self.speed = 6.0
        self.zone_tier = "none"
        self.zone_direction = None
        self.watchlist_match = None
        self.watchlist_similarity = 0.0

    def category(self):
        return "person"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--frames", type=int, default=120)
    ap.add_argument("--dark", action="store_true",
                    help="exercise the low-light preprocessing branch")
    ap.add_argument("--label", default="", help="tag printed with the report")
    ap.add_argument("--legacy-median", action="store_true",
                    help="restore the pre-optimization axis=0 temporal median, for "
                         "a controlled A/B. Patches the harness only — the shipped "
                         "module is untouched, so both arms run identical code "
                         "everywhere else.")
    args = ap.parse_args()

    if args.legacy_median:
        import numpy as _np
        from preprocessing import enhance as _enhance

        def _legacy_apply(self, frame):
            self._buffer.append(frame)
            if len(self._buffer) < 2:
                return frame
            stacked = _np.stack(self._buffer, axis=0)
            return _np.median(stacked, axis=0).astype(_np.uint8)

        _enhance.TemporalMedianFilter.apply = _legacy_apply

    tmp = tempfile.mkdtemp(prefix="ibvap-bench-")
    try:
        run(args, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run(args, tmp: str) -> None:
    width, height = CAMERA_WIDTH, CAMERA_HEIGHT
    frames = make_frames(args.frames + 5, width, height, args.dark)

    gate = ActivityGate()
    preprocessor = Preprocessor("bench", brightness_threshold=BRIGHTNESS_THRESHOLD)
    tracker = Tracker(model_path=DETECTION_MODEL_PATH, confidence=DETECTION_CONFIDENCE)
    false_alarm = FalseAlarmFilter()
    embedder = OSNetEmbedder(REID_MODEL_PATH)
    gallery = PersonGallery(
        embed_fn=embedder.embed,
        similarity_threshold=REID_SIMILARITY_THRESHOLD,
        ttl_seconds=REID_TTL_SECONDS,
        match_margin=REID_MATCH_MARGIN,
    )
    face = FaceRecognizer()
    watchlist = WatchlistDB(os.path.join(tmp, "watchlist.db"))
    matcher = WatchlistMatcher(watchlist, similarity_threshold=WATCHLIST_SIMILARITY_THRESHOLD)
    rules = ThreatRulesDB(os.path.join(tmp, "rules.db"))
    scorer = ThreatScorer(rules)
    loiter = LoiterTracker()

    # Real zones, so zone classification and the direction maths actually run
    # instead of short-circuiting on an empty zone list.
    zone_path = os.path.join(tmp, "zones.json")
    zones = ZoneEngine(config_path=zone_path)
    zones.add_zone(Zone("red", [(300, 100), (420, 100), (420, 460), (300, 460)]))
    zones.add_zone(Zone("green", [(20, 100), (140, 100), (140, 460), (20, 460)]))

    alerts = AlertManager(snapshot_dir=os.path.join(tmp, "snaps"), incident_store=None)

    from collections import deque
    buffers = deque(maxlen=3)

    prof = StageProfiler(enabled=True)

    # Warm up: first inference pays model init and CoreML compilation, which
    # would otherwise land entirely in frame 0's "detect_track" maximum.
    tracker.track(frames[0])
    embedder.embed(frames[0], PERSON_BOX)
    face.embed(frames[0], PERSON_BOX)

    for i, frame in enumerate(frames[5:5 + args.frames]):
        with prof.stage("activity_gate"):
            active, motion = gate.is_active(frame)

        with prof.stage("preprocess"):
            processed = preprocessor.process(frame)

        with prof.stage("detect_track"):
            detections = tracker.track(processed)

        with prof.stage("false_alarm_filter"):
            detections = false_alarm.filter(detections)

        # Drive the identity stages from a known box so they are measured every
        # frame; the live loop runs exactly these calls when a person is present.
        det = _Det(PERSON_BOX)
        with prof.stage("reid_resolve"):
            det.person_id = gallery.resolve(("bench", det.track_id), processed, det.box)

        with prof.stage("face_embed"):
            _fbox, embedding = face.embed(processed, det.box)

        with prof.stage("watchlist_match"):
            if embedding is not None:
                det.watchlist_match, det.watchlist_similarity = matcher.match(embedding)

        with prof.stage("zone_classify"):
            x1, y1, x2, y2 = det.box
            result = zones.classify(((x1 + x2) // 2, y2), det.direction)
            det.zone_tier, det.zone_direction = result["tier"], result["direction"]

        with prof.stage("loiter_update"):
            dwell = loiter.update(("track", det.track_id), det.zone_tier)

        with prof.stage("threat_score"):
            score = scorer.score(
                zone_tier=det.zone_tier, hour=2, speed_px_per_frame=det.speed,
                category=det.category(), zone_direction=det.zone_direction,
                dwell_seconds=dwell, group_count=1,
            )

        with prof.stage("draw_overlays"):
            draw_detections(processed, detections)
            cv2.putText(processed, f"T={score.total:.0f} ({score.tier})", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            zones.zones and None  # zone overlay drawing lives in ZoneDrawer (UI-only)

        with prof.stage("frame_buffer_copy"):
            buffers.append(processed.copy())

        with prof.stage("alert_handle"):
            alerts.handle(det, score, list(buffers))

        prof.frame_done()

    rules.close()
    watchlist.close()
    label = f"  [{args.label}]" if args.label else ""
    mode = "LOW-LIGHT" if args.dark else "DAYLIGHT"
    print(f"\nmodel={DETECTION_MODEL_PATH}  reid={os.path.basename(REID_MODEL_PATH)}  "
          f"{width}x{height}  mode={mode}{label}")
    print(prof.report())


if __name__ == "__main__":
    main()

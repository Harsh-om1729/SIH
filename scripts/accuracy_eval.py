"""Real accuracy measurement, not a guess: captures live webcam frames, runs
the REAL Detector (the same class app.py uses) on each one, and saves both
the raw and annotated frames so a human — or Claude, given eyes on the images
— can independently mark true/false positives and negatives per frame.

This exists because "does the detector actually work on our footage" had no
answer beyond "looks fine in the demo" — Phase 21 on the roadmap (Measured
Accuracy) was unchecked for a reason: no labelled set existed. This doesn't
require one. It captures a small, reviewable sample instead.

Usage (run from ibvap/):
    python scripts/accuracy_eval.py --seconds 40 --interval 1.0

Writes into eval_runs/<timestamp>/:
    raw/frame_0001.jpg          - what the camera actually saw
    annotated/frame_0001.jpg    - the same frame with the detector's boxes
    detections.json             - per-frame class/confidence/box, machine-readable
    REVIEW.md                   - a template to fill in ground truth per frame,
                                   pre-populated with what the detector claimed

Reviewing: open annotated/ frames next to raw/ frames (or just annotated/ —
a false positive shows as a box with nothing there; a false negative shows as
something present with no box). Fill in REVIEW.md's ground-truth column, then
run --score to get precision/recall/F1 per class from it.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2  # noqa: E402

from config.settings import (  # noqa: E402
    CAMERA_HEIGHT, CAMERA_WIDTH, DETECTION_CONFIDENCE, DETECTION_MODEL_PATH,
)
from detection.detector import Detector  # noqa: E402
from detection.draw import draw_detections  # noqa: E402


def capture_and_detect(seconds: float, interval: float, camera_index: int) -> Path:
    run_dir = Path("eval_runs") / time.strftime("%Y%m%d-%H%M%S")
    raw_dir = run_dir / "raw"
    annotated_dir = run_dir / "annotated"
    raw_dir.mkdir(parents=True)
    annotated_dir.mkdir(parents=True)

    cap = cv2.VideoCapture(camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    if not cap.isOpened():
        print(f"Could not open camera {camera_index}", file=sys.stderr)
        sys.exit(1)

    detector = Detector(model_path=DETECTION_MODEL_PATH, confidence=DETECTION_CONFIDENCE)
    print(f"Capturing for {seconds:.0f}s, one frame every {interval:.1f}s. "
          f"Move around, hold up objects, do whatever the review should judge.")
    print("Ctrl+C to stop early — frames captured so far are still saved.\n")

    records = []
    start = time.time()
    frame_num = 0
    next_capture = start
    try:
        while time.time() - start < seconds:
            ok, frame = cap.read()
            if not ok:
                continue
            now = time.time()
            if now < next_capture:
                continue
            next_capture = now + interval
            frame_num += 1

            detections = detector.detect(frame)
            raw_path = raw_dir / f"frame_{frame_num:04d}.jpg"
            cv2.imwrite(str(raw_path), frame)

            annotated = frame.copy()
            draw_detections(annotated, detections)
            cv2.imwrite(str(annotated_dir / f"frame_{frame_num:04d}.jpg"), annotated)

            records.append({
                "frame": frame_num,
                "t": round(now - start, 1),
                "detections": [
                    {
                        "class_name": d.class_name,
                        "category": d.category(),
                        "confidence": round(d.confidence, 3),
                        "box": list(d.box),
                    }
                    for d in detections
                ],
            })
            print(f"  frame {frame_num:4d}  t={now - start:5.1f}s  "
                  f"detected: {[d.class_name for d in detections] or 'none'}")
    except KeyboardInterrupt:
        print("\nStopped early.")
    finally:
        cap.release()

    (run_dir / "detections.json").write_text(json.dumps(records, indent=2))
    write_review_template(run_dir, records)
    print(f"\n{frame_num} frames captured -> {run_dir}/")
    print(f"Review template: {run_dir}/REVIEW.md")
    return run_dir


def write_review_template(run_dir: Path, records: list) -> None:
    lines = [
        "# Accuracy review\n",
        "For each frame, look at annotated/frame_NNNN.jpg next to raw/frame_NNNN.jpg.",
        "Fill in `ground_truth` with what is ACTUALLY in the frame (e.g. `person`,",
        "`person,person` for two, or empty if nothing relevant). Leave `detected`",
        "as-is — that's what the model claimed. Then run:\n",
        "    python scripts/accuracy_eval.py --score " + str(run_dir / "REVIEW.md") + "\n",
        "| frame | detected | ground_truth (fill in) |",
        "|---|---|---|",
    ]
    for r in records:
        detected = ",".join(d["class_name"] for d in r["detections"]) or "-"
        lines.append(f"| {r['frame']:04d} | {detected} | |")
    (run_dir / "REVIEW.md").write_text("\n".join(lines) + "\n")


def score(review_path: Path) -> None:
    """Parses the filled-in REVIEW.md table and prints precision/recall/F1.

    Per-frame, per-class counting (not per-box IoU matching — deliberately
    simple, matching what a person can fill in by eye): a class present in
    both detected and ground_truth for a frame counts min(count) as true
    positives; extra detected instances are false positives; extra
    ground-truth instances are false negatives.
    """
    text = review_path.read_text()
    rows = [
        line for line in text.splitlines()
        if line.startswith("|") and not line.startswith("| frame") and "---" not in line
    ]
    if not rows:
        print("No filled-in rows found — did you fill in the ground_truth column?")
        sys.exit(1)

    from collections import Counter

    tp = Counter()
    fp = Counter()
    fn = Counter()
    unfilled = 0

    for row in rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        if len(cells) < 3:
            continue
        _frame, detected_cell, truth_cell = cells[0], cells[1], cells[2]
        if truth_cell == "":
            unfilled += 1
            continue
        detected = Counter(c for c in detected_cell.split(",") if c and c != "-")
        truth = Counter(c for c in truth_cell.split(",") if c and c != "-")
        classes = set(detected) | set(truth)
        for cls in classes:
            d, t = detected[cls], truth[cls]
            tp[cls] += min(d, t)
            fp[cls] += max(0, d - t)
            fn[cls] += max(0, t - d)

    if unfilled:
        print(f"({unfilled} row(s) still have an empty ground_truth — skipped)\n")

    print(f"{'class':<12} {'TP':>4} {'FP':>4} {'FN':>4} {'precision':>10} {'recall':>8} {'F1':>6}")
    print("-" * 56)
    all_classes = sorted(set(tp) | set(fp) | set(fn))
    for cls in all_classes:
        p = tp[cls] / (tp[cls] + fp[cls]) if (tp[cls] + fp[cls]) else float("nan")
        r = tp[cls] / (tp[cls] + fn[cls]) if (tp[cls] + fn[cls]) else float("nan")
        f1 = 2 * p * r / (p + r) if p and r and (p + r) else float("nan")
        print(f"{cls:<12} {tp[cls]:>4} {fp[cls]:>4} {fn[cls]:>4} "
              f"{p:>10.2%} {r:>8.2%} {f1:>6.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=40.0)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--score", type=str, default=None, metavar="REVIEW.md",
                         help="Score a filled-in REVIEW.md instead of capturing")
    args = parser.parse_args()

    if args.score:
        score(Path(args.score))
    else:
        capture_and_detect(args.seconds, args.interval, args.camera)

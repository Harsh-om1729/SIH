"""Sub-operation profiler for preprocessing/enhance.py — measurement only.

    python scripts/profile_preprocessing.py                 # synthetic frames
    python scripts/profile_preprocessing.py --camera 0      # sample the real camera
                                                            # for trigger frequency

Breaks Preprocessor.process() into every atomic operation it actually performs
and times each one in isolation, so the cost of the low-light branch can be
attributed rather than guessed at.

This script changes nothing. It reimplements the same call sequence as
enhance.py rather than instrumenting it, so the module under measurement stays
exactly as it ships.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from config.settings import BRIGHTNESS_THRESHOLD, CAMERA_HEIGHT, CAMERA_WIDTH  # noqa: E402
from preprocessing.enhance import Preprocessor, TemporalMedianFilter  # noqa: E402

MEDIAN_WINDOW = 5
CLAHE_CLIP = 3.0
CLAHE_TILES = (8, 8)
GAMMA = 1.8


def make_frames(count, width, height, level):
    """Textured frames at a chosen brightness level. Texture matters: a flat
    fill makes the median filter and CLAHE unrealistically cheap."""
    rng = np.random.default_rng(7)
    frames = []
    for i in range(count):
        f = rng.integers(max(level - 25, 0), min(level + 25, 255),
                         (height, width, 3), dtype=np.uint8)
        shift = (i * 4) % 160
        cv2.rectangle(f, (240 + shift, 140), (330 + shift, 400),
                      (min(level + 60, 255),) * 3, -1)
        frames.append(f)
    return frames


class Bench:
    def __init__(self, frames, reps):
        self.frames = frames
        self.reps = reps
        self.results = []

    def run(self, label, fn, setup=None):
        """Times `fn(frame_or_setup_value)` across frames, reporting mean/max."""
        # Warm-up: first call pays any lazy allocation inside OpenCV.
        fn(setup(self.frames[0]) if setup else self.frames[0])
        samples = []
        for i in range(self.reps):
            frame = self.frames[i % len(self.frames)]
            arg = setup(frame) if setup else frame
            start = time.perf_counter()
            fn(arg)
            samples.append(time.perf_counter() - start)
        mean = sum(samples) / len(samples) * 1000
        self.results.append((label, mean, max(samples) * 1000, min(samples) * 1000))
        return mean

    def table(self, title, total_ref=None):
        lines = [f"\n{title}", "=" * 72,
                 f"{'operation':<38}{'avg ms':>10}{'max ms':>10}{'% branch':>12}",
                 "-" * 72]
        total = total_ref if total_ref is not None else sum(r[1] for r in self.results)
        for label, mean, mx, _mn in self.results:
            share = (mean / total * 100) if total else 0.0
            lines.append(f"{label:<38}{mean:>10.2f}{mx:>10.2f}{share:>11.1f}%")
        lines.append("-" * 72)
        lines.append(f"{'SUM OF OPERATIONS':<38}{sum(r[1] for r in self.results):>10.2f}")
        return "\n".join(lines)


def profile_operations(frames, reps):
    b = Bench(frames, reps)

    # --- 1. frame copy -----------------------------------------------------
    b.run("1. frame copy (.copy())", lambda f: f.copy())

    # --- 3/4. brightness gate (runs on EVERY frame, both branches) ---------
    b.run("3. cvtColor BGR2GRAY", lambda f: cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
    b.run("4. gray.mean()", lambda g: g.mean(),
          setup=lambda f: cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))

    # --- 9. temporal median filter (low-light branch) ----------------------
    # Mirrors the current TemporalMedianFilter.apply(): stack on the LAST axis
    # so each pixel's window is contiguous, then a partial sort for an odd
    # window. Keep this in step with enhance.py — a breakdown that measures a
    # call sequence the module no longer uses is worse than no breakdown.
    median = TemporalMedianFilter(MEDIAN_WINDOW)
    for f in frames[:MEDIAN_WINDOW]:
        median.apply(f)          # prime the deque so the window is full
    buf = list(median._buffer)
    middle = len(buf) // 2
    b.run("9a. np.stack (5 frames, axis=-1)", lambda _: np.stack(buf, axis=-1))
    stacked = np.stack(buf, axis=-1)
    b.run("9b. np.partition(axis=-1)[..., k]",
          lambda _: np.partition(stacked, middle, axis=-1)[..., middle])

    # --- 5/6/8. CLAHE pipeline --------------------------------------------
    b.run("8a. cvtColor BGR2LAB", lambda f: cv2.cvtColor(f, cv2.COLOR_BGR2LAB))
    lab = cv2.cvtColor(frames[0], cv2.COLOR_BGR2LAB)
    b.run("6a. cv2.split(lab)", lambda _: cv2.split(lab))
    l_ch, a_ch, b_ch = cv2.split(lab)
    b.run("5. cv2.createCLAHE (setup)",
          lambda _: cv2.createCLAHE(clipLimit=CLAHE_CLIP, tileGridSize=CLAHE_TILES))
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP, tileGridSize=CLAHE_TILES)
    b.run("6b. clahe.apply(L)", lambda _: clahe.apply(l_ch))
    l_eq = clahe.apply(l_ch)
    b.run("6c. cv2.merge", lambda _: cv2.merge((l_eq, a_ch, b_ch)))
    merged = cv2.merge((l_eq, a_ch, b_ch))
    b.run("8b. cvtColor LAB2BGR", lambda _: cv2.cvtColor(merged, cv2.COLOR_LAB2BGR))

    # --- 7. gamma ----------------------------------------------------------
    def build_lut(_):
        inv = 1.0 / GAMMA
        return np.array([((i / 255.0) ** inv) * 255 for i in range(256)]).astype("uint8")
    b.run("7a. build gamma LUT (per call)", build_lut)
    lut = build_lut(None)
    b.run("7b. cv2.LUT apply", lambda f: cv2.LUT(f, lut))

    # Superseded axis=0 path, timed for comparison only. Kept OUT of the table
    # so it can't distort the sum or the bottleneck ranking.
    stacked_axis0 = np.stack(buf, axis=0)
    old = Bench(frames, b.reps)
    old_ms = old.run("legacy", lambda _: np.median(stacked_axis0, axis=0).astype(np.uint8))

    return b, old_ms


def measure_branches(width, height, reps):
    """End-to-end Preprocessor.process() on each branch, for the comparison."""
    out = {}
    for label, level in (("NORMAL (daylight)", 150), ("LOW-LIGHT", 45)):
        frames = make_frames(30, width, height, level)
        pre = Preprocessor("prof", median_window=MEDIAN_WINDOW,
                           brightness_threshold=BRIGHTNESS_THRESHOLD)
        pre.process(frames[0])
        samples = []
        for i in range(reps):
            f = frames[i % len(frames)]
            start = time.perf_counter()
            pre.process(f)
            samples.append(time.perf_counter() - start)
        out[label] = {
            "mean": sum(samples) / len(samples) * 1000,
            "max": max(samples) * 1000,
            "boost": pre.last_boost_applied,
            "brightness": pre.last_brightness,
        }
    return out


def sample_camera(index, seconds, threshold):
    """Real trigger frequency: what fraction of live frames fall below the
    brightness threshold and take the expensive branch."""
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    values = []
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        h, w = frame.shape[:2]
        if (w, h) != (CAMERA_WIDTH, CAMERA_HEIGHT):
            frame = cv2.resize(frame, (CAMERA_WIDTH, CAMERA_HEIGHT))
        values.append(float(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean()))
    cap.release()
    if not values:
        return None
    below = sum(1 for v in values if v < threshold)
    return {
        "frames": len(values),
        "min": min(values), "max": max(values),
        "mean": sum(values) / len(values),
        "below": below,
        "pct": below / len(values) * 100,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reps", type=int, default=60)
    ap.add_argument("--camera", type=int, default=None,
                    help="sample this camera index for real trigger frequency")
    ap.add_argument("--camera-seconds", type=float, default=6.0)
    args = ap.parse_args()

    w, h = CAMERA_WIDTH, CAMERA_HEIGHT
    print(f"frame size {w}x{h}   reps={args.reps}   "
          f"BRIGHTNESS_THRESHOLD={BRIGHTNESS_THRESHOLD}")

    dark = make_frames(30, w, h, 45)
    b, legacy_ms = profile_operations(dark, args.reps)
    print(b.table("1. PREPROCESSING BREAKDOWN  (low-light branch, per frame)"))
    current = next(r[1] for r in b.results if r[0].startswith("9b."))
    print(f"   (median step: {current:.2f} ms on the current last-axis path vs "
          f"{legacy_ms:.2f} ms on the superseded axis=0 path — {legacy_ms / current:.1f}x)")

    ranked = sorted(b.results, key=lambda r: r[1], reverse=True)
    print("\n2. TOP 3 BOTTLENECKS")
    print("-" * 72)
    for i, (label, mean, mx, _mn) in enumerate(ranked[:3], 1):
        print(f"   #{i}  {label:<36}{mean:>8.2f} ms avg   {mx:>8.2f} ms max")

    print("\n3. NORMAL vs LOW-LIGHT  (end-to-end Preprocessor.process)")
    print("-" * 72)
    branches = measure_branches(w, h, args.reps)
    for label, d in branches.items():
        print(f"   {label:<22} {d['mean']:>8.2f} ms avg  {d['max']:>8.2f} ms max   "
              f"brightness={d['brightness']:.1f}  boost={d['boost']}")
    norm = branches["NORMAL (daylight)"]["mean"]
    low = branches["LOW-LIGHT"]["mean"]
    print(f"   {'ratio':<22} low-light is {low / norm:.0f}x the cost of daylight")

    print("\n4. LOW-LIGHT TRIGGER FREQUENCY")
    print("-" * 72)
    if args.camera is None:
        print("   Not sampled. Re-run with --camera 0 to measure the real rate on")
        print("   your scene; trigger frequency depends entirely on the deployment.")
    else:
        stats = sample_camera(args.camera, args.camera_seconds, BRIGHTNESS_THRESHOLD)
        if stats is None:
            print(f"   Could not read camera {args.camera}.")
        else:
            print(f"   sampled {stats['frames']} frames over {args.camera_seconds:.0f}s")
            print(f"   brightness  min={stats['min']:.1f}  mean={stats['mean']:.1f}  "
                  f"max={stats['max']:.1f}   threshold={BRIGHTNESS_THRESHOLD}")
            print(f"   below threshold: {stats['below']}/{stats['frames']} "
                  f"= {stats['pct']:.1f}% of frames take the expensive branch")


if __name__ == "__main__":
    main()

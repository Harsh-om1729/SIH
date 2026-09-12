"""Benchmarks PyTorch vs ONNX vs INT8-ONNX YOLOv8n inference latency/FPS
on this machine's CPU. Run from the ibvap/ directory: python scripts/benchmark_models.py
"""

import time

import numpy as np
from ultralytics import YOLO

MODELS = {
    "PyTorch (.pt)": "models/yolov8n.pt",
    "ONNX (fp32)": "models/yolov8n.onnx",
    "ONNX (int8)": "models/yolov8n_int8.onnx",
    "yolov8s ONNX (fp32)": "models/yolov8s.onnx",
}

WARMUP_RUNS = 5
TIMED_RUNS = 30


def benchmark(model_path: str) -> tuple[float, float]:
    model = YOLO(model_path)
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    for _ in range(WARMUP_RUNS):
        model.predict(frame, verbose=False)

    start = time.perf_counter()
    for _ in range(TIMED_RUNS):
        model.predict(frame, verbose=False)
    elapsed = time.perf_counter() - start

    avg_latency_ms = (elapsed / TIMED_RUNS) * 1000
    fps = TIMED_RUNS / elapsed
    return avg_latency_ms, fps


def main() -> None:
    print(f"{'Model':<18} {'Avg latency':>14} {'FPS':>10}")
    print("-" * 44)
    for label, path in MODELS.items():
        avg_latency_ms, fps = benchmark(path)
        print(f"{label:<18} {avg_latency_ms:>11.1f} ms {fps:>9.1f}")


if __name__ == "__main__":
    main()

"""Which ONNX Runtime execution providers the Re-ID and face models request.

The YOLO detector is not routed through here: Ultralytics' AutoBackend asks
onnxruntime.get_available_providers() itself and prefers whatever it finds,
so installing onnxruntime-openvino accelerates detection with no code change.
OSNet (reid/embedder.py) and InsightFace (face/face_recognizer.py) build their
own sessions and used to hardcode CPUExecutionProvider, which meant an
installed accelerator was silently ignored for 55% of per-frame time.

OpenVINO leads the default list because Intel CPUs are the field target.
CoreML is deliberately absent: it has only been measured for the detector,
and its graph partitioning made the int8 detector ~7x slower than fp32, so
it is not assumed to help these two models. ORT_PROVIDERS overrides the list
for experiments; CPU is always appended as the guaranteed fallback.
"""
import os

DEFAULT_PREFERENCE = ("OpenVINOExecutionProvider", "CPUExecutionProvider")


def select_providers(preference=None, available=None) -> list[str]:
    if preference is None:
        raw = os.getenv("ORT_PROVIDERS", "")
        preference = [p.strip() for p in raw.split(",") if p.strip()] or list(DEFAULT_PREFERENCE)
    if available is None:
        # Imported here, not at module top: config/settings.py must set the
        # ORT thread-count env vars before onnxruntime is first imported.
        import onnxruntime

        available = onnxruntime.get_available_providers()
    chosen = [p for p in preference if p in available]
    if "CPUExecutionProvider" not in chosen:
        chosen.append("CPUExecutionProvider")
    return chosen

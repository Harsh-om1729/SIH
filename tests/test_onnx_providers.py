"""ONNX Runtime execution-provider pinning (air-gapped requirement).

IBVAP must never construct an inference session that registers a remote
execution provider. Ultralytics builds its session from
`onnxruntime.get_available_providers()` verbatim, and a stock Windows
`onnxruntime` wheel reports `AzureExecutionProvider` ahead of
`CPUExecutionProvider`, so the pin in `detection.detector` is what keeps a
cloud provider off the session.
"""

import importlib

import pytest

import detection.detector as detector_module


@pytest.fixture
def fresh_detector_module(monkeypatch):
    """A reloaded copy of the module, with onnxruntime restored afterwards.

    The pin deliberately replaces `onnxruntime.get_available_providers` for
    the life of the process, so a test that exercises it has to put the real
    function back or it leaks into every later test.
    """
    import onnxruntime

    original = onnxruntime.get_available_providers
    try:
        yield importlib.reload(detector_module)
    finally:
        onnxruntime.get_available_providers = original
        importlib.reload(detector_module)


def test_pin_excludes_remote_providers(fresh_detector_module, monkeypatch):
    import onnxruntime

    module = fresh_detector_module
    monkeypatch.setattr(
        module, "ONNX_PROVIDERS_AVAILABLE",
        ("AzureExecutionProvider", "CPUExecutionProvider"),
    )
    monkeypatch.setattr(module, "_providers_pinned", False)

    assert module.force_cpu_only_onnx_providers() == ["CPUExecutionProvider"]
    assert onnxruntime.get_available_providers() == ["CPUExecutionProvider"]


def test_pin_is_idempotent(fresh_detector_module, monkeypatch):
    module = fresh_detector_module
    monkeypatch.setattr(module, "_providers_pinned", False)

    first = module.force_cpu_only_onnx_providers()
    second = module.force_cpu_only_onnx_providers()
    assert first == second == ["CPUExecutionProvider"]


def test_pin_raises_when_cpu_provider_missing(fresh_detector_module, monkeypatch):
    """No CPU provider must fail loudly, never fall back to a remote one."""
    module = fresh_detector_module
    monkeypatch.setattr(module, "ONNX_PROVIDERS_AVAILABLE", ("AzureExecutionProvider",))
    monkeypatch.setattr(module, "_providers_pinned", False)

    with pytest.raises(RuntimeError, match="CPUExecutionProvider is not available"):
        module.force_cpu_only_onnx_providers()


def test_real_session_registers_only_cpu(tmp_path):
    """End-to-end: the session the Tracker actually builds is CPU-only.

    This is the assertion that matters - the unit tests above check the
    helper, this one checks the session that inference really runs on.
    """
    import os

    import cv2
    import numpy as np

    model_path = "models/yolov8n.onnx"
    if not os.path.exists(model_path):
        pytest.skip(f"model weights not present at {model_path}")

    from tracking.tracker import Tracker

    tracker = Tracker(model_path=model_path, confidence=0.4)
    tracker.track(np.zeros((480, 640, 3), dtype=np.uint8))

    session = tracker._model.predictor.model.session
    assert session.get_providers() == ["CPUExecutionProvider"]

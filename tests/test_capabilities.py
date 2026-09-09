"""Optional intelligence capabilities must degrade, never block startup.

The architecture requires IBVAP to run air-gapped. Face recognition and Re-ID
both load weights through libraries that download on a cold cache
(InsightFace from GitHub, torchvision from download.pytorch.org), so the
guarantees under test are:

A. weights present  -> capability initialises, existing behaviour preserved
B. weights missing  -> core pipeline still starts, NO download attempted,
                       capability explicitly marked unavailable
C. capability fails -> failure is observable, core pipeline is not taken down
"""

import os

from capabilities import AVAILABLE, DEGRADED, UNAVAILABLE, CapabilityRegistry


# --------------------------------------------------------------------------
# A. Available capability
# --------------------------------------------------------------------------

def test_available_capability_is_constructed_and_marked_available():
    registry = CapabilityRegistry()
    sentinel = object()

    instance = registry.load(
        "face_recognition", lambda: sentinel, precheck=lambda: (True, "weights present")
    )

    assert instance is sentinel
    assert registry.states()["face_recognition"]["state"] == AVAILABLE


def test_available_capability_calls_through_unchanged():
    """call() must not alter the wrapped result when nothing fails."""
    registry = CapabilityRegistry()
    result = registry.call("face_recognition", lambda a, b: (a, b), "box", 7)
    assert result == ("box", 7)
    assert registry.failures() == {}


def test_face_precheck_accepts_provisioned_pack(tmp_path):
    from face.face_recognizer import buffalo_weights_available

    pack_dir = tmp_path / "models" / "buffalo_s"
    os.makedirs(pack_dir)
    (pack_dir / "det_500m.onnx").write_bytes(b"stub")

    ok, reason = buffalo_weights_available(pack="buffalo_s", root=str(tmp_path))
    assert ok is True
    assert "provisioned" in reason


# --------------------------------------------------------------------------
# B. Missing weights
# --------------------------------------------------------------------------

def test_missing_weights_returns_none_and_never_calls_factory():
    """The factory is what downloads. A failed precheck must not reach it."""
    registry = CapabilityRegistry()
    calls = []

    def factory():
        calls.append("constructed")
        raise AssertionError("factory must not run when the precheck fails")

    instance = registry.load(
        "reid_embedding", factory, precheck=lambda: (False, "weights not cached")
    )

    assert instance is None
    assert calls == []
    entry = registry.states()["reid_embedding"]
    assert entry["state"] == UNAVAILABLE
    assert "weights not cached" in entry["detail"]


def test_missing_weights_is_logged_explicitly(caplog):
    registry = CapabilityRegistry()
    with caplog.at_level("WARNING", logger="ibvap.capabilities"):
        registry.load("reid_embedding", object, precheck=lambda: (False, "no cache"))
    assert "UNAVAILABLE" in caplog.text
    assert "no cache" in caplog.text


def test_face_precheck_reports_missing_pack_without_network(tmp_path):
    from face.face_recognizer import buffalo_weights_available

    ok, reason = buffalo_weights_available(pack="buffalo_s", root=str(tmp_path))
    assert ok is False
    assert "not provisioned" in reason
    assert "no download attempted" in reason


def test_face_precheck_rejects_empty_pack_directory(tmp_path):
    """A directory with no .onnx satisfies InsightFace's own existence check
    but yields zero usable models, so the precheck must reject it."""
    from face.face_recognizer import buffalo_weights_available

    os.makedirs(tmp_path / "models" / "buffalo_s")
    ok, reason = buffalo_weights_available(pack="buffalo_s", root=str(tmp_path))
    assert ok is False
    assert "no .onnx" in reason


def test_reid_precheck_matches_torch_cache_state(monkeypatch, tmp_path):
    import torch
    from torchvision.models import ResNet18_Weights

    from reid.embedder import resnet18_weights_available

    monkeypatch.setattr(torch.hub, "get_dir", lambda: str(tmp_path))
    ok, reason = resnet18_weights_available()
    assert ok is False
    assert "no download attempted" in reason

    checkpoints = tmp_path / "checkpoints"
    os.makedirs(checkpoints)
    (checkpoints / os.path.basename(ResNet18_Weights.DEFAULT.url)).write_bytes(b"stub")
    ok, _reason = resnet18_weights_available()
    assert ok is True


def test_prechecks_make_no_network_call(monkeypatch, tmp_path):
    """Belt and braces: any socket use during a precheck is a failure."""
    import socket

    import torch

    from face.face_recognizer import buffalo_weights_available
    from reid.embedder import resnet18_weights_available

    def forbidden(*args, **kwargs):
        raise AssertionError("precheck attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(torch.hub, "get_dir", lambda: str(tmp_path))

    assert buffalo_weights_available(root=str(tmp_path))[0] is False
    assert resnet18_weights_available()[0] is False


# --------------------------------------------------------------------------
# C. Failing capability
# --------------------------------------------------------------------------

def test_construction_failure_is_contained_and_observable(caplog):
    registry = CapabilityRegistry()

    def exploding_factory():
        raise RuntimeError("corrupt weights")

    with caplog.at_level("WARNING", logger="ibvap.capabilities"):
        instance = registry.load("face_recognition", exploding_factory)

    assert instance is None
    entry = registry.states()["face_recognition"]
    assert entry["state"] == UNAVAILABLE
    assert "corrupt weights" in entry["detail"]
    assert "corrupt weights" in caplog.text


def test_runtime_failure_marks_degraded_and_returns_default(caplog):
    registry = CapabilityRegistry()

    def exploding(_frame, _box):
        raise ValueError("inference blew up")

    with caplog.at_level("WARNING", logger="ibvap.capabilities"):
        result = registry.call(
            "face_recognition", exploding, "frame", (0, 0, 1, 1), default=(None, None)
        )

    assert result == (None, None)
    assert registry.states()["face_recognition"]["state"] == DEGRADED
    assert registry.failures()["face_recognition"] == 1
    assert "inference blew up" in caplog.text


def test_repeated_failures_are_all_counted_even_when_log_is_rate_limited(caplog):
    """Rate-limiting the log must not lose failures from the observable state."""
    registry = CapabilityRegistry(log_every=5)

    def exploding():
        raise ValueError("boom")

    with caplog.at_level("WARNING", logger="ibvap.capabilities"):
        for _ in range(12):
            registry.call("reid_embedding", exploding)

    assert registry.failures()["reid_embedding"] == 12
    assert registry.states()["reid_embedding"]["state"] == DEGRADED
    # Logged on failure 1, 5 and 10 - not all twelve.
    assert 2 <= caplog.text.count("reid_embedding") <= 5


def test_capability_failure_does_not_propagate_to_caller():
    """The core pipeline must never see an optional capability's exception."""
    registry = CapabilityRegistry()

    def exploding():
        raise KeyError("optional model died")

    # No pytest.raises - the point is that nothing escapes.
    assert registry.call(
        "face_recognition", exploding, default="core-continues"
    ) == "core-continues"


def test_summary_exposes_every_capability_state():
    registry = CapabilityRegistry()

    def raises_db_error():
        raise OSError("db locked")

    registry.load("face_recognition", object, precheck=lambda: (True, "ok"))
    registry.load("reid_embedding", object, precheck=lambda: (False, "missing"))
    registry.call("watchlist", raises_db_error)

    assert registry.summary() == {
        "face_recognition": AVAILABLE,
        "reid_embedding": UNAVAILABLE,
        "watchlist": DEGRADED,
    }


def test_face_recognizer_still_loads_the_same_insightface_pack(monkeypatch):
    """Requirement 4: gating must not change what gets loaded when present.

    FaceAnalysis previously received name="buffalo_s" and its default
    root="~/.insightface". Those are now module constants shared with the
    precheck, so this pins the constructed arguments against drift.
    """
    import face.face_recognizer as fr

    captured = {}

    class StubApp:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def prepare(self, **kwargs):
            captured["prepare"] = kwargs

    monkeypatch.setattr(fr, "FaceAnalysis", StubApp)
    fr.FaceRecognizer(det_size=(320, 320))

    assert captured["name"] == "buffalo_s"
    assert captured["root"] == "~/.insightface"
    assert captured["providers"] == ["CPUExecutionProvider"]
    assert captured["prepare"] == {"ctx_id": 0, "det_size": (320, 320)}

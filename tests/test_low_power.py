"""Phase 26 — execution-provider selection and fixed-size ONNX detection.
Run from ibvap/: python -m unittest tests.test_low_power
"""
import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import onnx
from onnx import TensorProto, helper

from config.providers import select_providers
from detection.detector import model_input_size

CPU = "CPUExecutionProvider"
OPENVINO = "OpenVINOExecutionProvider"
COREML = "CoreMLExecutionProvider"


class TestSelectProviders(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ, {"ORT_PROVIDERS": ""})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_openvino_preferred_when_installed(self):
        self.assertEqual(select_providers(available=[OPENVINO, CPU]), [OPENVINO, CPU])

    def test_plain_onnxruntime_falls_back_to_cpu(self):
        self.assertEqual(select_providers(available=[CPU]), [CPU])

    def test_coreml_not_requested_by_default(self):
        # Only ever measured for the detector, where it made int8 ~7x slower.
        self.assertEqual(select_providers(available=[COREML, CPU]), [CPU])

    def test_cpu_always_appended_as_fallback(self):
        self.assertEqual(
            select_providers(preference=[OPENVINO], available=[OPENVINO, CPU]), [OPENVINO, CPU]
        )

    def test_env_override_for_experiments(self):
        with mock.patch.dict(os.environ, {"ORT_PROVIDERS": COREML}):
            self.assertEqual(select_providers(available=[COREML, CPU]), [COREML, CPU])


class TestModelInputSize(unittest.TestCase):
    def _model(self, dims) -> str:
        tensor = helper.make_tensor_value_info("images", TensorProto.FLOAT, dims)
        out = helper.make_tensor_value_info("out", TensorProto.FLOAT, dims)
        graph = helper.make_graph(
            [helper.make_node("Identity", ["images"], ["out"])], "g", [tensor], [out]
        )
        path = str(Path(tempfile.mkdtemp()) / "m.onnx")
        onnx.save(helper.make_model(graph), path)
        return path

    def test_fixed_416_export(self):
        self.assertEqual(model_input_size(self._model([1, 3, 416, 416])), 416)

    def test_fixed_640_export(self):
        self.assertEqual(model_input_size(self._model([1, 3, 640, 640])), 640)

    def test_dynamic_shape_leaves_ultralytics_default(self):
        self.assertIsNone(model_input_size(self._model([1, 3, "h", "w"])))

    def test_pytorch_weights_not_inspected(self):
        self.assertIsNone(model_input_size("models/yolov8n.pt"))


class TestHardwareProfile(unittest.TestCase):
    PINNED = ("DETECTION_MODEL_PATH", "ORT_NUM_THREADS", "REID_FACE_CHECK_INTERVAL", "IDLE_MIN_FPS")

    def _settings(self, **env) -> dict:
        """Re-imports config.settings under exactly `env`, with .env loading
        disabled so a developer's own pinned values can't leak in."""
        import config.settings as settings

        clean = {
            k: v for k, v in os.environ.items() if k not in self.PINNED + ("HARDWARE_PROFILE",)
        }
        clean.update(env)
        try:
            with mock.patch.dict(os.environ, clean, clear=True), mock.patch("dotenv.load_dotenv"):
                module = importlib.reload(settings)
                return {k: getattr(module, k) for k in ("HARDWARE_PROFILE",) + self.PINNED}
        finally:
            importlib.reload(settings)

    def test_standard_is_the_default(self):
        s = self._settings()
        self.assertEqual(s["HARDWARE_PROFILE"], "standard")
        self.assertEqual(s["DETECTION_MODEL_PATH"], "models/yolov8s.onnx")
        self.assertEqual(s["ORT_NUM_THREADS"], 2)
        self.assertEqual(s["REID_FACE_CHECK_INTERVAL"], 5)
        self.assertEqual(s["IDLE_MIN_FPS"], 20.0)

    def test_low_profile_values(self):
        s = self._settings(HARDWARE_PROFILE="low")
        self.assertEqual(s["DETECTION_MODEL_PATH"], "models/yolov8n_416.onnx")
        self.assertEqual(s["ORT_NUM_THREADS"], 1)
        self.assertEqual(s["REID_FACE_CHECK_INTERVAL"], 10)
        self.assertEqual(s["IDLE_MIN_FPS"], 5.0)

    def test_explicit_env_value_beats_profile(self):
        s = self._settings(HARDWARE_PROFILE="low", DETECTION_MODEL_PATH="models/yolov8s.onnx")
        self.assertEqual(s["DETECTION_MODEL_PATH"], "models/yolov8s.onnx")
        self.assertEqual(s["ORT_NUM_THREADS"], 1)

    def test_profile_name_is_case_insensitive(self):
        self.assertEqual(self._settings(HARDWARE_PROFILE="LOW")["HARDWARE_PROFILE"], "low")

    def test_empty_profile_means_standard_without_warning(self):
        # `HARDWARE_PROFILE=` in .env is set-but-empty, not a typo to warn about.
        with self.assertNoLogs("ibvap", level="WARNING"):
            s = self._settings(HARDWARE_PROFILE="")
        self.assertEqual(s["HARDWARE_PROFILE"], "standard")

    def test_unknown_profile_falls_back_to_standard(self):
        s = self._settings(HARDWARE_PROFILE="potato")
        self.assertEqual(s["HARDWARE_PROFILE"], "standard")
        self.assertEqual(s["DETECTION_MODEL_PATH"], "models/yolov8s.onnx")


if __name__ == "__main__":
    unittest.main()

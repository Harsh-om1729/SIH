"""FaceRecognizer's graceful-degradation path — no real model load, no
network, so this runs fast as part of the normal suite.
Run from ibvap/: python -m unittest tests.test_face_recognizer
"""
import unittest
from unittest.mock import patch

from face.face_recognizer import FaceRecognizer


class TestFaceRecognizerUnavailable(unittest.TestCase):
    """The bug this closes: buffalo_s auto-downloads on first use if
    ~/.insightface has no cache yet. On a fresh, offline machine — exactly
    the deployment this project targets — that raised out of __init__ and
    crashed the whole pipeline before a single frame was processed, instead
    of just running without face recognition/watchlist matching."""

    def test_constructor_failure_is_caught_not_raised(self):
        with patch("face.face_recognizer.FaceAnalysis", side_effect=RuntimeError("no network")):
            recognizer = FaceRecognizer()  # must not raise
        self.assertFalse(recognizer.available)

    def test_embed_returns_none_none_when_unavailable(self):
        with patch("face.face_recognizer.FaceAnalysis", side_effect=RuntimeError("no network")):
            recognizer = FaceRecognizer()
        face_box, embedding = recognizer.embed(frame=object(), person_box=(0, 0, 50, 100))
        self.assertIsNone(face_box)
        self.assertIsNone(embedding)

    def test_available_stays_true_on_normal_construction(self):
        with patch("face.face_recognizer.FaceAnalysis") as mock_analysis:
            mock_analysis.return_value.prepare.return_value = None
            recognizer = FaceRecognizer()
        self.assertTrue(recognizer.available)

    def test_prepare_failure_is_also_caught(self):
        # The model can construct but fail during .prepare() (e.g. a partial
        # download) - that must degrade the same way as a constructor failure.
        with patch("face.face_recognizer.FaceAnalysis") as mock_analysis:
            mock_analysis.return_value.prepare.side_effect = RuntimeError("corrupt weights")
            recognizer = FaceRecognizer()
        self.assertFalse(recognizer.available)


if __name__ == "__main__":
    unittest.main()

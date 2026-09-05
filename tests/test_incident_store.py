"""Offline unit tests for the encrypted incident store — no camera required.
Run from ibvap/: python -m unittest tests.test_incident_store
"""

import tempfile
import unittest
from pathlib import Path

import numpy as np

from database.incident_store import IncidentStore
from detection.detector import Detection
from intelligence.threat_score import ThreatScore


def make_detection() -> Detection:
    det = Detection(class_id=0, class_name="person", confidence=0.9, box=(10, 10, 60, 110))
    det.track_id = 7
    det.person_id = 3
    det.zone_tier = "red"
    return det


def make_frame() -> np.ndarray:
    return np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)


class TestIncidentStore(unittest.TestCase):
    def _store(self) -> IncidentStore:
        tmp_dir = Path(tempfile.mkdtemp())
        return IncidentStore(
            db_path=str(tmp_dir / "incidents.db"),
            evidence_dir=str(tmp_dir / "snapshots"),
            key_path=str(tmp_dir / "evidence.key"),
        )

    def test_record_creates_queryable_incident(self):
        store = self._store()
        det = make_detection()
        score = ThreatScore(sector_risk=30, time_risk=25, kinematics_risk=10, class_confidence=15)

        incident_id = store.record(det, score, make_frame())

        incidents = store.list_incidents()
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0]["id"], incident_id)
        self.assertEqual(incidents[0]["track_id"], 7)
        self.assertEqual(incidents[0]["person_id"], 3)
        self.assertEqual(incidents[0]["category"], "person")
        self.assertEqual(incidents[0]["zone_tier"], "red")
        self.assertEqual(incidents[0]["tier"], score.tier)

    def test_snapshot_file_is_encrypted_not_plain_jpeg(self):
        store = self._store()
        det = make_detection()
        score = ThreatScore(sector_risk=30, time_risk=25, kinematics_risk=10, class_confidence=15)
        store.record(det, score, make_frame())

        incident = store.list_incidents()[0]
        with open(incident["snapshot_path"], "rb") as f:
            raw = f.read()
        # A plain JPEG starts with the SOI marker (0xFFD8); encrypted output must not.
        self.assertNotEqual(raw[:2], b"\xff\xd8")

    def test_snapshot_decrypts_back_to_a_valid_image(self):
        import cv2

        store = self._store()
        det = make_detection()
        score = ThreatScore(sector_risk=30, time_risk=25, kinematics_risk=10, class_confidence=15)
        original_frame = make_frame()
        store.record(det, score, original_frame)

        incident = store.list_incidents()[0]
        decrypted_bytes = store.decrypt_image_bytes(incident["snapshot_path"])
        decoded = cv2.imdecode(np.frombuffer(decrypted_bytes, np.uint8), cv2.IMREAD_COLOR)

        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.shape, original_frame.shape)

    def test_crop_and_burst_frames_are_saved(self):
        store = self._store()
        det = make_detection()
        score = ThreatScore(sector_risk=30, time_risk=25, kinematics_risk=10, class_confidence=15)

        store.record(
            det, score, make_frame(),
            crop_frame=make_frame(), burst_frames=[make_frame(), make_frame()],
        )

        incident = store.list_incidents()[0]
        self.assertIsNotNone(incident["crop_path"])
        import json
        burst_paths = json.loads(incident["burst_paths"])
        self.assertEqual(len(burst_paths), 2)

    def test_encryption_key_persists_across_reconnection(self):
        tmp_dir = Path(tempfile.mkdtemp())
        db_path = str(tmp_dir / "incidents.db")
        evidence_dir = str(tmp_dir / "snapshots")
        key_path = str(tmp_dir / "evidence.key")

        store_a = IncidentStore(db_path=db_path, evidence_dir=evidence_dir, key_path=key_path)
        det = make_detection()
        score = ThreatScore(sector_risk=30, time_risk=25, kinematics_risk=10, class_confidence=15)
        store_a.record(det, score, make_frame())
        incident = store_a.list_incidents()[0]
        store_a.close()

        # A fresh store instance (simulating app restart) must reuse the same
        # key, so evidence written by the previous run stays decryptable.
        store_b = IncidentStore(db_path=db_path, evidence_dir=evidence_dir, key_path=key_path)
        decrypted = store_b.decrypt_image_bytes(incident["snapshot_path"])
        self.assertGreater(len(decrypted), 0)

    def test_incidents_ordered_most_recent_first(self):
        store = self._store()
        det = make_detection()
        score = ThreatScore(sector_risk=30, time_risk=25, kinematics_risk=10, class_confidence=15)

        first_id = store.record(det, score, make_frame())
        second_id = store.record(det, score, make_frame())

        incidents = store.list_incidents()
        self.assertEqual(incidents[0]["id"], second_id)
        self.assertEqual(incidents[1]["id"], first_id)


if __name__ == "__main__":
    unittest.main()

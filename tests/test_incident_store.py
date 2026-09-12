"""Offline unit tests for the encrypted incident store — no camera required.
Run from ibvap/: python -m unittest tests.test_incident_store
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

import numpy as np

from database.incident_store import RESOLUTION_REASONS, STATUS_ACKNOWLEDGED, STATUS_OPEN, STATUS_RESOLVED, IncidentStore
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

    def test_new_incident_defaults_to_open_with_no_operator_fields(self):
        store = self._store()
        det = make_detection()
        score = ThreatScore(sector_risk=30, time_risk=25, kinematics_risk=10, class_confidence=15)
        store.record(det, score, make_frame())

        incident = store.list_incidents()[0]
        self.assertEqual(incident["status"], STATUS_OPEN)
        self.assertIsNone(incident["acknowledged_by"])
        self.assertIsNone(incident["resolved_by"])
        self.assertIsNone(incident["resolution_reason"])

    def test_acknowledge_sets_status_operator_and_timestamp(self):
        store = self._store()
        det = make_detection()
        score = ThreatScore(sector_risk=30, time_risk=25, kinematics_risk=10, class_confidence=15)
        incident_id = store.record(det, score, make_frame())

        store.acknowledge(incident_id, "Sentry Rao")

        incident = store.get_incident(incident_id)
        self.assertEqual(incident["status"], STATUS_ACKNOWLEDGED)
        self.assertEqual(incident["acknowledged_by"], "Sentry Rao")
        self.assertIsNotNone(incident["acknowledged_at"])

    def test_resolve_sets_status_operator_timestamp_and_reason(self):
        store = self._store()
        det = make_detection()
        score = ThreatScore(sector_risk=30, time_risk=25, kinematics_risk=10, class_confidence=15)
        incident_id = store.record(det, score, make_frame())

        store.resolve(incident_id, "Sentry Rao", "cattle")

        incident = store.get_incident(incident_id)
        self.assertEqual(incident["status"], STATUS_RESOLVED)
        self.assertEqual(incident["resolved_by"], "Sentry Rao")
        self.assertEqual(incident["resolution_reason"], "cattle")
        self.assertIsNotNone(incident["resolved_at"])

    def test_resolve_rejects_unknown_reason(self):
        store = self._store()
        det = make_detection()
        score = ThreatScore(sector_risk=30, time_risk=25, kinematics_risk=10, class_confidence=15)
        incident_id = store.record(det, score, make_frame())

        with self.assertRaises(ValueError):
            store.resolve(incident_id, "Sentry Rao", "not_a_real_reason")

    def test_all_five_resolution_reasons_are_accepted(self):
        store = self._store()
        det = make_detection()
        score = ThreatScore(sector_risk=30, time_risk=25, kinematics_risk=10, class_confidence=15)

        for reason in RESOLUTION_REASONS:
            incident_id = store.record(det, score, make_frame())
            store.resolve(incident_id, "Sentry Rao", reason)
            self.assertEqual(store.get_incident(incident_id)["resolution_reason"], reason)

    def test_get_incident_returns_none_for_unknown_id(self):
        store = self._store()
        self.assertIsNone(store.get_incident(99999))

    def test_schema_migration_preserves_existing_rows_on_old_database(self):
        """Simulates a real pre-existing incidents.db from before this
        feature existed (base columns only, no status/operator columns) —
        opening it with the new IncidentStore must add the new columns
        without losing or altering any existing row.
        """
        tmp_dir = Path(tempfile.mkdtemp())
        db_path = str(tmp_dir / "incidents.db")

        # Hand-build the OLD schema and insert a row, bypassing IncidentStore
        # entirely so this truly represents "already existed before the upgrade".
        old_conn = sqlite3.connect(db_path)
        old_conn.execute(
            """
            CREATE TABLE incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER,
                person_id INTEGER,
                category TEXT,
                zone_tier TEXT,
                score REAL,
                tier TEXT,
                timestamp REAL,
                snapshot_path TEXT,
                crop_path TEXT,
                burst_paths TEXT
            )
            """
        )
        old_conn.execute(
            "INSERT INTO incidents (track_id, category, zone_tier, score, tier, timestamp) "
            "VALUES (5, 'person', 'red', 80.0, 'red', 1000.0)"
        )
        old_conn.commit()
        old_conn.close()

        # Opening it through IncidentStore should migrate in place.
        store = IncidentStore(
            db_path=db_path,
            evidence_dir=str(tmp_dir / "snapshots"),
            key_path=str(tmp_dir / "evidence.key"),
        )
        incidents = store.list_incidents()

        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0]["track_id"], 5)  # old data intact
        self.assertEqual(incidents[0]["status"], STATUS_OPEN)  # new column, defaulted

        # And the new workflow methods must work on this migrated row.
        store.acknowledge(incidents[0]["id"], "Sentry Rao")
        self.assertEqual(store.get_incident(incidents[0]["id"])["status"], STATUS_ACKNOWLEDGED)


if __name__ == "__main__":
    unittest.main()

"""Phase 20 — the dashboard-facing API additions and the pipeline -> dashboard
runtime state: evidence decryption, incident resolution, system health,
camera source reporting, and camera/breakdown persistence."""

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from fastapi.testclient import TestClient

import integration.api as api_module
from database.incident_store import RESOLUTION_REASONS, IncidentStore
from detection.detector import Detection
from integration import runtime_state

TOKEN = "v1-test-token-not-a-real-secret"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def make_frame() -> np.ndarray:
    frame = np.full((120, 160, 3), 90, dtype=np.uint8)
    cv2.rectangle(frame, (40, 20), (100, 110), (0, 200, 0), -1)
    return frame


def make_detection(camera: "str | None" = "cam7") -> Detection:
    det = Detection(class_id=0, class_name="person", confidence=0.9, box=(40, 20, 100, 110))
    det.track_id = 3
    det.person_id = 5
    det.zone_tier = "red"
    det.camera_name = camera
    return det


def make_score():
    # A stand-in carrying exactly what IncidentStore.record reads.
    return types.SimpleNamespace(
        total=84.0, tier="red",
        sector_risk=40.0, time_risk=25.0, kinematics_risk=12.0, class_confidence=7.0,
        direction_risk=0.0, loiter_risk=0.0, group_risk=0.0, override_reason=None,
    )


class TmpDirCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)


class TestRuntimeState(TmpDirCase):
    def test_frame_and_health_round_trip(self):
        pub = runtime_state.PipelinePublisher(self.tmp, max_fps=1000)
        self.assertTrue(pub.publish_frame("cam0", make_frame()))
        with open(runtime_state.frame_path("cam0", self.tmp), "rb") as f:
            self.assertEqual(f.read(2), b"\xff\xd8")  # a real JPEG, not a torn write
        pub.publish_health({"cameras": {"cam0": {"health": "online"}}})
        state = runtime_state.read_health(self.tmp)
        self.assertTrue(state["running"])
        self.assertEqual(state["cameras"]["cam0"]["health"], "online")

    def test_publishing_is_rate_limited_per_camera(self):
        pub = runtime_state.PipelinePublisher(self.tmp, max_fps=1)
        self.assertTrue(pub.publish_frame("cam0", make_frame()))
        self.assertFalse(pub.publish_frame("cam0", make_frame()))
        self.assertTrue(pub.publish_frame("cam1", make_frame()))  # independent budget

    def test_stale_health_is_not_running(self):
        path = runtime_state.health_path(self.tmp)
        with open(path, "w") as f:
            json.dump({"pid": os.getpid(), "updatedAt": time.time() - 60}, f)
        self.assertFalse(runtime_state.read_health(self.tmp)["running"])

    def test_fresh_file_from_a_dead_process_is_not_running(self):
        """A SIGKILLed pipeline cannot remove its file; a fresh timestamp alone
        must not keep the dashboard on a frozen frame."""
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        proc.wait()
        with open(runtime_state.health_path(self.tmp), "w") as f:
            json.dump({"pid": proc.pid, "updatedAt": time.time()}, f)
        self.assertFalse(runtime_state.read_health(self.tmp)["running"])

    def test_clean_close_removes_health(self):
        pub = runtime_state.PipelinePublisher(self.tmp)
        pub.publish_health({})
        pub.close()
        self.assertIsNone(runtime_state.read_health(self.tmp))

    def test_unsafe_camera_names_never_reach_a_path(self):
        with self.assertRaises(ValueError):
            runtime_state.frame_path("../../etc/passwd", self.tmp)
        pub = runtime_state.PipelinePublisher(self.tmp, max_fps=1000)
        self.assertFalse(pub.publish_frame("../escape", make_frame()))


class TestIncidentStorePersistsContext(TmpDirCase):
    def _store(self):
        return IncidentStore(
            db_path=os.path.join(self.tmp, "i.db"),
            evidence_dir=os.path.join(self.tmp, "snap"),
            key_path=os.path.join(self.tmp, "k.key"),
        )

    def test_camera_and_breakdown_are_stored(self):
        store = self._store()
        incident_id = store.record(make_detection("cam7"), make_score(), make_frame())
        row = store.get_incident(incident_id)
        store.close()
        self.assertEqual(row["camera_name"], "cam7")
        self.assertEqual(json.loads(row["breakdown"])["sector_risk"], 40.0)

    def test_detection_without_camera_stores_null(self):
        store = self._store()
        incident_id = store.record(make_detection(None), make_score(), make_frame())
        self.assertIsNone(store.get_incident(incident_id)["camera_name"])
        store.close()

    def test_existing_database_is_migrated_without_losing_rows(self):
        db = os.path.join(self.tmp, "i.db")
        conn = sqlite3.connect(db)
        conn.execute(
            "CREATE TABLE incidents (id INTEGER PRIMARY KEY AUTOINCREMENT, track_id INTEGER,"
            " person_id INTEGER, category TEXT, zone_tier TEXT, score REAL, tier TEXT,"
            " timestamp REAL, snapshot_path TEXT, crop_path TEXT, burst_paths TEXT)"
        )
        conn.execute("INSERT INTO incidents (category, tier, score) VALUES ('person', 'yellow', 40)")
        conn.commit()
        conn.close()
        store = self._store()
        rows = store.list_incidents()
        store.close()
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["camera_name"])
        self.assertIsNone(rows[0]["breakdown"])


class ApiCase(TmpDirCase):
    def setUp(self):
        super().setUp()
        self.db_path = os.path.join(self.tmp, "incidents.db")
        self.evidence_dir = os.path.join(self.tmp, "snapshots")
        self.key_path = os.path.join(self.tmp, "evidence.key")
        self.runtime_dir = os.path.join(self.tmp, "runtime")
        original_init = IncidentStore.__init__
        case = self

        def patched_init(store_self, *args, **kwargs):
            original_init(store_self, db_path=case.db_path,
                          evidence_dir=case.evidence_dir, key_path=case.key_path)

        for p in (
            patch.object(IncidentStore, "__init__", patched_init),
            patch.object(api_module, "IBVAP_API_TOKEN", TOKEN),
            patch.object(runtime_state, "RUNTIME_DIR", self.runtime_dir),
            patch.object(api_module, "_camera_sources", lambda: {"cam0": 0}),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.client = TestClient(api_module.app)

    def record(self, **kwargs) -> int:
        store = IncidentStore()
        try:
            return store.record(make_detection(), make_score(), make_frame(), **kwargs)
        finally:
            store.close()

    def raw_sql(self, sql: str, params=()):
        conn = sqlite3.connect(self.db_path)
        conn.execute(sql, params)
        conn.commit()
        conn.close()


class TestIncidentPayload(ApiCase):
    def test_incident_carries_camera_breakdown_and_evidence_urls(self):
        incident_id = self.record(crop_frame=make_frame(), burst_frames=[make_frame(), make_frame()])
        item = self.client.get("/api/v1/incidents", headers=AUTH).json()[0]
        self.assertEqual(item["cameraName"], "cam7")
        self.assertTrue(item["breakdown"]["recorded"])
        self.assertEqual(item["breakdown"]["sectorRisk"], 40.0)
        self.assertEqual(item["snapshotUrl"], f"/incidents/{incident_id}/evidence/snapshot")
        self.assertEqual(item["cropUrl"], f"/incidents/{incident_id}/evidence/crop")
        self.assertEqual(len(item["burstUrls"]), 2)

    def test_legacy_incident_says_breakdown_was_not_recorded(self):
        self.record()
        self.raw_sql("UPDATE incidents SET breakdown = NULL, camera_name = NULL")
        item = self.client.get("/api/v1/incidents", headers=AUTH).json()[0]
        self.assertFalse(item["breakdown"]["recorded"])
        self.assertEqual(item["cameraName"], "unknown")

    def test_history_limit_is_bounded(self):
        self.assertEqual(self.client.get("/api/v1/incidents?limit=5000", headers=AUTH).status_code, 422)


class TestEvidence(ApiCase):
    def url(self, incident_id, tail="snapshot", token=TOKEN):
        return f"/api/v1/incidents/{incident_id}/evidence/{tail}?token={token}"

    def test_snapshot_is_decrypted_to_a_viewable_jpeg(self):
        incident_id = self.record()
        resp = self.client.get(self.url(incident_id))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "image/jpeg")
        decoded = cv2.imdecode(np.frombuffer(resp.content, np.uint8), cv2.IMREAD_COLOR)
        self.assertIsNotNone(decoded)

    def test_burst_frames_by_index(self):
        incident_id = self.record(burst_frames=[make_frame(), make_frame()])
        self.assertEqual(self.client.get(self.url(incident_id, "burst/1")).status_code, 200)
        self.assertEqual(self.client.get(self.url(incident_id, "burst/5")).status_code, 404)

    def test_requires_a_token(self):
        incident_id = self.record()
        resp = self.client.get(f"/api/v1/incidents/{incident_id}/evidence/snapshot")
        self.assertEqual(resp.status_code, 401)

    def test_refuses_a_path_outside_the_evidence_store(self):
        incident_id = self.record()
        outside = os.path.join(self.tmp, "outside.jpg.enc")
        shutil.copy(os.path.join(self.evidence_dir, os.listdir(self.evidence_dir)[0]), outside)
        self.raw_sql("UPDATE incidents SET snapshot_path = ? WHERE id = ?", (outside, incident_id))
        resp = self.client.get(self.url(incident_id))
        self.assertEqual(resp.status_code, 404)
        self.assertIn("outside", resp.json()["detail"])

    def test_missing_file_is_reported_as_gone(self):
        incident_id = self.record()
        for name in os.listdir(self.evidence_dir):
            os.remove(os.path.join(self.evidence_dir, name))
        self.assertEqual(self.client.get(self.url(incident_id)).status_code, 410)

    def test_unknown_kind(self):
        incident_id = self.record()
        self.assertEqual(self.client.get(self.url(incident_id, "video")).status_code, 404)


class TestResolve(ApiCase):
    def test_resolves_with_a_known_reason(self):
        incident_id = self.record()
        resp = self.client.post(f"/api/v1/incidents/{incident_id}/resolve",
                                json={"reason": RESOLUTION_REASONS[0]}, headers=AUTH)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "resolved")
        self.assertEqual(resp.json()["resolutionReason"], RESOLUTION_REASONS[0])

    def test_free_text_reason_is_refused(self):
        incident_id = self.record()
        resp = self.client.post(f"/api/v1/incidents/{incident_id}/resolve",
                                json={"reason": "looked fine to me"}, headers=AUTH)
        self.assertEqual(resp.status_code, 422)

    def test_unknown_incident(self):
        resp = self.client.post("/api/v1/incidents/999999/resolve",
                                json={"reason": RESOLUTION_REASONS[0]}, headers=AUTH)
        self.assertEqual(resp.status_code, 404)

    def test_meta_exposes_the_reason_vocabulary(self):
        meta = self.client.get("/api/v1/meta", headers=AUTH).json()
        self.assertEqual(meta["resolutionReasons"], RESOLUTION_REASONS)


class TestSystemHealthAndCameras(ApiCase):
    def publish(self, cameras):
        pub = runtime_state.PipelinePublisher(self.runtime_dir, max_fps=1000)
        pub.publish_frame("cam0", make_frame())
        pub.publish_health({"cameras": cameras, "models": {"detector": "x.onnx"}})
        return pub

    def test_reports_pipeline_stopped_when_nothing_has_published(self):
        self.record()
        health = self.client.get("/api/v1/system/health", headers=AUTH).json()
        self.assertEqual(health["status"], "pipeline-stopped")
        self.assertFalse(health["pipeline"]["running"])
        self.assertEqual(health["database"]["total"], 1)
        self.assertEqual(health["database"]["open"], 1)
        for key in ("api", "evidence", "disk", "models", "zones", "watchlist"):
            self.assertIn(key, health)

    def test_healthy_pipeline_is_ok_and_a_degraded_camera_is_not(self):
        self.publish({"cam0": {"health": "online", "fps": 18.0}})
        self.assertEqual(self.client.get("/api/v1/system/health", headers=AUTH).json()["status"], "ok")
        self.publish({"cam0": {"health": "reconnecting"}})
        self.assertEqual(self.client.get("/api/v1/system/health", headers=AUTH).json()["status"], "degraded")

    def test_camera_list_says_the_pipeline_owns_the_feed(self):
        self.publish({"cam0": {"health": "online", "fps": 17.5, "active": True, "zones": 3}})
        cam = self.client.get("/api/v1/cameras", headers=AUTH).json()[0]
        self.assertEqual(cam["source"], "pipeline")
        self.assertEqual(cam["health"], "online")
        self.assertEqual(cam["activityGate"], "HIGH")
        self.assertEqual(cam["zones"], 3)

    def test_camera_list_without_pipeline_is_not_reported_live(self):
        cam = self.client.get("/api/v1/cameras", headers=AUTH).json()[0]
        self.assertIn(cam["source"], ("idle", "direct"))

    def test_pipeline_stream_serves_the_published_frame(self):
        self.publish({"cam0": {"health": "online"}})
        gen = api_module._pipeline_frames("cam0")
        try:
            chunk = next(gen)
        finally:
            gen.close()
        self.assertIn(b"Content-Type: image/jpeg", chunk)
        self.assertIn(b"\xff\xd8", chunk)


class TestCorsOrigins(ApiCase):
    """The bug this closes: Vite falls back to 5174/5175/... the moment 5173
    is taken (observed live - "Port 5173 is in use, trying another one"),
    but IBVAP_CORS_ORIGINS was a fixed list containing only 5173, so every
    dashboard API call failed CORS in the browser the moment that happened.
    Any port on localhost/127.0.0.1 must work regardless of IBVAP_ALLOW_LAN;
    it is still the same machine, and the bearer token is still required."""

    def _preflight_origin(self, origin: str) -> "str | None":
        resp = self.client.options(
            "/api/v1/system/health",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )
        return resp.headers.get("access-control-allow-origin")

    def test_configured_origin_is_allowed(self):
        self.assertEqual(self._preflight_origin("http://localhost:5173"), "http://localhost:5173")

    def test_a_different_localhost_port_is_still_allowed(self):
        # The exact scenario that broke: Vite moved off 5173.
        self.assertEqual(self._preflight_origin("http://localhost:5176"), "http://localhost:5176")

    def test_a_different_127_0_0_1_port_is_still_allowed(self):
        self.assertEqual(self._preflight_origin("http://127.0.0.1:5180"), "http://127.0.0.1:5180")

    def test_an_arbitrary_public_origin_is_rejected(self):
        self.assertIsNone(self._preflight_origin("http://evil.example.com"))

    def test_lan_origin_regex_matches_private_ranges_only(self):
        # Exercises the building block IBVAP_ALLOW_LAN=1 wires in, independent
        # of whatever that flag happens to be at import time in this run.
        import re

        pattern = re.compile(rf"^https?://({api_module._LAN_ORIGIN_RE})(:\d+)?$")
        for origin in (
            "http://192.168.1.59:5173", "http://10.0.0.5:8080", "http://172.20.3.4",
        ):
            self.assertIsNotNone(pattern.match(origin), origin)
        for origin in ("http://8.8.8.8:5173", "http://172.32.0.1", "http://evil.example.com"):
            self.assertIsNone(pattern.match(origin), origin)


if __name__ == "__main__":
    unittest.main()

"""Offline unit tests for Phase 16's C2 integration pieces — no camera, real
network, or real syslog daemon required.
Run from ibvap/: python -m unittest tests.test_integration
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database.incident_store import IncidentStore
from detection.detector import Detection
from integration.syslog_notifier import SyslogNotifier
from integration.webhook import WebhookNotifier
from intelligence.threat_score import ThreatScore


class TestWebhookNotifier(unittest.TestCase):
    def test_empty_url_never_calls_requests(self):
        notifier = WebhookNotifier(url="")
        with patch("integration.webhook.requests.post") as mock_post:
            notifier.notify({"tier": "red"})
        mock_post.assert_not_called()

    def test_configured_url_posts_payload_as_json(self):
        notifier = WebhookNotifier(url="http://example.invalid/webhook")
        with patch("integration.webhook.requests.post") as mock_post:
            notifier.notify({"tier": "red", "score": 85})
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "http://example.invalid/webhook")
        self.assertEqual(kwargs["json"], {"tier": "red", "score": 85})

    def test_request_exception_is_swallowed_not_raised(self):
        notifier = WebhookNotifier(url="http://example.invalid/webhook")
        with patch("integration.webhook.requests.post", side_effect=ConnectionError("down")):
            try:
                notifier.notify({"tier": "red"})
            except Exception as e:
                self.fail(f"notify() must not raise, but raised: {e}")


class TestSyslogNotifier(unittest.TestCase):
    def test_emit_does_not_raise_even_with_no_listener(self):
        # UDP is fire-and-forget — this must succeed even though nothing is
        # listening on this port in a test environment.
        notifier = SyslogNotifier(host="localhost", port=51499)
        try:
            notifier.emit("ALERT tier=red category=person score=85 track=1 zone=red")
        except Exception as e:
            self.fail(f"emit() must not raise, but raised: {e}")


_TEST_TOKEN = "test-token-not-a-real-secret"


def _auth_header() -> dict:
    return {"Authorization": f"Bearer {_TEST_TOKEN}"}


class TestIncidentAPI(unittest.TestCase):
    def test_incidents_endpoint_returns_recorded_incidents(self):
        from fastapi.testclient import TestClient

        import integration.api as api_module

        tmp_dir = Path(tempfile.mkdtemp())
        db_path = str(tmp_dir / "incidents.db")
        evidence_dir = str(tmp_dir / "snapshots")
        key_path = str(tmp_dir / "evidence.key")

        # Seed a real incident using the same default-path IncidentStore the
        # API constructs internally, by monkeypatching IncidentStore's
        # defaults for the duration of this test.
        store = IncidentStore(db_path=db_path, evidence_dir=evidence_dir, key_path=key_path)
        det = Detection(class_id=0, class_name="person", confidence=0.9, box=(0, 0, 50, 100))
        det.track_id = 1
        det.zone_tier = "red"
        score = ThreatScore(sector_risk=30, time_risk=25, kinematics_risk=10, class_confidence=15)
        import numpy as np
        store.record(det, score, np.zeros((100, 100, 3), dtype=np.uint8))
        store.close()

        original_init = IncidentStore.__init__

        def patched_init(self, *args, **kwargs):
            original_init(self, db_path=db_path, evidence_dir=evidence_dir, key_path=key_path)

        with patch.object(IncidentStore, "__init__", patched_init), \
                patch.object(api_module, "IBVAP_API_TOKEN", _TEST_TOKEN):
            client = TestClient(api_module.app)
            response = client.get("/incidents", headers=_auth_header())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["incidents"][0]["category"], "person")

    def test_status_endpoint_ok(self):
        from fastapi.testclient import TestClient

        import integration.api as api_module

        with patch.object(api_module, "IBVAP_API_TOKEN", _TEST_TOKEN):
            client = TestClient(api_module.app)
            response = client.get("/status", headers=_auth_header())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_endpoints_refuse_unauthenticated_requests(self):
        """Phase 17: the feed lists sightings with timestamps and zones, so
        both endpoints must reject an unauthenticated caller even when a
        token IS configured."""
        from fastapi.testclient import TestClient

        import integration.api as api_module

        with patch.object(api_module, "IBVAP_API_TOKEN", _TEST_TOKEN):
            client = TestClient(api_module.app)
            for path in ("/status", "/incidents"):
                self.assertEqual(client.get(path).status_code, 401, path)
                self.assertEqual(
                    client.get(path, headers={"Authorization": "Bearer wrong"}).status_code,
                    401,
                    path,
                )


if __name__ == "__main__":
    unittest.main()

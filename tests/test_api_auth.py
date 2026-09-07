"""Offline unit tests for integration API authentication (Phase 0B item 2).
Run from ibvap/: python -m unittest tests.test_api_auth

The incident feed is never queried here — `/status` exercises the same
dependency, so these assert the auth boundary without touching a real
IncidentStore or database file.
"""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import integration.api as api

TOKEN = "test-token-not-a-real-secret"


class AuthTestCase(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api.app)


class TestValidAuthentication(AuthTestCase):
    def test_valid_token_is_accepted(self):
        with patch.object(api, "API_TOKEN", TOKEN):
            response = self.client.get(
                "/status", headers={"Authorization": f"Bearer {TOKEN}"}
            )
        self.assertEqual(response.status_code, 200)

    def test_endpoint_behaviour_preserved_for_authenticated_callers(self):
        """Auth must gate the endpoint, not change what it returns."""
        with patch.object(api, "API_TOKEN", TOKEN):
            response = self.client.get(
                "/status", headers={"Authorization": f"Bearer {TOKEN}"}
            )
        self.assertEqual(response.json(), {"status": "ok", "service": "IBVAP"})


class TestMissingAuthentication(AuthTestCase):
    def test_missing_header_is_rejected(self):
        with patch.object(api, "API_TOKEN", TOKEN):
            response = self.client.get("/status")
        self.assertEqual(response.status_code, 401)

    def test_missing_header_on_incidents_is_rejected_without_touching_store(self):
        with patch.object(api, "API_TOKEN", TOKEN):
            response = self.client.get("/incidents")
        self.assertEqual(response.status_code, 401)

    def test_rejection_advertises_bearer_scheme(self):
        with patch.object(api, "API_TOKEN", TOKEN):
            response = self.client.get("/status")
        self.assertEqual(response.headers.get("WWW-Authenticate"), "Bearer")


class TestInvalidAuthentication(AuthTestCase):
    def test_wrong_token_is_rejected(self):
        with patch.object(api, "API_TOKEN", TOKEN):
            response = self.client.get(
                "/status", headers={"Authorization": "Bearer wrong-token"}
            )
        self.assertEqual(response.status_code, 401)

    def test_wrong_scheme_is_rejected(self):
        with patch.object(api, "API_TOKEN", TOKEN):
            response = self.client.get(
                "/status", headers={"Authorization": f"Basic {TOKEN}"}
            )
        self.assertEqual(response.status_code, 401)

    def test_empty_bearer_token_is_rejected(self):
        with patch.object(api, "API_TOKEN", TOKEN):
            response = self.client.get("/status", headers={"Authorization": "Bearer "})
        self.assertEqual(response.status_code, 401)

    def test_token_prefix_is_rejected(self):
        """Guards against any accidental prefix/startswith comparison."""
        with patch.object(api, "API_TOKEN", TOKEN):
            response = self.client.get(
                "/status", headers={"Authorization": f"Bearer {TOKEN[:-1]}"}
            )
        self.assertEqual(response.status_code, 401)


class TestNoInformationLeak(AuthTestCase):
    def test_error_body_does_not_echo_credentials_or_the_real_token(self):
        supplied = "supplied-credential-value"
        with patch.object(api, "API_TOKEN", TOKEN):
            response = self.client.get(
                "/status", headers={"Authorization": f"Bearer {supplied}"}
            )
        body = response.text
        self.assertNotIn(supplied, body)
        self.assertNotIn(TOKEN, body)
        self.assertEqual(response.json(), {"detail": "Unauthorized"})

    def test_missing_and_invalid_are_indistinguishable(self):
        """The caller must not learn *which* part of its credential was wrong."""
        with patch.object(api, "API_TOKEN", TOKEN):
            missing = self.client.get("/status")
            invalid = self.client.get(
                "/status", headers={"Authorization": "Bearer nope"}
            )
        self.assertEqual(missing.status_code, invalid.status_code)
        self.assertEqual(missing.json(), invalid.json())


class TestFailsClosed(AuthTestCase):
    def test_unconfigured_token_refuses_everyone(self):
        """A misconfigured deployment must not serve the feed unauthenticated."""
        with patch.object(api, "API_TOKEN", ""):
            anonymous = self.client.get("/status")
            with_token = self.client.get(
                "/status", headers={"Authorization": f"Bearer {TOKEN}"}
            )
        self.assertEqual(anonymous.status_code, 503)
        self.assertEqual(with_token.status_code, 503)

    def test_unconfigured_error_does_not_leak_the_token_value(self):
        with patch.object(api, "API_TOKEN", ""):
            response = self.client.get("/status")
        self.assertNotIn(TOKEN, response.text)


if __name__ == "__main__":
    unittest.main()

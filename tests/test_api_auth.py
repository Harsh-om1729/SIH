"""Offline unit tests for the integration API's bearer auth (Phase 17).

Tests the dependency directly rather than through fastapi.testclient, which
would pull in httpx — this suite deliberately runs with no extra deps.
Run from ibvap/: python -m unittest tests.test_api_auth
"""

import unittest
from unittest import mock

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import integration.api as api


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


class TestRequireToken(unittest.TestCase):
    def test_unset_token_refuses_everything(self):
        """Fail closed. An unconfigured deployment must not serve the incident
        feed openly — .env has claimed this behaviour since before it existed."""
        with mock.patch.object(api, "IBVAP_API_TOKEN", ""):
            for supplied in (None, _creds(""), _creds("anything")):
                with self.assertRaises(HTTPException) as ctx:
                    api.require_token(supplied)
                self.assertEqual(ctx.exception.status_code, 503)

    def test_correct_token_is_accepted(self):
        with mock.patch.object(api, "IBVAP_API_TOKEN", "s3cret-token"):
            self.assertIsNone(api.require_token(_creds("s3cret-token")))

    def test_wrong_token_is_rejected(self):
        with mock.patch.object(api, "IBVAP_API_TOKEN", "s3cret-token"):
            with self.assertRaises(HTTPException) as ctx:
                api.require_token(_creds("wrong-token"))
            self.assertEqual(ctx.exception.status_code, 401)

    def test_missing_header_is_rejected(self):
        with mock.patch.object(api, "IBVAP_API_TOKEN", "s3cret-token"):
            with self.assertRaises(HTTPException) as ctx:
                api.require_token(None)
            self.assertEqual(ctx.exception.status_code, 401)

    def test_token_prefix_is_not_accepted(self):
        """A prefix must fail like any other wrong value — guards against a
        truncating comparison creeping in."""
        with mock.patch.object(api, "IBVAP_API_TOKEN", "s3cret-token"):
            with self.assertRaises(HTTPException):
                api.require_token(_creds("s3cret"))


if __name__ == "__main__":
    unittest.main()

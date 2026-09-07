"""Phase 16 — lightweight REST endpoint exposing the incident feed as JSON,
so any C2/SIEM system a deploying force already runs can poll this platform
without needing to know its internals (ONNX/ByteTrack/etc. stay invisible).

Access requires a bearer token (Phase 0B, item 2). The incident feed carries
operational surveillance data, so it is not served to unauthenticated callers.
Set the token in the environment before starting the service:

    IBVAP_API_TOKEN=<a long random secret>

Run from ibvap/: uvicorn integration.api:app --port 8000
Then: curl -H "Authorization: Bearer $IBVAP_API_TOKEN" http://localhost:8000/incidents
"""

import hmac
import logging

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config.settings import API_TOKEN
from database.incident_store import IncidentStore

log = logging.getLogger("ibvap.integration.api")

app = FastAPI(title="IBVAP Integration API")

# auto_error=False so a *missing* Authorization header reaches our own handler
# and gets the same generic 401 as a malformed one — the caller learns only
# that it is unauthorized, never which part of its credential was wrong.
_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Unauthorized",
    headers={"WWW-Authenticate": "Bearer"},
)


def require_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """Rejects any caller without a valid bearer token.

    Fails *closed*: if no token is configured the API serves nobody, so a
    misconfigured deployment cannot silently expose the incident feed. The
    comparison is constant-time to avoid leaking the token byte-by-byte
    through response timing, and no error message ever echoes the supplied
    credential or says which check failed.
    """
    if not API_TOKEN:
        # Logged (operators need to know why every call 503s) but the value
        # itself is never logged, here or anywhere else.
        log.error(
            "IBVAP_API_TOKEN is not configured - refusing all API requests. "
            "Set it in the environment to enable the integration API."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API authentication is not configured",
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _UNAUTHORIZED
    if not hmac.compare_digest(credentials.credentials, API_TOKEN):
        raise _UNAUTHORIZED


@app.get("/status")
def status_endpoint(_: None = Depends(require_token)) -> dict:
    return {"status": "ok", "service": "IBVAP"}


@app.get("/incidents")
def incidents(limit: int = 20, _: None = Depends(require_token)) -> dict:
    store = IncidentStore()
    try:
        rows = store.list_incidents(limit=limit)
    finally:
        store.close()
    return {"count": len(rows), "incidents": rows}

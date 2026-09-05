"""Phase 16 — lightweight REST endpoint exposing the incident feed as JSON,
so any C2/SIEM system a deploying force already runs can poll this platform
without needing to know its internals (ONNX/ByteTrack/etc. stay invisible).

Run from ibvap/: uvicorn integration.api:app --port 8000
Then: curl http://localhost:8000/incidents
"""

from fastapi import FastAPI

from database.incident_store import IncidentStore

app = FastAPI(title="IBVAP Integration API")


@app.get("/status")
def status() -> dict:
    return {"status": "ok", "service": "IBVAP"}


@app.get("/incidents")
def incidents(limit: int = 20) -> dict:
    store = IncidentStore()
    try:
        rows = store.list_incidents(limit=limit)
    finally:
        store.close()
    return {"count": len(rows), "incidents": rows}

import json
import logging
import os
import sqlite3
import time

import cv2
from cryptography.fernet import Fernet

log = logging.getLogger("ibvap.incidents")


class IncidentStore:
    """Persists alert-worthy events to a local, queryable `incidents.db` and
    encrypts the accompanying evidence images at rest (Fernet, per the
    roadmap's zero-cost stack) — no cloud, no network dependency, matching
    the air-gapped deployment requirement. The encryption key is generated
    once and persisted locally; losing it makes existing evidence
    unreadable, same tradeoff as any local-key encryption scheme.
    """

    def __init__(
        self,
        db_path: str = "database/incidents.db",
        evidence_dir: str = "snapshots",
        key_path: str = "database/evidence.key",
    ):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        os.makedirs(evidence_dir, exist_ok=True)
        self.evidence_dir = evidence_dir
        self._fernet = Fernet(self._load_or_create_key(key_path))
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_table()

    def _load_or_create_key(self, key_path: str) -> bytes:
        os.makedirs(os.path.dirname(key_path) or ".", exist_ok=True)
        if os.path.exists(key_path):
            with open(key_path, "rb") as f:
                return f.read()
        key = Fernet.generate_key()
        with open(key_path, "wb") as f:
            f.write(key)
        log.info("Generated new evidence encryption key at %s", key_path)
        return key

    def _create_table(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
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
        self._conn.commit()

    def record(self, det, score, frame, crop_frame=None, burst_frames=None) -> int:
        timestamp = time.time()
        ts_label = time.strftime("%Y%m%d-%H%M%S", time.localtime(timestamp))
        track_key = det.person_id if det.person_id is not None else det.track_id
        prefix = f"{score.tier}_{det.category()}_{track_key}_{ts_label}"

        snapshot_path = self._save_encrypted(frame, f"{prefix}_full.jpg.enc")

        crop_path = None
        if crop_frame is not None and crop_frame.size > 0:
            crop_path = self._save_encrypted(crop_frame, f"{prefix}_crop.jpg.enc")

        burst_paths = []
        for i, burst_frame in enumerate(burst_frames or []):
            path = self._save_encrypted(burst_frame, f"{prefix}_burst{i}.jpg.enc")
            if path:
                burst_paths.append(path)

        cur = self._conn.execute(
            """
            INSERT INTO incidents
                (track_id, person_id, category, zone_tier, score, tier, timestamp,
                 snapshot_path, crop_path, burst_paths)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                det.track_id, det.person_id, det.category(), det.zone_tier,
                score.total, score.tier, timestamp,
                snapshot_path, crop_path, json.dumps(burst_paths),
            ),
        )
        self._conn.commit()
        log.info("Recorded incident #%d (%s, score=%.0f)", cur.lastrowid, score.tier, score.total)
        return cur.lastrowid

    def _save_encrypted(self, frame, filename: str) -> "str | None":
        ok, buffer = cv2.imencode(".jpg", frame)
        if not ok:
            return None
        encrypted = self._fernet.encrypt(buffer.tobytes())
        path = os.path.join(self.evidence_dir, filename)
        with open(path, "wb") as f:
            f.write(encrypted)
        return path

    def decrypt_image_bytes(self, path: str) -> bytes:
        with open(path, "rb") as f:
            encrypted = f.read()
        return self._fernet.decrypt(encrypted)

    def list_incidents(self, limit: int = 50) -> list:
        cur = self._conn.execute(
            "SELECT id, track_id, person_id, category, zone_tier, score, tier, timestamp, "
            "snapshot_path, crop_path, burst_paths FROM incidents ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        columns = [d[0] for d in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()

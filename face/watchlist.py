import json
import logging
import os
import sqlite3

import numpy as np

from face.face_recognizer import cosine_similarity

log = logging.getLogger("ibvap.face")


class WatchlistDB:
    """Local, offline watchlist of known-person face embeddings (SQLite).
    In a real deployment this would be updated via the same encrypted-USB
    transfer mechanism as threat_rules.db — no cloud, no network dependency,
    matching the air-gapped requirement.

    NOTE for the SIH report: any real deployment of a watchlist database
    needs authorized data-handling procedures under India's DPDP Act — this
    is genuine personal biometric data, not a detail to gloss over.
    """

    def __init__(self, db_path: str = "database/watchlist.db"):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_table()

    def _create_table(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                embedding TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def add_person(self, name: str, embedding: np.ndarray) -> int:
        cur = self._conn.execute(
            "INSERT INTO watchlist (name, embedding) VALUES (?, ?)",
            (name, json.dumps(embedding.tolist())),
        )
        self._conn.commit()
        log.info("Added '%s' to watchlist (id=%d)", name, cur.lastrowid)
        return cur.lastrowid

    def all_entries(self) -> list:
        cur = self._conn.execute("SELECT id, name, embedding FROM watchlist")
        return [
            (row[0], row[1], np.array(json.loads(row[2]), dtype=np.float32))
            for row in cur.fetchall()
        ]

    def close(self) -> None:
        self._conn.close()


class WatchlistMatcher:
    """Cosine-similarity match against the watchlist. A match instantly
    escalates the track to Red tier regardless of zone score (applied by the
    caller) — false positives here are a real operational risk, so this
    returns the matched name and similarity for transparency, never a bare
    yes/no, per the roadmap's testing checklist.
    """

    def __init__(self, watchlist: WatchlistDB, similarity_threshold: float = 0.5):
        self.watchlist = watchlist
        self.similarity_threshold = similarity_threshold

    def match(self, embedding: np.ndarray):
        best_name = None
        best_similarity = 0.0
        for _id, name, entry_embedding in self.watchlist.all_entries():
            similarity = cosine_similarity(embedding, entry_embedding)
            if similarity > best_similarity:
                best_similarity = similarity
                best_name = name

        if best_name is not None and best_similarity >= self.similarity_threshold:
            return best_name, best_similarity
        return None, best_similarity

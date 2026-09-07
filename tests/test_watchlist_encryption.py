"""Offline unit tests for watchlist embedding encryption at rest
(Phase 0B item 3). Run from ibvap/: python -m unittest tests.test_watchlist_encryption

Synthetic embeddings stand in for real face vectors — no face model needed.
These assert that what lands on disk is not readable biometric data, that
matching still works after decryption, and that pre-encryption databases keep
working.
"""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import numpy as np

from face.watchlist import WatchlistDB, WatchlistMatcher


class WatchlistEncryptionTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.db_path = str(self.tmp / "watchlist.db")
        self.key_path = str(self.tmp / "watchlist.key")

    def _db(self) -> WatchlistDB:
        return WatchlistDB(db_path=self.db_path, key_path=self.key_path)

    def _raw_embedding_column(self) -> str:
        conn = sqlite3.connect(self.db_path)
        try:
            return conn.execute("SELECT embedding FROM watchlist").fetchone()[0]
        finally:
            conn.close()


class TestEncryptedAtRest(WatchlistEncryptionTestCase):
    def test_stored_embedding_is_not_plaintext(self):
        embedding = np.array([0.11, 0.22, 0.33], dtype=np.float32)
        db = self._db()
        db.add_person("Alice", embedding)
        db.close()

        stored = self._raw_embedding_column()
        self.assertNotIn("0.11", stored)
        with self.assertRaises(json.JSONDecodeError):
            json.loads(stored)

    def test_key_file_is_created_and_db_holds_no_key(self):
        db = self._db()
        db.add_person("Alice", np.array([1.0, 2.0], dtype=np.float32))
        db.close()

        self.assertTrue(Path(self.key_path).exists())
        key = Path(self.key_path).read_bytes()
        self.assertNotIn(key.decode("ascii"), self._raw_embedding_column())

    def test_roundtrip_returns_the_original_vector(self):
        embedding = np.array([0.5, -1.25, 3.75], dtype=np.float32)
        db = self._db()
        db.add_person("Alice", embedding)
        db.close()

        reopened = self._db()
        _id, name, restored = reopened.all_entries()[0]
        reopened.close()
        self.assertEqual(name, "Alice")
        np.testing.assert_array_almost_equal(restored, embedding)

    def test_persists_across_reconnection(self):
        db_a = self._db()
        db_a.add_person("Bob", np.array([4.0, 5.0, 6.0], dtype=np.float32))
        db_a.close()

        db_b = self._db()
        entries = db_b.all_entries()
        db_b.close()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][1], "Bob")

    def test_wrong_key_cannot_read_embeddings(self):
        db = self._db()
        db.add_person("Alice", np.array([1.0, 2.0, 3.0], dtype=np.float32))
        db.close()

        other_key = str(self.tmp / "other.key")
        intruder = WatchlistDB(db_path=self.db_path, key_path=other_key)
        with self.assertRaises(Exception):
            intruder.all_entries()
        intruder.close()


class TestMatchingStillWorks(WatchlistEncryptionTestCase):
    def test_match_succeeds_after_decryption(self):
        target = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        db = self._db()
        db.add_person("Suspect", target)
        db.add_person("Other", np.array([0.0, 1.0, 0.0], dtype=np.float32))

        matcher = WatchlistMatcher(db, similarity_threshold=0.5)
        name, similarity = matcher.match(np.array([0.99, 0.01, 0.0], dtype=np.float32))
        db.close()

        self.assertEqual(name, "Suspect")
        self.assertGreater(similarity, 0.5)

    def test_non_matching_face_returns_no_name(self):
        db = self._db()
        db.add_person("Suspect", np.array([1.0, 0.0, 0.0], dtype=np.float32))
        matcher = WatchlistMatcher(db, similarity_threshold=0.9)
        name, _similarity = matcher.match(np.array([0.0, 1.0, 0.0], dtype=np.float32))
        db.close()
        self.assertIsNone(name)


class TestLegacyCompatibility(WatchlistEncryptionTestCase):
    def test_pre_encryption_plaintext_rows_still_load(self):
        """An existing watchlist.db written before this change must keep working."""
        legacy = np.array([7.0, 8.0, 9.0], dtype=np.float32)
        db = self._db()  # creates the schema
        db.close()

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO watchlist (name, embedding) VALUES (?, ?)",
            ("LegacyPerson", json.dumps(legacy.tolist())),
        )
        conn.commit()
        conn.close()

        db = self._db()
        entries = db.all_entries()
        db.close()
        self.assertEqual(entries[0][1], "LegacyPerson")
        np.testing.assert_array_almost_equal(entries[0][2], legacy)

    def test_legacy_and_encrypted_rows_coexist(self):
        legacy = np.array([1.0, 0.0], dtype=np.float32)
        db = self._db()
        db.close()
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO watchlist (name, embedding) VALUES (?, ?)",
            ("Legacy", json.dumps(legacy.tolist())),
        )
        conn.commit()
        conn.close()

        db = self._db()
        db.add_person("Encrypted", np.array([0.0, 1.0], dtype=np.float32))
        names = sorted(name for _id, name, _e in db.all_entries())
        db.close()
        self.assertEqual(names, ["Encrypted", "Legacy"])


class TestNoSensitiveLogging(WatchlistEncryptionTestCase):
    def test_adding_a_person_never_logs_the_embedding_or_key(self):
        embedding = np.array([0.123456, 0.654321], dtype=np.float32)
        with self.assertLogs("ibvap", level="DEBUG") as captured:
            db = self._db()
            db.add_person("Alice", embedding)
            db.all_entries()
            db.close()

        joined = "\n".join(captured.output)
        self.assertNotIn("0.123456", joined)
        self.assertNotIn("0.654321", joined)
        self.assertNotIn(Path(self.key_path).read_bytes().decode("ascii"), joined)


if __name__ == "__main__":
    unittest.main()

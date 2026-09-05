"""Offline unit tests for the watchlist DB and matcher — no camera or real
face model required (synthetic embeddings stand in for real face vectors).
Run from ibvap/: python -m unittest tests.test_watchlist
"""

import tempfile
import unittest
from pathlib import Path

import numpy as np

from face.face_recognizer import cosine_similarity
from face.watchlist import WatchlistDB, WatchlistMatcher


class TestWatchlistDB(unittest.TestCase):
    def _db(self) -> WatchlistDB:
        tmp_dir = tempfile.mkdtemp()
        return WatchlistDB(db_path=str(Path(tmp_dir) / "watchlist.db"))

    def test_add_and_retrieve_entry(self):
        db = self._db()
        embedding = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        db.add_person("Alice", embedding)

        entries = db.all_entries()
        self.assertEqual(len(entries), 1)
        _id, name, stored_embedding = entries[0]
        self.assertEqual(name, "Alice")
        np.testing.assert_array_almost_equal(stored_embedding, embedding)

    def test_persists_across_reconnection(self):
        tmp_dir = tempfile.mkdtemp()
        db_path = str(Path(tmp_dir) / "watchlist.db")
        db_a = WatchlistDB(db_path=db_path)
        db_a.add_person("Bob", np.array([4.0, 5.0, 6.0], dtype=np.float32))
        db_a.close()

        db_b = WatchlistDB(db_path=db_path)
        entries = db_b.all_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][1], "Bob")


class TestWatchlistMatcher(unittest.TestCase):
    def test_matches_similar_embedding_above_threshold(self):
        db = WatchlistDB(db_path=str(Path(tempfile.mkdtemp()) / "watchlist.db"))
        known = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        db.add_person("Alice", known)
        matcher = WatchlistMatcher(db, similarity_threshold=0.9)

        query = np.array([0.99, 0.01, 0.0], dtype=np.float32)  # nearly identical direction
        name, similarity = matcher.match(query)

        self.assertEqual(name, "Alice")
        self.assertGreaterEqual(similarity, 0.9)

    def test_no_match_when_below_threshold(self):
        db = WatchlistDB(db_path=str(Path(tempfile.mkdtemp()) / "watchlist.db"))
        db.add_person("Alice", np.array([1.0, 0.0, 0.0], dtype=np.float32))
        matcher = WatchlistMatcher(db, similarity_threshold=0.9)

        query = np.array([0.0, 1.0, 0.0], dtype=np.float32)  # orthogonal, similarity 0
        name, similarity = matcher.match(query)

        self.assertIsNone(name)
        self.assertLess(similarity, 0.9)

    def test_empty_watchlist_never_matches(self):
        db = WatchlistDB(db_path=str(Path(tempfile.mkdtemp()) / "watchlist.db"))
        matcher = WatchlistMatcher(db, similarity_threshold=0.5)

        name, similarity = matcher.match(np.array([1.0, 0.0, 0.0], dtype=np.float32))

        self.assertIsNone(name)
        self.assertEqual(similarity, 0.0)

    def test_matches_best_of_multiple_entries(self):
        db = WatchlistDB(db_path=str(Path(tempfile.mkdtemp()) / "watchlist.db"))
        db.add_person("Alice", np.array([1.0, 0.0, 0.0], dtype=np.float32))
        db.add_person("Bob", np.array([0.0, 1.0, 0.0], dtype=np.float32))
        matcher = WatchlistMatcher(db, similarity_threshold=0.5)

        query = np.array([0.05, 0.99, 0.0], dtype=np.float32)  # closest to Bob
        name, _ = matcher.match(query)

        self.assertEqual(name, "Bob")


class TestCosineSimilarity(unittest.TestCase):
    def test_identical_vectors_similarity_one(self):
        v = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        self.assertAlmostEqual(cosine_similarity(v, v), 1.0, places=5)

    def test_orthogonal_vectors_similarity_zero(self):
        a = np.array([1.0, 0.0], dtype=np.float32)
        b = np.array([0.0, 1.0], dtype=np.float32)
        self.assertAlmostEqual(cosine_similarity(a, b), 0.0, places=5)

    def test_zero_vector_returns_zero_not_error(self):
        a = np.zeros(3, dtype=np.float32)
        b = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        self.assertEqual(cosine_similarity(a, b), 0.0)


if __name__ == "__main__":
    unittest.main()

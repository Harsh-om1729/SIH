"""Offline unit tests for the Re-ID person gallery — no camera required.
Run from ibvap/: python -m unittest tests.test_reid

Uses a fast, deterministic fake embedder (mean crop color) instead of the
real OSNet model, so these tests exercise PersonGallery's bookkeeping
logic (buffering, matching, TTL eviction) independent of embedding quality.
"""

import unittest

import numpy as np

from reid.reid import PersonGallery

FRAME_SIZE = (480, 640, 3)


def make_frame_with_patch(color: tuple, box: tuple) -> np.ndarray:
    """A synthetic frame with a solid-color rectangle at `box`, standing in
    for a person's appearance."""
    frame = np.zeros(FRAME_SIZE, dtype=np.uint8)
    x1, y1, x2, y2 = box
    frame[y1:y2, x1:x2] = color
    return frame


def fake_embed(frame: np.ndarray, box: tuple):
    """Deterministic stand-in for a real embedder: mean BGR color of the crop."""
    x1, y1, x2, y2 = box
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    return crop.reshape(-1, 3).mean(axis=0).astype(np.float32)


def resolve_until_decided(gallery: PersonGallery, track_id: int, frame, box):
    """Keeps calling resolve() (as app.py does, once per frame) until the
    gallery has buffered enough samples to return a decision."""
    for _ in range(10):
        person_id = gallery.resolve(track_id, frame, box)
        if person_id is not None:
            return person_id
    raise AssertionError("gallery never resolved a person_id within 10 frames")


class TestPersonGalleryReappearance(unittest.TestCase):
    def test_same_person_reassigned_new_track_id_keeps_same_person_id(self):
        """Simulates ByteTrack losing a person (ID 101) and, on return,
        assigning a brand-new track_id (102) after a short absence — the
        gallery should still resolve both to the same person_id.
        """
        clock = {"t": 0.0}
        gallery = PersonGallery(
            embed_fn=fake_embed,
            similarity_threshold=0.8,
            ttl_seconds=30.0,
            min_samples=3,
            now_fn=lambda: clock["t"],
        )

        box = (100, 100, 160, 260)  # tall person-shaped box
        red_frame = make_frame_with_patch((0, 0, 220), box)

        person_id_first = resolve_until_decided(gallery, 101, red_frame, box)

        # Time passes (person briefly out of frame) but within the TTL window.
        clock["t"] = 5.0

        # ByteTrack assigns a new track_id on reappearance, same appearance.
        person_id_second = resolve_until_decided(gallery, 102, red_frame, box)

        self.assertEqual(person_id_first, person_id_second)

    def test_different_person_gets_new_person_id(self):
        clock = {"t": 0.0}
        gallery = PersonGallery(
            embed_fn=fake_embed,
            similarity_threshold=0.8,
            ttl_seconds=30.0,
            min_samples=3,
            now_fn=lambda: clock["t"],
        )

        box = (100, 100, 160, 260)
        red_frame = make_frame_with_patch((0, 0, 220), box)
        blue_frame = make_frame_with_patch((220, 0, 0), box)

        person_id_a = resolve_until_decided(gallery, 201, red_frame, box)
        clock["t"] = 2.0
        person_id_b = resolve_until_decided(gallery, 202, blue_frame, box)

        self.assertNotEqual(person_id_a, person_id_b)

    def test_same_track_id_reuses_cached_person_id_without_rematching(self):
        """While the same track_id keeps appearing (ByteTrack hasn't lost it),
        repeated calls must return the same person_id every time."""
        clock = {"t": 0.0}
        gallery = PersonGallery(
            embed_fn=fake_embed,
            similarity_threshold=0.8,
            ttl_seconds=30.0,
            min_samples=3,
            now_fn=lambda: clock["t"],
        )

        box = (100, 100, 160, 260)
        red_frame = make_frame_with_patch((0, 0, 220), box)

        first = resolve_until_decided(gallery, 301, red_frame, box)
        clock["t"] = 1.0
        second = gallery.resolve(301, red_frame, box)
        clock["t"] = 2.0
        third = gallery.resolve(301, red_frame, box)

        self.assertEqual(first, second)
        self.assertEqual(second, third)

    def test_reappearance_after_ttl_expires_gets_new_person_id(self):
        """If the gap is longer than ttl_seconds, the old entry is evicted and
        must NOT be matched, even with identical appearance — otherwise two
        unrelated people who happen to look similar days apart could merge."""
        clock = {"t": 0.0}
        gallery = PersonGallery(
            embed_fn=fake_embed,
            similarity_threshold=0.8,
            ttl_seconds=10.0,
            min_samples=3,
            now_fn=lambda: clock["t"],
        )

        box = (100, 100, 160, 260)
        red_frame = make_frame_with_patch((0, 0, 220), box)

        person_id_first = resolve_until_decided(gallery, 401, red_frame, box)

        clock["t"] = 100.0  # far beyond the 10s TTL
        person_id_second = resolve_until_decided(gallery, 402, red_frame, box)

        self.assertNotEqual(person_id_first, person_id_second)

    def test_resolve_returns_none_while_buffering_samples(self):
        """A brand-new track_id must not get an identity decision until
        min_samples frames have been seen (avoids deciding off one noisy frame)."""
        gallery = PersonGallery(embed_fn=fake_embed, similarity_threshold=0.8, ttl_seconds=30.0, min_samples=3)
        box = (100, 100, 160, 260)
        red_frame = make_frame_with_patch((0, 0, 220), box)

        self.assertIsNone(gallery.resolve(501, red_frame, box))
        self.assertIsNone(gallery.resolve(501, red_frame, box))
        self.assertIsNotNone(gallery.resolve(501, red_frame, box))  # 3rd sample decides

    def test_too_small_box_never_contributes_a_sample(self):
        """A tiny/edge-clipped box (partial view of a person) shouldn't count
        toward the sample buffer at all, since its embedding would be noise."""
        gallery = PersonGallery(embed_fn=fake_embed, similarity_threshold=0.8, ttl_seconds=30.0, min_samples=2)
        tiny_box = (100, 100, 110, 115)  # well under the min crop size
        frame = make_frame_with_patch((0, 0, 220), tiny_box)

        for _ in range(5):
            self.assertIsNone(gallery.resolve(601, frame, tiny_box))


class TestSimultaneousPeople(unittest.TestCase):
    """Two people visible in the same frame must never share a person_id, even
    when their appearance embeddings are close enough to cross the similarity
    threshold — one person cannot be in two places at once.
    """

    def test_two_lookalikes_on_screen_together_stay_on_separate_ids(self):
        clock = {"t": 0.0}
        gallery = PersonGallery(
            embed_fn=fake_embed,
            similarity_threshold=0.8,
            ttl_seconds=30.0,
            min_samples=3,
            now_fn=lambda: clock["t"],
        )

        # Two people in near-identical clothing — cosine similarity between
        # these two mean colors is ~0.999, well above the threshold.
        box_a = (100, 100, 160, 260)
        box_b = (300, 100, 360, 260)
        frame = make_frame_with_patch((60, 60, 200), box_a)
        frame[100:260, 300:360] = (62, 61, 198)

        for _ in range(5):
            person_a = gallery.resolve(("cam1", 201), frame, box_a)
            person_b = gallery.resolve(("cam1", 202), frame, box_b)
            clock["t"] += 0.04  # ~25 FPS: both tracks are live every frame

        self.assertIsNotNone(person_a)
        self.assertIsNotNone(person_b)
        self.assertNotEqual(
            person_a, person_b,
            "two people visible in the same frame were merged onto one person_id",
        )

    def test_lookalike_arriving_after_the_other_left_may_reuse_the_id(self):
        """The exclusion must be scoped to *live* tracks only — a person who
        left the frame stays matchable, which is the gallery's whole purpose.
        """
        clock = {"t": 0.0}
        gallery = PersonGallery(
            embed_fn=fake_embed,
            similarity_threshold=0.8,
            ttl_seconds=30.0,
            min_samples=3,
            now_fn=lambda: clock["t"],
        )

        box = (100, 100, 160, 260)
        frame = make_frame_with_patch((60, 60, 200), box)

        first = resolve_until_decided(gallery, ("cam1", 301), frame, box)
        clock["t"] = 5.0  # track 301 is long gone from the live window
        second = resolve_until_decided(gallery, ("cam1", 302), frame, box)

        self.assertEqual(first, second)


class TestCrossCameraReID(unittest.TestCase):
    """Phase 15: one shared gallery serving multiple cameras must key on
    (camera_name, track_id), not raw track_id, or two cameras that happen to
    both assign track_id=1 to different people would get wrongly merged."""

    def test_same_numeric_track_id_different_cameras_different_appearance_stays_separate(self):
        gallery = PersonGallery(embed_fn=fake_embed, similarity_threshold=0.8, ttl_seconds=30.0, min_samples=3)
        box = (100, 100, 160, 260)
        red_frame = make_frame_with_patch((0, 0, 220), box)
        blue_frame = make_frame_with_patch((220, 0, 0), box)

        # Both cameras' ByteTrack independently assign track_id=1 to a
        # DIFFERENT physical person (different appearance).
        person_on_cam0 = resolve_until_decided(gallery, ("cam0", 1), red_frame, box)
        person_on_cam1 = resolve_until_decided(gallery, ("cam1", 1), blue_frame, box)

        self.assertNotEqual(person_on_cam0, person_on_cam1)

    def test_same_person_recognized_across_two_cameras_gets_same_id(self):
        """The actual point of Phase 15: a person walking from one camera's
        view into another's keeps the same identity via appearance match."""
        clock = {"t": 0.0}
        gallery = PersonGallery(
            embed_fn=fake_embed, similarity_threshold=0.8, ttl_seconds=30.0, min_samples=3,
            now_fn=lambda: clock["t"],
        )
        box = (100, 100, 160, 260)
        red_frame = make_frame_with_patch((0, 0, 220), box)

        person_on_cam0 = resolve_until_decided(gallery, ("cam0", 7), red_frame, box)

        clock["t"] = 3.0  # a couple seconds later, now seen by a different camera
        person_on_cam1 = resolve_until_decided(gallery, ("cam1", 42), red_frame, box)

        self.assertEqual(person_on_cam0, person_on_cam1)


class TestPendingBufferIsBounded(unittest.TestCase):
    """Issue D: embeddings buffered for a track that vanishes before reaching
    min_samples used to stay in `_pending` for the life of the process. Every
    person who walks past for a frame or two leaves one behind, so on a
    24/7 border deployment the buffer only ever grows."""

    def _gallery(self, clock, **kwargs):
        options = dict(
            embed_fn=fake_embed,
            similarity_threshold=0.8,
            ttl_seconds=10.0,
            min_samples=3,
            now_fn=lambda: clock["t"],
        )
        options.update(kwargs)
        return PersonGallery(**options)

    def test_track_reaching_min_samples_still_resolves_and_clears_its_buffer(self):
        clock = {"t": 0.0}
        gallery = self._gallery(clock)
        box = (100, 100, 160, 260)
        frame = make_frame_with_patch((0, 0, 220), box)

        person_id = resolve_until_decided(gallery, 701, frame, box)

        self.assertIsNotNone(person_id)
        self.assertEqual(gallery._pending, {}, "resolved track left its samples buffered")

    def test_track_that_disappears_before_min_samples_is_eventually_cleaned_up(self):
        clock = {"t": 0.0}
        gallery = self._gallery(clock)
        box = (100, 100, 160, 260)
        frame = make_frame_with_patch((0, 0, 220), box)

        gallery.resolve(801, frame, box)  # one sample, then the person is gone
        self.assertIn(801, gallery._pending)

        # Another track appears well after the TTL, driving a purge.
        clock["t"] = 50.0
        gallery.resolve(802, frame, box)

        self.assertNotIn(801, gallery._pending, "abandoned buffer was never released")

    def test_cleanup_does_not_touch_a_track_still_collecting_samples(self):
        clock = {"t": 0.0}
        gallery = self._gallery(clock, min_samples=5)
        box = (100, 100, 160, 260)
        frame = make_frame_with_patch((0, 0, 220), box)

        gallery.resolve(901, frame, box)
        clock["t"] = 5.0  # inside the TTL - this track is still live
        gallery.resolve(901, frame, box)
        clock["t"] = 9.0
        gallery.resolve(901, frame, box)

        self.assertIn(901, gallery._pending)
        self.assertEqual(len(gallery._pending[901]["samples"]), 3)

        # It goes on to resolve normally once it has enough samples.
        clock["t"] = 10.0
        self.assertIsNone(gallery.resolve(901, frame, box))
        self.assertIsNotNone(gallery.resolve(901, frame, box))

    def test_many_short_lived_tracks_stay_memory_bounded(self):
        clock = {"t": 0.0}
        gallery = self._gallery(clock)
        box = (100, 100, 160, 260)
        frame = make_frame_with_patch((0, 0, 220), box)

        # 2000 people glimpsed for a single frame each, one per second.
        for track_id in range(2000):
            clock["t"] = float(track_id)
            gallery.resolve(track_id, frame, box)

        self.assertLessEqual(
            len(gallery._pending), 12, "pending buffer grew with every short-lived track"
        )

    def test_buffers_are_purged_even_when_no_track_ever_resolves(self):
        """Purging used to happen only on the paths that return a person_id,
        so a stream of never-resolving tracks reached cleanup never."""
        clock = {"t": 0.0}
        gallery = self._gallery(clock, min_samples=50)  # nothing will ever resolve
        box = (100, 100, 160, 260)
        frame = make_frame_with_patch((0, 0, 220), box)

        for track_id in range(500):
            clock["t"] = float(track_id)
            self.assertIsNone(gallery.resolve(track_id, frame, box))

        self.assertLessEqual(len(gallery._pending), 12)

    def test_tiny_boxes_alone_still_drive_cleanup(self):
        """The 'box too small' path returns before ever buffering a sample; it
        must still let earlier abandoned buffers expire."""
        clock = {"t": 0.0}
        gallery = self._gallery(clock)
        box = (100, 100, 160, 260)
        tiny_box = (100, 100, 110, 115)
        frame = make_frame_with_patch((0, 0, 220), box)

        gallery.resolve(1001, frame, box)
        self.assertIn(1001, gallery._pending)

        clock["t"] = 50.0
        gallery.resolve(1002, frame, tiny_box)

        self.assertNotIn(1001, gallery._pending)


if __name__ == "__main__":
    unittest.main()

import logging
import time
from typing import Callable

import numpy as np

log = logging.getLogger("ibvap.reid")


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


class PersonGallery:
    """Resolves ByteTrack's churning `track_id` to a stable `person_id`.

    ByteTrack only matches detections frame-to-frame by motion/position, so a
    person who leaves the frame (or is occluded) longer than its track buffer
    gets a brand new track_id on return. This gallery closes that gap using
    an appearance embedding (`embed_fn`, e.g. a ResNet-18 feature extractor):
    a close-enough match to a recently-disappeared person reuses their id
    instead of minting a new one.

    A new track_id's identity is decided from the *average* of its first
    `min_samples` embeddings (not a single frame) to cancel out noise from
    partial/edge-clipped boxes or momentary motion blur — `resolve()` returns
    None for those first few calls while samples are still being collected.
    Once resolved, the gallery's stored embedding keeps being refined via a
    slow moving average for as long as the track stays alive, so the
    reference representation improves rather than freezing at first sight.
    """

    def __init__(
        self,
        embed_fn: Callable[[np.ndarray, tuple], "np.ndarray | None"],
        similarity_threshold: float = 0.7,
        ttl_seconds: float = 30.0,
        min_samples: int = 3,
        update_alpha: float = 0.15,
        min_box_size: tuple = (40, 60),
        now_fn: Callable[[], float] = time.time,
    ):
        self.embed_fn = embed_fn
        self.similarity_threshold = similarity_threshold
        self.ttl_seconds = ttl_seconds
        self.min_samples = min_samples
        self.update_alpha = update_alpha
        self.min_box_width, self.min_box_height = min_box_size
        self._now = now_fn
        self._next_person_id = 1
        # person_id -> {"embedding": np.ndarray, "last_seen": float}
        self._gallery: dict[int, dict] = {}
        # track_id -> {"person_id": int, "last_seen": float}, once resolved
        self._track_to_person: dict[int, dict] = {}
        # track_id -> list[np.ndarray], while still buffering samples
        self._pending: dict[int, list[np.ndarray]] = {}

    def resolve(self, track_id: int, frame: np.ndarray, box: tuple) -> "int | None":
        now = self._now()

        resolved = self._track_to_person.get(track_id)
        if resolved is not None:
            resolved["last_seen"] = now
            person_id = resolved["person_id"]
            embedding = self._embed(frame, box)
            if embedding is not None:
                entry = self._gallery[person_id]
                entry["embedding"] = (
                    (1 - self.update_alpha) * entry["embedding"] + self.update_alpha * embedding
                )
                entry["last_seen"] = now
            self._purge_stale(now)
            return person_id

        embedding = self._embed(frame, box)
        if embedding is None:
            return None  # box too small/clipped to contribute a sample yet

        samples = self._pending.setdefault(track_id, [])
        samples.append(embedding)
        if len(samples) < self.min_samples:
            return None  # still buffering — decide once we have enough samples

        mean_embedding = np.mean(samples, axis=0)
        del self._pending[track_id]

        person_id = self._match_or_create(mean_embedding, now)
        self._gallery[person_id] = {"embedding": mean_embedding, "last_seen": now}
        self._track_to_person[track_id] = {"person_id": person_id, "last_seen": now}
        self._purge_stale(now)
        return person_id

    def _embed(self, frame: np.ndarray, box: tuple):
        x1, y1, x2, y2 = box
        if (x2 - x1) < self.min_box_width or (y2 - y1) < self.min_box_height:
            return None
        return self.embed_fn(frame, box)

    def _match_or_create(self, embedding: np.ndarray, now: float) -> int:
        best_person_id = None
        best_similarity = 0.0
        for person_id, entry in self._gallery.items():
            if now - entry["last_seen"] > self.ttl_seconds:
                continue
            similarity = cosine_similarity(embedding, entry["embedding"])
            if similarity > best_similarity:
                best_similarity = similarity
                best_person_id = person_id

        if best_person_id is not None and best_similarity >= self.similarity_threshold:
            log.info(
                "Re-ID match: reusing person #%d (similarity=%.2f)",
                best_person_id, best_similarity,
            )
            return best_person_id

        person_id = self._next_person_id
        self._next_person_id += 1
        log.info("Re-ID: assigning new person #%d", person_id)
        return person_id

    def _purge_stale(self, now: float) -> None:
        stale_persons = [
            pid for pid, e in self._gallery.items() if now - e["last_seen"] > self.ttl_seconds
        ]
        for pid in stale_persons:
            del self._gallery[pid]

        stale_tracks = [
            tid for tid, e in self._track_to_person.items() if now - e["last_seen"] > self.ttl_seconds
        ]
        for tid in stale_tracks:
            del self._track_to_person[tid]

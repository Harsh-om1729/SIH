import logging
import time
from typing import Callable, Hashable

import numpy as np

log = logging.getLogger("ibvap.reid")


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def l2_normalize(v: np.ndarray) -> np.ndarray:
    """Unit-length copy of `v` (unchanged if it is the zero vector).

    Cosine similarity ignores magnitude, but *averaging* does not: a mean over
    raw embeddings is dominated by whichever samples happened to have the
    largest norm (a brighter, larger, or closer crop), so the reference drifts
    toward those instead of representing the person. Normalizing before every
    mean and every moving-average update makes each sample count equally.
    """
    norm = float(np.linalg.norm(v))
    if norm == 0.0:
        return v
    return v / norm


class PersonGallery:
    """Resolves a track's churning identity to a stable `person_id`.

    ByteTrack only matches detections frame-to-frame by motion/position, so a
    person who leaves the frame (or is occluded) longer than its track buffer
    gets a brand new track_id on return. This gallery closes that gap using
    an appearance embedding (`embed_fn`, e.g. the OSNet Re-ID extractor):
    a close-enough match to a recently-disappeared person reuses their id
    instead of minting a new one.

    A single shared instance also gives cross-camera Re-ID (Phase 15): pass a
    `track_key` that's unique per camera (e.g. `(camera_name, track_id)`, not
    a raw track_id) when the same gallery serves multiple cameras — otherwise
    two different cameras' ByteTrack instances could coincidentally produce
    the same numeric track_id and wrongly merge unrelated people.

    A new track_key's identity is decided from the *average* of its first
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
        match_margin: float = 0.05,
        live_window_seconds: float = 1.0,
        min_box_size: tuple = (40, 60),
        now_fn: Callable[[], float] = time.time,
    ):
        self.embed_fn = embed_fn
        self.similarity_threshold = similarity_threshold
        self.ttl_seconds = ttl_seconds
        self.min_samples = min_samples
        self.update_alpha = update_alpha
        self.match_margin = match_margin
        self.live_window_seconds = live_window_seconds
        self.min_box_width, self.min_box_height = min_box_size
        self._now = now_fn
        self._next_person_id = 1
        # person_id -> {"embedding": np.ndarray, "last_seen": float}
        self._gallery: dict[int, dict] = {}
        # track_key -> {"person_id": int, "last_seen": float}, once resolved
        self._track_to_person: dict[Hashable, dict] = {}
        # track_key -> list[np.ndarray], while still buffering samples
        self._pending: dict[Hashable, list] = {}

    def resolve(self, track_key: Hashable, frame: np.ndarray, box: tuple) -> "int | None":
        now = self._now()

        resolved = self._track_to_person.get(track_key)
        if resolved is not None:
            person_id = resolved["person_id"]
            entry = self._gallery.get(person_id)
            if entry is None:
                # The gallery entry expired while this track was still alive —
                # possible because a track's last_seen refreshes every frame but
                # its gallery entry's only refreshes on a frame that produced an
                # embedding (a long run of too-small boxes produces none). Drop
                # the dangling binding and re-identify from scratch rather than
                # indexing into a purged entry.
                del self._track_to_person[track_key]
            else:
                resolved["last_seen"] = now
                embedding = self._embed(frame, box)
                if embedding is not None:
                    entry["embedding"] = l2_normalize(
                        (1 - self.update_alpha) * entry["embedding"]
                        + self.update_alpha * embedding
                    )
                    entry["last_seen"] = now
                self._purge_stale(now)
                return person_id

        embedding = self._embed(frame, box)
        if embedding is None:
            return None  # box too small/clipped to contribute a sample yet

        samples = self._pending.setdefault(track_key, [])
        samples.append(embedding)
        if len(samples) < self.min_samples:
            return None  # still buffering — decide once we have enough samples

        mean_embedding = l2_normalize(np.mean(samples, axis=0))
        del self._pending[track_key]

        person_id = self._match_or_create(mean_embedding, now)
        entry = self._gallery.get(person_id)
        if entry is None:
            self._gallery[person_id] = {"embedding": mean_embedding, "last_seen": now}
        else:
            # Blend into the existing reference instead of replacing it. An
            # overwrite would throw away every earlier observation of this
            # person, so one borderline match could redefine the identity as
            # whoever matched last and drag further people onto the same id.
            entry["embedding"] = l2_normalize(
                (1 - self.update_alpha) * entry["embedding"]
                + self.update_alpha * mean_embedding
            )
            entry["last_seen"] = now
        self._track_to_person[track_key] = {"person_id": person_id, "last_seen": now}
        self._purge_stale(now)
        return person_id

    def _embed(self, frame: np.ndarray, box: tuple):
        x1, y1, x2, y2 = box
        if (x2 - x1) < self.min_box_width or (y2 - y1) < self.min_box_height:
            return None
        embedding = self.embed_fn(frame, box)
        if embedding is None:
            return None
        return l2_normalize(embedding)

    def _match_or_create(self, embedding: np.ndarray, now: float) -> int:
        claimed = self._live_person_ids(now)

        scored = []
        for person_id, entry in self._gallery.items():
            if now - entry["last_seen"] > self.ttl_seconds:
                continue
            scored.append((cosine_similarity(embedding, entry["embedding"]), person_id))
        scored.sort(reverse=True)

        # A person can only be in one place at a time, so an identity that some
        # *other* track is holding right now is not a candidate. Without this,
        # two people standing in frame together both match the same gallery
        # entry and get handed the same person_id.
        available = [(sim, pid) for sim, pid in scored if pid not in claimed]

        if available:
            best_similarity, best_person_id = available[0]
            runner_up = available[1][0] if len(available) > 1 else 0.0
            if best_similarity >= self.similarity_threshold:
                # Require the winner to beat the next-best identity by a clear
                # margin. When two stored people score near-identically, the
                # embedding is not actually telling them apart, and picking the
                # higher one is a coin flip that merges two people.
                if best_similarity - runner_up >= self.match_margin:
                    log.info(
                        "Re-ID match: reusing person #%d (similarity=%.2f, runner-up=%.2f)",
                        best_person_id, best_similarity, runner_up,
                    )
                    return best_person_id
                log.info(
                    "Re-ID: ambiguous match for person #%d (similarity=%.2f vs runner-up "
                    "%.2f, margin<%.2f) — assigning a new id instead of guessing",
                    best_person_id, best_similarity, runner_up, self.match_margin,
                )

        person_id = self._next_person_id
        self._next_person_id += 1
        log.info("Re-ID: assigning new person #%d", person_id)
        return person_id

    def _live_person_ids(self, now: float) -> set:
        """person_ids currently held by a track seen within the live window.

        Scoped to the last `live_window_seconds` rather than the full TTL: a
        person who walked out of frame a moment ago must stay matchable (that
        reappearance is the whole point of the gallery), while someone visible
        in this very frame must not be.
        """
        return {
            e["person_id"]
            for e in self._track_to_person.values()
            if now - e["last_seen"] <= self.live_window_seconds
        }

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

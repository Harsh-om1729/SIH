import logging

import numpy as np
from insightface.app import FaceAnalysis

log = logging.getLogger("ibvap.face")


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


class FaceRecognizer:
    """Wraps InsightFace's buffalo_s pack (bundles its own face detector plus
    a 512-d ArcFace-style recognition embedding) to extract a face embedding
    from a person's bounding box crop. Should only be called on detections
    that already passed the false-alarm filter, per the roadmap's "keeps
    cost low" guidance — face embedding is one of the pricier steps.
    """

    # Faces sit in the top portion of a person's box. Handing the *whole*
    # (tall, narrow) person box to the detector forces it to shrink the
    # entire crop down to fit det_size, which shrinks the face far more
    # than necessary and is the main cause of inconsistent detection.
    # Cropping to just the head/shoulder region keeps the face much larger
    # relative to the detector's analysis window.
    HEAD_HEIGHT_FRACTION = 0.5

    def __init__(self, det_size: tuple = (416, 416), det_thresh: float = 0.4):
        log.info("Loading InsightFace buffalo_s for face recognition")
        self._app = FaceAnalysis(name="buffalo_s", providers=["CPUExecutionProvider"])
        self._app.prepare(ctx_id=0, det_size=det_size, det_thresh=det_thresh)

    def embed(self, frame, person_box: tuple):
        """Returns (face_box_in_frame_coords, embedding) for the largest
        detected face within person_box's head/shoulder region, or
        (None, None) if no face found."""
        x1, y1, x2, y2 = person_box
        x1, y1 = max(x1, 0), max(y1, 0)
        height = y2 - y1
        if height <= 0 or x2 <= x1:
            return None, None

        head_bottom = y1 + max(int(height * self.HEAD_HEIGHT_FRACTION), 1)
        crop = frame[y1:head_bottom, x1:x2]
        if crop.size == 0:
            return None, None

        faces = self._app.get(crop)
        if not faces:
            return None, None

        face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        fx1, fy1, fx2, fy2 = face.bbox.astype(int)
        face_box = (x1 + fx1, y1 + fy1, x1 + fx2, y1 + fy2)
        return face_box, face.normed_embedding

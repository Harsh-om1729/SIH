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

    def __init__(self, det_size: tuple = (320, 320)):
        log.info("Loading InsightFace buffalo_s for face recognition")
        self._app = FaceAnalysis(name="buffalo_s", providers=["CPUExecutionProvider"])
        self._app.prepare(ctx_id=0, det_size=det_size)

    def embed(self, frame, person_box: tuple):
        """Returns (face_box_in_frame_coords, embedding) for the largest
        detected face within person_box, or (None, None) if no face found."""
        x1, y1, x2, y2 = person_box
        x1, y1 = max(x1, 0), max(y1, 0)
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None, None

        faces = self._app.get(crop)
        if not faces:
            return None, None

        face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        fx1, fy1, fx2, fy2 = face.bbox.astype(int)
        face_box = (x1 + fx1, y1 + fy1, x1 + fx2, y1 + fy2)
        return face_box, face.normed_embedding

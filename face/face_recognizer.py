import glob
import logging
import os

import numpy as np
from insightface.app import FaceAnalysis

log = logging.getLogger("ibvap.face")

# The pack and cache root FaceRecognizer loads. Kept as module constants so
# the availability precheck below cannot drift from what is actually loaded.
INSIGHTFACE_PACK = "buffalo_s"
INSIGHTFACE_ROOT = "~/.insightface"


def buffalo_weights_available(
    pack: str = INSIGHTFACE_PACK, root: str = INSIGHTFACE_ROOT
) -> tuple[bool, str]:
    """Whether the InsightFace pack is already provisioned locally.

    `FaceAnalysis.__init__` calls `insightface.utils.ensure_available`, which
    downloads the pack zip from GitHub whenever its directory is absent. On an
    air-gapped deployment that download cannot succeed, and attempting it at
    startup is the exact behaviour being prevented - so the directory is
    checked directly rather than discovered through a failed request. No
    network call is made here.

    Provision offline by extracting the pack into the reported directory.
    """
    model_dir = os.path.join(os.path.expanduser(root), "models", pack)
    if not os.path.isdir(model_dir):
        return False, (
            f"InsightFace pack '{pack}' is not provisioned at {model_dir}; "
            "face recognition disabled (no download attempted)"
        )
    onnx_files = glob.glob(os.path.join(model_dir, "*.onnx"))
    if not onnx_files:
        return False, (
            f"InsightFace pack directory {model_dir} exists but contains no "
            ".onnx model files; face recognition disabled"
        )
    return True, f"{len(onnx_files)} model file(s) provisioned at {model_dir}"


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
        self._app = FaceAnalysis(
            name=INSIGHTFACE_PACK,
            root=INSIGHTFACE_ROOT,
            providers=["CPUExecutionProvider"],
        )
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

import logging
import os

import cv2
import numpy as np
import torch
from torchvision.models import ResNet18_Weights, resnet18

log = logging.getLogger("ibvap.reid")


def resnet18_weights_available() -> tuple[bool, str]:
    """Whether the ImageNet ResNet-18 weights are already in the torch cache.

    `resnet18(weights=ResNet18_Weights.DEFAULT)` fetches the checkpoint from
    download.pytorch.org when the cache is cold. That download is exactly what
    must not happen on an air-gapped host at startup, so the cache file is
    checked directly instead of being discovered by a failed request. No
    network call is made here.

    Provision offline by copying the .pth into the reported path.
    """
    url = ResNet18_Weights.DEFAULT.url
    cache_path = os.path.join(torch.hub.get_dir(), "checkpoints", os.path.basename(url))
    if os.path.exists(cache_path):
        return True, f"ResNet-18 weights cached at {cache_path}"
    return False, (
        f"ResNet-18 weights not cached at {cache_path}; Re-ID disabled "
        "(no download attempted)"
    )

_IMAGENET_MEAN = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
_IMAGENET_STD = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
_INPUT_SIZE = 128


class ResNetEmbedder:
    """Deep appearance embedding (shape/texture/pattern, not just color) for
    Re-ID, using an ImageNet-pretrained ResNet-18 with its classification head
    removed. This is the "ResNet-18 embedding" option named in the roadmap's
    Phase 15 notes — used here in place of a plain color histogram, which
    fails to distinguish different people wearing similarly-colored clothing
    (low-saturation clothing gives near-meaningless hue, so histograms of two
    people in white/grey/beige collapse into false matches).
    """

    def __init__(self):
        log.info("Loading ResNet-18 for Re-ID embeddings")
        self._model = resnet18(weights=ResNet18_Weights.DEFAULT)
        self._model.fc = torch.nn.Identity()  # drop the 1000-class head, keep 512-d features
        self._model.eval()

    def embed(self, frame: np.ndarray, box: tuple) -> np.ndarray | None:
        x1, y1, x2, y2 = box
        width, height = x2 - x1, y2 - y1
        if width < 40 or height < 60:
            return None

        x1, y1 = max(x1, 0), max(y1, 0)
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None

        resized = cv2.resize(crop, (_INPUT_SIZE, _INPUT_SIZE))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        tensor = torch.from_numpy(rgb).permute(2, 0, 1).float().unsqueeze(0) / 255.0
        tensor = (tensor - _IMAGENET_MEAN) / _IMAGENET_STD

        with torch.no_grad():
            features = self._model(tensor)

        return features.squeeze(0).numpy().astype(np.float32)

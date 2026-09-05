import logging
import os

from dotenv import load_dotenv

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Comma-separated name=source pairs, e.g. "cam0=0,cam1=rtsp://user:pass@host/stream"
def _parse_camera_sources(raw: str) -> dict[str, int | str]:
    sources: dict[str, int | str] = {}
    for pair in raw.split(","):
        name, _, value = pair.partition("=")
        name = name.strip()
        value = value.strip()
        if not name:
            continue
        sources[name] = int(value) if value.isdigit() else value
    return sources


CAMERA_SOURCES: dict[str, int | str] = _parse_camera_sources(
    os.getenv("CAMERA_SOURCES", "cam0=0")
)

# 0-255 scale; frames measured below this trigger a CLAHE + gamma low-light boost
BRIGHTNESS_THRESHOLD = float(os.getenv("BRIGHTNESS_THRESHOLD", "90"))

# Mean grayscale frame-diff above this counts as "activity detected"
MOTION_THRESHOLD = float(os.getenv("MOTION_THRESHOLD", "2.0"))

# When idle, only run the full pipeline every Nth frame (low-FPS keep-alive)
LOW_FPS_INTERVAL = int(os.getenv("LOW_FPS_INTERVAL", "10"))

# Minimum YOLO confidence to keep a detection
DETECTION_CONFIDENCE = float(os.getenv("DETECTION_CONFIDENCE", "0.4"))

# Path to the model file the detector loads (.pt, .onnx, or an int8 .onnx)
DETECTION_MODEL_PATH = os.getenv("DETECTION_MODEL_PATH", "models/yolov8n.onnx")

# Requested camera capture resolution. Cameras often default to a much higher
# resolution (e.g. 1080p) which inflates every downstream stage for no benefit.
CAMERA_WIDTH = int(os.getenv("CAMERA_WIDTH", "640"))
CAMERA_HEIGHT = int(os.getenv("CAMERA_HEIGHT", "480"))

# Re-ID: cosine similarity (0-1) above which a reappearing track is matched
# back to an existing person instead of being treated as a new one
REID_SIMILARITY_THRESHOLD = float(os.getenv("REID_SIMILARITY_THRESHOLD", "0.7"))

# Re-ID: how long (seconds) a disappeared person stays eligible for matching
REID_TTL_SECONDS = float(os.getenv("REID_TTL_SECONDS", "30"))


def configure_logging() -> None:
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

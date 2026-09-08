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

# When idle, run the full pipeline at (at least) this many frames per second —
# a keep-alive floor, not a cap: as soon as the activity gate sees motion, every
# frame is processed again. This was a frame-count divisor ("every Nth frame"),
# which made the idle rate depend on the camera: the same divisor of 10 gave
# 3 fps on a 30 fps webcam and 1.5 fps on a 15 fps one. A rate in fps is what
# an operator actually wants to specify, and it holds across mismatched cameras.
IDLE_MIN_FPS = float(os.getenv("IDLE_MIN_FPS", "20"))

# Minimum YOLO confidence to keep a detection
DETECTION_CONFIDENCE = float(os.getenv("DETECTION_CONFIDENCE", "0.5"))

# Path to the model file the detector loads (.pt, .onnx, or an int8 .onnx)
DETECTION_MODEL_PATH = os.getenv("DETECTION_MODEL_PATH", "models/yolov8s.onnx")

# Requested camera capture resolution. Cameras often default to a much higher
# resolution (e.g. 1080p) which inflates every downstream stage for no benefit.
CAMERA_WIDTH = int(os.getenv("CAMERA_WIDTH", "640"))
CAMERA_HEIGHT = int(os.getenv("CAMERA_HEIGHT", "480"))

# Re-ID: cosine similarity (0-1) above which a reappearing track is matched
# back to an existing person instead of being treated as a new one
# Measured on real pedestrian crops with the OSNet embedder: unrelated people
# score at most ~0.50, the same person under box jitter at least ~0.87. 0.70
# sits in the middle of that gap. (It was also 0.70 under the old ImageNet
# ResNet-18, but there unrelated people reached 0.795 — above the gate — which
# is what merged strangers onto one person_id.)
REID_SIMILARITY_THRESHOLD = float(os.getenv("REID_SIMILARITY_THRESHOLD", "0.70"))

# Re-ID: how far the best-matching person must beat the second-best before the
# match is trusted. Near-tied candidates mean the embedding isn't actually
# telling those people apart, so the gallery mints a new id rather than guess.
REID_MATCH_MARGIN = float(os.getenv("REID_MATCH_MARGIN", "0.05"))

# Person Re-ID appearance model (OSNet x0.25 / MSMT17). Bundled in models/ and
# never fetched at runtime, so air-gapped operation still works.
REID_MODEL_PATH = os.getenv("REID_MODEL_PATH", "models/osnet_x0_25_msmt17.onnx")

# Re-ID: how long (seconds) a disappeared person stays eligible for matching
REID_TTL_SECONDS = float(os.getenv("REID_TTL_SECONDS", "30"))

# Green zones are re-tiered to "yellow" during this hour window (wraps midnight)
CURFEW_START_HOUR = int(os.getenv("CURFEW_START_HOUR", "23"))
CURFEW_END_HOUR = int(os.getenv("CURFEW_END_HOUR", "5"))

# Seconds between repeat alerts for the same track at the same tier
ALERT_COOLDOWN_SECONDS = float(os.getenv("ALERT_COOLDOWN_SECONDS", "8"))

# Cosine similarity (0-1) above which a face is treated as a watchlist match
WATCHLIST_SIMILARITY_THRESHOLD = float(os.getenv("WATCHLIST_SIMILARITY_THRESHOLD", "0.5"))

# Outbound webhook URL for alert events (empty = disabled)
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

# Syslog target for alert events (UDP; fire-and-forget, safe if unreachable)
SYSLOG_HOST = os.getenv("SYSLOG_HOST", "localhost")
SYSLOG_PORT = int(os.getenv("SYSLOG_PORT", "514"))

# Re-run Re-ID embedding + face/watchlist recognition for an already-resolved
# track only every Nth frame, not every frame. Measured cost: ~7.6ms (Re-ID)
# + ~6.4ms (face) per person per frame — real, avoidable weight once an
# identity is already known, since appearance barely changes frame-to-frame.
# A brand-new (not-yet-resolved) track is never throttled by this — it still
# gets checked every frame, since PersonGallery needs consecutive samples to
# decide an identity in the first place.
REID_FACE_CHECK_INTERVAL = int(os.getenv("REID_FACE_CHECK_INTERVAL", "5"))


def configure_logging() -> None:
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

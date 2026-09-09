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

# Green zones are re-tiered to "yellow" during this hour window (wraps midnight)
CURFEW_START_HOUR = int(os.getenv("CURFEW_START_HOUR", "23"))
CURFEW_END_HOUR = int(os.getenv("CURFEW_END_HOUR", "5"))

# Seconds between repeat alerts for the same track at the same tier
ALERT_COOLDOWN_SECONDS = float(os.getenv("ALERT_COOLDOWN_SECONDS", "8"))
# Bounded queue for off-thread alert side effects (webhook + evidence).
ALERT_DISPATCH_QUEUE_SIZE = int(os.getenv("ALERT_DISPATCH_QUEUE_SIZE", "64"))

# Phase 1 runtime instrumentation (metrics/collector.py). Bounded and
# thread-free; ~3us per stage timing. Off => NullCollector, zero overhead.
METRICS_ENABLED = os.getenv("METRICS_ENABLED", "1").lower() not in ("0", "false", "no")
METRICS_REPORT_INTERVAL_S = float(os.getenv("METRICS_REPORT_INTERVAL_S", "30"))

# Cosine similarity (0-1) above which a face is treated as a watchlist match
WATCHLIST_SIMILARITY_THRESHOLD = float(os.getenv("WATCHLIST_SIMILARITY_THRESHOLD", "0.5"))

# Outbound webhook URL for alert events (empty = disabled)
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")

# Syslog target for alert events (UDP; fire-and-forget, safe if unreachable)
SYSLOG_HOST = os.getenv("SYSLOG_HOST", "localhost")
SYSLOG_PORT = int(os.getenv("SYSLOG_PORT", "514"))

# Bearer token guarding the integration REST API (integration/api.py).
# No default: unset means the API refuses every request rather than serving
# the incident feed unauthenticated. Never commit a real value.
API_TOKEN = os.getenv("IBVAP_API_TOKEN", "")

# Fernet key protecting watchlist face embeddings at rest (face/watchlist.py).
# Same mechanism as the evidence store; kept in its own file so biometric data
# and evidence data do not share one key.
WATCHLIST_KEY_PATH = os.getenv("WATCHLIST_KEY_PATH", "database/watchlist.key")


def configure_logging() -> None:
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

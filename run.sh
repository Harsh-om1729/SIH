#!/usr/bin/env bash
# Launch IBVAP from any working directory.
#   ./run.sh          # live OpenCV app
#   ./run.sh dash     # Streamlit incident dashboard
#   ./run.sh app 0 rtsp://...   # extra args pass through to app.py
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -d "$SCRIPT_DIR/ibvap" ]]; then
  cd "$SCRIPT_DIR/ibvap"
else
  cd "$SCRIPT_DIR"
fi
source venv/bin/activate

case "${1:-app}" in
  dash|dashboard) exec streamlit run dashboard/streamlit_app.py ;;
  app)            shift || true; exec python app.py "$@" ;;
  *)              exec python app.py "$@" ;;
esac

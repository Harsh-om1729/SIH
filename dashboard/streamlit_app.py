"""Phase 13 — Streamlit monitoring dashboard (prototype stage; the roadmap
positions this as a quick-to-build step before a hardened React + FastAPI
version, without changing the underlying pipeline).

Run from ibvap/: streamlit run dashboard/streamlit_app.py

Reuses the exact same detection/tracking/zone/scoring/alerting pipeline as
app.py, rendered into a browser dashboard instead of an OpenCV window. Zone
drawing stays in app.py's interactive OpenCV drawer (Phase 8) — this
dashboard loads the same config/zones_<camera>.json files read-only.

Video and the incidents panel share ONE st.fragment with a single
run_every. Two fragments with different run_every values were tried first
and measured (via a temporary diagnostic) to both collapse onto a shared
~1000ms tick regardless of their configured intervals — a real Streamlit
quirk, not a bug in our own code, which was timed at 1-2ms per tick and was
never the bottleneck. A follow-up attempt to keep the incidents panel on
its own slower cadence *within* the single fragment (manually clearing a
placeholder created outside it and redrawing a variable number of widgets
into it) crashed the browser with a "Bad 'setIn' index" error — fragments
already replace their own contents automatically on each rerun, and fighting
that with a manual placeholder/.empty() trick desyncs the frontend's
element tracking. Both video and the incidents panel now just render
directly, every tick, with no placeholder tricks — the same way the video
placeholder above always worked (a plain per-tick update, nothing manual).
"""

import atexit
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import streamlit as st

from activity_gate.gate import ActivityGate
from alerts.alert_manager import AlertManager
from alerts.dispatch import AlertDispatcher
from camera.stream_manager import StreamManager
from config.settings import (
    ALERT_COOLDOWN_SECONDS,
    ALERT_DISPATCH_QUEUE_SIZE,
    BRIGHTNESS_THRESHOLD,
    CAMERA_HEIGHT,
    CAMERA_SOURCES,
    CAMERA_WIDTH,
    CURFEW_END_HOUR,
    CURFEW_START_HOUR,
    DETECTION_CONFIDENCE,
    DETECTION_MODEL_PATH,
    IDLE_MIN_FPS,
    MOTION_THRESHOLD,
)
from database.incident_store import RESOLUTION_REASONS, IncidentStore
from detection.draw import draw_detections
from filtering.false_alarm import FalseAlarmFilter
from intelligence.threat_rules import ThreatRulesDB
from intelligence.threat_score import ThreatScorer
from preprocessing.enhance import Preprocessor
from tracking.tracker import Tracker
from zones.zone_engine import ZoneEngine

TIER_COLORS_BGR = {"green": (0, 200, 0), "yellow": (0, 220, 220), "red": (0, 0, 255)}
STATUS_BADGES = {"open": "🔴 OPEN", "acknowledged": "🟡 ACKNOWLEDGED", "resolved": "🟢 RESOLVED"}

st.set_page_config(page_title="IBVAP Dashboard", layout="wide")
st.title("IBVAP — Operator Dashboard")
st.caption(
    "For live, moment-to-moment monitoring use the `python app.py` OpenCV window — "
    "it draws natively and is noticeably smoother. This dashboard is the incident-review "
    "and operator workflow surface (Acknowledge → Resolve); its video feed is best-effort, "
    "not a real-time stream. Draw zones in the OpenCV window (Phase 8) — this dashboard "
    "loads them read-only."
)


@st.cache_resource
def build_pipeline():
    manager = StreamManager(CAMERA_SOURCES, width=CAMERA_WIDTH, height=CAMERA_HEIGHT)
    manager.start_all()
    incident_store = IncidentStore()
    # Same guarantee as app.py: evidence persistence must not run on this
    # dashboard's frame loop. Built here (inside the cached resource) so one
    # dispatcher is shared by the single cached pipeline, and stopped at
    # interpreter exit since this Streamlit script has no shutdown hook.
    alert_dispatcher = AlertDispatcher(maxsize=ALERT_DISPATCH_QUEUE_SIZE)
    atexit.register(alert_dispatcher.stop)
    return {
        "manager": manager,
        "preprocessors": {
            n: Preprocessor(n, brightness_threshold=BRIGHTNESS_THRESHOLD) for n in CAMERA_SOURCES
        },
        "gates": {n: ActivityGate(motion_threshold=MOTION_THRESHOLD) for n in CAMERA_SOURCES},
        "trackers": {
            n: Tracker(model_path=DETECTION_MODEL_PATH, confidence=DETECTION_CONFIDENCE)
            for n in CAMERA_SOURCES
        },
        "false_alarm_filters": {n: FalseAlarmFilter() for n in CAMERA_SOURCES},
        "zone_engines": {
            n: ZoneEngine(
                config_path=f"config/zones_{n}.json",
                curfew_start_hour=CURFEW_START_HOUR,
                curfew_end_hour=CURFEW_END_HOUR,
            )
            for n in CAMERA_SOURCES
        },
        "threat_scorer": ThreatScorer(ThreatRulesDB()),
        "incident_store": incident_store,
        "alert_dispatcher": alert_dispatcher,
        "alert_manager": AlertManager(
            cooldown_seconds=ALERT_COOLDOWN_SECONDS,
            incident_store=incident_store,
            dispatcher=alert_dispatcher,
        ),
        "frame_counters": {n: 0 for n in CAMERA_SOURCES},
        "last_processed": {n: None for n in CAMERA_SOURCES},
        "frame_buffers": {n: [] for n in CAMERA_SOURCES},
    }


pipeline = build_pipeline()

with st.sidebar:
    st.header("Operator")
    st.text_input(
        "Operator name",
        value=st.session_state.get("operator_name", "Duty Operator"),
        key="operator_name",
    )
    st.markdown("---")
    st.markdown("### System Info")
    st.markdown(f"**Cameras:** {len(CAMERA_SOURCES)}")
    st.markdown(f"**Detection Model:** `{DETECTION_MODEL_PATH}`")
    st.markdown(f"**Confidence Threshold:** `{DETECTION_CONFIDENCE}`")

col_video, col_incidents = st.columns([2, 1])

with col_video:
    st.subheader("Live Feed")

    @st.fragment(run_every=0.2)
    def render_video_feed() -> None:
        frames = pipeline["manager"].read_all()
        for name, frame in frames.items():
            if frame is None:
                continue

            active, _motion_score = pipeline["gates"][name].is_active(frame)
            pipeline["frame_counters"][name] += 1

            # Same idle floor as app.py: a still scene still refreshes at
            # IDLE_MIN_FPS instead of stalling. This fragment reruns every
            # 0.2s, so that interval is the practical ceiling here.
            now = time.perf_counter()
            last_processed = pipeline["last_processed"][name]
            due = last_processed is None or (now - last_processed) >= 1.0 / IDLE_MIN_FPS
            if not (active or due):
                continue
            pipeline["last_processed"][name] = now

            processed = pipeline["preprocessors"][name].process(frame)
            detections = pipeline["trackers"][name].track(processed)
            detections = pipeline["false_alarm_filters"][name].filter(detections)

            for det in detections:
                x1, y1, x2, y2 = det.box
                ground_point = ((x1 + x2) // 2, y2)
                zone_result = pipeline["zone_engines"][name].classify(ground_point, det.direction)
                det.zone_tier = zone_result["tier"]
                det.zone_direction = zone_result["direction"]

            draw_detections(processed, detections)

            scores = []
            for det in detections:
                score = pipeline["threat_scorer"].score(
                    zone_tier=det.zone_tier,
                    hour=datetime.now().hour,
                    speed_px_per_frame=det.speed,
                    category=det.category(),
                )
                scores.append(score)
                x1, y1, x2, y2 = det.box
                label = f"T={score.total:.0f} ({score.tier.upper()})"
                cv2.putText(
                    processed, label, (x1, y2 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    TIER_COLORS_BGR[score.tier], 2,
                )

            buffer = pipeline["frame_buffers"][name]
            buffer.append(processed.copy())
            if len(buffer) > 3:
                buffer.pop(0)
            for det, score in zip(detections, scores):
                pipeline["alert_manager"].handle(det, score, buffer)

            rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
            st.image(
                rgb, channels="RGB", caption=name, output_format="JPEG"
            )

    render_video_feed()

with col_incidents:
    st.subheader("Recent Incidents")

    @st.fragment(run_every=2.0)
    def render_incidents_panel() -> None:
        operator_name = st.session_state.get("operator_name", "Duty Operator")
        incidents = pipeline["incident_store"].list_incidents(limit=15)
        if not incidents:
            st.info("No incidents recorded yet.")
            return

        for inc in incidents:
            status = inc.get("status") or "open"
            badge = STATUS_BADGES.get(status, status)
            ts = datetime.fromtimestamp(inc["timestamp"]).strftime("%H:%M:%S")

            with st.container(border=True):
                st.markdown(
                    f"**#{inc['id']}** · {ts} · {inc['category']} · zone={inc['zone_tier']} · "
                    f"score={inc['score']:.0f} ({inc['tier']}) · {badge}"
                )

                if inc.get("snapshot_path") and os.path.exists(inc["snapshot_path"]):
                    with st.expander("📷 View Evidence Snapshot"):
                        try:
                            img_bytes = pipeline["incident_store"].decrypt_image_bytes(inc["snapshot_path"])
                            st.image(img_bytes, caption=f"Snapshot #{inc['id']}", use_container_width=True)
                            if inc.get("crop_path") and os.path.exists(inc["crop_path"]):
                                crop_bytes = pipeline["incident_store"].decrypt_image_bytes(inc["crop_path"])
                                st.image(crop_bytes, caption=f"Cropped Target #{inc['id']}", width=150)
                        except Exception as e:
                            st.caption(f"Failed to decrypt evidence: {e}")

                if status == "resolved":
                    st.caption(
                        f"Resolved by {inc['resolved_by']} — {inc['resolution_reason']}"
                    )
                    continue

                ack_col, reason_col, resolve_col = st.columns([1, 2, 1])
                if status == "open":
                    if ack_col.button("Acknowledge", key=f"ack_{inc['id']}"):
                        pipeline["incident_store"].acknowledge(inc["id"], operator_name)
                        st.rerun(scope="fragment")
                else:
                    ack_col.caption(f"Ack: {inc['acknowledged_by']}")

                reason = reason_col.selectbox(
                    "Resolution", RESOLUTION_REASONS, key=f"reason_{inc['id']}",
                    label_visibility="collapsed",
                )
                if resolve_col.button("Resolve", key=f"resolve_{inc['id']}"):
                    pipeline["incident_store"].resolve(inc["id"], operator_name, reason)
                    st.rerun(scope="fragment")

    render_incidents_panel()

"""Phase 13 — Streamlit monitoring dashboard (prototype stage; the roadmap
positions this as a quick-to-build step before a hardened React + FastAPI
version, without changing the underlying pipeline).

Run from ibvap/: streamlit run dashboard/streamlit_app.py

Reuses the exact same detection/tracking/zone/scoring/alerting pipeline as
app.py, rendered into a browser dashboard instead of an OpenCV window. Zone
drawing stays in app.py's interactive OpenCV drawer (Phase 8) — this
dashboard loads the same config/zones_<camera>.json files read-only.
"""

import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import pandas as pd
import streamlit as st

from activity_gate.gate import ActivityGate
from alerts.alert_manager import AlertManager
from camera.stream_manager import StreamManager
from config.settings import (
    ALERT_COOLDOWN_SECONDS,
    BRIGHTNESS_THRESHOLD,
    CAMERA_HEIGHT,
    CAMERA_SOURCES,
    CAMERA_WIDTH,
    CURFEW_END_HOUR,
    CURFEW_START_HOUR,
    DETECTION_CONFIDENCE,
    DETECTION_MODEL_PATH,
    LOW_FPS_INTERVAL,
    MOTION_THRESHOLD,
)
from database.incident_store import IncidentStore
from detection.draw import draw_detections
from filtering.false_alarm import FalseAlarmFilter
from intelligence.threat_rules import ThreatRulesDB
from intelligence.threat_score import ThreatScorer
from preprocessing.enhance import Preprocessor
from tracking.tracker import Tracker
from zones.zone_engine import ZoneEngine

TIER_COLORS_BGR = {"green": (0, 200, 0), "yellow": (0, 220, 220), "red": (0, 0, 255)}

st.set_page_config(page_title="IBVAP Dashboard", layout="wide")
st.title("IBVAP — Live Monitoring Dashboard")
st.caption(
    "Draw zones in the main `python app.py` OpenCV window first (Phase 8) — "
    "this dashboard loads them read-only."
)


@st.cache_resource
def build_pipeline():
    manager = StreamManager(CAMERA_SOURCES, width=CAMERA_WIDTH, height=CAMERA_HEIGHT)
    manager.start_all()
    incident_store = IncidentStore()
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
        "alert_manager": AlertManager(
            cooldown_seconds=ALERT_COOLDOWN_SECONDS, incident_store=incident_store
        ),
        "frame_counters": {n: 0 for n in CAMERA_SOURCES},
        "frame_buffers": {n: [] for n in CAMERA_SOURCES},
    }


pipeline = build_pipeline()

col_video, col_incidents = st.columns([2, 1])
video_placeholders = {name: col_video.empty() for name in CAMERA_SOURCES}
col_incidents.subheader("Recent Incidents")
incidents_placeholder = col_incidents.empty()

while True:
    frames = pipeline["manager"].read_all()
    for name, frame in frames.items():
        if frame is None:
            continue

        active, _motion_score = pipeline["gates"][name].is_active(frame)
        pipeline["frame_counters"][name] += 1
        should_process = active or (pipeline["frame_counters"][name] % LOW_FPS_INTERVAL == 0)
        if not should_process:
            continue

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
        video_placeholders[name].image(rgb, channels="RGB", caption=name)

    incidents = pipeline["incident_store"].list_incidents(limit=15)
    if incidents:
        df = pd.DataFrame(incidents)[["id", "timestamp", "category", "zone_tier", "tier", "score"]]
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s").dt.strftime("%H:%M:%S")
        incidents_placeholder.dataframe(df, hide_index=True, use_container_width=True)
    else:
        incidents_placeholder.info("No incidents recorded yet.")

    time.sleep(0.03)

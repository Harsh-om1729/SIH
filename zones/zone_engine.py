import json
import logging
import os
from datetime import datetime

import cv2
import numpy as np

log = logging.getLogger("ibvap.zones")

ZONE_PRIORITY = {"red": 3, "yellow": 2, "green": 1}


class Zone:
    def __init__(self, zone_type: str, polygon: list):
        self.zone_type = zone_type  # "red" | "yellow" | "green"
        self.polygon = polygon  # list of (x, y) pixel points

    def contains(self, point: tuple) -> bool:
        contour = np.array(self.polygon, dtype=np.int32)
        return cv2.pointPolygonTest(contour, point, False) >= 0

    def centroid(self) -> tuple:
        xs = [p[0] for p in self.polygon]
        ys = [p[1] for p in self.polygon]
        return (sum(xs) / len(xs), sum(ys) / len(ys))

    def to_dict(self) -> dict:
        return {"zone_type": self.zone_type, "polygon": self.polygon}

    @classmethod
    def from_dict(cls, data: dict) -> "Zone":
        return cls(data["zone_type"], [tuple(p) for p in data["polygon"]])


class ZoneEngine:
    """Classifies a detection's ground position into a Red/Yellow/Green zone
    tier. Zones are simple polygons (drawn interactively — see
    zones/drawer.py) persisted to a small JSON file per camera, so this is
    the "virtual fence" the roadmap describes, minus the dashboard UI (that's
    Phase 13; this engine's logic doesn't change when that UI arrives).

    - Red: highest priority when zones overlap (border line).
    - Yellow: direction-aware — a track's movement direction is compared
      against the vector from this zone's centroid toward the nearest Red
      zone's centroid, to classify the movement as inward (toward the
      border) or outward.
    - Green: re-tiered to "yellow" during the configured curfew window, since
      an otherwise-safe interior area is more suspicious overnight.
    """

    def __init__(
        self,
        config_path: str,
        curfew_start_hour: int = 23,
        curfew_end_hour: int = 5,
        now_fn=datetime.now,
    ):
        self.config_path = config_path
        self.curfew_start_hour = curfew_start_hour
        self.curfew_end_hour = curfew_end_hour
        self._now_fn = now_fn
        self.zones: list = []
        self.load()

    def add_zone(self, zone: Zone) -> None:
        self.zones.append(zone)
        self.save()

    def clear(self) -> None:
        self.zones = []
        self.save()

    def load(self) -> None:
        if not os.path.exists(self.config_path):
            return
        with open(self.config_path) as f:
            data = json.load(f)
        self.zones = [Zone.from_dict(z) for z in data]
        log.info("Loaded %d zone(s) from %s", len(self.zones), self.config_path)

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump([z.to_dict() for z in self.zones], f, indent=2)

    def _is_curfew(self) -> bool:
        hour = self._now_fn().hour
        if self.curfew_start_hour > self.curfew_end_hour:
            return hour >= self.curfew_start_hour or hour < self.curfew_end_hour
        return self.curfew_start_hour <= hour < self.curfew_end_hour

    def classify(self, ground_point: tuple, direction: "tuple | None" = None) -> dict:
        """Returns {"tier": "red"|"yellow"|"green"|"none", "direction": "inward"|"outward"|None}"""
        matches = [z for z in self.zones if z.contains(ground_point)]
        if not matches:
            return {"tier": "none", "direction": None}

        best = max(matches, key=lambda z: ZONE_PRIORITY[z.zone_type])
        tier = best.zone_type
        direction_label = None

        if tier == "yellow" and direction is not None:
            red_zones = [z for z in self.zones if z.zone_type == "red"]
            if red_zones:
                zx, zy = best.centroid()
                rx, ry = min(
                    (z.centroid() for z in red_zones),
                    key=lambda c: (c[0] - zx) ** 2 + (c[1] - zy) ** 2,
                )
                inward_vec = (rx - zx, ry - zy)
                dot = direction[0] * inward_vec[0] + direction[1] * inward_vec[1]
                direction_label = "inward" if dot > 0 else "outward"

        if tier == "green" and self._is_curfew():
            tier = "yellow"  # curfew re-tiering

        return {"tier": tier, "direction": direction_label}

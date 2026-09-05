import cv2

from detection.detector import Detection

CATEGORY_COLORS = {
    "person": (0, 220, 0),
    "vehicle": (255, 140, 0),
    "animal": (0, 200, 255),
}
ZONE_TIER_COLORS = {"red": (0, 0, 255), "yellow": (0, 255, 255), "green": (0, 255, 0)}


def draw_detections(frame, detections: list[Detection]) -> None:
    for det in detections:
        x1, y1, x2, y2 = det.box
        color = CATEGORY_COLORS[det.category()]
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        label = f"{det.class_name} {det.confidence:.2f}"
        if det.person_id is not None:
            label = f"#{det.person_id} {label}"
        elif det.category() == "person" and det.track_id is not None:
            label = f"T{det.track_id} {label}"  # Re-ID identity still resolving
        elif det.track_id is not None:
            label = f"#{det.track_id} {label}"  # vehicle/animal: plain track id, no Re-ID
        cv2.putText(
            frame, label, (x1, max(y1 - 8, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2
        )

        if det.direction is not None:
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            dx, dy = det.direction
            cv2.arrowedLine(
                frame, (cx, cy), (int(cx + dx), int(cy + dy)), color, 2, tipLength=0.4
            )

        if det.watchlist_match is not None:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 4)  # thick red lock
            watchlist_label = f"WATCHLIST: {det.watchlist_match} ({det.watchlist_similarity:.2f})"
            cv2.putText(
                frame, watchlist_label, (x1, y1 - 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2
            )

        if det.zone_tier and det.zone_tier != "none":
            ground_point = ((x1 + x2) // 2, y2)
            zone_color = ZONE_TIER_COLORS[det.zone_tier]
            cv2.circle(frame, ground_point, 6, zone_color, -1)
            zone_label = det.zone_tier.upper()
            if det.zone_direction:
                zone_label += f" ({det.zone_direction})"
            cv2.putText(
                frame, zone_label, (ground_point[0] + 10, ground_point[1]),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, zone_color, 2,
            )

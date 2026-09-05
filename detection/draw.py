import cv2

from detection.detector import Detection

CATEGORY_COLORS = {
    "person": (0, 220, 0),
    "vehicle": (255, 140, 0),
    "animal": (0, 200, 255),
}


def draw_detections(frame, detections: list[Detection]) -> None:
    for det in detections:
        x1, y1, x2, y2 = det.box
        color = CATEGORY_COLORS[det.category()]
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        label = f"{det.class_name} {det.confidence:.2f}"
        if det.person_id is not None:
            label = f"#{det.person_id} {label}"
        elif det.track_id is not None:
            label = f"T{det.track_id} {label}"  # identity still resolving
        cv2.putText(
            frame, label, (x1, max(y1 - 8, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2
        )

        if det.direction is not None:
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            dx, dy = det.direction
            cv2.arrowedLine(
                frame, (cx, cy), (int(cx + dx), int(cy + dy)), color, 2, tipLength=0.4
            )

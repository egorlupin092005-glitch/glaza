from pathlib import Path
import time
import cv2
import mediapipe as mp

MODEL = Path(__file__).resolve().parents[1] / 'models' / 'hand_landmarker.task'
CONNECTIONS = ((0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),
               (5,9),(9,10),(10,11),(11,12),(9,13),(13,14),(14,15),
               (15,16),(13,17),(0,17),(17,18),(18,19),(19,20))


class HandDetector:
    def __init__(self, model=MODEL):
        if not model.is_file():
            raise RuntimeError('Нет модели распознавания. Запустите Установить.cmd.')
        self.last_timestamp = -1
        options = mp.tasks.vision.HandLandmarkerOptions(
            # Buffer also supports Cyrillic paths on Windows native libraries.
            base_options=mp.tasks.BaseOptions(model_asset_buffer=model.read_bytes()),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=1, min_hand_detection_confidence=0.6,
            min_hand_presence_confidence=0.6, min_tracking_confidence=0.6,
        )
        self.detector = mp.tasks.vision.HandLandmarker.create_from_options(options)

    def detect(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        stamp = max(self.last_timestamp + 1, time.monotonic_ns() // 1_000_000)
        self.last_timestamp = stamp
        result = self.detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), stamp)
        if not result.hand_landmarks:
            return None
        landmarks = result.hand_landmarks[0]
        # Wrist and four knuckles; fingers opening/closing barely shifts this center.
        point = tuple(sum(getattr(landmarks[i], axis) for i in (0,5,9,13,17))/5 for axis in ('x','y'))
        h, w = frame.shape[:2]
        points = [(int(p.x*w), int(p.y*h)) for p in landmarks]
        for a, b in CONNECTIONS:
            cv2.line(frame, points[a], points[b], (180, 220, 80), 2, cv2.LINE_AA)
        for p in points:
            cv2.circle(frame, p, 3, (235, 250, 210), -1, cv2.LINE_AA)
        center = (int(point[0]*w), int(point[1]*h))
        cv2.circle(frame, center, 11, (70, 230, 255), 2, cv2.LINE_AA)
        return point

    def close(self):
        self.detector.close()

import logging
import queue
import threading
import time
import cv2
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage
from hardware.serial_controller import SerialController
from tracking.detectors import HandDetector
from tracking.motion import Motion


class Worker(QThread):
    notice = Signal(str)
    connection = Signal(bool, str)
    following = Signal(bool)

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.commands = queue.Queue()
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.latest = None

    def command(self, name, value=None):
        self.commands.put((name, value))

    def snapshot(self):
        with self.lock:
            packet, self.latest = self.latest, None
            return packet

    def run(self):
        capture = detector = None
        controller = SerialController()
        motion = Motion(self.settings)
        following = False
        centering = False
        try:
            self.notice.emit('Подготавливаю распознавание…')
            detector = HandDetector()
            capture = cv2.VideoCapture(self.settings.camera, cv2.CAP_DSHOW)
            if not capture.isOpened():
                capture.release()
                capture = cv2.VideoCapture(self.settings.camera)
            if not capture.isOpened():
                raise RuntimeError('Камера недоступна. Выберите другой номер или закройте приложение, которое её использует.')
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            capture.set(cv2.CAP_PROP_FPS, 30)
            previous = time.monotonic()
            failures = 0
            fps = 0.0
            self.notice.emit('Камера работает. Покажите ладонь и включите сопровождение.')
            while not self.stop_event.is_set():
                while not self.commands.empty():
                    name, value = self.commands.get_nowait()
                    if name == 'follow':
                        following = bool(value)
                        centering = False
                        motion.hold()
                        self.following.emit(following)
                    elif name == 'center':
                        following = False
                        centering = True
                        motion.center()
                        self.following.emit(False)
                    elif name in ('connect', 'connect_csv'):
                        following = centering = False
                        self.following.emit(False)
                        controller.close()
                        controller = SerialController(csv_mode=name == 'connect_csv')
                        self.notice.emit('Открываю порт…' if controller.csv_mode else 'Ожидаю ответ Arduino…')
                        try:
                            controller.connect(value, self.stop_event.is_set)
                            motion = Motion(self.settings, controller.home, controller.position)
                            self.connection.emit(True, value)
                            if controller.csv_mode:
                                self.notice.emit('Порт открыт. servo_control работает без подтверждений. Включите сопровождение.')
                            else:
                                home = f'{controller.home[0]}° / {controller.home[1]}°'
                                message = f'Arduino подключена. Исходная поза {home}.'
                                if min(controller.home) < 10 or max(controller.home) > 170:
                                    message += ' У края хода движение в одну сторону ограничено.'
                                self.notice.emit(message)
                        except Exception as exc:
                            self.connection.emit(False, '')
                            self.notice.emit(str(exc))
                    elif name == 'disconnect':
                        controller.close()
                        following = centering = False
                        motion.hold()
                        self.following.emit(False)
                        self.connection.emit(False, '')
                        self.notice.emit('Arduino отключена. Доступна проверка на экране.')
                if self.stop_event.is_set():
                    break
                ok, frame = capture.read()
                if not ok:
                    failures += 1
                    motion.hold()
                    if failures >= 5:
                        raise RuntimeError('Камера перестала передавать изображение. Проверьте подключение.')
                    time.sleep(0.03)
                    continue
                failures = 0
                if self.settings.mirror:
                    frame = cv2.flip(frame, 1)
                point = detector.detect(frame)
                now = time.monotonic()
                dt = now - previous
                previous = now
                fps = 0.9*fps + 0.1/max(dt, 0.001) if fps else 1/max(dt, 0.001)
                if following:
                    motion.observe(point, dt)
                elif not centering:
                    motion.hold()
                angles = motion.step(dt)
                try:
                    if not controller.csv_mode or following or centering:
                        controller.tick(*angles, now=now)
                except Exception as exc:
                    logging.exception('Serial communication failed')
                    controller.close()
                    following = centering = False
                    motion.hold()
                    self.following.emit(False)
                    self.connection.emit(False, '')
                    self.notice.emit(str(exc))
                h, w = frame.shape[:2]
                cv2.drawMarker(frame, (w//2, h//2), (130,130,130), cv2.MARKER_CROSS, 16, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888).copy()
                with self.lock:
                    self.latest = (img, point, angles, fps, controller.ack_angles)
        except Exception as exc:
            logging.exception('Camera worker failed')
            self.notice.emit(str(exc))
        finally:
            controller.close()
            if capture is not None:
                capture.release()
            if detector is not None:
                detector.close()
            self.following.emit(False)
            self.connection.emit(False, '')

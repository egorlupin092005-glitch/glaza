"""Real model + worker + serial protocol with prerecorded camera and fake board.

Fixture: official MediaPipe sample woman_hands.jpg. No hardware is opened.
"""
import sys
import time
from pathlib import Path
from unittest.mock import patch
import cv2
import numpy as np
from PySide6.QtCore import QCoreApplication, QTimer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tracking.worker import Worker
from tracking.motion import Settings

csv_mode = '--servo-control' in sys.argv
zero_home = '--zero-home' in sys.argv
home = (0, 0) if zero_home else (90, 90)

sample = cv2.imdecode(np.fromfile(Path(__file__).with_name('hand_sample.jpg'), dtype=np.uint8), cv2.IMREAD_COLOR)
if sample is None:
    raise SystemExit('Missing tests/hand_sample.jpg. See tests/fixtures.md.')


class Capture:
    blank = False
    released = False

    def isOpened(self):
        return True

    def set(self,*args):
        return True

    def read(self):
        time.sleep(0.015)
        return True, np.zeros_like(sample) if self.blank else sample.copy()

    def release(self):
        self.released = True


class Board:
    def __init__(self):
        self.rx = bytearray()
        self.angles = []
        self.closed = False

    @property
    def in_waiting(self):
        return len(self.rx)

    def read(self,n):
        data = bytes(self.rx[:n])
        del self.rx[:n]
        return data

    def write(self,data):
        if csv_mode:
            assert data.endswith(b'\n')
            pan, tilt = data.decode('ascii').strip().split(',')
            self.angles.append((int(pan), int(tilt)))
        elif data == b'HELLO\n':
            if zero_home:
                self.rx.extend(b'POSE 0 0 0 0\n')
            self.rx.extend(b'GLAZA 1\n')
        else:
            _,seq,pan,tilt = data.decode().split()
            self.angles.append((int(pan),int(tilt)))
            self.rx.extend(f'OK {seq} {pan} {tilt}\n'.encode())
        return len(data)

    def close(self):
        self.closed = True


application = QCoreApplication([])
capture = Capture()
board = Board()
worker = Worker(Settings(mirror=False, invert_pan=zero_home, invert_tilt=not zero_home))
state = {'stage':'start', 'frames':0, 'held':None, 'error':None}
messages = []
worker.notice.connect(messages.append)
def connected(active, port):
    if active and csv_mode:
        assert not board.angles
        worker.command('follow', True)
        state['stage'] = 'follow'

worker.connection.connect(connected)


def poll():
    try:
        packet = worker.snapshot()
        if packet is None:
            return
        _, point, angles, _, ack = packet
        stage = state['stage']
        if stage == 'start' and point is not None:
            worker.command('connect_csv' if csv_mode else 'connect','TEST')
            state['stage'] = 'connect'
        elif stage == 'connect' and ack is not None:
            worker.command('follow',True)
            state['stage'] = 'follow'
        elif stage == 'follow' and (
            (zero_home and angles[0] > 5 and angles[1] > 3) or
            (not zero_home and angles[0] < 80 and angles[1] < 85)
        ):
            capture.blank = True
            state['stage'] = 'lost'
        elif stage == 'lost' and point is None:
            state['held'] = angles
            state['stage'] = 'hold'
        elif stage == 'hold':
            assert point is None and angles == state['held'], (angles,state['held'])
            state['frames'] += 1
            if state['frames'] >= 8:
                worker.command('center')
                state['stage'] = 'center'
        elif stage == 'center' and angles == home:
            state['stage'] = 'done'
            worker.stop_event.set()
    except Exception as exc:
        state['error'] = repr(exc)
        worker.stop_event.set()


timer = QTimer()
timer.timeout.connect(poll)
timer.start(20)
timeout = QTimer()
timeout.setSingleShot(True)
timeout.timeout.connect(worker.stop_event.set)
timeout.start(15000)
worker.finished.connect(application.quit)
with patch('tracking.worker.cv2.VideoCapture',return_value=capture), patch(
    'hardware.serial_controller.serial.Serial',return_value=board):
    worker.start()
    application.exec()
    worker.wait()
assert state['error'] is None, state['error']
assert state['stage'] == 'done', (state,messages)
assert capture.released and board.closed
assert len(board.angles) > 5
print(f'Pipeline passed: {len(board.angles)} commands; servo_control={csv_mode}; hand lost/hold, center and shutdown OK.')

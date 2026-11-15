"""Serial transport for glaza_pointer and the one-way servo_control sketch."""
import time
import serial


class SerialController:
    def __init__(self, *, csv_mode=False):
        self.csv_mode = csv_mode
        self.port = None
        self.buffer = bytearray()
        self.sequence = 0
        self.pending = None
        self.sent_at = 0.0
        self.last_send = 0.0
        self.last_angles = None
        self.ack_angles = None
        self.home = self.position = (90, 90)

    def _lines(self):
        count = self.port.in_waiting
        if count:
            self.buffer.extend(self.port.read(min(count, 512)))
        if len(self.buffer) > 2048:
            raise RuntimeError('Arduino присылает некорректные данные.')
        lines = []
        while b'\n' in self.buffer:
            line, _, rest = self.buffer.partition(b'\n')
            self.buffer = bytearray(rest)
            lines.append(line.decode('ascii', errors='replace').strip())
        return lines

    def connect(self, name, cancelled=lambda: False):
        self.close()
        try:
            baud = 9600 if self.csv_mode else 115200
            self.port = serial.Serial(name, baud, timeout=0, write_timeout=0.2)
            if self.csv_mode:
                # A classic Uno/Nano can reset when the serial port opens.
                ready_at = time.monotonic() + 2.0
                while time.monotonic() < ready_at:
                    if cancelled():
                        raise RuntimeError('Подключение отменено.')
                    time.sleep(0.02)
                return
            deadline = time.monotonic() + 5.0
            next_hello = 0.0
            while time.monotonic() < deadline and not cancelled():
                now = time.monotonic()
                if now >= next_hello:
                    self.port.write(b'HELLO\n')
                    next_hello = now + 0.4
                for line in self._lines():
                    if line.startswith('POSE '):
                        parts = line.split()
                        if len(parts) != 5 or not all(v.isascii() and v.isdecimal() and int(v) <= 180 for v in parts[1:]):
                            raise RuntimeError('Arduino прислала некорректное исходное положение.')
                        pan, tilt, current_pan, current_tilt = map(int, parts[1:])
                        self.home = (pan, tilt)
                        self.position = (current_pan, current_tilt)
                    elif line == 'GLAZA 1':
                        return
                time.sleep(0.02)
            raise RuntimeError('Arduino не ответила. Загрузите glaza_pointer.ino и закройте монитор порта.')
        except Exception:
            self.close()
            raise

    def tick(self, pan, tilt, now=None):
        if self.port is None:
            return
        now = time.monotonic() if now is None else now
        angles = (int(pan), int(tilt))
        if not all(min(10, home) <= angle <= max(170, home) for angle, home in zip(angles, self.home)):
            raise ValueError('Команда вне допустимого диапазона.')
        if self.csv_mode:
            interval = 1/30 if angles != self.last_angles else 0.25
            if now - self.last_send >= interval:
                frame = f'{angles[0]},{angles[1]}\n'.encode('ascii')
                if self.port.write(frame) != len(frame):
                    raise RuntimeError('Не удалось передать команду целиком.')
                self.last_angles, self.last_send = angles, now
            return
        for line in self._lines():
            parts = line.split()
            if len(parts) == 4 and parts[0] == 'OK':
                try:
                    seq, a, b = map(int, parts[1:])
                except ValueError:
                    continue
                if seq == self.pending:
                    self.pending = None
                    self.ack_angles = (a, b)
            elif line in ('GLAZA 1', 'BOOT'):
                raise RuntimeError('Arduino перезапустилась. Подключите её заново.')
        if self.pending is not None:
            if now - self.sent_at > 0.7:
                raise RuntimeError('Нет подтверждения Arduino. Соединение остановлено.')
            return
        interval = 1/30 if angles != self.last_angles else 0.25
        if now - self.last_send < interval:
            return
        self.sequence = (self.sequence + 1) % 65536
        self.port.write(f'S {self.sequence} {angles[0]} {angles[1]}\n'.encode('ascii'))
        self.pending = self.sequence
        self.sent_at = self.last_send = now
        self.last_angles = angles

    def close(self):
        port, self.port = self.port, None
        if port is not None:
            try:
                port.close()
            except serial.SerialException:
                pass
        self.buffer.clear()
        self.pending = None
        self.last_angles = self.ack_angles = None
        self.last_send = 0.0
        self.home = self.position = (90, 90)

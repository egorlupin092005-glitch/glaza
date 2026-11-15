"""Camera-space palm position to bounded, rate-limited pointer commands."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Settings:
    camera: int = 0
    mirror: bool = True
    invert_pan: bool = False
    invert_tilt: bool = True
    pan_min: int = 45
    pan_max: int = 135
    tilt_min: int = 60
    tilt_max: int = 120
    smoothing: float = 0.35
    deadzone: float = 0.04
    speed: float = 70.0

    def validate(self):
        if type(self.camera) is not int or not 0 <= self.camera <= 9:
            raise ValueError('Номер камеры должен быть от 0 до 9.')
        for name in ('mirror', 'invert_pan', 'invert_tilt'):
            if type(getattr(self, name)) is not bool:
                raise ValueError('Некорректная настройка направления.')
        for lo, hi in ((self.pan_min, self.pan_max), (self.tilt_min, self.tilt_max)):
            if not 10 <= lo < 90 < hi <= 170:
                raise ValueError('Пределы каждой оси должны включать 90° и лежать в 10–170°.')
        if not 0.05 <= self.smoothing <= 1 or not 0 <= self.deadzone <= 0.2:
            raise ValueError('Некорректное сглаживание или зона покоя.')
        if not 10 <= self.speed <= 120:
            raise ValueError('Скорость должна быть в пределах 10–120°/с.')
        return self


def map_axis(value, low, high, invert, deadzone, neutral=90):
    value = min(1.0, max(0.0, value))
    offset = (value - 0.5) * (-1 if invert else 1)
    half_dead = deadzone / 2
    if abs(offset) <= half_dead:
        return float(neutral)
    normalized = (abs(offset) - half_dead) / (0.5 - half_dead)
    angle = neutral + normalized * (high - 90 if offset > 0 else low - 90)
    # The configured spans are relative to the calibrated rest pose.
    # A positional servo cannot move past an endpoint, e.g. below 0 degrees.
    return min(max(170, neutral), max(min(10, neutral), angle))


class Motion:
    def __init__(self, settings=None, home=(90, 90), position=None):
        self.settings = (settings or Settings()).validate()
        self.home = tuple(home)
        self.pan, self.tilt = position if position is not None else self.home
        self.target = (self.pan, self.tilt)
        self.filtered = None

    def hold(self):
        self.target = (self.pan, self.tilt)
        self.filtered = None

    def center(self):
        self.target = self.home
        self.filtered = None

    def observe(self, point, dt):
        if point is None or not all(math.isfinite(v) for v in point):
            self.hold()
            return
        s = self.settings
        if self.filtered is None:
            self.filtered = point
        else:
            # Same smoothing at 15, 30 and 60 FPS; alpha is specified for 30 FPS.
            a = 1 - (1 - s.smoothing) ** (max(0, min(dt, 0.1)) * 30)
            self.filtered = tuple(old + a * (new - old) for old, new in zip(self.filtered, point))
        self.target = (
            map_axis(self.filtered[0], s.pan_min, s.pan_max, s.invert_pan, s.deadzone, self.home[0]),
            map_axis(self.filtered[1], s.tilt_min, s.tilt_max, s.invert_tilt, s.deadzone, self.home[1]),
        )

    def step(self, dt):
        step = self.settings.speed * max(0, min(dt, 0.1))
        self.pan += max(-step, min(step, self.target[0] - self.pan))
        self.tilt += max(-step, min(step, self.target[1] - self.tilt))
        return round(self.pan), round(self.tilt)

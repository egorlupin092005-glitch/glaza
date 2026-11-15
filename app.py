"""Глаза — desktop hand-following pointer demonstrator."""
from dataclasses import asdict
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
    QFormLayout, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QScrollArea, QSpinBox, QVBoxLayout, QWidget)
from serial.tools import list_ports
from tracking.motion import Settings
from tracking.worker import Worker

ROOT = Path(__file__).resolve().parent

STYLE = '''
QWidget { color: #24364b; font-family: "Segoe UI"; font-size: 13px; }
QMainWindow, QWidget#workspace { background: #f3f6fb; }
QFrame#panel { background: #ffffff; border: 1px solid #dce4ee; border-radius: 16px; }
QLabel { background: transparent; }
QLabel#title { color: #182e4d; font-size: 30px; font-weight: 700; }
QLabel#section { font-size: 15px; font-weight: 600; color: #254873; }
QLabel#muted { color: #61738a; }
QLabel#mode { color: #2257a5; background: #e7effd; border-radius: 8px; padding: 7px 10px; font-weight: 600; }
QLabel#status { background: #ffffff; border: 1px solid #dce4ee; border-radius: 10px; padding: 9px 12px; }
QLabel#video { background: #e9eff7; border: 1px solid #d5dfed; border-radius: 16px; color: #566d89; }
QPushButton { background: #ffffff; border: 1px solid #ccd8e7; border-radius: 8px; padding: 9px 12px; font-weight: 500; }
QPushButton:hover { background: #edf3fd; border-color: #93b4e9; }
QPushButton:pressed { background: #dde9fb; }
QPushButton:focus { border: 1px solid #3977d5; }
QPushButton:disabled { background: #f0f3f7; color: #7c8a9c; border-color: #e0e6ef; }
QPushButton#primary { background: #2563d9; border-color: #2563d9; color: #ffffff; font-weight: 600; }
QPushButton#primary:hover { background: #1d52bb; border-color: #1d52bb; }
QPushButton#primary:checked { background: #e5f4ec; border-color: #8cc4a5; color: #226340; }
QPushButton#primary:disabled { background: #e5ecf7; border-color: #d5dfef; color: #7487a6; }
QPushButton#stop { color: #a23b42; background: #fff2f2; border-color: #e9c7ca; }
QPushButton#stop:hover { background: #ffe3e5; }
QPushButton#stop:disabled { color: #a28b90; background: #f7f1f2; border-color: #e8dfe2; }
QComboBox, QSpinBox, QDoubleSpinBox { background: #f8faff; border: 1px solid #d5deeb; border-radius: 6px; padding: 5px; min-height: 20px; selection-background-color: #2563d9; selection-color: #ffffff; }
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color: #3977d5; }
QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled { color: #7c8a9c; background: #f0f3f7; }
QComboBox QAbstractItemView { background: #ffffff; border: 1px solid #d5deeb; selection-background-color: #e3edfd; selection-color: #183f78; }
QCheckBox { spacing: 8px; background: transparent; }
QCheckBox:disabled { color: #7c8a9c; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #edf1f7; width: 9px; margin: 2px; border-radius: 4px; }
QScrollBar::handle:vertical { background: #b9c9dd; min-height: 28px; border-radius: 3px; }
QScrollBar::handle:vertical:hover { background: #8fa9ca; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
'''


def apply_theme(application):
    application.setStyle('Fusion')
    application.setFont(QFont('Segoe UI', 10))
    palette = QPalette()
    for role, color in (
        (QPalette.ColorRole.Window, '#f3f6fb'),
        (QPalette.ColorRole.WindowText, '#24364b'),
        (QPalette.ColorRole.Base, '#ffffff'),
        (QPalette.ColorRole.AlternateBase, '#f3f6fb'),
        (QPalette.ColorRole.Text, '#24364b'),
        (QPalette.ColorRole.Button, '#ffffff'),
        (QPalette.ColorRole.ButtonText, '#24364b'),
        (QPalette.ColorRole.Highlight, '#2563d9'),
        (QPalette.ColorRole.HighlightedText, '#ffffff'),
        (QPalette.ColorRole.ToolTipBase, '#ffffff'),
        (QPalette.ColorRole.ToolTipText, '#24364b'),
    ):
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor('#7c8a9c'))
    application.setPalette(palette)
    application.setStyleSheet(STYLE)


class PointerPreview(QWidget):
    def __init__(self):
        super().__init__()
        self.angles = (90, 90)
        self.setMinimumHeight(112)

    def paintEvent(self, event):
        import math
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for index, title in enumerate(('Поворот', 'Наклон')):
            cx = int(self.width()*(0.25 if index == 0 else 0.75))
            cy = 66
            p.setPen(QPen(QColor('#c3d1e3'), 2))
            p.drawArc(cx-32, cy-32, 64, 64, 0, 180*16)
            angle = math.radians(self.angles[index])
            p.setPen(QPen(QColor('#2563d9'), 4))
            p.drawLine(cx, cy, round(cx+32*math.cos(angle)), round(cy-32*math.sin(angle)))
            p.setPen(QColor('#405975'))
            p.drawText(cx-65, 5, 130, 22, Qt.AlignmentFlag.AlignCenter, title)
            p.drawText(cx-65, 80, 130, 22, Qt.AlignmentFlag.AlignCenter, f'{self.angles[index]}°')
        p.end()


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Модуль обнаружения')
        self.resize(1140, 830)
        self.worker = None
        self.connected = False
        self.connecting = False
        self.closing = False
        self.pixmap = None
        self.config_error = ''
        settings = self.load_settings()
        host = QWidget()
        host.setObjectName('workspace')
        outer = QVBoxLayout(host)
        outer.setContentsMargins(24, 18, 24, 18)
        header = QHBoxLayout()
        title = QLabel('Модуль обнаружения')
        title.setObjectName('title')
        subtitle = QLabel('Камера → ладонь → маленький указатель')
        subtitle.setObjectName('muted')
        header.addWidget(title)
        header.addSpacing(16)
        header.addWidget(subtitle)
        header.addStretch()
        self.mode = QLabel('ПРОВЕРКА БЕЗ ARDUINO')
        self.mode.setObjectName('mode')
        header.addWidget(self.mode)
        outer.addLayout(header)
        body = QHBoxLayout()
        outer.addLayout(body, 1)
        left = QVBoxLayout()
        self.video = QLabel('Включите камеру\n\nПокажите открытую ладонь в кадре')
        self.video.setObjectName('video')
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video.setMinimumSize(480, 340)
        left.addWidget(self.video, 1)
        self.telemetry = QLabel('Рука: —     Кадры/с: —     Команда: 90° / 90°')
        self.telemetry.setObjectName('muted')
        left.addWidget(self.telemetry)
        self.preview = PointerPreview()
        left.addWidget(self.preview)
        note = QLabel('Палочка следует за положением ладони в изображении.\nЕсли рука пропадает, команда удерживается. Углы на экране — заданные, без датчика положения.')
        note.setObjectName('muted')
        note.setWordWrap(True)
        left.addWidget(note)
        body.addLayout(left, 1)

        side = QFrame()
        side.setObjectName('panel')
        side.setFixedWidth(340)
        controls = QVBoxLayout(side)
        controls.setContentsMargins(16,16,16,16)
        self.section(controls, 'Камера')
        self.camera = QSpinBox()
        self.camera.setRange(0,9)
        self.camera.setValue(settings.camera)
        form = QFormLayout()
        form.addRow('Номер камеры', self.camera)
        controls.addLayout(form)
        self.mirror = QCheckBox('Зеркальное изображение')
        self.mirror.setChecked(settings.mirror)
        controls.addWidget(self.mirror)
        self.camera_button = QPushButton('Включить камеру')
        self.camera_button.clicked.connect(self.toggle_camera)
        controls.addWidget(self.camera_button)
        self.section(controls, 'Arduino')
        self.sketch = QComboBox()
        self.sketch.addItem('glaza_pointer · с подтверждением', 'connect')
        self.sketch.addItem('servo_control · без подтверждения', 'connect_csv')
        sketch_form = QFormLayout()
        sketch_form.addRow('Скетч на плате', self.sketch)
        controls.addLayout(sketch_form)
        ports_row = QHBoxLayout()
        self.ports = QComboBox()
        ports_row.addWidget(self.ports, 1)
        self.refresh = QPushButton('Обн.')
        self.refresh.setToolTip('Обновить список портов')
        self.refresh.setFixedWidth(58)
        self.refresh.clicked.connect(self.refresh_ports)
        ports_row.addWidget(self.refresh)
        controls.addLayout(ports_row)
        self.connect_button = QPushButton('Подключить Arduino')
        self.connect_button.clicked.connect(self.toggle_connection)
        self.connect_button.setEnabled(False)
        controls.addWidget(self.connect_button)
        self.section(controls, 'Движение')
        self.follow = QPushButton('Следовать за рукой')
        self.follow.setObjectName('primary')
        self.follow.setCheckable(True)
        self.follow.setEnabled(False)
        self.follow.clicked.connect(lambda checked: self.worker.command('follow', checked) if self.worker else None)
        controls.addWidget(self.follow)
        row = QHBoxLayout()
        self.center = QPushButton('В центр')
        self.center.setEnabled(False)
        self.center.clicked.connect(lambda: self.worker.command('center') if self.worker else None)
        self.stop = QPushButton('Стоп')
        self.stop.setObjectName('stop')
        self.stop.setEnabled(False)
        self.stop.clicked.connect(lambda: self.worker.command('follow', False) if self.worker else None)
        row.addWidget(self.center)
        row.addWidget(self.stop)
        controls.addLayout(row)
        self.section(controls, 'Настройка осей')
        self.invert_pan = QCheckBox('Развернуть горизонтальную ось')
        self.invert_pan.setChecked(settings.invert_pan)
        self.invert_tilt = QCheckBox('Развернуть вертикальную ось')
        self.invert_tilt.setChecked(settings.invert_tilt)
        controls.addWidget(self.invert_pan)
        controls.addWidget(self.invert_tilt)
        limits = QFormLayout()
        self.numeric = {}
        for name, label, low, high, step in (
            ('pan_min','Ход поворота −, °',1,80,1),
            ('pan_max','Ход поворота +, °',1,80,1),
            ('tilt_min','Ход наклона −, °',1,80,1),
            ('tilt_max','Ход наклона +, °',1,80,1),
            ('speed','Скорость, °/с',10,120,5),
            ('smoothing','Отклик (меньше = плавнее)',0.05,1,0.05),
            ('deadzone','Зона покоя в центре',0,0.2,0.01),
        ):
            field = QDoubleSpinBox() if name in ('smoothing','deadzone') else QSpinBox()
            field.setRange(low,high)
            field.setSingleStep(step)
            value = getattr(settings, name)
            if name in ('pan_min', 'tilt_min'):
                value = 90 - value
            elif name in ('pan_max', 'tilt_max'):
                value -= 90
            field.setValue(value)
            self.numeric[name] = field
            limits.addRow(label,field)
        controls.addLayout(limits)
        tip = QLabel('Настройки меняются при выключенной камере и сохраняются при запуске.')
        tip.setWordWrap(True)
        tip.setObjectName('muted')
        controls.addWidget(tip)
        controls.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(side)
        scroll.setFixedWidth(360)
        body.addWidget(scroll)
        self.status = QLabel(self.config_error or 'Начните с камеры. Arduino можно подключить после проверки распознавания.')
        self.status.setObjectName('status')
        self.status.setWordWrap(True)
        self.status.setMinimumHeight(40)
        outer.addWidget(self.status)
        self.setCentralWidget(host)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(33)
        self.refresh_ports()

    @staticmethod
    def section(layout, text):
        label = QLabel(text)
        label.setObjectName('section')
        label.setContentsMargins(0,8,0,3)
        layout.addWidget(label)

    def load_settings(self):
        try:
            path = ROOT/'settings.json'
            return Settings(**json.loads(path.read_text(encoding='utf-8'))).validate() if path.exists() else Settings()
        except (OSError, ValueError, TypeError) as exc:
            self.config_error = f'Настройки сброшены к исходным: {exc}'
            return Settings()

    def get_settings(self):
        values = {name: widget.value() for name, widget in self.numeric.items()}
        for name in ('pan_min', 'tilt_min'):
            values[name] = 90 - values[name]
        for name in ('pan_max', 'tilt_max'):
            values[name] += 90
        return Settings(camera=self.camera.value(), mirror=self.mirror.isChecked(),
            invert_pan=self.invert_pan.isChecked(), invert_tilt=self.invert_tilt.isChecked(), **values).validate()

    def refresh_ports(self):
        selected = self.ports.currentData()
        self.ports.clear()
        for port in list_ports.comports():
            self.ports.addItem(f'{port.device} · {port.description}', port.device)
        index = self.ports.findData(selected)
        if index >= 0:
            self.ports.setCurrentIndex(index)
        if self.ports.count() == 0:
            self.ports.addItem('Нет подключённых плат', None)

    def lock_settings(self, locked):
        for widget in (self.camera,self.mirror,self.invert_pan,self.invert_tilt,*self.numeric.values()):
            widget.setEnabled(not locked)

    def toggle_camera(self):
        if self.worker is not None:
            self.stop_camera()
            return
        try:
            settings = self.get_settings()
            temp = ROOT/'settings.tmp'
            temp.write_text(json.dumps(asdict(settings), indent=2), encoding='utf-8')
            temp.replace(ROOT/'settings.json')
        except (ValueError,OSError) as exc:
            self.status.setText(str(exc))
            return
        self.worker = Worker(settings)
        self.worker.notice.connect(self.status.setText)
        self.worker.connection.connect(self.connection_changed)
        self.worker.following.connect(self.follow_changed)
        self.worker.finished.connect(self.worker_finished)
        self.lock_settings(True)
        self.camera_button.setText('Выключить камеру')
        self.worker.start()

    def stop_camera(self):
        if self.worker:
            self.worker.stop_event.set()
            self.camera_button.setEnabled(False)
            self.connect_button.setEnabled(False)
            for widget in (self.follow,self.center,self.stop):
                widget.setEnabled(False)
            self.status.setText('Останавливаю камеру…')

    def worker_finished(self):
        self.worker.wait()
        self.worker.deleteLater()
        self.worker = None
        self.lock_settings(False)
        self.camera_button.setEnabled(True)
        self.camera_button.setText('Включить камеру')
        self.connect_button.setEnabled(False)
        for widget in (self.follow,self.center,self.stop):
            widget.setEnabled(False)
        self.pixmap = None
        self.video.clear()
        self.video.setText('Камера выключена')
        self.telemetry.setText('Камера выключена · команды не передаются')
        if self.closing:
            self.close()

    def toggle_connection(self):
        if not self.worker:
            return
        if self.connected:
            self.worker.command('disconnect')
        elif self.ports.currentData():
            self.connecting = True
            for widget in (self.sketch, self.ports, self.refresh, self.follow, self.center, self.stop):
                widget.setEnabled(False)
            self.connect_button.setEnabled(False)
            self.connect_button.setText('Подключение…')
            self.worker.command(self.sketch.currentData(), self.ports.currentData())
        else:
            self.status.setText('Подключите Arduino по USB и нажмите «Обн.».')

    def connection_changed(self, connected, port):
        self.connecting = False
        self.connected = connected
        self.connect_button.setText('Отключить Arduino' if connected else 'Подключить Arduino')
        self.connect_button.setEnabled(self.worker is not None and not self.worker.stop_event.is_set())
        self.ports.setEnabled(not connected)
        self.sketch.setEnabled(not connected)
        self.refresh.setEnabled(not connected)
        label = 'Порт открыт · без ответа' if self.sketch.currentData() == 'connect_csv' else 'Arduino'
        self.mode.setText(f'{label} · {port}' if connected else 'ПРОВЕРКА БЕЗ ARDUINO')

    def follow_changed(self, following):
        self.follow.setChecked(following)
        self.follow.setText('Сопровождение включено' if following else 'Следовать за рукой')

    def update_frame(self):
        if self.worker is None:
            return
        packet = self.worker.snapshot()
        if packet is None:
            return
        img, point, angles, fps, ack = packet
        self.pixmap = QPixmap.fromImage(img)
        self.render_video()
        hand = 'найдена' if point is not None else 'не видна'
        acknowledgment = f' · Arduino: {ack[0]}° / {ack[1]}°' if ack else ''
        self.telemetry.setText(f'Рука: {hand}    Кадры/с: {fps:.0f}    Команда: {angles[0]}° / {angles[1]}°{acknowledgment}')
        self.preview.angles = angles
        self.preview.update()
        if not self.worker.stop_event.is_set():
            for widget in (self.follow,self.center,self.stop):
                widget.setEnabled(not self.connecting)
            self.connect_button.setEnabled(not self.connecting)

    def render_video(self):
        if self.pixmap:
            self.video.setPixmap(self.pixmap.scaled(self.video.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'video'):
            self.render_video()

    def closeEvent(self, event):
        if self.worker is not None:
            self.closing = True
            self.stop_camera()
            event.ignore()
        else:
            event.accept()


def main():
    (ROOT/'logs').mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[RotatingFileHandler(
        ROOT/'logs'/'glaza.log', maxBytes=1_000_000, backupCount=2, encoding='utf-8')])
    application = QApplication(sys.argv)
    apply_theme(application)
    window = Window()
    window.show()
    return application.exec()


if __name__ == '__main__':
    sys.exit(main())

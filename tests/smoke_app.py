"""Offscreen window rendering; does not open the camera or any serial port."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QFont
from app import Window, apply_theme, ROOT

app = QApplication([])
for name in ('segoeui.ttf', 'segoeuib.ttf'):
    QFontDatabase.addApplicationFont(str(Path(os.environ['WINDIR'])/'Fonts'/name))
apply_theme(app)
window = Window()
window.show()
app.processEvents()
assert window.worker is None
assert not window.follow.isEnabled()
assert not window.connect_button.isEnabled()
assert window.get_settings() == window.load_settings()
assert window.video.width() >= 480
window.grab().save(str(ROOT/'docs'/'interface.png'))
window.close()
app.processEvents()
print('UI opened, rendered and closed successfully; no devices opened.')

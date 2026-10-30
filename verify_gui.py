"""Offscreen GUI checks; backend runs only in simulation mode."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt, QPoint, QProcess
from recovery_gui import RecoveryWindow

app = QApplication([])
w = RecoveryWindow(simulate=True)
w.show()
deadline = time.monotonic() + 20
while time.monotonic() < deadline:
    app.processEvents()
    if any('Simulation passed' in s for s in w.history) and w.proc.state() == QProcess.ProcessState.NotRunning:
        break
    QTest.qWait(30)
assert any('Simulation passed' in s for s in w.history), w.history
assert w.width() / w.height() == .75
Path('gui-previews').mkdir(exist_ok=True)
w.terminal.verticalScrollBar().setValue(0)
w.grab().save('gui-previews/english.png')
QTest.mouseClick(w, Qt.MouseButton.LeftButton, pos=QPoint(75, 520))
assert w.lang == 'zh'
assert '模拟恢复成功' in w.terminal.toPlainText()
assert 'Simulation passed' not in w.terminal.toPlainText()
w.terminal.verticalScrollBar().setValue(0)
w.grab().save('gui-previews/chinese.png')
QTest.mouseClick(w, Qt.MouseButton.LeftButton, pos=QPoint(35, 520))
assert w.lang == 'en'
assert 'Simulation passed' in w.terminal.toPlainText()
w.active = True
assert not w.close()
w.active = False
assert w.close()
print('PASS: simulated backend stream, both language views, 3:4 layout, close protection')

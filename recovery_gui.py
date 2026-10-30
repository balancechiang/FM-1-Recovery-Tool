"""Vector GUI for FM-1 Recovery Tool. See README and retained upstream credits."""
import os
import sys
import json
import codecs
from pathlib import Path
import traceback


def report_startup_error(exc_type, exc, tb):
    base = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
    (base / 'logs').mkdir(exist_ok=True)
    with (base / 'logs/gui-startup-error.log').open('a', encoding='utf-8') as stream:
        traceback.print_exception(exc_type, exc, tb, file=stream)


sys.excepthook = report_startup_error

from PySide6.QtCore import Qt, QRectF, QProcess, QProcessEnvironment, QTimer, QPointF
from PySide6.QtGui import QFont, QFontDatabase, QPainter, QPen, QColor
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QWidget, QPlainTextEdit, QLineEdit

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
BG = '#0b0b0a'


def terminal_font():
    """Use Windows Terminal's configured face when available, with system CJK fallback."""
    face = ''
    local = Path(os.environ.get('LOCALAPPDATA', ''))
    for path in [local / 'Packages/Microsoft.WindowsTerminal_8wekyb3d8bbwe/LocalState/settings.json',
                 local / 'Microsoft/Windows Terminal/settings.json']:
        try:
            data = json.loads(path.read_text(encoding='utf-8-sig'))
            defaults = data.get('profiles', {}).get('defaults', {})
            face = defaults.get('font', {}).get('face', defaults.get('fontFace', ''))
            if face:
                break
        except (OSError, ValueError, AttributeError):
            pass
    # System font files are loaded in place, never redistributed or installed.
    for name in ('consola.ttf', 'msyh.ttc'):
        path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / name
        if path.is_file():
            QFontDatabase.addApplicationFont(str(path))
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setFamilies([x for x in (face, font.family(), 'Cascadia Mono', 'Consolas',
                                 'Microsoft YaHei UI', 'Microsoft YaHei') if x])
    return font


class RecoveryWindow(QWidget):
    def __init__(self, simulate=False):
        super().__init__()
        self.simulate = simulate
        self.lang, self.active, self.pending = 'en', False, False
        self.drag_origin = None
        self.history, self.partial = [], ''
        self.decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        self.setWindowTitle('FM-1 Recovery Tool')
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setFixedSize(600, 800)
        self.setStyleSheet('background:' + BG + ';color:white;')
        font_id = QFontDatabase.addApplicationFont(str(ROOT / 'assets/SprayMindsMono-Regular.ttf'))
        if font_id < 0:
            raise RuntimeError('Bundled SprayMindsMono font could not be loaded')
        self.english = QFontDatabase.applicationFontFamilies(font_id)[0]
        self.fixed = terminal_font()
        self.art = QSvgRenderer(str(ROOT / 'assets/illustration.svg'))
        if not self.art.isValid():
            raise RuntimeError('Vector illustration could not be loaded')
        self.terminal = QPlainTextEdit(self)
        self.terminal.setReadOnly(True)
        self.terminal.setMaximumBlockCount(3000)
        self.terminal.setFrameStyle(0)
        self.terminal.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.terminal.setStyleSheet('QPlainTextEdit {border:0;background:#0b0b0a;color:#fff;selection-background-color:#555;} QScrollBar:vertical {width:5px;background:#161616;} QScrollBar::handle:vertical {background:#555;min-height:20px;}')
        self.entry = QLineEdit(self)
        self.entry.setStyleSheet('QLineEdit {border:0;border-bottom:1px solid #555;background:#0b0b0a;color:#fff;padding:3px;}')
        self.entry.setAccessibleName('V15 confirmation')
        self.entry.returnPressed.connect(self.submit)
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self.receive)
        self.proc.finished.connect(self.finished)
        self.proc.errorOccurred.connect(self.process_error)
        self.apply_language()
        self.layout_children()
        QTimer.singleShot(0, self.prepare)

    def text(self, en, zh):
        return en if self.lang == 'en' else zh

    def layout_children(self):
        self.terminal.setGeometry(27, 594, 546, 145)
        self.entry.setGeometry(27, 752, 546, 28)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(BG))
        p.setPen(QColor('white'))
        p.setFont(QFont(self.english, 30))
        p.drawText(QPointF(18, 50), 'FM-1')
        p.drawText(QPointF(18, 99), 'RECOVERY TOOL')
        p.setPen(QPen(QColor('white'), 2))
        p.drawRect(QRectF(552, 19, 31, 31))
        p.drawLine(QPointF(553, 20), QPointF(582, 49))
        p.drawLine(QPointF(582, 20), QPointF(553, 49))
        self.art.render(p, QRectF(0, 270, 600, 257))
        p.setFont(QFont(self.english, 13))
        p.setPen(QColor('white' if self.lang == 'en' else '#666'))
        p.drawText(QPointF(27, 527), 'EN')
        chinese_font = QFont(self.fixed)
        chinese_font.setPointSize(13)
        p.setFont(chinese_font)
        p.setPen(QColor('white' if self.lang == 'zh' else '#666'))
        p.drawText(QPointF(59, 527), '中文')
        p.setPen(QColor('#777'))
        status_font = QFont(self.english, 8) if self.lang == 'en' else QFont(self.fixed)
        status_font.setPointSize(8)
        p.setFont(status_font)
        status = self.text('RECOVERING — KEEP USB CONNECTED', '恢复中，请勿断开 USB') if self.active else self.text('OFFLINE / OFFICIAL V15', '离线恢复 / 官方 V15')
        p.drawText(QPointF(27, 566), status)

    def mousePressEvent(self, event):
        pos = event.position()
        if QRectF(546, 12, 47, 47).contains(pos):
            self.close()
        elif QRectF(22, 505, 33, 32).contains(pos):
            self.lang = 'en'; self.apply_language()
        elif QRectF(56, 505, 48, 32).contains(pos):
            self.lang = 'zh'; self.apply_language()
        elif QRectF(400, 365, 75, 75).contains(pos):
            if not self.active:
                if self.proc.state() == QProcess.ProcessState.NotRunning:
                    self.prepare()
                self.entry.setFocus()
        elif pos.y() < 200 and event.button() == Qt.MouseButton.LeftButton:
            self.drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.drag_origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_origin)

    def mouseReleaseEvent(self, event):
        self.drag_origin = None

    def apply_language(self):
        font = QFont(self.english, 8) if self.lang == 'en' else QFont(self.fixed)
        font.setPointSize(9 if self.lang == 'zh' else 8)
        self.terminal.setFont(font)
        self.entry.setFont(font)
        self.entry.setPlaceholderText(self.text('Type V15 and press Enter to start', '输入 V15 并回车开始恢复'))
        self.entry.setEnabled(not self.active)
        self.render_history()
        self.update()

    @staticmethod
    def chinese(line):
        mappings = [
            ('FM-1 Recovery Tool', 'FM-1 恢复工具'),
            ('Offline official V15 recovery', '官方 V15 离线恢复'),
            ('Connect one FM-1', '请只连接一台 FM-1，使用 USB 数据线；关闭网页升级工具、DAW 和其他 MIDI 软件。'),
            ('Cancel any Windows', '如 Windows 提示格式化磁盘，请取消。'),
            ('Flow:', '流程：校验 V15 → 进入 UBOOT → 双读备份 → 写入 → 回读验证。'),
            ('Only firmware region', '仅恢复固件区 0x4000–0x92FFF，请保留备份。'),
            ('Bundled official', '内置官方 V15 和 USB loader 校验通过。'),
            ('Type V15', '输入 V15 并回车开始（大小写不限；先备份再恢复）：'),
            ('No UBOOT device', '尚未发现 UBOOT，正在发送 MIDI 启动指令。'),
            ('Boot key sent', 'MIDI 启动指令已发送。'),
            ('Waiting for the UBOOT', '等待 UBOOT 设备出现。'),
            ('Device startup attempt', '设备启动尝试：' + line.rsplit(' ', 1)[-1]),
            ('USB settling', '等待 USB 稳定：5 秒。'),
            ('RAM loader settling', '等待 RAM loader 稳定：1 秒。'),
            ('USB loader uploaded', 'USB loader 已上传并启动。'),
            ('Startup USB transport failed', '启动通信失败；关闭连接，等待 10 秒后重试一次。'),
            ('Opening device', '启动失败，尚未擦写固件，详情已保存至日志。'),
            ('Step 1/6', '步骤 1/6：校验固件包。'), ('Step 2/6', '步骤 2/6：检查设备。'),
            ('Step 3/6', '步骤 3/6：完整双读备份。'), ('Step 4/6', '步骤 4/6：确认恢复。'),
            ('Step 5/6', '步骤 5/6：写入及验证，请勿断电或拔线。'),
            ('Step 6/6', '步骤 6/6：恢复成功，已逐字节验证。'),
            ('Backing up', '完整读取 Flash 两次，比较一致后才能写入。'),
            ('Backup OK', '完整备份已保存并校验。'),
            ('The firmware region already', '固件已与官方 V15 完全一致，跳过重复写入。'),
            ('Write attempt', '正在擦除并写入固件区，请勿断电或拔线。'),
            ('Verifying:', '正在回读固件并逐字节验证。'),
            ('byte-for-byte identical', '回读数据逐字节一致。'),
            ('Retrying the write', '回读不一致，重试写入一次。'),
            ('V15 firmware verified', 'V15 固件验证成功。拔 USB → 关机 → 等待 5 秒 → 开机。'),
            ('Backups:', '完整备份：程序旁 backups 文件夹；日志：logs 文件夹。'),
            ('Recovery incomplete', '恢复未完成，请保留并查看 logs 文件夹中的日志。'),
            ('If startup or backup', '启动或备份失败时尚未擦写固件，可检查线缆和接口后重试。'),
            ('Write not verified', '写入未验证成功：不要断电或拔线，请保留日志并重新恢复。'),
            ('!!! The firmware', '固件验证失败：不要断电或拔线，请保留日志并重新恢复。'),
            ('ERROR:', '操作失败，请保留日志；如已开始擦写，请勿断电。'),
            ('Operation failed', '操作失败，请保留 logs 文件夹中的错误日志。'),
            ('Simulation passed', '模拟恢复成功，未访问真实硬件。'),
            ('Simulation:', '模拟模式，不访问真实设备。'),
            ('Network blocking', '离线网络阻止检查通过。'),
            ('Cancelled.', '已取消。'),
        ]
        line = line.strip()
        for prefix, translated in mappings:
            if line.startswith(prefix):
                return translated
        return ''  # full technical details remain available in logs and English view

    def render_history(self):
        lines = self.history if self.lang == 'en' else [self.chinese(s) for s in self.history]
        self.terminal.setPlainText('\n'.join(s for s in lines if s))
        self.terminal.verticalScrollBar().setValue(self.terminal.verticalScrollBar().maximum())

    def receive(self):
        data = self.decoder.decode(bytes(self.proc.readAllStandardOutput()))
        self.partial += data.replace('\r', '\n')
        if 'Type V15 to start' in self.partial:
            self.pending = True
        chunks = self.partial.split('\n')
        self.history.extend(chunks[:-1])
        self.partial = chunks[-1]
        if 'Type V15 to start' in self.partial:
            self.history.append(self.partial)
            self.partial = ''
        self.render_history()

    def prepare(self):
        if self.proc.state() != QProcess.ProcessState.NotRunning:
            return
        self.active = self.pending = False
        self.history, self.partial = [], ''
        self.decoder.reset()
        env = QProcessEnvironment.systemEnvironment()
        env.insert('FM1_GUI_PIPE', '1')
        base = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else ROOT
        env.insert('FM1_GUI_WORK_DIR', str(base))
        self.proc.setProcessEnvironment(env)
        self.proc.setWorkingDirectory(str(base))
        args = ['--lang', 'en', '--no-pause']
        if self.simulate:
            args += ['--self-test']
        if getattr(sys, 'frozen', False):
            self.proc.start(str(ROOT / 'backend/FM-1 Recovery Tool.exe'), args)
        else:
            self.proc.start(sys.executable, [str(ROOT / 'offline_recover.py'), *args])
        self.apply_language()

    def submit(self):
        if self.active:
            return
        if self.entry.text().strip().casefold() != 'v15':
            self.entry.clear()
            self.entry.setPlaceholderText(self.text('Enter V15 to confirm', '请输入 V15 确认'))
            return
        if not self.pending:
            return
        self.active, self.pending = True, False
        self.proc.write(b'V15\n')
        self.entry.clear()
        self.entry.setEnabled(False)
        self.update()

    def finished(self, code, status):
        self.receive()
        if self.partial:
            self.history.append(self.partial); self.partial = ''
        self.active = self.pending = False
        self.apply_language()

    def process_error(self, error):
        self.history.append('Operation failed: ' + self.proc.errorString())
        self.render_history()

    def closeEvent(self, event):
        if self.active:
            self.entry.setPlaceholderText(self.text('Recovery running — keep the app open', '恢复中，请保持窗口打开'))
            event.ignore()
            return
        if self.proc.state() != QProcess.ProcessState.NotRunning:
            self.proc.kill()
            self.proc.waitForFinished(1000)
        event.accept()


def main():
    smoke = '--smoke-test' in sys.argv
    if smoke:
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    app = QApplication(sys.argv)
    window = RecoveryWindow(simulate=smoke or '--demo' in sys.argv)
    window.show()
    if smoke:
        def check():
            if window.proc.state() != QProcess.ProcessState.NotRunning:
                QTimer.singleShot(100, check)
                return
            ok = any('Simulation passed' in s for s in window.history)
            if ok:
                window.grab().save('gui-smoke-english.png')
                window.lang = 'zh'; window.apply_language()
                ok = '模拟恢复成功' in window.terminal.toPlainText()
                window.grab().save('gui-smoke-chinese.png')
            Path('gui-smoke-result.txt').write_text('PASS' if ok else '\n'.join(window.history), encoding='utf-8')
            window.close()
            app.exit(0 if ok else 1)
        QTimer.singleShot(1000, check)
        QTimer.singleShot(30000, lambda: app.exit(2))
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())

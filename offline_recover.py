"""FM-1 Recovery Tool — offline V15 recovery.
Credits: https://www.reddit.com/r/MVaveFM1/s/lUaXiCsOk8
Firmware source: https://github.com/m-vave/fm1_open
Backend: MvaveFM1Unbricker (MIT); jl-uboot-tool (MIT).
"""
import argparse
import ctypes
import logging
import os
import re
import time
from pathlib import Path
import subprocess
import sys
import traceback

if os.environ.get('FM1_GUI_PIPE') == '1':
    for stream in (sys.stdout, sys.stderr):
        if stream is not None:
            stream.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / 'upstream'))
import fm1_unbrick as fm


LANGUAGE = 'en'


def localize(text):
    """Select one side of the launcher's paired messages."""
    if not re.search(r'[\u4e00-\u9fff]', text):
        return text
    if text.startswith('FM-1 Recovery Tool\n'):
        return 'FM-1 Recovery Tool\n' + ('官方 V15 离线恢复\n' if LANGUAGE == 'zh' else 'Offline official V15 recovery\n')
    if ' / ' in text:
        zh, en = text.split(' / ', 1)
    elif '\n' in text.strip():
        zh, en = text.strip().split('\n', 1)
    else:
        return text
    return zh if LANGUAGE == 'zh' else en


def show(*values, **kwargs):
    print(*(localize(v) if isinstance(v, str) else v for v in values), **kwargs)


def ask(prompt):
    return input(localize(prompt))


def choose_language():
    print('1. English\n2. 中文')
    while True:
        choice = input('Select / 请选择 [1/2]: ').strip()
        if choice in ('1', '2'):
            return 'en' if choice == '1' else 'zh'
        print('Enter 1 or 2 / 请输入 1 或 2')


class LanguageProgress(logging.Formatter):
    """Pair operational backend messages with Chinese; retain original diagnostics."""
    translations = {
        'Step 1/6: package': '步骤 1/6：校验固件包',
        'Step 2/6: device': '步骤 2/6：检查设备',
        'Step 3/6: backup': '步骤 3/6：完整双读备份',
        'Step 4/6: confirmation': '步骤 4/6：确认恢复',
        'Step 5/6: write': '步骤 5/6：写入及验证，期间不要断电或拔线',
        'Step 6/6: restored': '步骤 6/6：恢复成功，已逐字节验证',
        'Device startup attempt': '设备启动尝试（最多两次）',
        'USB settling:': '等待 USB 稳定：5 秒',
        'RAM loader settling:': '等待 RAM loader 稳定：1 秒',
        'Startup USB transport failed': '启动通信失败；关闭连接，等待 10 秒后重新扫描重试一次',
        'Opening device / starting RAM loader failed': '打开设备或启动 RAM loader 失败，尚未擦写固件',
        'USB loader uploaded and running': 'USB loader 已上传并启动',
        'Backing up the whole flash': '完整 Flash 读取两次，比较一致后才能写入',
        'Backup OK': '完整备份已保存并校验',
        'The firmware region already holds exactly this firmware': '固件已与 V15 完全一致，跳过重复写入',
        'Write attempt': '开始擦除和写入固件区，请勿断电或拔线',
        'Verifying:': '回读固件并逐字节验证',
        '  byte-for-byte identical': '回读数据逐字节完全一致',
        'Retrying the write once': '回读不一致，重试写入一次',
        '  MISMATCH:': '回读数据不一致',
        'Done. Now:': '已完成：拔 USB → 关机 → 等待 5 秒 → 开机',
        '!!! The firmware region could not be verified.': '固件验证失败！不要断电或拔线；保留备份并重新恢复',
        'ERROR:': '操作失败，请保留日志；如已开始擦写，请勿断电',
        'Log:': '日志文件',
        'Everything from this run is in one folder:': '本次运行文件夹（请保留）',
    }

    def format(self, record):
        original = record.getMessage()
        if LANGUAGE == 'en':
            return original
        for prefix, chinese in self.translations.items():
            if original.lstrip('\n').startswith(prefix):
                return chinese
        # Detailed protocol messages remain in the full log, avoiding mixed-language UI.
        return ''


_setup_logging = fm.setup_logging


class ChineseConsoleFilter(logging.Filter):
    def filter(self, record):
        return LANGUAGE != 'zh' or any(record.getMessage().lstrip('\n').startswith(p)
                                       for p in LanguageProgress.translations)


def setup_localized_logging(*args, **kwargs):
    path = _setup_logging(*args, **kwargs)
    for handler in fm.log.handlers:
        if not isinstance(handler, logging.FileHandler):
            handler.setFormatter(LanguageProgress())
            handler.addFilter(ChineseConsoleFilter())
    return path


fm.setup_logging = setup_localized_logging

_Progress = fm.Progress


class LocalizedProgress(_Progress):
    def __init__(self, label, total):
        if LANGUAGE == 'zh':
            label = {'Backup read 1/2': '备份读取 1/2', 'Backup read 2/2': '备份读取 2/2',
                     'Verify': '回读验证', 'Erasing': '擦除中', 'Writing': '写入中',
                     'Reading': '读取中'}.get(label, '处理中')
        super().__init__(label, total)

    def close(self):
        if self.tty:
            sys.stderr.write('\r  %-24s %s\n' % (self.label, '完成' if LANGUAGE == 'zh' else 'done'))
            sys.stderr.flush()


fm.Progress = LocalizedProgress


def offline_guard(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo', 'socket.connect_ex'):
        raise RuntimeError('此恢复程序禁止网络访问 / Network disabled')


sys.addaudithook(offline_guard)


def send_boot_key(rt=None):
    """Output-only SysEx, like the Hub button; no input port or identity handshake."""
    if rt is None:
        import rtmidi as rt
    output = rt.MidiOut()
    try:
        names = list(output.get_ports())
        show('MIDI 输出端口 / MIDI output ports:', names)
        candidates = [(i, n) for i, n in enumerate(names)
                      if re.search(r'fm[\s_-]*1|felucca|sloop|clipper|etch|jiant|ota|update|composite|sinco|usb-midi', n, re.I)]
        if not candidates:
            raise RuntimeError('没有找到 FM-1 MIDI 输出端口，请关闭其他 MIDI 软件后重试。 / No FM-1 MIDI output. Close other MIDI apps and retry.')
        if len(candidates) != 1:
            raise RuntimeError('找到多个 FM-1 MIDI 输出端口，请只连接一台设备。 / Multiple matching MIDI outputs. Connect only one device.')
        index, name = candidates[0]
        output.open_port(index)
        output.send_message(list(fm.SOFT_KEY))
        time.sleep(0.2)  # allow WinMM to finish the SysEx before releasing the port
        show('已发送启动指令 / Boot key sent:', name, 'F0 22 24 35 7D F7')
        show('等待 UBOOT 设备出现 / Waiting for the UBOOT device.')
    finally:
        try:
            output.close_port()
        finally:
            output.delete()


def confirm_v15(value):
    return value.strip().casefold() == 'v15'


def run():
    global LANGUAGE
    parser = argparse.ArgumentParser(description='FM-1 Recovery Tool / 官方 V15 离线恢复 / Offline official V15 recovery')
    parser.add_argument('--self-test', action='store_true', help='只模拟，不访问设备 / Simulate without accessing hardware')
    parser.add_argument('--no-pause', action='store_true')
    parser.add_argument('--lang', choices=['en', 'zh'], help='UI language (otherwise selected at startup)')
    args = parser.parse_args()
    LANGUAGE = args.lang or choose_language()
    if args.self_test:
        import rtmidi  # verify the bundled native MIDI extension without opening ports
        import socket
        try:
            socket.getaddrinfo('offline-test.invalid', 443)
        except RuntimeError:
            show('网络访问阻止检查通过 / Network blocking check passed.')
        else:
            raise RuntimeError('Network guard failed')
    base = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else ROOT
    if os.environ.get('FM1_GUI_PIPE') == '1' and os.environ.get('FM1_GUI_WORK_DIR'):
        base = Path(os.environ['FM1_GUI_WORK_DIR']).resolve()
    os.chdir(base)
    if not args.self_test and not ctypes.windll.shell32.IsUserAnAdmin():
        if getattr(sys, 'frozen', False):
            params = subprocess.list2cmdline([*sys.argv[1:], '--lang', LANGUAGE])
            exe = sys.executable
        else:
            exe = sys.executable
            params = subprocess.list2cmdline([str(Path(__file__).resolve()), *sys.argv[1:], '--lang', LANGUAGE])
        result = ctypes.windll.shell32.ShellExecuteW(None, 'runas', exe, params, str(base), 1)
        if result <= 32:
            show('未获得管理员权限，无法访问恢复设备。 / Administrator permission was not granted.')
            return 1
        return 0

    show('FM-1 Recovery Tool\n官方 V15 离线恢复 / Offline official V15 recovery\n')
    show('模拟模式：不打开真实设备。 / Simulation: no real hardware access.' if args.self_test else
          '请只连接一台 FM-1，使用 USB 数据线，并关闭其他 MIDI 软件。\n'
          'Connect one FM-1 using a USB data cable. Close browser updaters, DAWs and other MIDI apps.')
    show('如 Windows 提示格式化磁盘，请取消。 / Cancel any Windows disk-format prompt.')
    show('流程：校验 V15 → 切换 UBOOT → 双读备份 → 写入 → 回读验证。\n'
          'Flow: validate V15 → enter UBOOT → double-read backup → write → verify.')
    show('仅恢复固件区 0x4000–0x92FFF；请保留备份。\n'
          'Only firmware region 0x4000–0x92FFF is restored. Keep your backup.\n')
    package = ROOT / 'FM-1_015.fwsc'
    pkg = fm.Package.load(package)
    if pkg.file_sha256 != fm.V15_FILE_SHA256 or pkg.kind != 'official-v15':
        raise RuntimeError('内置固件校验失败，已停止。 / Bundled firmware validation failed. Stopped.')
    jl = ROOT / 'upstream' / 'jl-uboot-tool'
    fm.verify_jlub(jl)
    fm.load_jlub(jl)  # fail on missing dependencies BEFORE entering boot mode
    show('内置官方 V15 和 USB loader 校验通过。 / Bundled official V15 and USB loader validated.')
    if not args.self_test:
        if not confirm_v15(ask('输入 V15 开始（大小写不限；先备份再恢复）。\nType V15 to start (case-insensitive; backup before restore): ')):
            show('已取消。 / Cancelled.')
            return 1
        devices = fm.find_devices()
        if len(devices) > 1:
            raise RuntimeError('检测到多台 UBOOT 设备，请只保留一台 FM-1。 / Multiple UBOOT devices. Connect only one FM-1.')
        if not devices:
            show('未检测到 UBOOT，尝试发送 MIDI 启动指令。 / No UBOOT device; sending the MIDI boot key.')
            send_boot_key()
            if not fm.wait_for_uboot(timeout=30):
                show('无法进入 UBOOT；没有写入固件。 / UBOOT not detected. No firmware was written.')
                return 1
    common = ['--jl-dir', str(jl)]
    if args.self_test:
        common += ['--dry-run']
        rc = fm.main(['softkey', '--yes', *common])
        if rc:
            return rc
    rc = fm.main(['restore', str(package), '--verify-v15', '--yes', *common])
    if rc == 0:
        show('\n模拟成功，未访问硬件。 / Simulation passed. No hardware accessed.' if args.self_test else
              '\nV15 固件区已验证。拔掉 USB → 关机 → 等 5 秒 → 开机。\n'
              'V15 firmware verified. Unplug USB → power off → wait 5 seconds → power on.')
        show('程序旁 backups 为完整备份，logs 为日志。 / Backups: ./backups; logs: ./logs (beside the EXE).')
    elif rc == 3:
        show('\n写入未验证成功：不要断电、不要拔线。保留日志并重新运行恢复。\n'
              'Write not verified: DO NOT power off or unplug. Keep logs and run recovery again.')
    else:
        show('\n恢复未完成，请查看 logs。 / Recovery incomplete. Check the error above and ./logs.')
        show('若在启动或备份阶段失败，本次尚未擦写固件，可换线或接口后重新运行。\n'
              'If startup or backup failed, no firmware erase/write has started; check the cable/port and retry.')
    return rc


if __name__ == '__main__':
    code = 1
    try:
        code = run()
    except Exception as exc:
        Path('logs').mkdir(exist_ok=True)
        with Path('logs/launcher-error.log').open('a', encoding='utf-8') as error_log:
            traceback.print_exc(file=error_log)
        show(localize(str(exc)))
        show('\n操作失败，请保留以上错误信息。 / Operation failed. Keep the error information above.')
    finally:
        if '--no-pause' not in sys.argv:
            try:
                ask('\n按回车关闭窗口 / Press Enter to close...')
            except EOFError:
                pass
    sys.exit(code)

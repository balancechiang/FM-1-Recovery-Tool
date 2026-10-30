from pathlib import Path
import os
root = Path(SPECPATH)
debug_console = os.environ.get('FM1_GUI_DEBUG') == '1'
a = Analysis([str(root / 'recovery_gui.py')], pathex=[str(root)],
             datas=[(str(root / 'assets/illustration.svg'), 'assets'),
                    (str(root / 'assets/SprayMindsMono-Regular.ttf'), 'assets'),
                    (str(root / 'dist/FM-1 Recovery Tool.exe'), 'backend')],
             hiddenimports=[], hookspath=[], runtime_hooks=[],
             excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
                       'PySide6.QtPdf', 'numpy', 'pymupdf'])
# Qt ships a newer compatible MSVC runtime than this Python installation.
# Use one runtime version at the extraction root before CPython loads it.
qt_dir = root / '.venv/Lib/site-packages/PySide6'
a.binaries = [(dest, str(qt_dir / Path(dest).name), kind)
              if dest.upper() in ('VCRUNTIME140.DLL', 'VCRUNTIME140_1.DLL')
              and (qt_dir / Path(dest).name).is_file() else (dest, src, kind)
              for dest, src, kind in a.binaries]
# Build-host PATH contains an unrelated old UCRT; Windows 10/11 provides UCRT.
a.binaries = [(dest, src, kind) for dest, src, kind in a.binaries
              if Path(dest).name.lower() != 'ucrtbase.dll'
              and not Path(dest).name.lower().startswith('api-ms-win-')
              and '.cache\\codex-runtimes' not in src.lower()]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='FM-1 Recovery Tool',
          debug=False, strip=False, upx=False, console=debug_console, uac_admin=not debug_console)

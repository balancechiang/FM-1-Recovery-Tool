"""Prepare clean binary/source archives; exclude device backups and logs."""
from pathlib import Path
import hashlib
import importlib.metadata
import shutil
import zipfile

root = Path(__file__).resolve().parent
release = root / 'release-gui' / 'FM-1 Recovery Tool'
release.mkdir(parents=True, exist_ok=True)
shutil.copy2(root / 'gui-dist/FM-1 Recovery Tool.exe', release)
shutil.copy2(root / 'README-Recovery.md', release / 'README.md')
shutil.copy2(root / 'LICENSE-Recovery.txt', release / 'LICENSE.txt')
licenses = release / 'licenses'
licenses.mkdir(exist_ok=True)
shutil.copy2(root / 'upstream/LICENSE', licenses / 'MvaveFM1Unbricker.txt')
shutil.copy2(root / 'upstream/jl-uboot-tool/LICENSE', licenses / 'jl-uboot-tool.txt')
for package in ('python-rtmidi', 'crcmod', 'PyYAML', 'tqdm', 'colorama'):
    dist = importlib.metadata.distribution(package)
    for entry in dist.files or ():
        if 'license' in entry.name.lower() or 'copying' in entry.name.lower():
            path = Path(dist.locate_file(entry))
            if path.is_file():
                dest = licenses / package / entry.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dest)
for name in ('SprayMindsMono-OFL.txt', 'SprayMindsMono-README.md', 'LGPL-3.0-only.txt', 'GPL-3.0-only.txt'):
    shutil.copy2(root / 'assets' / name, licenses / name)
python_license = Path(__import__('sys').base_prefix) / 'LICENSE.txt'
if python_license.is_file():
    shutil.copy2(python_license, licenses / 'Python-LICENSE.txt')

def zip_files(target, files):
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path, name in files:
            archive.write(path, name)

zip_files(root / 'FM-1 Recovery Tool.zip',
          ((p, 'FM-1 Recovery Tool/' + p.relative_to(release).as_posix())
           for p in release.rglob('*') if p.is_file()))

files = []
for name in ('offline_recover.py', 'FM1-V15-Offline.spec', 'FM-1_015.fwsc',
             'build-requirements.txt', 'test_boot_key.py', 'test_read_failure.py',
             'validate_backend.py', 'package_release.py', 'recovery_gui.py', 'verify_gui.py',
             'FM1-GUI.spec', 'gui-requirements.txt'):
    files.append((root / name, 'FM-1 Recovery Tool Source/' + name))
for src, dest in (('README-Recovery.md', 'README.md'), ('LICENSE-Recovery.txt', 'LICENSE.txt')):
    files.append((root / src, 'FM-1 Recovery Tool Source/' + dest))
for tree in (root / 'upstream', licenses, root / 'assets'):
    for p in tree.rglob('*'):
        rel = p.relative_to(tree)
        if not p.is_file() or any(x in ('.git', '__pycache__') for x in rel.parts):
            continue
        if p.suffix in ('.pyc', '.pyo'):
            continue
        if tree.name == 'assets' and p.suffix == '.png':
            continue
        prefix = tree.name
        files.append((p, 'FM-1 Recovery Tool Source/' + prefix + '/' + rel.as_posix()))
zip_files(root / 'FM-1 Recovery Tool Source.zip', files)
for name in ('FM-1 Recovery Tool.zip', 'FM-1 Recovery Tool Source.zip'):
    path = root / name
    print(name, path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest())

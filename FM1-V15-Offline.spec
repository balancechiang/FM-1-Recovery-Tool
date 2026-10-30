from pathlib import Path
root = Path(SPECPATH)
jl = root / 'upstream' / 'jl-uboot-tool'
datas = [(str(root / 'FM-1_015.fwsc'), '.'),
         (str(root / 'upstream' / 'LICENSE'), 'licenses/MvaveFM1Unbricker')]
for folder in ('jltech', 'scsiio', 'data'):
    datas.append((str(jl / folder), 'upstream/jl-uboot-tool/' + folder))
datas += [(str(jl / '.fm1-unbrick-commit'), 'upstream/jl-uboot-tool'),
          (str(jl / 'LICENSE'), 'licenses/jl-uboot-tool')]
a = Analysis([str(root / 'offline_recover.py')],
             pathex=[str(root / 'upstream'), str(jl)], datas=datas,
             hiddenimports=['rtmidi', 'yaml', 'crcmod', 'tqdm',
                            'jltech.uboot', 'jltech.cipher',
                            'scsiio.win32port', 'scsiio.common'],
             hookspath=[], runtime_hooks=[], excludes=[])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [],
          name='FM-1 Recovery Tool', debug=False, strip=False, upx=False, console=True)

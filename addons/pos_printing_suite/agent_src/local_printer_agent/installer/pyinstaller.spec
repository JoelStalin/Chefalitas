# -*- mode: python ; coding: utf-8 -*-
# Build: pyinstaller pyinstaller.spec
# Use onedir (not onefile) for Windows service stability.

import os
try:
    specdir = os.path.dirname(os.path.abspath(SPECPATH))
except NameError:
    specdir = os.path.abspath(os.path.join(os.getcwd(), "installer"))
agent_dir = os.path.normpath(os.path.join(specdir, ".."))
if not os.path.isfile(os.path.join(agent_dir, "run_agent.py")):
    if os.path.isfile(os.path.join(specdir, "run_agent.py")):
        agent_dir = specdir
    else:
        cwd = os.getcwd()
        if os.path.isfile(os.path.join(cwd, "run_agent.py")):
            agent_dir = cwd

a = Analysis(
    [os.path.join(agent_dir, 'run_agent.py')],
    pathex=[agent_dir],
    binaries=[],
    datas=[],
    hiddenimports=[
        'win32timezone',
        'win32print',
        'win32api',
        'win32serviceutil',
        'win32service',
        'win32event',
        'servicemanager',
        'PIL',
        'PIL.Image',
        'PIL.ImageWin',
        'fitz',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LocalPrinterAgent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LocalPrinterAgent',
)

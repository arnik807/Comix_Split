# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec: python -m PyInstaller packaging/comicsplit.spec

import sys
from pathlib import Path

block_cipher = None
root = Path(SPECPATH).resolve().parent

a = Analysis(
    [str(root / 'main.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(root / 'config.yaml'), '.'),
        (str(root / 'models' / 'yolo_comic_int8.onnx'), 'models'),
        (str(root / 'models' / 'mobilesam_encoder_int8.onnx'), 'models'),
        (str(root / 'models' / 'mobilesam_decoder_int8.onnx'), 'models'),
    ],
    hiddenimports=['onnxruntime', 'cv2', 'yaml', 'gradio'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ComicSplit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

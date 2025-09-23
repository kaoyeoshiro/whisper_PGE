# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_data_files

# Essential data files only
datas = [
    ('app/version.json', 'app'),
]

# Exclude unnecessary modules to reduce size
excludes = [
    # Exclude heavy libraries that we don't need pre-installed
    'torch', 'torchaudio', 'torchvision', 'whisper',
    'numpy', 'scipy', 'pandas', 'matplotlib', 'PIL', 'cv2',
    # GUI libraries we don't use
    'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx',
    # Development/testing tools
    'test', 'unittest', 'doctest', 'pdb', 'difflib', 'sqlite3',
    'xml', 'email', 'urllib3', 'setuptools', 'distutils',
    'curses', 'readline', 'ctypes.test', 'lib2to3',
    # Concurrency libs we don't need bundled
    'multiprocessing', 'concurrent.futures', 'asyncio',
    # Other heavy modules (but NOT psutil - we need it)
    'certifi', 'charset_normalizer', 'idna', 'requests'
]

# Only essential hidden imports (built-in modules)
hiddenimports = [
    'tkinter', 'tkinter.ttk', 'tkinter.filedialog',
    'tkinter.messagebox', 'tkinter.scrolledtext',
    'psutil'
]

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=2,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='WhisperPGE-Installer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,  # Compress the executable
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    optimize=2,
)
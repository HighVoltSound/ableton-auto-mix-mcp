# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for MusicMixCode backend sidecar."""

import os, sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
ROOT = os.path.abspath('.')

# Collect only what we need
uvicorn_imports = collect_submodules('uvicorn')

a = Analysis(
    [os.path.join(ROOT, 'scripts', 'backend_entry.py')],
    pathex=[os.path.join(ROOT, 'src')],
    binaries=[],
    datas=[
        (os.path.join(ROOT, 'src', 'ableton_auto_mix', 'styles'), os.path.join('ableton_auto_mix', 'styles')),
    ],
    hiddenimports=[
        'ableton_auto_mix',
        'ableton_auto_mix.api_app',
        'ableton_auto_mix.analyzer',
        'ableton_auto_mix.mixer',
        'ableton_auto_mix.preview',
        'ableton_auto_mix.profiles',
        'ableton_auto_mix.qa',
        'ableton_auto_mix.planner',
        'ableton_auto_mix.reference',
        # audio
        'soundfile',
        'pyloudnorm',
        'soxr',
        # numpy/scipy
        'numpy', 'numpy.core', 'numpy.core._methods', 'numpy.lib', 'numpy.lib.format',
        'scipy', 'scipy.signal',
        # web
        'fastapi', 'fastapi.middleware.cors',
        'uvicorn', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto',
        'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto',
        'uvicorn.lifespan', 'uvicorn.lifespan.on',
        'starlette', 'starlette.routing', 'starlette.middleware', 'starlette.responses',
        'click', 'click.core',
        # librosa deps
        'audioread', 'audioread.global_setup',
        'joblib',
        'decorator',
        'poissonsonlib',
        'threadpoolctl',
    ] + uvicorn_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
        'pytest', '_pytest', 'pluggy',
        'IPython', 'ipykernel', 'jupyter', 'notebook',
        'jedi', 'parso',
        'sklearn', 'sklearn.utils', 'sklearn.exceptions',
        'PIL', 'PIL.Image',
        'lxml', 'lxml.etree', 'lxml.html',
        'pywin32', 'win32com', 'win32com.client', 'win32api', 'win32gui',
        'numba', 'numba.core', 'numba.cuda',
        'llvmlite', 'llvmlite.binding',
        'torch', 'torchvision', 'torchaudio',
        'cv2', 'cv2.cv2',
        'setuptools', 'pip', 'pkg_resources',
        'doctest', 'pdb', 'profile', 'cProfile',
        'distutils',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='musicmixcode-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='musicmixcode-backend',
)

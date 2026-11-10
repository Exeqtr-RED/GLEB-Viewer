# -*- mode: python ; coding: utf-8 -*-
"""
Onefile-сборка GLEB Viewer.

В отличие от onedir-режима, здесь EXE включает все binaries и datas.
Результат — один файл GLEB_Viewer.exe (Windows) / GLEB_Viewer (Linux),
который при запуске распаковывает себя во временную папку.
"""
from PyInstaller.utils.hooks import collect_data_files

datas = [('themes', 'themes'), ('hdri', 'hdri'), ('icons', 'icons')]
datas += collect_data_files('f3d')
datas += collect_data_files('PySide6')


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['f3d'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# onefile: EXE получает a.binaries и a.datas напрямую,
# без отдельного COLLECT.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    exclude_binaries=False,  # ← onefile-режим
    name='GLEB_Viewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
)

# -*- mode: python ; coding: utf-8 -*-
"""
Onefile-сборка GLEB Viewer.

В отличие от onedir-режима, здесь EXE включает все binaries и datas.
Результат — один файл GLEB_Viewer.exe (Windows) / GLEB_Viewer (Linux),
который при запуске распаковывает себя во временную папку.

ВАЖНО про datas: PyInstaller на Windows в CI-среде иногда не подхватывает
относительные пути вида ('hdri', 'hdri'). Поэтому используем абсолютные
пути, вычисленные от местоположения этого spec-файла (через SPECPATH,
который PyInstaller подставляет автоматически).
"""
import os
from PyInstaller.utils.hooks import collect_data_files

# SPECPATH — это директория, где лежит .spec файл (PyInstaller передаёт
# её как глобальную переменную при выполнении spec). Если по какой-то
# причине она не задана — берём текущую директорию.
SPEC_DIR = SPECPATH if 'SPECPATH' in globals() else os.getcwd()

# Логируем для отладки — попадёт в вывод PyInstaller
print(f"[spec] SPECPATH = {SPEC_DIR!r}")
print(f"[spec] os.path.abspath('.') = {os.path.abspath('.')!r}")

# Абсолютные пути к ресурсам проекта — гарантированно работают в любой среде
themes_src = os.path.join(SPEC_DIR, 'themes')
hdri_src = os.path.join(SPEC_DIR, 'hdri')
icons_src = os.path.join(SPEC_DIR, 'icons')

# Проверяем, что папки существуют, и логируем
for name, path in [('themes', themes_src), ('hdri', hdri_src), ('icons', icons_src)]:
    exists = os.path.isdir(path)
    print(f"[spec] {name}: {path!r} (exists={exists})")
    if not exists:
        raise SystemExit(
            f"[spec] ОШИБКА: папка {name!r} не найдена по пути {path!r}. "
            f"PyInstaller не сможет собрать .exe с ресурсами. "
            f"Проверь, что spec-файл лежит в корне проекта рядом с папками "
            f"themes/, hdri/, icons/."
        )

datas = [
    (themes_src, 'themes'),
    (hdri_src, 'hdri'),
    (icons_src, 'icons'),
]
datas += collect_data_files('f3d')
datas += collect_data_files('PySide6')


a = Analysis(
    ['main.py'],
    pathex=[SPEC_DIR],
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

# onefile: EXE получает a.binaries и a.datas напрямую, без отдельного COLLECT.
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

"""
Общие утилиты GLEB Viewer.
"""

import os
import sys


def resource_path(relative_path: str) -> str:
    """Путь к ресурсу: работает и в Python, и в PyInstaller bundle."""
    if hasattr(sys, 'frozen'):
        base = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)

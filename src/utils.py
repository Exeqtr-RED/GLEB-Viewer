"""
Общие утилиты GLEB Viewer.
"""

import logging
import os
import sys

log = logging.getLogger(__name__)


def _candidate_resource_bases() -> list[str]:
    """Вернуть список кандидатных базовых директорий для ресурсов."""
    candidates = []
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        candidates.append(meipass)
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates.append(exe_dir)
    candidates.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    seen = set()
    uniq = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq


def resource_path(relative_path: str) -> str:
    """Путь к ресурсу: работает и в Python, и в PyInstaller bundle."""
    bases = _candidate_resource_bases()
    if not bases:
        return relative_path
    for base in bases:
        full = os.path.join(base, relative_path)
        if os.path.exists(full):
            log.debug(f"resource_path: {relative_path!r} -> {full!r} (exists)")
            return full
    fallback = os.path.join(bases[0], relative_path)
    log.warning(
        f"resource_path: {relative_path!r} не найден ни в одном из "
        f"кандидатов {bases!r}, возвращаю fallback {fallback!r}"
    )
    return fallback
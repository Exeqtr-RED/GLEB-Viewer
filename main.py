"""
GLEB Viewer — F3D Embedded Edition
Нативное встраивание F3D 3.5.0 в PySide6 через offscreen рендеринг.
"""

import logging
import os
import sys
import traceback

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from src.main_window import MainWindow
from src.utils import resource_path

log = logging.getLogger(__name__)


def _log_file_path() -> str:
    """Путь к файлу логов: рядом с .exe в frozen-режиме, либо в
    корне проекта в dev-режиме."""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "GLEB_Viewer.log")


def _setup_logging() -> None:
    """Логи пишутся в stderr И в файл GLEB_Viewer.log рядом с .exe."""
    level = logging.DEBUG if os.environ.get("GLEB_DEBUG") == "1" else logging.INFO
    fmt = logging.Formatter(
        fmt="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    root = logging.getLogger()
    root.setLevel(level)
    for h in list(root.handlers):
        root.removeHandler(h)
    stderr_handler = logging.StreamHandler()
    stderr_handler.setFormatter(fmt)
    root.addHandler(stderr_handler)
    try:
        file_handler = logging.FileHandler(_log_file_path(), encoding="utf-8")
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
        log.info(f"Лог-файл: {_log_file_path()}")
    except (OSError, PermissionError) as e:
        log.warning(f"Не удалось открыть файл лога {_log_file_path()}: {e}")


def _install_excepthook() -> None:
    def hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        log.error("Необработанное исключение:\n%s", tb_str)
        sys.__excepthook__(exc_type, exc_value, exc_tb)
    sys.excepthook = hook


def main():
    _setup_logging()
    _install_excepthook()
    log.info("=== GLEB Viewer запущен ===")
    log.info(f"sys.frozen: {getattr(sys, 'frozen', False)}")
    log.info(f"sys.executable: {sys.executable!r}")
    if hasattr(sys, '_MEIPASS'):
        log.info(f"sys._MEIPASS: {sys._MEIPASS!r}")
    log.info(f"CWD: {os.getcwd()!r}")

    app = QApplication(sys.argv)
    app.setApplicationName("GLEB Viewer")
    app.setApplicationVersion("2.0")

    icon_path = resource_path("icon.ico")
    log.info(f"icon_path: {icon_path!r}, exists={os.path.isfile(icon_path)}")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    if os.path.isfile(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

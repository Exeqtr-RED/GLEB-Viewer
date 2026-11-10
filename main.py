"""
GLEB Viewer — F3D Embedded Edition
Нативное встраивание F3D 3.5.0 в PySide6 через offscreen рендеринг.
"""

import logging
import os
import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from src.main_window import MainWindow
from src.utils import resource_path


def _setup_logging() -> None:
    """Настроить логирование.

    Уровень INFO по умолчанию, DEBUG — если задана переменная окружения
    GLEB_DEBUG=1. Формат: «время уровень [модуль] сообщение».
    """
    level = logging.DEBUG if os.environ.get("GLEB_DEBUG") == "1" else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def main():
    _setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("GLEB Viewer")
    app.setApplicationVersion("2.0")

    # Иконка программы
    icon_path = resource_path("icon.ico")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    if os.path.isfile(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

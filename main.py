"""
GLEB Viewer — F3D Embedded Edition
Нативное встраивание F3D 3.5.0 в PySide6 через offscreen рендеринг.
"""

import os
import sys

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from src.main_window import MainWindow
from src.utils import resource_path


def main():
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

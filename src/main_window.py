"""
Главное окно GLEB Viewer — F3D Embedded Edition.
QSplitter: дерево моделей слева, просмотр справа.
"""

import os

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFileDialog,
    QMessageBox, QSplitter, QProgressDialog, QInputDialog,
    QLabel, QScrollArea, QSizePolicy,
)
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import (
    QAction, QActionGroup, QKeySequence,
    QDropEvent, QDragEnterEvent, QPixmap, QIcon,
)
from PySide6.QtWidgets import QApplication

from src.f3d_widget import F3DWidget
from src.model_tree import ModelTree
from src.settings_dialog import F3DSettingsDialog
from src.utils import resource_path


# Путь к папке с темами
THEMES_DIR = resource_path("themes")

# Путь к папке с HDRI картами
HDRI_DIR = resource_path("hdri")

# Путь к папке с иконками
ICONS_DIR = resource_path("icons")

# Соответствие: имя папки (любое место в пути) -> имя HDRI файла
CATEGORY_HDRI: dict[str, str] = {
    "kosmos":   "space.hdr",
    "voda":     "lakeside_4k.hdr",
    "vozduh":   "sky_4k.hdr",
    "zemlya":   "land_4k.hdr",
}

# Доступные темы: имя → файл
THEMES = {
    "По умолчанию": None,  # без темы
    "Тёмная": "dark_theme.qss",
    "Светлая": "light_theme.qss",
    "Синяя": "blue_theme.qss",
    "Astra Deep": "astra_deep.qss",
    "Astra Z.ai": "astra_z.qss",
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GLEB Viewer — F3D Embedded")
        self.setMinimumSize(1024, 768)
        self.resize(1280, 900)

        # Настройки (запоминание папки и т.д.)
        self._settings = QSettings("GLEB_Viewer", "GLEB_Viewer")
        self._last_dir: str = self._settings.value("last_directory", "", type=str)  # type: ignore[assignment]
        self._current_theme_name: str = self._settings.value("theme", "По умолчанию", type=str)  # type: ignore[assignment]
        self._font_size: int = self._settings.value("font_size", 9)  # type: ignore[assignment]
        self._menu_font_size: int = self._settings.value("menu_font_size", 9)  # type: ignore[assignment]

        self._setup_ui()
        self._setup_menu()
        self._setup_statusbar()
        self._setup_connections()

        # Применить сохранённую тему
        self._apply_theme(self._current_theme_name)

        # Применить сохранённый размер шрифта
        self._set_font_size(self._font_size)
        self._set_menu_font_size(self._menu_font_size)

        self.setAcceptDrops(True)

        # Автозагрузка моделей из последней папки
        if self._last_dir and os.path.isdir(self._last_dir):
            self._scan_and_load_directory(self._last_dir)
            # set_hide_reference сработает через toggled при setChecked в _setup_menu
            self.statusBar().showMessage(
                f"Загружено из: {self._last_dir}"
            )
        else:
            self.statusBar().showMessage(
                "Готов. Настройки → Открыть папку"
            )

    # ─── UI ───────────────────────────────────────────────────────

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.splitter)

        # Слева — дерево моделей
        self.model_tree = ModelTree()
        self.splitter.addWidget(self.model_tree)

        # Справа — F3D просмотр
        self.f3d_widget = F3DWidget()
        self.splitter.addWidget(self.f3d_widget)

        # Оверлей для превью/галереи (поверх f3d_widget)
        self._preview_container = QWidget(self.f3d_widget)
        self._preview_container.setStyleSheet("background: #1a1a1a;")
        self._preview_layout = QVBoxLayout(self._preview_container)
        self._preview_layout.setContentsMargins(8, 8, 8, 8)
        self._preview_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Одиночное превью
        self._preview_label = QLabel(self._preview_container)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._preview_layout.addWidget(self._preview_label)

        # Галерея reference (3 колонки)
        self._ref_scroll = QScrollArea(self._preview_container)
        self._ref_scroll.setWidgetResizable(True)
        self._ref_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._ref_gallery_widget = QWidget()
        self._ref_gallery_layout = QGridLayout(self._ref_gallery_widget)
        self._ref_gallery_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self._ref_gallery_layout.setSpacing(8)
        self._ref_gallery_layout.setContentsMargins(8, 8, 8, 8)
        self._ref_scroll.setWidget(self._ref_gallery_widget)
        self._preview_layout.addWidget(self._ref_scroll)
        self._ref_scroll.hide()

        # Оверлей для полного просмотра картинки из галереи
        self._full_view_container = QWidget(self._preview_container)
        self._full_view_container.setStyleSheet("background: #1a1a1a;")
        self._full_view_layout = QVBoxLayout(self._full_view_container)
        self._full_view_layout.setContentsMargins(0, 0, 0, 0)
        self._full_view_label = QLabel(self._full_view_container)
        self._full_view_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._full_view_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self._full_view_label.setStyleSheet("QLabel { background: #1a1a1a; }")
        self._full_view_layout.addWidget(self._full_view_label)
        self._full_view_container.hide()
        self._full_view_container.resize(self.f3d_widget.size())
        self._full_view_label.mousePressEvent = lambda event: self._hide_full_view()
        self._full_view_container.mousePressEvent = lambda event: self._hide_full_view()

        self._preview_container.hide()

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setSizes([250, 750])

    def _make_icon(self, name: str) -> QIcon:
        """Загрузить SVG иконку из папки icons."""
        path = os.path.join(ICONS_DIR, name)
        if os.path.isfile(path):
            return QIcon(path)
        return QIcon()

    def _setup_menu(self):
        menubar = self.menuBar()

        # ── Настройки (бывший Файл) ──
        settings_menu = menubar.addMenu(self._make_icon("settings.svg"), "Настройки")

        open_dir = QAction("Выбрать директорию моделей", self)
        open_dir.setShortcut(QKeySequence.StandardKey.Open)
        open_dir.triggered.connect(self._open_directory)
        settings_menu.addAction(open_dir)

        settings_menu.addSeparator()

        f3d_settings = QAction(self._make_icon("f3d.svg"), "Настройки F3D...", self)
        f3d_settings.triggered.connect(self._show_settings)
        settings_menu.addAction(f3d_settings)

        # ── Вид ──
        view_menu = menubar.addMenu(self._make_icon("theme.svg"), "Вид")

        # Подменю «Тема»
        theme_menu = view_menu.addMenu("Тема")
        self._theme_action_group = QActionGroup(self)
        self._theme_action_group.setExclusive(True)
        self._theme_actions = {}
        for theme_name in THEMES:
            action = QAction(theme_name, self, checkable=True)
            action.setChecked(theme_name == self._current_theme_name)
            action.triggered.connect(lambda checked, tn=theme_name: self._apply_theme(tn))
            self._theme_action_group.addAction(action)
            theme_menu.addAction(action)
            self._theme_actions[theme_name] = action

        # Подменю «Шрифт дерева»
        tree_font_menu = view_menu.addMenu("Шрифт дерева")
        self._font_action_group = QActionGroup(self)
        self._font_action_group.setExclusive(True)
        for pt in range(7, 15):
            act = QAction(f"{pt} пт", self, checkable=True)
            act.setChecked(pt == self._font_size)
            act.triggered.connect(lambda checked, p=pt: self._set_font_size(p))
            self._font_action_group.addAction(act)
            tree_font_menu.addAction(act)

        # Подменю «Шрифт меню»
        menu_font_menu = view_menu.addMenu("Шрифт меню")
        self._menu_font_action_group = QActionGroup(self)
        self._menu_font_action_group.setExclusive(True)
        for pt in range(7, 15):
            act = QAction(f"{pt} пт", self, checkable=True)
            act.setChecked(pt == self._menu_font_size)
            act.triggered.connect(lambda checked, p=pt: self._set_menu_font_size(p))
            self._menu_font_action_group.addAction(act)
            menu_font_menu.addAction(act)

        view_menu.addSeparator()

        hide_ref = QAction(self._make_icon("reference_folder.svg"), "Скрывать reference", self)
        hide_ref.setCheckable(True)
        hide_ref.toggled.connect(self._on_hide_ref_toggled)
        view_menu.addAction(hide_ref)
        self._hide_ref_action = hide_ref
        # Устанавливаем ПОСЛЕ подключения сигнала
        if self._settings.value("hide_reference", False, type=bool):  # type: ignore[assignment]
            hide_ref.setChecked(True)

        # ── Анимация ──
        anim_menu = menubar.addMenu(self._make_icon("animation.svg"), "Анимация")

        self._anim_play_act = QAction("Воспроизвести / Пауза", self)
        self._anim_play_act.setShortcut("Space")
        self._anim_play_act.triggered.connect(self._toggle_animation)
        anim_menu.addAction(self._anim_play_act)

        anim_stop = QAction("Остановить и сбросить", self)
        anim_stop.triggered.connect(self._stop_animation)
        anim_menu.addAction(anim_stop)

        anim_menu.addSeparator()

        speed_menu = anim_menu.addMenu("Скорость")
        self._speed_action_group = QActionGroup(self)
        self._speed_action_group.setExclusive(True)
        for spd in [0.25, 0.5, 1.0, 2.0, 4.0]:
            act = QAction(f"{spd}x", self, checkable=True)
            act.setChecked(spd == 1.0)
            act.triggered.connect(lambda checked, s=spd: self._set_anim_speed(s))
            self._speed_action_group.addAction(act)
            speed_menu.addAction(act)

        # ── Пакетный менеджер ──
        batch_menu = menubar.addMenu(self._make_icon("screenshot.svg"), "Пакетный менеджер")

        batch_screenshots = QAction("Создать скриншоты всех моделей", self)
        batch_screenshots.triggered.connect(self._batch_screenshots)
        batch_menu.addAction(batch_screenshots)

        # ── Справка ──
        help_menu = menubar.addMenu(self._make_icon("about.svg"), "Справка")
        about = QAction("О программе", self)
        about.triggered.connect(self._show_about)
        help_menu.addAction(about)

    def _setup_statusbar(self):
        self.statusBar()

    def _setup_connections(self):
        self.f3d_widget.scene_loaded.connect(self._on_model_loaded)
        self.f3d_widget.scene_cleared.connect(self._on_scene_cleared)
        self.f3d_widget.error_occurred.connect(self._on_error)
        self.f3d_widget.animation_state_changed.connect(self._on_animation_state_changed)

        self.model_tree.model_selected.connect(self._on_tree_select)
        self.model_tree.preview_requested.connect(self._on_preview_requested)
        self.model_tree.reference_gallery_requested.connect(self._on_reference_gallery)
        self.model_tree.tags_changed.connect(self._on_tags_changed)

    # ─── Действия ────────────────────────────────────────────────

    def _open_directory(self):
        start_dir = self._last_dir if self._last_dir else ""
        dirpath = QFileDialog.getExistingDirectory(
            self, "Выбрать директорию моделей", start_dir
        )
        if not dirpath:
            return

        self._settings.setValue("last_directory", dirpath)
        self._last_dir = dirpath

        # Очистить старый список перед загрузкой новой папки
        self.model_tree.clear_all()
        count = self._scan_and_load_directory(dirpath)
        self.statusBar().showMessage(f"Найдено моделей: {count} в {dirpath}")

    def _scan_and_load_directory(self, dirpath: str) -> int:
        """Рекурсивный поиск .glb файлов во всех подпапках."""
        found = []
        for root, dirs, files in os.walk(dirpath):
            for fname in sorted(files):
                ext = os.path.splitext(fname)[1].lower()
                if ext == ".glb":
                    found.append(os.path.join(root, fname))

        self.model_tree.add_models(found, root_dir=dirpath)
        return len(found)

    def _do_load_model(self, filepath: str):
        self.model_tree.add_models([filepath])
        self.f3d_widget.clear_scene()
        # HDRI ДО загрузки модели — f3d применяет окружение при scene.add()
        self._apply_hdri_by_path(filepath)
        self.f3d_widget.load_model(filepath)

        # Обновить корневую папку если ещё не задана
        if not self.model_tree.root_dir:
            self.model_tree.root_dir = os.path.dirname(filepath)
            self.model_tree.header.setText(f"Модели ({os.path.basename(os.path.dirname(filepath))})")

    def _hide_preview_overlay(self):
        self._full_view_container.hide()
        self._preview_container.hide()
        self._preview_label.show()
        self._ref_scroll.hide()

    def _show_preview_overlay(self):
        self._preview_container.setGeometry(0, 0, self.f3d_widget.width(), self.f3d_widget.height())
        self._preview_container.raise_()
        self._preview_container.show()

    def _on_tree_select(self, filepath: str):
        if filepath:
            self._hide_preview_overlay()
            self.f3d_widget.clear_scene()
            self._apply_hdri_by_path(filepath)
            self.f3d_widget.load_model(filepath)

    def _on_preview_requested(self, image_path: str):
        """Показать картинку превью поверх f3d виджета."""
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            print(f"[Preview] QPixmap isNull для: {image_path}")
            return
        self._full_view_container.hide()
        self._ref_scroll.hide()
        self._preview_label.show()
        self._preview_label.setPixmap(pixmap)
        self._preview_label.setScaledContents(True)
        self._show_preview_overlay()
        self.statusBar().showMessage(f"Превью: {os.path.basename(image_path)}")

    def _on_reference_gallery(self, folder_path: str):
        """Показать все картинки из папки reference как галерею в 3 колонки."""
        image_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".tif"}
        images = []
        try:
            for fname in sorted(os.listdir(folder_path)):
                if os.path.splitext(fname)[1].lower() in image_exts:
                    images.append(os.path.join(folder_path, fname))
        except OSError:
            return

        if not images:
            return

        # Очистить старые картинки из галереи
        while self._ref_gallery_layout.count():
            child = self._ref_gallery_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self._preview_label.hide()
        self._full_view_container.hide()
        self._ref_scroll.show()

        # Рисуем ячейки фиксированного размера в 3 колонки
        cols = 3
        available_w = self.f3d_widget.width() - 16
        available_h = self.f3d_widget.height() - 16
        cell_w = max((available_w - (cols - 1) * 8) // cols, 100)
        cell_h = max(int(cell_w * 0.66), 100)

        for idx, img_path in enumerate(images):
            row, col = divmod(idx, cols)
            frame = QWidget(self._ref_gallery_widget)
            frame.setFixedSize(cell_w, cell_h)
            frame.setStyleSheet("QWidget { background: #2a2a2a; border: 1px solid #444; border-radius: 4px; }")
            frame.setCursor(Qt.CursorShape.PointingHandCursor)
            frame.setToolTip(os.path.basename(img_path))
            fl = QVBoxLayout(frame)
            fl.setContentsMargins(4, 4, 4, 4)
            fl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl = QLabel(frame)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setScaledContents(False)
            lbl.setMinimumSize(1, 1)
            pixmap = QPixmap(img_path)
            if not pixmap.isNull():
                lbl.setPixmap(pixmap.scaled(
                    cell_w - 8, cell_h - 8,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
            fl.addWidget(lbl)
            lbl.mousePressEvent = lambda event, p=img_path, cv=self._show_full_view: cv(p)
            frame.mousePressEvent = lambda event, p=img_path, cv=self._show_full_view: cv(p)
            self._ref_gallery_layout.addWidget(frame, row, col)

        self._show_preview_overlay()
        self.statusBar().showMessage(f"Reference: {len(images)} изображений")

    def _show_full_view(self, image_path: str):
        """Показать картинку во весь экран (поверх галереи)."""
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            return
        self._full_view_label.setPixmap(pixmap.scaled(
            self._full_view_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))
        self._full_view_label.adjustSize()
        self._full_view_container.resize(self.f3d_widget.size())
        self._full_view_container.raise_()
        self._full_view_container.show()
        self.statusBar().showMessage(f"Reference: {os.path.basename(image_path)} — кликните чтобы закрыть")

    def _hide_full_view(self):
        """Скрыть полный просмотр картинки."""
        self._full_view_container.hide()

    def _on_hide_ref_toggled(self, checked: bool):
        """Сменить иконку, текст и скрыть/показать reference папки."""
        icon_name = "reference_folder_dis.svg" if checked else "reference_folder.svg"
        self._hide_ref_action.setIcon(self._make_icon(icon_name))
        self._hide_ref_action.setText("Отобразить reference" if checked else "Скрывать reference")
        self.model_tree.set_hide_reference(checked)
        self._settings.setValue("hide_reference", checked)
        self.statusBar().showMessage(f"Reference папки: {'скрыты' if checked else 'отображены'}")

    def _apply_hdri_by_path(self, filepath: str):
        """Определить категорию модели по пути и применить соответствующую HDRI."""
        # Разбираем путь на компоненты и ищем совпадение с категориями
        parts = os.path.normpath(filepath).lower().split(os.sep)
        hdri_name = None
        for part in parts:
            if part in CATEGORY_HDRI:
                hdri_name = CATEGORY_HDRI[part]
                break

        if hdri_name:
            hdri_path = os.path.join(HDRI_DIR, hdri_name)
            if os.path.isfile(hdri_path):
                self.f3d_widget.set_hdri(hdri_path)
                self.statusBar().showMessage(f"HDRI: {hdri_name}")
            else:
                print(f"[HDRI] Файл не найден: {hdri_path}")
        else:
            print(f"[HDRI] Нет маппинга для пути: {filepath}")

    def _reset_camera(self):
        self.f3d_widget.reset_camera()
        self.statusBar().showMessage("Камера сброшена")

    def _apply_theme(self, theme_name: str):
        """Применить тему по имени."""
        qss_file = THEMES.get(theme_name)
        if qss_file is None:
            self.setStyleSheet("")
        else:
            path = os.path.join(THEMES_DIR, qss_file)
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    qss = f.read()
                icons_dir = ICONS_DIR.replace("\\", "/")
                qss = qss.replace("url(icons/", f"url({icons_dir}/")
                self.setStyleSheet(qss)
            else:
                print(f"[Theme] Файл не найден: {path}")
                return
        self._current_theme_name = theme_name
        self._settings.setValue("theme", theme_name)
        print(f"[Theme] Тема: {theme_name}")

    def _set_font_size(self, pt: int):
        self._font_size = pt
        font = self.model_tree.tree.font()
        font.setPointSize(pt)
        self.model_tree.tree.setFont(font)
        self.model_tree.search_edit.setFont(font)
        self.model_tree.sort_combo.setFont(font)
        self.model_tree.sort_dir_btn.setFont(font)
        self.model_tree.btn_tags.setFont(font)
        self.model_tree.header.setFont(font)
        self.model_tree.lbl_count.setFont(font)
        self._settings.setValue("font_size", pt)
        self.statusBar().showMessage(f"Размер шрифта дерева: {pt} пт")

    def _set_menu_font_size(self, pt: int):
        self._menu_font_size = pt
        font = self.menuBar().font()
        font.setPointSize(pt)
        self.menuBar().setFont(font)
        self._settings.setValue("menu_font_size", pt)
        self.statusBar().showMessage(f"Размер шрифта меню: {pt} пт")

    def _show_settings(self):
        dialog = F3DSettingsDialog(self.f3d_widget, self)
        dialog.exec()

    # ─── Пакетный менеджер ──────────────────────────────────────

    def _batch_screenshots(self):
        """Создать скриншоты для всех моделей из дерева."""
        paths = self.model_tree.get_all_paths()
        if not paths:
            QMessageBox.information(self, "Пакетный менеджер",
                                    "Нет моделей для создания скриншотов.\n"
                                    "Сначала выберите директорию моделей.")
            return

        # Спросить размер
        sizes = {
            "512 x 512": (512, 512),
            "1024 x 1024": (1024, 1024),
            "2048 x 2048": (2048, 2048),
        }
        size_names = list(sizes.keys())
        size_name, ok = QInputDialog.getItem(
            self, "Размер скриншотов",
            "Выберите размер скриншотов:",
            size_names, 1, False
        )
        if not ok:
            return

        shot_size = sizes[size_name]
        total = len(paths)

        # Убеждаемся, что движок инициализирован
        if not self.f3d_widget.ensure_engine():
            QMessageBox.warning(self, "Ошибка", "Не удалось инициализировать F3D движок.")
            return

        progress = QProgressDialog(
            "Создание скриншотов...", "Отмена",
            0, total, self
        )
        progress.setWindowTitle("Пакетный менеджер")
        progress.setMinimumDuration(0)
        progress.setFixedWidth(400)

        saved = 0
        skipped = 0
        errors = 0
        error_list = []

        for i, filepath in enumerate(paths):
            if progress.wasCanceled():
                break

            name = os.path.splitext(os.path.basename(filepath))[0]
            preview_dir = os.path.join(os.path.dirname(filepath), "preview")
            os.makedirs(preview_dir, exist_ok=True)
            out_path = os.path.join(preview_dir, name + ".png")

            progress.setLabelText(f"{i + 1} / {total}\n{name}")
            progress.setValue(i)
            QApplication.processEvents()

            if progress.wasCanceled():
                break

            try:
                # Загрузить модель
                self.f3d_widget.clear_scene()
                self._apply_hdri_by_path(filepath)
                if not self.f3d_widget.load_model(filepath):
                    print(f"[Batch] Пропуск (не поддерживается): {filepath}")
                    skipped += 1
                    continue

                # Настроить камеру
                self.f3d_widget.reset_camera()

                # Сохранить скриншот
                if self.f3d_widget.render_to_file(out_path, size=shot_size):
                    saved += 1
                else:
                    errors += 1
                    error_list.append(f"{name}: ошибка сохранения")

                QApplication.processEvents()

            except Exception as e:
                errors += 1
                error_list.append(f"{name}: {e}")
                print(f"[Batch] Ошибка: {name} — {e}")

        progress.setValue(total)
        progress.close()

        # Восстановить UI: очистить сцену и отрендерить пустой кадр
        self.f3d_widget.clear_scene()

        # Итог
        msg = f"Сохранено: {saved}\nПропущено: {skipped}\nОшибок: {errors}"
        if error_list:
            msg += "\n\nОшибки:\n" + "\n".join(error_list[:20])
            if len(error_list) > 20:
                msg += f"\n... и ещё {len(error_list) - 20}"
        QMessageBox.information(self, "Пакетный менеджер — Готово", msg)

    # ─── Анимация ──────────────────────────────────────────────

    def _toggle_animation(self):
        self.f3d_widget.toggle_animation()

    def _stop_animation(self):
        self.f3d_widget.stop_animation()

    def _set_anim_speed(self, speed: float):
        self.f3d_widget.set_animation_speed(speed)

    def _on_animation_state_changed(self, playing: bool):
        state = "▶ Воспроизведение" if playing else "⏸ Пауза"
        speed_info = f" ({self.f3d_widget.animation_speed}x)" if playing else ""
        self.statusBar().showMessage(f"Анимация: {state}{speed_info}")

    # ─── Теги ─────────────────────────────────────────────────────

    def _on_tags_changed(self):
        self.statusBar().showMessage("Теги обновлены")

    def _show_about(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("О программе")
        msg.setText(
            "<h3>GLEB Viewer — F3D Embedded Edition</h3>"
            "<p>Версия 2.0</p>"
            "<p>F3D 3.5.0 + PySide6</p>"
            "<p><a href='https://f3d.app' style='color: #1c9dff; font-weight: bold;'>f3d.app</a></p>"
            "<p>Powered by Exeqtr <a href='https://my-3d-portfolio-beige.vercel.app/#contact' style='color: #1c9dff; font-weight: bold;'>contact</a></p>"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)  # Правильный синтаксис
        msg.button(QMessageBox.StandardButton.Ok).setFixedSize(100, 30)  # Правильный синтаксис
        msg.exec()

    # ─── Слоты ────────────────────────────────────────────────────

    def _on_model_loaded(self, filepath: str, _user_data):
        name = os.path.basename(filepath)
        self.statusBar().showMessage(f"Загружено: {name}")

    def _on_scene_cleared(self):
        self.statusBar().showMessage("Сцена очищена")

    def _on_error(self, message: str):
        self.statusBar().showMessage(f"Ошибка: {message}")
        QMessageBox.warning(self, "Ошибка", message)

    # ─── Drag & Drop ──────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            filepath = url.toLocalFile()
            if filepath:
                self._do_load_model(filepath)

    # ─── Close ────────────────────────────────────────────────────

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._preview_container.isVisible():
            self._preview_container.resize(self.f3d_widget.size())

    def closeEvent(self, event):
        self.f3d_widget.cleanup()
        super().closeEvent(event)

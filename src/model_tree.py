"""
Панель дерева моделей — иерархия: корень -> папки -> подпапки -> .glb модели.
Строка поиска с транслитерацией кириллицы в латиницу.
Сортировка по имени / размеру / дате.
Теги: управление через отдельное окно, вызываемое кнопкой.
Теги можно ставить папкам (применяются ко всем файлам внутри).
"""

import os
import re
import json
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QLabel, QAbstractItemView, QLineEdit, QMenu, QComboBox,
    QPushButton, QInputDialog, QHBoxLayout, QFrame, QSizePolicy,
    QDialog, QGroupBox, QScrollArea,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QAction, QPixmap


# ─── Таблица транслитерации ──────────────────────────────────────

_TRANSLIT_MULTI = {
    "а": ["a"], "б": ["b"], "в": ["v"], "г": ["g"], "д": ["d"],
    "е": ["e", "ye"], "ё": ["yo"], "ж": ["zh"], "з": ["z"],
    "и": ["i"], "й": ["y"], "к": ["k"], "л": ["l"], "м": ["m"],
    "н": ["n"], "о": ["o"], "п": ["p"], "р": ["r"], "с": ["s"],
    "т": ["t"], "у": ["u", "ou"], "ф": ["f", "ph"], "х": ["kh"],
    "ц": ["ts"], "ч": ["ch", "tch"], "ш": ["sh"], "щ": ["sch", "shch"],
    "ъ": [""], "ы": ["y"], "ь": [""], "э": ["e"],
    "ю": ["yu", "ju"], "я": ["ya", "ja"],
}

_REVERSE_TRANSLIT: dict[str, list[str]] = {}
for _cyr, _lat_variants in _TRANSLIT_MULTI.items():
    for _lat in _lat_variants:
        if not _lat:
            continue
        _REVERSE_TRANSLIT.setdefault(_lat, []).append(_cyr)


def transliterate(text: str) -> list[str]:
    lower = text.lower()
    if not any("\u0400" <= ch <= "\u04FF" for ch in lower):
        return [lower]
    variants = [""]
    for ch in lower:
        if ch in _TRANSLIT_MULTI:
            new_variants = []
            for prefix in variants:
                for lat in _TRANSLIT_MULTI[ch]:
                    new_variants.append(prefix + lat)
            variants = new_variants
        else:
            variants = [v + ch for v in variants]
    return variants


def expand_search_query(query: str) -> list[str]:
    lower = query.strip().lower()
    if not lower:
        return []
    has_cyrillic = any("\u0400" <= ch <= "\u04FF" for ch in lower)
    results = {lower}
    if has_cyrillic:
        for v in transliterate(lower):
            results.add(v)
    else:
        cyrillic_variants = _reverse_transliterate(lower)
        for v in cyrillic_variants:
            results.add(v)
    return list(results)


def _reverse_transliterate(text: str) -> list[str]:
    results = [text]
    sorted_keys = sorted(_REVERSE_TRANSLIT.keys(), key=len, reverse=True)

    def _greedy_replace(t: str) -> str:
        i = 0
        out = ""
        while i < len(t):
            matched = False
            for key in sorted_keys:
                if t[i:i + len(key)].lower() == key and key:
                    out += _REVERSE_TRANSLIT[key][0]
                    i += len(key)
                    matched = True
                    break
            if not matched:
                out += t[i]
                i += 1
        return out

    cyrillic = _greedy_replace(text)
    if cyrillic != text:
        results.append(cyrillic)
    return results


# ─── Окно управления тегами ───────────────────────────────────────

class TagManagerDialog(QDialog):
    """Отдельное окно для управления тегами."""

    def __init__(self, model_tree: "ModelTree", parent=None):
        super().__init__(parent)
        self._mt = model_tree
        self._suppress = False
        self.setWindowTitle("Управление тегами")
        self.setMinimumWidth(320)
        self.setMinimumHeight(360)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)

        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setSpacing(8)

        # ── Группа: текущий элемент ──
        grp_item = QGroupBox("Выделенный элемент")
        grp_item_layout = QVBoxLayout(grp_item)
        grp_item_layout.setSpacing(4)

        self.lbl_item = QLabel("Не выбрано")
        self.lbl_item.setStyleSheet("font-weight: bold;")
        grp_item_layout.addWidget(self.lbl_item)

        # Строка добавления тега
        add_row = QHBoxLayout()
        add_row.setSpacing(4)
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Новый тег...")
        self.tag_input.setClearButtonEnabled(True)
        self.tag_input.returnPressed.connect(self._on_add_tag)
        add_row.addWidget(self.tag_input, 1)
        btn_add = QPushButton("+")
        btn_add.setFixedSize(28, 28)
        btn_add.setToolTip("Добавить тег")
        btn_add.clicked.connect(self._on_add_tag)
        add_row.addWidget(btn_add)
        btn_del = QPushButton("−")
        btn_del.setFixedSize(28, 28)
        btn_del.setToolTip("Удалить выбранный тег")
        btn_del.clicked.connect(self._on_remove_tag)
        add_row.addWidget(btn_del)
        grp_item_layout.addLayout(add_row)

        # Список тегов элемента
        tag_list_row = QHBoxLayout()
        tag_list_row.setSpacing(4)
        tag_list_row.addWidget(QLabel("Теги:"))
        self.tag_combo = QComboBox()
        self.tag_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.tag_combo.setToolTip("Теги выделенного элемента")
        tag_list_row.addWidget(self.tag_combo, 1)
        grp_item_layout.addLayout(tag_list_row)

        outer.addWidget(grp_item)

        # ── Группа: фильтр ──
        grp_filter = QGroupBox("Фильтр по тегу")
        grp_filter_layout = QHBoxLayout(grp_filter)
        grp_filter_layout.setSpacing(4)
        self.filter_combo = QComboBox()
        self.filter_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.filter_combo.setToolTip("Показать только модели с этим тегом")
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        grp_filter_layout.addWidget(self.filter_combo, 1)
        btn_clear = QPushButton("Сбросить")
        btn_clear.setFixedWidth(70)
        btn_clear.clicked.connect(self._clear_filter)
        grp_filter_layout.addWidget(btn_clear)
        outer.addWidget(grp_filter)

        # Кнопка закрытия
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.close)
        outer.addWidget(btn_close)

    def refresh(self):
        """Обновить содержимое окна (вызвать при открытии и смене выделения)."""
        self._refresh_item_info()
        self._refresh_tag_list()
        self._refresh_filter_list()

    def _refresh_item_info(self):
        target, is_folder = self._mt._get_selected_item_info()
        if target is None:
            self.lbl_item.setText("Не выбрано")
            return
        if is_folder:
            self.lbl_item.setText(f"Папка: {os.path.basename(target)}")
        else:
            self.lbl_item.setText(f"Файл: {os.path.basename(target)}")

    def _refresh_tag_list(self):
        self._suppress = True
        self.tag_combo.clear()
        target, is_folder = self._mt._get_selected_item_info()
        if target is None:
            self._suppress = False
            return
        if is_folder:
            self.tag_combo.addItems(self._mt._get_folder_own_tags(target))
        else:
            tags = self._mt._get_model_tags(target)
            own = self._mt._get_own_tags(target)
            inherited = [t for t in tags if t not in own]
            if own and inherited:
                self.tag_combo.addItems(own)
                self.tag_combo.insertSeparator(self.tag_combo.count())
                self.tag_combo.addItems(inherited)
            else:
                self.tag_combo.addItems(tags)
        self._suppress = False

    def _refresh_filter_list(self):
        self._suppress = True
        cur = self._mt._active_tag_filter
        self.filter_combo.clear()
        self.filter_combo.addItem("Все теги")
        for tag in self._mt._get_all_tag_names_for_filter():
            self.filter_combo.addItem(tag)
        if cur:
            idx = self.filter_combo.findText(cur)
            if idx >= 0:
                self.filter_combo.setCurrentIndex(idx)
        self._suppress = False

    def _on_add_tag(self):
        tag = self.tag_input.text().strip()
        if not tag:
            return
        target, is_folder = self._mt._get_selected_item_info()
        if target is None:
            return
        if is_folder:
            self._mt._add_tag_to_folder(target, tag)
        else:
            self._mt._add_tag_to_model(target, tag)
        self.tag_input.clear()
        self.refresh()

    def _on_remove_tag(self):
        tag = self.tag_combo.currentText()
        if not tag:
            return
        target, is_folder = self._mt._get_selected_item_info()
        if target is None:
            return
        if is_folder:
            self._mt._remove_tag_from_folder(target, tag)
        else:
            own = self._mt._get_own_tags(target)
            if tag in own:
                self._mt._remove_tag_from_model(target, tag)
            else:
                # Унаследованный от папки — ищем источник
                if self._mt._root_dir:
                    try:
                        rel = os.path.relpath(target, self._mt._root_dir)
                        parts = rel.replace("/", os.sep).split(os.sep)
                        for i in range(len(parts) - 1):
                            folder = os.path.join(self._mt._root_dir, *parts[:i + 1])
                            ft = self._mt._get_folder_own_tags(folder)
                            if tag in ft:
                                self._mt._remove_tag_from_folder(folder, tag)
                                break
                    except ValueError:
                        pass
        self.refresh()

    def _on_filter_changed(self, index: int):
        if self._suppress:
            return
        if index <= 0:
            self._mt._active_tag_filter = None
        else:
            self._mt._active_tag_filter = self.filter_combo.currentText()
        self._mt._do_filter()

    def _clear_filter(self):
        self._mt._active_tag_filter = None
        self._refresh_filter_list()
        self._mt._do_filter()


# ─── Основной виджет дерева ──────────────────────────────────────

class ModelTree(QWidget):
    """Иерархическое дерево .glb моделей с поиском, сортировкой и тегами."""

    model_selected = Signal(str)
    preview_requested = Signal(str)  # путь к картинке превью
    reference_gallery_requested = Signal(str)  # путь к папке reference
    tags_changed = Signal()

    TAGS_FILE = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tags.json"
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_paths: list[str] = []
        self._ref_folders: list[str] = []  # пути к папкам reference
        self._root_dir = ""
        self._file_meta: dict[str, dict] = {}   # path -> {"size": int, "mtime": float}
        self._tags: dict[str, list[str]] = {}    # path -> [tag1, tag2, ...]
        self._folder_tags: dict[str, list[str]] = {}  # folder_path -> [tag1, ...]
        self._active_tag_filter: str | None = None
        self._sort_by = "name"   # "name" | "size" | "date"
        self._sort_asc = True

        self._tag_dialog: TagManagerDialog | None = None
        self._hide_reference = False

        self.setMinimumWidth(200)
        self.setMaximumWidth(400)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._do_filter)

        # Таймер для различения single/double click по папкам
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(250)  # порог двойного клика Qt
        self._click_timer.timeout.connect(self._on_single_click_confirmed)
        self._pending_click_item = None

        self._build_ui()
        self._load_tags()

    # ─── UI ────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        self.header = QLabel("Модели (.glb)")
        self.header.setStyleSheet("font-weight: bold; font-size: 13px; padding: 2px;")
        layout.addWidget(self.header)

        # Поиск
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск (поддержка кириллицы)...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        layout.addWidget(self.search_edit)

        # Кнопка открытия окна тегов
        self.btn_tags = QPushButton("Теги...")
        self.btn_tags.setFixedHeight(26)
        self.btn_tags.setToolTip("Открыть окно управления тегами")
        self.btn_tags.clicked.connect(self._open_tag_dialog)
        layout.addWidget(self.btn_tags)

        # ─── Сортировка (компактная) ───────────────────────────────
        sort_bar = QHBoxLayout()
        sort_bar.setSpacing(2)
        sort_bar.setContentsMargins(0, 0, 0, 0)
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Имя", "Размер", "Дата"])
        self.sort_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.sort_combo.setFixedHeight(24)
        self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        sort_bar.addWidget(self.sort_combo)
        self.sort_dir_btn = QPushButton("↑")
        self.sort_dir_btn.setFixedSize(24, 24)
        self.sort_dir_btn.setToolTip("Направление сортировки")
        self.sort_dir_btn.clicked.connect(self._toggle_sort_dir)
        sort_bar.addWidget(self.sort_dir_btn)
        layout.addLayout(sort_bar)

        # Разделитель
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        # Дерево
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)  # Скрыть заголовок полностью
        self.tree.setHeaderLabels(["Имя"])
        self.tree.setAnimated(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setColumnCount(1)
        self.tree.setIndentation(20)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        self.tree.keyPressEvent = self._tree_key_press
        layout.addWidget(self.tree)

        # Счётчик
        self.lbl_count = QLabel("0 моделей")
        self.lbl_count.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self.lbl_count)

    # ─── Окно тегов ──────────────────────────────────────────────

    def _open_tag_dialog(self):
        if self._tag_dialog is None or not self._tag_dialog.isVisible():
            self._tag_dialog = TagManagerDialog(self, self.window())
        self._tag_dialog.refresh()
        self._tag_dialog.show()
        self._tag_dialog.raise_()
        self._tag_dialog.activateWindow()

    # ─── Сортировка ───────────────────────────────────────────────

    def _on_sort_changed(self, index: int):
        sort_map = {0: "name", 1: "size", 2: "date"}
        self._sort_by = sort_map.get(index, "name")
        self._rebuild_tree()

    def _toggle_sort_dir(self):
        self._sort_asc = not self._sort_asc
        self.sort_dir_btn.setText("↑" if self._sort_asc else "↓")
        self._rebuild_tree()

    def _sort_paths(self) -> list[str]:
        paths = list(self._all_paths)
        reverse = not self._sort_asc
        if self._sort_by == "name":
            paths.sort(key=lambda p: os.path.basename(p).lower(), reverse=reverse)
        elif self._sort_by == "size":
            paths.sort(
                key=lambda p: self._file_meta.get(p, {}).get("size", 0), reverse=reverse
            )
        elif self._sort_by == "date":
            paths.sort(
                key=lambda p: self._file_meta.get(p, {}).get("mtime", 0), reverse=reverse
            )
        return paths

    # ─── Теги: хранение ──────────────────────────────────────────

    def _load_tags(self):
        if os.path.isfile(self.TAGS_FILE):
            try:
                with open(self.TAGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._tags = data.get("files", {})
                    self._folder_tags = data.get("folders", {})
            except Exception as e:
                print(f"[Tags] Ошибка загрузки: {e}")
                self._tags = {}
                self._folder_tags = {}

    def _save_tags(self):
        try:
            os.makedirs(os.path.dirname(self.TAGS_FILE) or ".", exist_ok=True)
            with open(self.TAGS_FILE, "w", encoding="utf-8") as f:
                json.dump({"files": self._tags, "folders": self._folder_tags},
                          f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Tags] Ошибка сохранения: {e}")

    def _get_model_tags(self, path: str) -> list[str]:
        """Теги модели: свои + теги родительских папок."""
        model_tags = list(self._tags.get(path, []))
        # Добавляем теги папок из пути
        if self._root_dir:
            try:
                rel = os.path.relpath(path, self._root_dir)
                parts = rel.replace("/", os.sep).split(os.sep)
                for i in range(len(parts) - 1):
                    folder = os.path.join(self._root_dir, *parts[:i + 1])
                    ft = self._folder_tags.get(folder, [])
                    for t in ft:
                        if t not in model_tags:
                            model_tags.append(t)
            except ValueError:
                pass
        return model_tags

    def _get_own_tags(self, path: str) -> list[str]:
        """Только собственные теги модели (без папок)."""
        return list(self._tags.get(path, []))

    def _get_folder_own_tags(self, folder_path: str) -> list[str]:
        """Собственные теги папки."""
        return list(self._folder_tags.get(folder_path, []))

    def _add_tag_to_model(self, path: str, tag: str):
        if path not in self._tags:
            self._tags[path] = []
        if tag not in self._tags[path]:
            self._tags[path].append(tag)
            self._save_tags()
            self._rebuild_tree()
            self.tags_changed.emit()

    def _remove_tag_from_model(self, path: str, tag: str):
        if path in self._tags and tag in self._tags[path]:
            self._tags[path].remove(tag)
            if not self._tags[path]:
                del self._tags[path]
            self._save_tags()
            self._rebuild_tree()
            self.tags_changed.emit()

    def _add_tag_to_folder(self, folder_path: str, tag: str):
        """Добавить тег папке — применяется ко всем файлам внутри."""
        if folder_path not in self._folder_tags:
            self._folder_tags[folder_path] = []
        if tag not in self._folder_tags[folder_path]:
            self._folder_tags[folder_path].append(tag)
            self._save_tags()
            self._rebuild_tree()
            self.tags_changed.emit()

    def _remove_tag_from_folder(self, folder_path: str, tag: str):
        """Удалить тег папки."""
        if folder_path in self._folder_tags and tag in self._folder_tags[folder_path]:
            self._folder_tags[folder_path].remove(tag)
            if not self._folder_tags[folder_path]:
                del self._folder_tags[folder_path]
            self._save_tags()
            self._rebuild_tree()
            self.tags_changed.emit()

    def _get_all_tags(self) -> set[str]:
        """Все уникальные теги из моделей и папок текущего дерева."""
        tags = set()
        for p in self._all_paths:
            for t in self._get_model_tags(p):
                tags.add(t)
        return tags

    def _get_all_tag_names_for_filter(self) -> list[str]:
        """Все уникальные имена тегов для фильтра."""
        return sorted(self._get_all_tags())

    # ─── Теги: вспомогательные ───────────────────────────────────

    def _get_selected_item_info(self):
        """(path_or_folder, is_folder)."""
        item = self.tree.currentItem()
        if not item:
            return None, False
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            return path, False
        folder_path = self._get_folder_path_from_item(item)
        return folder_path, True

    def _get_folder_path_from_item(self, item) -> str | None:
        """Восстановить полный путь папки по элементу дерева."""
        if item is None:
            return None
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            return None
        parts = []
        cur = item
        while cur is not None:
            text = cur.text(0).strip().lstrip("\U0001F4C2 ").strip()
            parts.append(text)
            cur = cur.parent()
            if cur is self.tree.invisibleRootItem():
                break
        parts.reverse()
        if not parts:
            return None
        if parts[0] == os.path.basename(self._root_dir) and self._root_dir:
            return os.path.join(self._root_dir, *parts[1:])
        return None

    # ─── Поиск / Фильтрация ───────────────────────────────────────

    def _on_search_text_changed(self, text: str):
        self._search_timer.start()

    def _do_filter(self):
        query = self.search_edit.text().strip()
        if query:
            search_terms = expand_search_query(query)
            escaped = [re.escape(term) for term in search_terms]
            text_pattern = re.compile("|".join(escaped), re.IGNORECASE)
        else:
            text_pattern = None
        self._apply_filter(self.tree.invisibleRootItem(), text_pattern)
        visible = self._count_visible_files(self.tree.invisibleRootItem())
        total = len(self._all_paths)
        if visible == total:
            self._update_count()
        else:
            self.lbl_count.setText(f"{visible} из {total} моделей")

    def _apply_filter(self, parent: QTreeWidgetItem, text_pattern) -> bool:
        """Рекурсивная фильтрация с учётом тегов и текста."""
        has_visible = False
        for i in range(parent.childCount()):
            child = parent.child(i)
            text = child.text(0).strip()
            clean_text = text.lstrip("\U0001F4C2 ").strip()
            path = child.data(0, Qt.ItemDataRole.UserRole)

            # Тег-фильтр (только для файлов)
            tag_ok = True
            if path and self._active_tag_filter:
                tag_ok = self._active_tag_filter in self._get_model_tags(path)

            # Скрытие reference папок — безусловно
            if self._hide_reference and clean_text.lower() == "reference":
                child.setHidden(True)
                continue

            # Текст-фильтр (для файлов и папок)
            text_ok = True
            if text_pattern:
                text_ok = bool(text_pattern.search(clean_text))

            # Рекурсия потомков
            child_has_visible = self._apply_filter(child, text_pattern)

            visible = child_has_visible or (tag_ok and text_ok)
            child.setHidden(not visible)
            if visible:
                has_visible = True
        return has_visible

    def _show_all_items(self, parent: QTreeWidgetItem):
        for i in range(parent.childCount()):
            child = parent.child(i)
            child.setHidden(False)
            self._show_all_items(child)

    def _count_visible_files(self, parent: QTreeWidgetItem) -> int:
        count = 0
        for i in range(parent.childCount()):
            child = parent.child(i)
            if child.isHidden():
                continue
            if child.data(0, Qt.ItemDataRole.UserRole):
                count += 1
            count += self._count_visible_files(child)
        return count

    # ─── Публичные методы ────────────────────────────────────────

    def add_models(self, filepaths: list[str], root_dir: str = ""):
        if root_dir:
            self._root_dir = root_dir
            self.header.setText(f"Модели ({os.path.basename(root_dir)})")
            # Найти все папки reference внутри root_dir
            self._ref_folders = []
            if root_dir:
                for dirpath, dirnames, _ in os.walk(root_dir):
                    for d in dirnames:
                        if d.lower() == "reference":
                            self._ref_folders.append(os.path.join(dirpath, d))

        added = 0
        for fp in filepaths:
            if fp in self._all_paths:
                continue
            ext = os.path.splitext(fp)[1].lower()
            if ext != ".glb":
                continue
            self._all_paths.append(fp)

            try:
                stat = os.stat(fp)
                self._file_meta[fp] = {
                    "size": stat.st_size,
                    "mtime": stat.st_mtime,
                }
            except OSError:
                self._file_meta[fp] = {"size": 0, "mtime": 0}

            added += 1

        if added > 0:
            self._rebuild_tree()

    def add_model(self, filepath: str, root_dir: str = ""):
        self.add_models([filepath], root_dir)

    def clear_all(self):
        self._all_paths.clear()
        self._ref_folders.clear()
        self._file_meta.clear()
        self.tree.clear()
        self._root_dir = ""
        self.header.setText("Модели (.glb)")
        self.search_edit.clear()
        self._active_tag_filter = None
        self._update_count()

    def get_all_paths(self) -> list[str]:
        return list(self._all_paths)

    @property
    def root_dir(self) -> str:
        """Корневая директория моделей (read-only)."""
        return self._root_dir

    @root_dir.setter
    def root_dir(self, value: str):
        self._root_dir = value

    # ─── Перестроение дерева ───────────────────────────────────────

    def _rebuild_tree(self):
        """Полная перестройка дерева с сортировкой и тегами."""
        self.tree.clear()
        sorted_paths = self._sort_paths()
        root_item = self.tree.invisibleRootItem()

        if not sorted_paths:
            self._update_count()
            return

        root_node_name = os.path.basename(self._root_dir) if self._root_dir else "Root"
        root_node = self._find_or_create_child(root_item, root_node_name, is_folder=True)

        for fp in sorted_paths:
            if self._root_dir:
                rel = os.path.relpath(fp, self._root_dir)
            else:
                rel = os.path.basename(fp)
            parts = rel.replace("/", os.sep).split(os.sep)

            current = root_node
            for part in parts[:-1]:
                current = self._find_or_create_child(current, part, is_folder=True)

            fname = parts[-1]
            tags = self._get_model_tags(fp)
            if tags:
                display = f"{fname}  [{', '.join(tags)}]"
            else:
                display = fname

            item = QTreeWidgetItem(current, [display])
            item.setData(0, Qt.ItemDataRole.UserRole, fp)
            meta = self._file_meta.get(fp, {})
            size_str = _format_size(meta.get("size", 0))
            mtime_str = _format_date(meta.get("mtime", 0))
            tip = f"{fp}\nРазмер: {size_str}\nДата: {mtime_str}"
            if tags:
                tip += f"\nТеги: {', '.join(tags)}"
            item.setToolTip(0, tip)

        # Добавить папки reference, которых нет среди родителей .glb файлов
        existing_folders = set()
        self._collect_folder_names(root_node, existing_folders)
        for ref_path in sorted(self._ref_folders, key=lambda p: p.lower()):
            if self._root_dir:
                try:
                    rel = os.path.relpath(ref_path, self._root_dir)
                except ValueError:
                    continue
            else:
                rel = os.path.basename(ref_path)
            if rel.lower() in existing_folders:
                continue
            parts = rel.replace("/", os.sep).split(os.sep)
            current = root_node
            for part in parts:
                current = self._find_or_create_child(current, part, is_folder=True)
            existing_folders.add(rel.lower())

        # Сортируем папки по имени на каждом уровне (файлы уже отсортированы)
        self._sort_folders(root_node)

        # Рекурсивно разворачиваем все уровни дерева
        self._expand_all(root_node)

        self._update_count()

        # Применяем текущий фильтр (текстовый, теговый или скрытие reference)
        if self.search_edit.text().strip() or self._active_tag_filter or self._hide_reference:
            self._do_filter()

    # ─── Внутренние методы ────────────────────────────────────────

    def _find_or_create_child(self, parent: QTreeWidgetItem, name: str,
                                is_folder: bool = False) -> QTreeWidgetItem:
        for i in range(parent.childCount()):
            child = parent.child(i)
            child_text = child.text(0).strip()
            if child_text == name or child_text == f"\U0001F4C2 {name}":
                return child
        display = f"\U0001F4C2 {name}" if is_folder else name
        item = QTreeWidgetItem(parent, [display])
        item.setFirstColumnSpanned(True)
        if is_folder:
            item.setData(0, Qt.ItemDataRole.UserRole, None)
        return item

    def _collect_folder_names(self, parent: QTreeWidgetItem, out: set[str], prefix: str = ""):
        """Собрать все пути папок (в нижнем регистре) для проверки дубликатов."""
        for i in range(parent.childCount()):
            child = parent.child(i)
            if child.data(0, Qt.ItemDataRole.UserRole) is None:
                name = child.text(0).strip().lstrip("\U0001F4C2 ").strip()
                path_lower = (prefix + name).lower()
                out.add(path_lower)
                self._collect_folder_names(child, out, path_lower + os.sep)

    def _sort_folders(self, parent: QTreeWidgetItem):
        """Рекурсивно отсортировать дочерние элементы: папки сверху по имени, файлы ниже."""
        folders = []
        files = []
        for i in range(parent.childCount()):
            child = parent.child(i)
            if child.data(0, Qt.ItemDataRole.UserRole) is None:
                folders.append(child)
            else:
                files.append(child)

        # Сортируем папки по имени (с учётом направления сортировки)
        folders.sort(
            key=lambda item: item.text(0).strip().lstrip("\U0001F4C2 ").strip().lower(),
            reverse=not self._sort_asc,
        )

        # Убираем всех детей
        for _ in range(parent.childCount()):
            parent.removeChild(parent.child(0))

        # Добавляем папки, потом файлы
        for item in folders + files:
            parent.addChild(item)
            self._sort_folders(item)

    def set_hide_reference(self, hide: bool):
        """Показать/скрыть папки reference в дереве."""
        self._hide_reference = hide
        # Всегда вызываем _do_filter(), чтобы учесть все активные фильтры
        # (текстовый поиск, тег-фильтр и скрытие reference)
        self._do_filter()

    def _expand_all(self, parent: QTreeWidgetItem):
        """Рекурсивно развернуть все узлы дерева."""
        parent.setExpanded(True)
        for i in range(parent.childCount()):
            self._expand_all(parent.child(i))

    def _hide_ref_folders(self, parent: QTreeWidgetItem):
        """Рекурсивно скрыть все папки с именем reference."""
        for i in range(parent.childCount()):
            child = parent.child(i)
            text = child.text(0).strip().lstrip("\U0001F4C2 ").strip()
            if text.lower() == "reference":
                child.setHidden(True)
            else:
                self._hide_ref_folders(child)

    def _update_count(self):
        n = len(self._all_paths)
        if n == 0:
            word = "моделей"
        elif n == 1:
            word = "модель"
        elif n <= 4:
            word = "модели"
        else:
            word = "моделей"
        self.lbl_count.setText(f"{n} {word}")

    def _tree_key_press(self, event):
        """Обработка Ctrl+- (свернуть) и Ctrl++ (развернуть)."""
        item = self.tree.currentItem()
        if item is None:
            super(QTreeWidget, self.tree).keyPressEvent(event)
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            key = event.key()
            if key == Qt.Key.Key_Minus:
                item.setExpanded(False)
                event.accept()
                return
            elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                item.setExpanded(True)
                event.accept()
                return
        super(QTreeWidget, self.tree).keyPressEvent(event)

    def _on_item_clicked(self, item, _column):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            # Файл — загружаем модель как раньше
            self.model_selected.emit(path)
        else:
            # Папка — ждём, не будет ли двойного клика
            self._pending_click_item = item
            self._click_timer.start()

    def _on_item_double_clicked(self, item, _column):
        # Двойной клик отменяет показ превью, переключает раскрытие папки
        self._click_timer.stop()
        self._pending_click_item = None

        # Если это папка reference — показать галерею картинок
        folder_path = self._get_folder_path_from_item(item)
        if folder_path:
            folder_name = os.path.basename(folder_path).lower()
            if folder_name == "reference":
                self.reference_gallery_requested.emit(folder_path)
                return

        item.setExpanded(not item.isExpanded())

    def _on_single_click_confirmed(self):
        """Сработал одиночный клик по папке — проверить preview."""
        item = self._pending_click_item
        self._pending_click_item = None
        if item is None:
            return

        folder_path = self._get_folder_path_from_item(item)
        if not folder_path:
            return

        preview_dir = os.path.join(folder_path, "preview")
        if not os.path.isdir(preview_dir):
            return

        # Ищем первую картинку в папке preview
        image_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".tif"}
        for fname in sorted(os.listdir(preview_dir)):
            ext = os.path.splitext(fname)[1].lower()
            if ext in image_exts:
                self.preview_requested.emit(os.path.join(preview_dir, fname))
                return

    # ─── Контекстное меню (ПКМ) ──────────────────────────────────

    def _on_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return

        filepath = item.data(0, Qt.ItemDataRole.UserRole)
        is_folder = filepath is None
        folder_path = self._get_folder_path_from_item(item) if is_folder else None

        menu = QMenu(self)

        if filepath:
            act_open = QAction("Открыть в проводнике", self)
            act_open.triggered.connect(lambda: self._open_in_explorer(filepath))
            menu.addAction(act_open)

            menu.addSeparator()

            act_copy_name = QAction("Копировать имя файла", self)
            act_copy_name.triggered.connect(lambda: self._copy_to_clipboard(os.path.basename(filepath)))
            menu.addAction(act_copy_name)

            act_copy_path = QAction("Копировать путь", self)
            act_copy_path.triggered.connect(lambda: self._copy_to_clipboard(os.path.dirname(filepath)))
            menu.addAction(act_copy_path)

            act_copy_full = QAction("Копировать путь и имя файла", self)
            act_copy_full.triggered.connect(lambda: self._copy_to_clipboard(filepath))
            menu.addAction(act_copy_full)

            # Подменю тегов
            menu.addSeparator()
            tags_menu = menu.addMenu("Теги")
            model_tags = self._get_model_tags(filepath)
            for tag in model_tags:
                act = QAction(f"  ✕  {tag}", self)
                act.triggered.connect(lambda t=tag: self._remove_tag_by_context(filepath, t))
                tags_menu.addAction(act)

            if model_tags:
                tags_menu.addSeparator()

            add_act = QAction("Добавить тег...", self)
            add_act.triggered.connect(lambda: self._add_tag_dialog(filepath, is_folder=False))
            tags_menu.addAction(add_act)

        elif folder_path:
            act_copy_path = QAction("Копировать путь папки", self)
            act_copy_path.triggered.connect(lambda: self._copy_to_clipboard(folder_path))
            menu.addAction(act_copy_path)

            menu.addSeparator()
            tags_menu = menu.addMenu("Теги папки")
            folder_tags = self._get_folder_own_tags(folder_path)
            for tag in folder_tags:
                act = QAction(f"  ✕  {tag}", self)
                act.triggered.connect(lambda t=tag: self._remove_tag_by_context_folder(folder_path, t))
                tags_menu.addAction(act)

            if folder_tags:
                tags_menu.addSeparator()

            add_act = QAction("Добавить тег...", self)
            add_act.triggered.connect(lambda: self._add_tag_dialog(folder_path, is_folder=True))
            tags_menu.addAction(add_act)

        menu.exec(self.tree.mapToGlobal(pos))

    def _remove_tag_by_context(self, filepath: str, tag: str):
        own_tags = self._get_own_tags(filepath)
        if tag in own_tags:
            self._remove_tag_from_model(filepath, tag)
            return
        if self._root_dir:
            try:
                rel = os.path.relpath(filepath, self._root_dir)
                parts = rel.replace("/", os.sep).split(os.sep)
                for i in range(len(parts) - 1):
                    folder = os.path.join(self._root_dir, *parts[:i + 1])
                    ft = self._get_folder_own_tags(folder)
                    if tag in ft:
                        self._remove_tag_from_folder(folder, tag)
                        return
            except ValueError:
                pass

    def _remove_tag_by_context_folder(self, folder_path: str, tag: str):
        self._remove_tag_from_folder(folder_path, tag)

    def _add_tag_dialog(self, target: str, is_folder: bool):
        label = os.path.basename(target)
        tag, ok = QInputDialog.getText(
            self, "Добавить тег",
            f"Тег для {label}:",
            text=""
        )
        if ok and tag.strip():
            if is_folder:
                self._add_tag_to_folder(target, tag.strip())
            else:
                self._add_tag_to_model(target, tag.strip())

    @staticmethod
    def _open_in_explorer(filepath: str):
        if not os.path.isfile(filepath):
            return
        try:
            import subprocess
            import sys
            if sys.platform == "win32":
                subprocess.run(["explorer", "/select," + os.path.normpath(filepath)], check=False)
            elif sys.platform == "darwin":
                subprocess.run(["open", "-R", filepath], check=False)
            else:
                subprocess.run(["xdg-open", os.path.dirname(filepath)], check=False)
        except Exception as e:
            print(f"[Tree] Ошибка открытия проводника: {e}")

    @staticmethod
    def _copy_to_clipboard(text: str):
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)


# ─── Форматирование ──────────────────────────────────────────────

def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size} Б"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} КБ"
    else:
        return f"{size / (1024 * 1024):.1f} МБ"


def _format_date(mtime: float) -> str:
    if mtime <= 0:
        return "—"
    try:
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
    except (OSError, ValueError):
        return "—"

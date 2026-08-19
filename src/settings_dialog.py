"""
Диалог настроек F3D 3.5.0.
Опции сгруппированы по смыслу, нерабочие в offscreen-режиме опции убраны.
Вкладка «Конфиги» — сохранение/загрузка пресетов в JSON.
"""

import json
import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QGroupBox, QFormLayout, QCheckBox, QComboBox,
    QDoubleSpinBox, QPushButton, QFileDialog, QLabel,
    QWidget, QScrollArea, QSpinBox, QAbstractItemView,
    QListWidget, QMessageBox, QInputDialog,
)
from PySide6.QtCore import Qt

from src.utils import resource_path


# Путь к папке с конфигами (рядом с программой)
CONFIGS_DIR = resource_path("configs")


class F3DSettingsDialog(QDialog):
    def __init__(self, f3d_widget, parent=None):
        super().__init__(parent)
        self.f3d = f3d_widget
        self.setWindowTitle("Настройки F3D")
        self.setMinimumSize(520, 520)
        self.resize(560, 580)
        self._build_ui()
        self._load_values()
        self._refresh_presets_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._build_render_tab()
        self._build_scene_tab()
        self._build_model_tab()
        self._build_presets_tab()

        # Кнопки внизу
        btn = QHBoxLayout()
        btn.addStretch()

        refresh_btn = QPushButton("↻ Обновить")
        refresh_btn.setToolTip("Перечитать текущие значения из движка")
        refresh_btn.clicked.connect(self._load_values)
        btn.addWidget(refresh_btn)

        apply_btn = QPushButton("Применить")
        apply_btn.setToolTip("Применить настройки (диалог остаётся открытым)")
        apply_btn.clicked.connect(self._apply_only)
        btn.addWidget(apply_btn)

        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        btn.addWidget(cancel_btn)

        ok_btn = QPushButton("Применить и закрыть")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._apply_and_close)
        btn.addWidget(ok_btn)

        layout.addLayout(btn)

    # ══════════════════════════════════════════════════════════════
    #  ВКЛАДКА: Рендеринг
    # ══════════════════════════════════════════════════════════════

    def _build_render_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form = QVBoxLayout(inner)
        form.setSpacing(12)

        # ── Raytracing ──
        grp_rt = QGroupBox("Raytracing")
        fl_rt = QFormLayout(grp_rt)

        self.chk_raytracing = QCheckBox("Включить")
        self.chk_raytracing.setToolTip("Рендеринг трассировкой лучей (требует поддержки)")
        fl_rt.addRow(self.chk_raytracing)

        self.chk_denoise = QCheckBox("Denoise")
        self.chk_denoise.setToolTip("Устранение шума в raytracing (AI денойзер)")
        fl_rt.addRow(self.chk_denoise)

        self.spin_rt_samples = QSpinBox()
        self.spin_rt_samples.setRange(1, 100)
        self.spin_rt_samples.setToolTip("Количество семплов на пиксель (больше = лучше качество, медленнее)")
        fl_rt.addRow("Сэмплы:", self.spin_rt_samples)

        form.addWidget(grp_rt)

        # ── Пост-эффекты ──
        grp_fx = QGroupBox("Пост-эффекты")
        fl_fx = QFormLayout(grp_fx)

        self.chk_ao = QCheckBox("Ambient Occlusion")
        self.chk_ao.setToolTip("Глобальное затенение в углах и стыках")
        fl_fx.addRow(self.chk_ao)

        self.chk_tone_mapping = QCheckBox("Tone Mapping")
        self.chk_tone_mapping.setToolTip("Сжатие динамического диапазона для HDR-сцен")
        fl_fx.addRow(self.chk_tone_mapping)

        self.chk_aa = QCheckBox("Anti-aliasing")
        fl_fx.addRow(self.chk_aa)

        self.cmb_aa_mode = QComboBox()
        self.cmb_aa_mode.addItems(["fxaa", "msaa", "ssaa"])
        self.cmb_aa_mode.setToolTip("fxaa — быстрый, msaa — сбалансированный, ssaa — качественный")
        fl_fx.addRow("Режим AA:", self.cmb_aa_mode)

        self.chk_blending = QCheckBox("Depth Peeling")
        self.chk_blending.setToolTip("Корректный порядок прозрачных объектов")
        fl_fx.addRow(self.chk_blending)

        self.chk_translucency = QCheckBox("Translucency")
        self.chk_translucency.setToolTip("Полупрозрачные объекты с subsurface scattering")
        fl_fx.addRow(self.chk_translucency)

        form.addWidget(grp_fx)

        # ── Фон ──
        grp_bg = QGroupBox("Фон")
        fl_bg = QFormLayout(grp_bg)

        self.chk_skybox = QCheckBox("Skybox (HDRI на фоне)")
        self.chk_skybox.setToolTip("Показать HDRI карту как фон сцены")
        fl_bg.addRow(self.chk_skybox)

        self.chk_bg_blur = QCheckBox("Размытие фона")
        self.chk_bg_blur.setToolTip("Боке-эффект для фона (depth of field)")
        fl_bg.addRow(self.chk_bg_blur)

        self.spin_bg_blur_coc = QDoubleSpinBox()
        self.spin_bg_blur_coc.setRange(0.1, 100.0)
        self.spin_bg_blur_coc.setSingleStep(1.0)
        self.spin_bg_blur_coc.setDecimals(1)
        self.spin_bg_blur_coc.setValue(20.0)
        self.spin_bg_blur_coc.setToolTip("Circle of confusion — сила размытия")
        fl_bg.addRow("Сила размытия:", self.spin_bg_blur_coc)

        # Цвет фона (когда skybox выключен)
        bg_layout = QHBoxLayout()
        self.spin_bg_r = self._make_color_spin()
        self.spin_bg_g = self._make_color_spin()
        self.spin_bg_b = self._make_color_spin()
        bg_layout.addWidget(QLabel("R:"))
        bg_layout.addWidget(self.spin_bg_r)
        bg_layout.addWidget(QLabel("G:"))
        bg_layout.addWidget(self.spin_bg_g)
        bg_layout.addWidget(QLabel("B:"))
        bg_layout.addWidget(self.spin_bg_b)
        fl_bg.addRow("Цвет фона:", bg_layout)

        self.chk_depth = QCheckBox("Отображение глубины")
        self.chk_depth.setToolTip("Визуализация z-buffer вместо цветов")
        fl_bg.addRow(self.chk_depth)

        form.addWidget(grp_bg)

        form.addStretch()
        scroll.setWidget(inner)
        self.tabs.addTab(scroll, "Рендеринг")

    # ══════════════════════════════════════════════════════════════
    #  ВКЛАДКА: Сцена
    # ══════════════════════════════════════════════════════════════

    def _build_scene_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form = QVBoxLayout(inner)
        form.setSpacing(12)

        # ── HDRI / Свет ──
        grp_hdri = QGroupBox("HDRI и освещение")
        fl_hdri = QFormLayout(grp_hdri)

        self.chk_hdri_ambient = QCheckBox("Ambient (освещение от HDRI)")
        self.chk_hdri_ambient.setToolTip("Использовать HDRI как источник окружающего света")
        fl_hdri.addRow(self.chk_hdri_ambient)

        self.spin_light_intensity = QDoubleSpinBox()
        self.spin_light_intensity.setRange(0.0, 100.0)
        self.spin_light_intensity.setSingleStep(0.1)
        self.spin_light_intensity.setDecimals(2)
        self.spin_light_intensity.setValue(1.0)
        self.spin_light_intensity.setToolTip("Интенсивность основного света")
        fl_hdri.addRow("Сила света:", self.spin_light_intensity)

        form.addWidget(grp_hdri)

        # ── Сетка и оси ──
        grp_grid = QGroupBox("Сетка и оси")
        fl_grid = QFormLayout(grp_grid)

        self.chk_grid = QCheckBox("Показать сетку")
        fl_grid.addRow(self.chk_grid)

        self.chk_grid_absolute = QCheckBox("Абсолютная сетка")
        self.chk_grid_absolute.setToolTip("Сетка в мировых координатах (не привязана к модели)")
        fl_grid.addRow(self.chk_grid_absolute)

        self.spin_grid_subdivisions = QSpinBox()
        self.spin_grid_subdivisions.setRange(1, 100)
        self.spin_grid_subdivisions.setValue(10)
        fl_grid.addRow("Деления сетки:", self.spin_grid_subdivisions)

        self.chk_axes_grid = QCheckBox("Оси координат (grid)")
        self.chk_axes_grid.setToolTip("Показать оси X/Y/Z с подписями")
        fl_grid.addRow(self.chk_axes_grid)

        form.addWidget(grp_grid)

        # ── Камера ──
        grp_cam = QGroupBox("Камера")
        fl_cam = QFormLayout(grp_cam)

        # Up direction
        up_layout = QHBoxLayout()
        self.spin_up_x = self._make_dir_spin()
        self.spin_up_y = self._make_dir_spin()
        self.spin_up_z = self._make_dir_spin()
        up_layout.addWidget(QLabel("X:"))
        up_layout.addWidget(self.spin_up_x)
        up_layout.addWidget(QLabel("Y:"))
        up_layout.addWidget(self.spin_up_y)
        up_layout.addWidget(QLabel("Z:"))
        up_layout.addWidget(self.spin_up_z)
        fl_cam.addRow("Направление «верх»:", up_layout)

        self.chk_invert_zoom = QCheckBox("Инвертировать зум")
        self.chk_invert_zoom.setToolTip("Колёсико мыши: прокрутка вверх = отдаление")
        fl_cam.addRow(self.chk_invert_zoom)

        form.addWidget(grp_cam)

        form.addStretch()
        scroll.setWidget(inner)
        self.tabs.addTab(scroll, "Сцена")

    # ══════════════════════════════════════════════════════════════
    #  ВКЛАДКА: Модель
    # ══════════════════════════════════════════════════════════════

    def _build_model_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form = QVBoxLayout(inner)
        form.setSpacing(12)

        # ── Визуализация модели ──
        grp_model = QGroupBox("Модель")
        fl_model = QFormLayout(grp_model)

        self.chk_checkerboard = QCheckBox("Шахматный текстурный фон")
        self.chk_checkerboard.setToolTip("Показать шахматную текстуру для проверки UV-развёртки")
        fl_model.addRow(self.chk_checkerboard)

        self.chk_normal_glyphs = QCheckBox("Нормали (glyphs)")
        self.chk_normal_glyphs.setToolTip("Показать векторы нормалей в каждой вершине")
        fl_model.addRow(self.chk_normal_glyphs)

        self.chk_armature = QCheckBox("Скелет (armature)")
        self.chk_armature.setToolTip("Показать кости анимации")
        fl_model.addRow(self.chk_armature)

        form.addWidget(grp_model)

        # ── Точечные спрайты ──
        grp_points = QGroupBox("Точечные спрайты")
        fl_points = QFormLayout(grp_points)

        self.chk_point_sprites = QCheckBox("Включить")
        fl_points.addRow(self.chk_point_sprites)

        self.spin_point_size = QDoubleSpinBox()
        self.spin_point_size.setRange(1.0, 100.0)
        self.spin_point_size.setSingleStep(1.0)
        self.spin_point_size.setValue(10.0)
        fl_points.addRow("Размер:", self.spin_point_size)

        self.cmb_point_type = QComboBox()
        self.cmb_point_type.addItems(["sphere", "circle", "square"])
        fl_points.addRow("Тип:", self.cmb_point_type)

        self.chk_point_absolute = QCheckBox("Абсолютный размер")
        self.chk_point_absolute.setToolTip("Размер не зависит от расстояния до камеры")
        fl_points.addRow(self.chk_point_absolute)

        form.addWidget(grp_points)

        # ── Volume ──
        grp_vol = QGroupBox("Volume rendering")
        fl_vol = QFormLayout(grp_vol)

        self.chk_volume = QCheckBox("Включить")
        fl_vol.addRow(self.chk_volume)

        self.chk_volume_inverse = QCheckBox("Инверсия")
        self.chk_volume_inverse.setToolTip("Инвертировать плотность объёма")
        fl_vol.addRow(self.chk_volume_inverse)

        form.addWidget(grp_vol)

        # ── SciVis ──
        grp_sv = QGroupBox("SciVis (цветовое отображение)")
        fl_sv = QFormLayout(grp_sv)

        self.chk_scivis = QCheckBox("Включить")
        self.chk_scivis.setToolTip("Цветовое картирование данных по скалярам")
        fl_sv.addRow(self.chk_scivis)

        self.spin_scivis_comp = QSpinBox()
        self.spin_scivis_comp.setRange(-1, 100)
        self.spin_scivis_comp.setValue(-1)
        self.spin_scivis_comp.setToolTip("Компонент данных (-1 = авто)")
        fl_sv.addRow("Компонент:", self.spin_scivis_comp)

        form.addWidget(grp_sv)

        form.addStretch()
        scroll.setWidget(inner)
        self.tabs.addTab(scroll, "Модель")

    # ══════════════════════════════════════════════════════════════
    #  ВКЛАДКА: Конфиги
    # ══════════════════════════════════════════════════════════════

    def _build_presets_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        info = QLabel(
            "Сохраняйте и загружайте наборы настроек как конфиг-файлы.\n"
            "Конфиги хранятся в папке configs/ рядом с программой."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #888; font-style: italic; margin-bottom: 8px;")
        layout.addWidget(info)

        # Список пресетов
        presets_grp = QGroupBox("Сохранённые конфиги")
        presets_lay = QVBoxLayout(presets_grp)

        self.presets_list = QListWidget()
        self.presets_list.setMaximumHeight(200)
        presets_lay.addWidget(self.presets_list)

        presets_btn = QHBoxLayout()

        btn_save = QPushButton("Сохранить как...")
        btn_save.clicked.connect(self._save_preset)
        presets_btn.addWidget(btn_save)

        btn_load = QPushButton("Загрузить в UI")
        btn_load.setToolTip("Загрузить настройки из конфига в поля (без применения)")
        btn_load.clicked.connect(self._load_preset)
        presets_btn.addWidget(btn_load)

        btn_apply = QPushButton("Загрузить и применить")
        btn_apply.clicked.connect(self._load_and_apply_preset)
        presets_btn.addWidget(btn_apply)

        btn_del = QPushButton("Удалить")
        btn_del.clicked.connect(self._delete_preset)
        presets_btn.addWidget(btn_del)

        presets_lay.addLayout(presets_btn)
        layout.addWidget(presets_grp)

        # Экспорт / Импорт
        io_grp = QGroupBox("Экспорт / Импорт")
        io_lay = QHBoxLayout(io_grp)

        btn_export = QPushButton("Экспорт в файл...")
        btn_export.clicked.connect(self._export_config)
        io_lay.addWidget(btn_export)

        btn_import = QPushButton("Импорт из файла...")
        btn_import.clicked.connect(self._import_config)
        io_lay.addWidget(btn_import)

        layout.addWidget(io_grp)
        layout.addStretch()

        self.tabs.addTab(widget, "Конфиги")

    # ─── Хелперы для создания spin'ов ─────────────────────────

    @staticmethod
    def _make_color_spin() -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(0.0, 1.0)
        s.setSingleStep(0.05)
        s.setDecimals(3)
        s.setFixedWidth(70)
        return s

    @staticmethod
    def _make_dir_spin() -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(-1.0, 1.0)
        s.setSingleStep(0.1)
        s.setDecimals(1)
        s.setFixedWidth(70)
        return s

    # ══════════════════════════════════════════════════════════════
    #  Загрузка значений из движка
    # ══════════════════════════════════════════════════════════════

    def _load_values(self):
        opts = self.f3d.get_all_options()

        def _get(key, default=None):
            return opts.get(key, default)

        def _float(key, default=0.0):
            try:
                return float(_get(key, default))
            except (TypeError, ValueError):
                return default

        def _list(key, default=None):
            v = _get(key, default)
            if isinstance(v, (list, tuple)):
                return list(v)
            return default if default is not None else []

        # Рендеринг
        self.chk_raytracing.setChecked(bool(_get("render.raytracing.enable")))
        self.chk_denoise.setChecked(bool(_get("render.raytracing.denoise")))
        self.spin_rt_samples.setValue(int(_get("render.raytracing.samples", 5)))
        self.chk_ao.setChecked(bool(_get("render.effect.ambient_occlusion")))
        self.chk_tone_mapping.setChecked(bool(_get("render.effect.tone_mapping")))
        self.chk_aa.setChecked(bool(_get("render.effect.antialiasing.enable")))
        aa_mode = str(_get("render.effect.antialiasing.mode", "fxaa"))
        idx = self.cmb_aa_mode.findText(aa_mode)
        if idx >= 0:
            self.cmb_aa_mode.setCurrentIndex(idx)
        self.chk_blending.setChecked(bool(_get("render.effect.blending.enable")))
        self.chk_translucency.setChecked(bool(_get("render.effect.translucency_support")))
        self.chk_skybox.setChecked(bool(_get("render.background.skybox")))
        self.chk_bg_blur.setChecked(bool(_get("render.background.blur.enable")))
        self.spin_bg_blur_coc.setValue(_float("render.background.blur.coc", 20.0))
        bg = _list("render.background.color", [0.2, 0.2, 0.2])
        if len(bg) >= 3:
            self.spin_bg_r.setValue(float(bg[0]))
            self.spin_bg_g.setValue(float(bg[1]))
            self.spin_bg_b.setValue(float(bg[2]))
        self.chk_depth.setChecked(bool(_get("render.effect.display_depth")))

        # Сцена
        self.chk_hdri_ambient.setChecked(bool(_get("render.hdri.ambient")))
        self.spin_light_intensity.setValue(_float("render.light.intensity", 1.0))
        self.chk_grid.setChecked(bool(_get("render.grid.enable")))
        self.chk_grid_absolute.setChecked(bool(_get("render.grid.absolute")))
        self.spin_grid_subdivisions.setValue(int(_get("render.grid.subdivisions", 10)))
        self.chk_axes_grid.setChecked(bool(_get("render.axes_grid.enable")))
        up = _list("scene.up_direction", [0.0, 1.0, 0.0])
        if len(up) >= 3:
            self.spin_up_x.setValue(float(up[0]))
            self.spin_up_y.setValue(float(up[1]))
            self.spin_up_z.setValue(float(up[2]))
        self.chk_invert_zoom.setChecked(bool(_get("interactor.invert_zoom")))

        # Модель
        self.chk_checkerboard.setChecked(bool(_get("model.checkerboard.enable")))
        self.chk_normal_glyphs.setChecked(bool(_get("model.normal_glyphs.enable")))
        self.chk_armature.setChecked(bool(_get("render.armature.enable")))
        self.chk_point_sprites.setChecked(bool(_get("model.point_sprites.enable")))
        self.spin_point_size.setValue(_float("model.point_sprites.size", 10.0))
        pt = str(_get("model.point_sprites.type", "sphere"))
        idx = self.cmb_point_type.findText(pt)
        if idx >= 0:
            self.cmb_point_type.setCurrentIndex(idx)
        self.chk_point_absolute.setChecked(bool(_get("model.point_sprites.absolute_size")))
        self.chk_volume.setChecked(bool(_get("model.volume.enable")))
        self.chk_volume_inverse.setChecked(bool(_get("model.volume.inverse")))
        self.chk_scivis.setChecked(bool(_get("model.scivis.enable")))
        self.spin_scivis_comp.setValue(int(_get("model.scivis.component", -1)))

    # ══════════════════════════════════════════════════════════════
    #  Сбор/загрузка конфига
    # ══════════════════════════════════════════════════════════════

    def _collect_config(self) -> dict:
        return {
            "render": {
                "raytracing.enable": self.chk_raytracing.isChecked(),
                "raytracing.denoise": self.chk_denoise.isChecked(),
                "raytracing.samples": self.spin_rt_samples.value(),
                "effect.ambient_occlusion": self.chk_ao.isChecked(),
                "effect.tone_mapping": self.chk_tone_mapping.isChecked(),
                "effect.antialiasing.enable": self.chk_aa.isChecked(),
                "effect.antialiasing.mode": self.cmb_aa_mode.currentText(),
                "effect.blending.enable": self.chk_blending.isChecked(),
                "effect.translucency_support": self.chk_translucency.isChecked(),
                "background.skybox": self.chk_skybox.isChecked(),
                "background.blur.enable": self.chk_bg_blur.isChecked(),
                "background.blur.coc": self.spin_bg_blur_coc.value(),
                "background.color": [
                    self.spin_bg_r.value(),
                    self.spin_bg_g.value(),
                    self.spin_bg_b.value(),
                ],
                "effect.display_depth": self.chk_depth.isChecked(),
            },
            "scene": {
                "hdri.ambient": self.chk_hdri_ambient.isChecked(),
                "light.intensity": self.spin_light_intensity.value(),
                "grid.enable": self.chk_grid.isChecked(),
                "grid.absolute": self.chk_grid_absolute.isChecked(),
                "grid.subdivisions": self.spin_grid_subdivisions.value(),
                "axes_grid.enable": self.chk_axes_grid.isChecked(),
                "up_direction": [
                    self.spin_up_x.value(),
                    self.spin_up_y.value(),
                    self.spin_up_z.value(),
                ],
                "invert_zoom": self.chk_invert_zoom.isChecked(),
            },
            "model": {
                "checkerboard.enable": self.chk_checkerboard.isChecked(),
                "normal_glyphs.enable": self.chk_normal_glyphs.isChecked(),
                "armature.enable": self.chk_armature.isChecked(),
                "point_sprites.enable": self.chk_point_sprites.isChecked(),
                "point_sprites.size": self.spin_point_size.value(),
                "point_sprites.type": self.cmb_point_type.currentText(),
                "point_sprites.absolute_size": self.chk_point_absolute.isChecked(),
                "volume.enable": self.chk_volume.isChecked(),
                "volume.inverse": self.chk_volume_inverse.isChecked(),
                "scivis.enable": self.chk_scivis.isChecked(),
                "scivis.component": self.spin_scivis_comp.value(),
            },
        }

    def _apply_config_to_ui(self, cfg: dict):
        if not cfg:
            return
        r = cfg.get("render", {})
        self.chk_raytracing.setChecked(r.get("raytracing.enable", False))
        self.chk_denoise.setChecked(r.get("raytracing.denoise", False))
        self.spin_rt_samples.setValue(r.get("raytracing.samples", 5))
        self.chk_ao.setChecked(r.get("effect.ambient_occlusion", False))
        self.chk_tone_mapping.setChecked(r.get("effect.tone_mapping", False))
        self.chk_aa.setChecked(r.get("effect.antialiasing.enable", False))
        aa = r.get("effect.antialiasing.mode", "fxaa")
        idx = self.cmb_aa_mode.findText(aa)
        if idx >= 0:
            self.cmb_aa_mode.setCurrentIndex(idx)
        self.chk_blending.setChecked(r.get("effect.blending.enable", False))
        self.chk_translucency.setChecked(r.get("effect.translucency_support", False))
        self.chk_skybox.setChecked(r.get("background.skybox", False))
        self.chk_bg_blur.setChecked(r.get("background.blur.enable", False))
        self.spin_bg_blur_coc.setValue(r.get("background.blur.coc", 20.0))
        bg = r.get("background.color", [0.2, 0.2, 0.2])
        if len(bg) >= 3:
            self.spin_bg_r.setValue(float(bg[0]))
            self.spin_bg_g.setValue(float(bg[1]))
            self.spin_bg_b.setValue(float(bg[2]))
        self.chk_depth.setChecked(r.get("effect.display_depth", False))

        s = cfg.get("scene", {})
        self.chk_hdri_ambient.setChecked(s.get("hdri.ambient", False))
        self.spin_light_intensity.setValue(s.get("light.intensity", 1.0))
        self.chk_grid.setChecked(s.get("grid.enable", False))
        self.chk_grid_absolute.setChecked(s.get("grid.absolute", False))
        self.spin_grid_subdivisions.setValue(s.get("grid.subdivisions", 10))
        self.chk_axes_grid.setChecked(s.get("axes_grid.enable", False))
        up = s.get("up_direction", [0.0, 1.0, 0.0])
        if len(up) >= 3:
            self.spin_up_x.setValue(float(up[0]))
            self.spin_up_y.setValue(float(up[1]))
            self.spin_up_z.setValue(float(up[2]))
        self.chk_invert_zoom.setChecked(s.get("invert_zoom", False))

        m = cfg.get("model", {})
        self.chk_checkerboard.setChecked(m.get("checkerboard.enable", False))
        self.chk_normal_glyphs.setChecked(m.get("normal_glyphs.enable", False))
        self.chk_armature.setChecked(m.get("armature.enable", False))
        self.chk_point_sprites.setChecked(m.get("point_sprites.enable", False))
        self.spin_point_size.setValue(m.get("point_sprites.size", 10.0))
        pt = m.get("point_sprites.type", "sphere")
        idx = self.cmb_point_type.findText(pt)
        if idx >= 0:
            self.cmb_point_type.setCurrentIndex(idx)
        self.chk_point_absolute.setChecked(m.get("point_sprites.absolute_size", False))
        self.chk_volume.setChecked(m.get("volume.enable", False))
        self.chk_volume_inverse.setChecked(m.get("volume.inverse", False))
        self.chk_scivis.setChecked(m.get("scivis.enable", False))
        self.spin_scivis_comp.setValue(m.get("scivis.component", -1))

    # ══════════════════════════════════════════════════════════════
    #  Пресеты
    # ══════════════════════════════════════════════════════════════

    def _refresh_presets_list(self):
        self.presets_list.clear()
        if not os.path.isdir(CONFIGS_DIR):
            return
        for fname in sorted(os.listdir(CONFIGS_DIR)):
            if fname.endswith(".json"):
                self.presets_list.addItem(fname)

    def _get_preset_path(self, name: str) -> str:
        if not name.endswith(".json"):
            name += ".json"
        return os.path.join(CONFIGS_DIR, name)

    def _save_preset(self):
        name, ok = QInputDialog.getText(
            self, "Сохранить конфиг", "Имя конфига:", text="my_settings"
        )
        if not ok or not name.strip():
            return
        name = name.strip().replace(" ", "_")
        cfg = self._collect_config()
        os.makedirs(CONFIGS_DIR, exist_ok=True)
        path = self._get_preset_path(name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        self._refresh_presets_list()
        QMessageBox.information(self, "Сохранено", f"Конфиг сохранён:\n{name}")

    def _load_preset(self):
        item = self.presets_list.currentItem()
        if not item:
            QMessageBox.information(self, "Инфо", "Выберите конфиг из списка")
            return
        path = self._get_preset_path(item.text())
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self._apply_config_to_ui(cfg)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить:\n{e}")

    def _load_and_apply_preset(self):
        item = self.presets_list.currentItem()
        if not item:
            QMessageBox.information(self, "Инфо", "Выберите конфиг из списка")
            return
        path = self._get_preset_path(item.text())
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self._apply_config_to_ui(cfg)
            self._apply_settings()
            QMessageBox.information(self, "Готово", f"Конфиг \"{item.text()}\" применён")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить:\n{e}")

    def _delete_preset(self):
        item = self.presets_list.currentItem()
        if not item:
            return
        reply = QMessageBox.question(
            self, "Удалить",
            f"Удалить конфиг \"{item.text()}\"?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            os.remove(self._get_preset_path(item.text()))
            self._refresh_presets_list()

    # ─── Экспорт / Импорт ────────────────────────────────────────

    def _export_config(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт конфига", "", "JSON (*.json);;Все (*)"
        )
        if not path:
            return
        cfg = self._collect_config()
        if not path.endswith(".json"):
            path += ".json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        QMessageBox.information(self, "Готово", f"Сохранено:\n{path}")

    def _import_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Импорт конфига", "", "JSON (*.json);;Все (*)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self._apply_config_to_ui(cfg)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить:\n{e}")

    # ══════════════════════════════════════════════════════════════
    #  Применение настроек к движку
    # ══════════════════════════════════════════════════════════════

    def _apply_only(self):
        self._apply_settings()

    def _apply_and_close(self):
        self._apply_settings()
        self.accept()

    def _apply_settings(self):
        f = self.f3d
        applied = 0
        failed = 0

        settings_map = {
            # Рендеринг
            "render.raytracing.enable": self.chk_raytracing.isChecked(),
            "render.raytracing.denoise": self.chk_denoise.isChecked(),
            "render.raytracing.samples": self.spin_rt_samples.value(),
            "render.effect.ambient_occlusion": self.chk_ao.isChecked(),
            "render.effect.tone_mapping": self.chk_tone_mapping.isChecked(),
            "render.effect.antialiasing.enable": self.chk_aa.isChecked(),
            "render.effect.antialiasing.mode": self.cmb_aa_mode.currentText(),
            "render.effect.blending.enable": self.chk_blending.isChecked(),
            "render.effect.translucency_support": self.chk_translucency.isChecked(),
            "render.background.skybox": self.chk_skybox.isChecked(),
            "render.background.blur.enable": self.chk_bg_blur.isChecked(),
            "render.background.blur.coc": self.spin_bg_blur_coc.value(),
            "render.background.color": [
                self.spin_bg_r.value(),
                self.spin_bg_g.value(),
                self.spin_bg_b.value(),
            ],
            "render.effect.display_depth": self.chk_depth.isChecked(),
            # Сцена
            "render.hdri.ambient": self.chk_hdri_ambient.isChecked(),
            "render.light.intensity": self.spin_light_intensity.value(),
            "render.grid.enable": self.chk_grid.isChecked(),
            "render.grid.absolute": self.chk_grid_absolute.isChecked(),
            "render.grid.subdivisions": self.spin_grid_subdivisions.value(),
            "render.axes_grid.enable": self.chk_axes_grid.isChecked(),
            "scene.up_direction": [
                self.spin_up_x.value(),
                self.spin_up_y.value(),
                self.spin_up_z.value(),
            ],
            "interactor.invert_zoom": self.chk_invert_zoom.isChecked(),
            # Модель
            "model.checkerboard.enable": self.chk_checkerboard.isChecked(),
            "model.normal_glyphs.enable": self.chk_normal_glyphs.isChecked(),
            "render.armature.enable": self.chk_armature.isChecked(),
            "model.point_sprites.enable": self.chk_point_sprites.isChecked(),
            "model.point_sprites.size": self.spin_point_size.value(),
            "model.point_sprites.type": self.cmb_point_type.currentText(),
            "model.point_sprites.absolute_size": self.chk_point_absolute.isChecked(),
            "model.volume.enable": self.chk_volume.isChecked(),
            "model.volume.inverse": self.chk_volume_inverse.isChecked(),
            "model.scivis.enable": self.chk_scivis.isChecked(),
            "model.scivis.component": self.spin_scivis_comp.value(),
        }

        for key, value in settings_map.items():
            if f.set_option(key, value):
                applied += 1
            else:
                failed += 1

        print(f"[Settings] Применено: {applied}, ошибок: {failed}")

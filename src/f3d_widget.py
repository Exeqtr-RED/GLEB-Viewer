"""
F3D Widget — встраивание F3D 3.5.0 в PySide6 через offscreen рендеринг.

Управление камерой через сферические координаты (azimuth, elevation, distance).
Position камеры вычисляется напрямую — view_up всегда (0,1,0), крен = 0.
"""

import os
import f3d
import math
import numpy as np
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPainter, QImage


class F3DWidget(QWidget):
    """Виджет с offscreen-рендерингом F3D 3.5.0."""

    # Все сигналы — на уровне класса!
    scene_loaded = Signal(str, object)
    scene_cleared = Signal()
    error_occurred = Signal(str)
    animation_state_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = None
        self._last_image = None
        self._current_model_path = None  # Текущий загруженный файл модели
        self._last_mouse_pos = None
        self._current_button = None
        self._pending_hdri_path = None  # HDRI, которую нужно применить после инициализации движка

        # -- Управление камерой (сферическая орбита) ------------
        # Состояние камеры — источник правды. Движок только получает
        # эти значения через _apply_camera_to_engine().
        self._cam_azimuth = 0.0          # градусы, горизонтальный угол
        self._cam_elevation = 30.0       # градусы, вертикальный угол
        self._cam_distance = 1.0         # расстояние до фокуса (мировые единицы)
        self._cam_focal_point = [0.0, 0.0, 0.0]  # точка фокуса (мировые координаты)
        self._cam_synced = False         # флаг: состояние синхронизировано с движком

        # Чувствительность
        self._rotate_sensitivity = 0.4   # градусы на пиксель
        self._pan_sensitivity = 0.5      # множитель панорамирования
        self._zoom_sensitivity = 0.08    # множитель зума колёсиком

        # Инерция (damping): 1.0 = мгновенная остановка, меньше = плавное затухание
        self._damping = 0.85

        # Скорости для инерции
        self._vel_azimuth = 0.0          # градусы/кадр
        self._vel_elevation = 0.0        # градусы/кадр
        self._vel_pan = np.zeros(3)      # смещение фокуса/кадр (мировые координаты)

        # Ограничения
        self._elevation_min = -85.0      # минимальный угол возвышения (градусы)
        self._elevation_max = 85.0       # максимальный угол возвышения (градусы)
        self._zoom_min_distance = 0.01   # минимальное расстояние до фокуса
        self._zoom_max_distance = 500.0  # максимальное расстояние до фокуса

        # Множитель точности (Shift)
        self._precision_factor = 0.2

        # Анимация
        self._animation_playing = False
        self._animation_speed = 1.0
        self._animation_timer = QTimer(self)
        self._animation_timer.setInterval(33)  # ~30 fps
        self._animation_timer.timeout.connect(self._animation_tick)

        self.setMinimumSize(640, 480)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)  # для слежения при зажатой кнопке

        # Таймер рендеринга (~60fps, только при взаимодействии)
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(16)
        self._render_timer.timeout.connect(self._render_frame)

        # Таймер остановки при бездействии
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.setInterval(800)
        self._idle_timer.timeout.connect(self._stop_loop)

    def _init_engine(self):
        if self.engine is not None:
            return
        try:
            self.engine = f3d.Engine.create(offscreen=True)
            self.engine.window.size = (self.width(), self.height())
            print(f"[F3D] Движок создан (offscreen), версия {f3d.__version__}")

            # Применить отложенную HDRI (если set_hdri вызван до init)
            if self._pending_hdri_path is not None:
                print(f"[F3D] Применение отложенной HDRI: {os.path.basename(self._pending_hdri_path)}")
                self._apply_hdri_internal(self._pending_hdri_path)
                self._pending_hdri_path = None
        except Exception as e:
            print(f"[F3D] Ошибка создания движка: {e}")
            self.error_occurred.emit(f"Не удалось создать F3D: {e}")
            self.engine = None

    # --- Цикл рендеринга ---------------------------------------------

    def _start_loop(self):
        if not self._render_timer.isActive():
            self._render_timer.start()
        self._idle_timer.start()

    def _stop_loop(self):
        self._render_timer.stop()
        self._render_frame()

    def _render_frame(self):
        if not self.engine:
            return
        try:
            # Применяем инерцию (обновляем наше состояние камеры)
            if self._cam_synced:
                if abs(self._vel_azimuth) > 0.001:
                    self._cam_azimuth += self._vel_azimuth
                if abs(self._vel_elevation) > 0.001:
                    self._cam_elevation += self._vel_elevation
                    self._cam_elevation = max(self._elevation_min,
                                              min(self._elevation_max, self._cam_elevation))
                pan_norm = np.linalg.norm(self._vel_pan)
                if pan_norm > 1e-8:
                    fp = np.array(self._cam_focal_point) + self._vel_pan
                    self._cam_focal_point = fp.tolist()

                # Затухание скоростей
                if self._damping > 0:
                    self._vel_azimuth *= self._damping
                    self._vel_elevation *= self._damping
                    self._vel_pan *= self._damping
                else:
                    self._vel_azimuth = 0.0
                    self._vel_elevation = 0.0
                    self._vel_pan = np.zeros(3)

            # Пушим наше состояние камеры в движок ПЕРЕД рендером
            if self._cam_synced:
                self._apply_camera_to_engine()

            self.engine.window.size = (self.width(), self.height())
            img = self.engine.window.render_to_image()
            if img is not None:
                self._last_image = self._f3d_image_to_qimage(img)
                self.update()
        except Exception as e:
            print(f"[F3D] Render error: {e}")

    def render_to_file(self, filepath: str, size: tuple[int, int] = (1024, 1024)) -> bool:
        """Отрендерить текущую сцену и сохранить как PNG (без зеркалирования UI)."""
        self._init_engine()
        if not self.engine:
            return False
        try:
            self._apply_camera_to_engine()
            self.engine.window.size = size
            img = self.engine.window.render_to_image()
            if img is None:
                return False

            w = img.width
            h = img.height
            channels = img.channel_count
            arr = np.frombuffer(img.content, dtype=np.uint8).reshape((h, w, channels))
            arr = np.flipud(arr).copy()

            if channels == 4:
                fmt = QImage.Format.Format_RGBA8888
            elif channels == 3:
                fmt = QImage.Format.Format_RGB888
            else:
                return False

            qimg = QImage(arr.data.tobytes(), w, h, w * channels, fmt).copy()
            result = qimg.save(filepath)
            # Восстановить размер виджета и камеру
            self.engine.window.size = (self.width(), self.height())
            self._apply_camera_to_engine()
            return result
        except Exception as e:
            print(f"[F3D] Ошибка сохранения скриншота: {e}")
            return False

    def _f3d_image_to_qimage(self, f3d_img) -> QImage:
        w = f3d_img.width
        h = f3d_img.height
        channels = f3d_img.channel_count
        arr = np.frombuffer(f3d_img.content, dtype=np.uint8).reshape((h, w, channels))

        # OpenGL offscreen: origin в bottom-left — переворачиваем по вертикали
        arr = np.flipud(arr).copy()

        if channels == 4:
            fmt = QImage.Format.Format_RGBA8888
        elif channels == 3:
            fmt = QImage.Format.Format_RGB888
        else:
            return QImage()

        return QImage(arr.data.tobytes(), w, h, w * channels, fmt).copy()

    # --- paintEvent / resizeEvent -------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._last_image:
            painter.drawImage(self.rect(), self._last_image)
        else:
            painter.fillRect(self.rect(), Qt.GlobalColor.darkGray)
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter,
                "Перетащите 3D модель сюда\nили Настройки -> Открыть папку"
            )
        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.engine:
            self.engine.window.size = (self.width(), self.height())
            self._render_frame()

    # --- Модели ------------------------------------------------------

    def load_model(self, filepath: str, user_data=None) -> bool:
        self._init_engine()
        if not self.engine:
            self.error_occurred.emit("Движок F3D не инициализирован")
            return False
        try:
            if not self.engine.scene.supports(filepath):  # type: ignore[arg-type]
                self.error_occurred.emit(f"Формат не поддерживается: {filepath}")
                return False
            self._current_model_path = filepath
            self.engine.scene.add(filepath)
            cam = self.engine.window.camera
            cam.reset_to_bounds()
            cam.view_up = (0, 1, 0)
            # Считываем состояние камеры, которое установил reset_to_bounds
            self._sync_camera_from_engine()
            self._render_frame()
            self.scene_loaded.emit(filepath, user_data)
            print(f"[F3D] Модель загружена: {filepath}")
            return True
        except Exception as e:
            print(f"[F3D] Ошибка загрузки: {e}")
            self.error_occurred.emit(str(e))
            return False

    def clear_scene(self):
        if self.engine:
            self.engine.scene.clear()
            self._last_image = None
            self._current_model_path = None
            self._cam_synced = False
            self.update()
            self.scene_cleared.emit()

    def reload_model(self) -> bool:
        """Перезагрузить текущую модель (с текущими опциями — wireframe и т.д.)."""
        if not self._current_model_path or not self.engine:
            return False
        try:
            filepath = self._current_model_path
            self.engine.scene.clear()
            self.engine.scene.add(filepath)
            # Камеру НЕ сбрасываем — пользователь мог настроить вид
            self._render_frame()
            print(f"[F3D] Модель перезагружена с текущими опциями: {filepath}")
            return True
        except Exception as e:
            print(f"[F3D] Ошибка перезагрузки модели: {e}")
            return False

    def reset_camera(self):
        if self.engine:
            cam = self.engine.window.camera
            cam.reset_to_bounds()
            cam.view_up = (0, 1, 0)
            self._sync_camera_from_engine()
            self._render_frame()


    # --- HDRI -------------------------------------------------------

    def set_hdri(self, hdri_path: str | None) -> bool:
        """
        Установить HDRI карту.
        hdri_path — абсолютный путь к .hdr/.exr файлу, или None для сброса.
        Если движок ещё не инициализирован — путь сохраняется и применяется при init.
        """
        if hdri_path is None:
            # Сброс HDRI
            if not self.engine:
                self._pending_hdri_path = None
                return True
            return self._apply_hdri_internal(None)

        if not os.path.isfile(hdri_path):
            print(f"[F3D] HDRI: файл не найден: {hdri_path}")
            return False

        if not self.engine:
            # Движок ещё не создан — отложим до _init_engine()
            print(f"[F3D] HDRI: движок не инициализирован, откладываем: {os.path.basename(hdri_path)}")
            self._pending_hdri_path = hdri_path
            return True

        return self._apply_hdri_internal(hdri_path)

    def _apply_hdri_internal(self, hdri_path: str | None) -> bool:
        """Внутренняя установка HDRI (движок должен существовать)."""
        if not self.engine:
            return False
        try:
            if hdri_path is not None:
                # Пробуем разные варианты имён опций — f3d 3.5.0 может использовать другие
                opt_names = [
                    "render.hdri.file",
                    "scene.background.hdri.file",
                    "background.hdri.file",
                ]

                file_set = False
                for opt_name in opt_names:
                    try:
                        self.engine.options[opt_name] = hdri_path
                        file_set = True
                        print(f"[F3D] HDRI файл установлен через: {opt_name}")
                        break
                    except (KeyError, Exception) as e:
                        print(f"[F3D] Опция '{opt_name}' недоступна: {e}")
                        continue

                if not file_set:
                    # Последняя попытка: принудительная запись
                    self.engine.options["render.hdri.file"] = hdri_path
                    print(f"[F3D] HDRI файл установлен принудительно: render.hdri.file")

                # Включаем ambient и skybox (имена опций из f3d 3.5.0)
                hdri_toggles = {
                    "render.hdri.ambient": True,
                    "render.background.skybox": True,   # НЕ render.hdri.skybox!
                }
                for opt, val in hdri_toggles.items():
                    try:
                        self.engine.options[opt] = val
                        print(f"[F3D] {opt} = {val}")
                    except Exception as e:
                        print(f"[F3D] Не удалось установить {opt}: {e}")

                self._render_frame()
                print(f"[F3D] HDRI установлена: {os.path.basename(hdri_path)}")
                return True
            else:
                # Сбросить HDRI
                try:
                    self.engine.options["render.hdri.file"] = ""
                    self.engine.options["render.hdri.ambient"] = False
                    self.engine.options["render.background.skybox"] = False
                except Exception:
                    pass
                self._render_frame()
                print(f"[F3D] HDRI сброшена")
                return True
        except Exception as e:
            print(f"[F3D] HDRI ошибка: {e}")
            return False

    # --- Анимация ---------------------------------------------------

    def play_animation(self):
        self._init_engine()
        if not self.engine:
            return
        self._animation_playing = True
        self._animation_timer.start()
        print("[F3D] Animation: play")
        self.animation_state_changed.emit(True)

    def stop_animation(self):
        self._animation_timer.stop()
        self._animation_playing = False
        print("[F3D] Animation: stop")
        self.animation_state_changed.emit(False)

    def toggle_animation(self):
        if self._animation_playing:
            self.stop_animation()
        else:
            self.play_animation()

    def set_animation_speed(self, speed: float):
        self._animation_speed = speed
        print(f"[F3D] Animation speed: {speed}x")

    @property
    def is_animating(self) -> bool:
        return self._animation_playing

    @property
    def animation_speed(self) -> float:
        """Текущая скорость анимации (read-only)."""
        return self._animation_speed

    def _animation_tick(self):
        if not self.engine or not self._animation_playing:
            return
        try:
            # Пробуем продвинуть время анимации через разные API
            try:
                am = self.engine.animation_manager  # type: ignore[union-attr]
                # f3d может автоматически продвигать время
            except AttributeError:
                pass
            try:
                try:
                    cur = self.engine.options["scene.animation.time"]  # type: ignore[union-attr]
                except (KeyError, TypeError):
                    cur = 0
                if isinstance(cur, (int, float)):
                    self.engine.options["scene.animation.time"] = cur + 0.033 * self._animation_speed
            except Exception:
                pass
            self._render_frame()
        except Exception as e:
            print(f"[F3D] Animation error: {e}")

    # --- Опции -------------------------------------------------------

    def set_option(self, key: str, value):
        if not self.engine:
            print(f"[F3D] set_option '{key}' — движок не инициализирован")
            return False
        try:
            # Проверяем существование опции
            try:
                current = self.engine.options[key]
                print(f"[F3D] set_option '{key}': {current} -> {value}")
            except (KeyError, TypeError):
                print(f"[F3D] set_option '{key}': опция не найдена, пробуем установить {value}")
            
            self.engine.options[key] = value
            
            # Опции model.* (wireframe, normal_glyphs и т.д.) применяются
            # только при загрузке модели — перезагружаем без сброса камеры
            if key.startswith("model.") and self._current_model_path:
                self.engine.scene.clear()
                self.engine.scene.add(self._current_model_path)
                print(f"[F3D] Перезагрузка модели для опции '{key}'")
            
            self._render_frame()
            # Проверяем что опция реально применилась
            try:
                actual = self.engine.options[key]
                print(f"[F3D] set_option '{key}' = {value} — ОК (фактически: {actual})")
            except Exception:
                print(f"[F3D] set_option '{key}' = {value} — не удалось прочитать обратно")
            return True
        except Exception as e:
            print(f"[F3D] set_option '{key}' = {value} — ОШИБКА: {e}")
            return False

    def get_option(self, key: str):
        if self.engine:
            try:
                return self.engine.options[key]
            except (KeyError, AttributeError):
                return None
        return None

    def toggle_option(self, key: str):
        if self.engine:
            try:
                current = self.engine.options[key]
                self.engine.options[key] = not current
                self._render_frame()
                print(f"[F3D] toggle '{key}' = {self.engine.options[key]}")
            except Exception as e:
                print(f"[F3D] toggle error '{key}': {e}")

    def get_all_options(self) -> dict:
        if not self.engine:
            return {}
        result = {}
        try:
            # Попробуем разные способы получить список опций
            keys = list(self.engine.options.keys())
            for k in keys:
                try:
                    result[k] = self.engine.options[k]
                except Exception:
                    pass
        except Exception as e:
            print(f"[F3D] get_all_options error: {e}")
        return result

    def _sync_camera_from_engine(self):
        """Прочитать текущее состояние камеры из движка в наши переменные.
        Вызывать после reset_to_bounds() и загрузки модели."""
        if not self.engine:
            return
        try:
            cam = self.engine.window.camera
            pos = np.array(cam.position, dtype=float)
            fp = np.array(cam.focal_point, dtype=float)

            diff = fp - pos
            self._cam_distance = float(np.linalg.norm(diff))
            self._cam_focal_point = fp.tolist()

            if self._cam_distance > 1e-9:
                d = diff / self._cam_distance
                self._cam_elevation = math.degrees(
                    math.asin(float(np.clip(d[1], -1.0, 1.0)))
                )
                self._cam_azimuth = math.degrees(
                    math.atan2(float(d[0]), float(d[2]))
                )

            self._cam_synced = True
            print(f"[Cam] Synced: az={self._cam_azimuth:.1f} el={self._cam_elevation:.1f} dist={self._cam_distance:.3f}")
        except Exception as e:
            print(f"[Cam] Sync error: {e}")

    def _apply_camera_to_engine(self):
        """Установить камеру движка из наших сферических координат.
        Вызывать перед каждым render_to_image()."""
        if not self.engine:
            return
        try:
            cam = self.engine.window.camera

            az = math.radians(self._cam_azimuth)
            el = math.radians(self._cam_elevation)
            ce = math.cos(el)
            se = math.sin(el)
            ca = math.cos(az)
            sa = math.sin(az)

            fp = np.array(self._cam_focal_point, dtype=float)
            pos = np.array([
                fp[0] + self._cam_distance * ce * sa,
                fp[1] + self._cam_distance * se,
                fp[2] + self._cam_distance * ce * ca,
            ])

            cam.position = (float(pos[0]), float(pos[1]), float(pos[2]))
            cam.focal_point = (float(fp[0]), float(fp[1]), float(fp[2]))
            cam.view_up = (0.0, 1.0, 0.0)
        except Exception as e:
            print(f"[Cam] Apply error: {e}")

    def _get_camera_axes(self):
        """Правый и верхний векторы камеры в мировых координатах."""
        az = math.radians(self._cam_azimuth)
        el = math.radians(self._cam_elevation)
        ce = math.cos(el)
        se = math.sin(el)
        ca = math.cos(az)
        sa = math.sin(az)

        forward = np.array([ce * sa, se, ce * ca])
        world_up = np.array([0.0, 1.0, 0.0])

        right = np.cross(forward, world_up)
        rl = np.linalg.norm(right)
        if rl < 1e-6:
            right = np.array([1.0, 0.0, 0.0])
        else:
            right /= rl

        up = np.cross(right, forward)
        up /= np.linalg.norm(up)

        return right, up

    # --- Мышь -> управление камерой -----------------------------------
    #
    # ЛКМ (Left)          -> Орбитальное вращение (orbit)
    # Ср. кнопка (Middle)  -> Панорамирование (pan)
    # ПКМ (Right)          -> Панорамирование (pan)
    # Колёсико             -> Зум (dolly)
    #
    # Shift — режим точности (в 5 раз медленнее).

    def _is_invert_zoom(self) -> bool:
        """Проверить настройку инверсии зума из движка."""
        if not self.engine:
            return False
        try:
            return bool(self.engine.options["interactor.invert_zoom"])
        except (KeyError, AttributeError):
            return False

    def mousePressEvent(self, event):
        if not self.engine or event.button() not in (
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.RightButton,
        ):
            return
        if event.button() == Qt.MouseButton.RightButton:
            event.accept()
        self._init_engine()
        self._last_mouse_pos = event.position()
        self._current_button = event.button()
        self._vel_azimuth = 0.0
        self._vel_elevation = 0.0
        self._vel_pan = np.zeros(3)
        self._start_loop()

    def mouseReleaseEvent(self, event):
        if event.button() == self._current_button:
            self._current_button = None
        self._last_mouse_pos = None
        self._idle_timer.start()

    def mouseMoveEvent(self, event):
        if not self.engine or self._last_mouse_pos is None or self._current_button is None:
            return
        if not self._cam_synced:
            return

        pos = event.position()
        dx = pos.x() - self._last_mouse_pos.x()
        dy = pos.y() - self._last_mouse_pos.y()
        self._last_mouse_pos = pos

        ref_size = max(self.width(), self.height(), 1)
        scale = 1000.0 / ref_size

        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            scale *= self._precision_factor

        if self._current_button == Qt.MouseButton.LeftButton:
            az = dx * self._rotate_sensitivity * scale
            el = -dy * self._rotate_sensitivity * scale

            self._cam_azimuth += az
            self._cam_elevation += el
            self._cam_elevation = max(self._elevation_min,
                                      min(self._elevation_max, self._cam_elevation))

            if self._damping > 0:
                self._vel_azimuth = az
                self._vel_elevation = el

        elif self._current_button in (
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.RightButton,
        ):
            pan_speed = self._cam_distance * self._pan_sensitivity * scale * 0.001
            right, up = self._get_camera_axes()
            displacement = right * (-dx * pan_speed) + up * (dy * pan_speed)
            self._cam_focal_point = (np.array(self._cam_focal_point) + displacement).tolist()

            if self._damping > 0:
                self._vel_pan = displacement

        self._idle_timer.start()

    def wheelEvent(self, event):
        if not self.engine or not self._cam_synced:
            return
        self._init_engine()
        delta = event.angleDelta().y()
        invert = self._is_invert_zoom()

        zoom_sens = self._zoom_sensitivity
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            zoom_sens *= self._precision_factor

        factor = 1.0 + zoom_sens

        if delta > 0:
            if invert:
                self._cam_distance *= factor
            else:
                self._cam_distance /= factor
        elif delta < 0:
            if invert:
                self._cam_distance /= factor
            else:
                self._cam_distance *= factor

        self._cam_distance = max(self._zoom_min_distance,
                                  min(self._zoom_max_distance, self._cam_distance))
        self._start_loop()

    def keyPressEvent(self, event):
        if not self.engine or not self._cam_synced:
            return
        key = event.key()

        step = max(2.0, min(8.0, self.width() / 200.0))
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            step *= self._precision_factor

        handled = True
        if key in (Qt.Key.Key_Left, Qt.Key.Key_A):
            self._cam_azimuth -= step
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_D):
            self._cam_azimuth += step
        elif key in (Qt.Key.Key_Up, Qt.Key.Key_W):
            self._cam_elevation = min(self._elevation_max, self._cam_elevation + step)
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_S):
            self._cam_elevation = max(self._elevation_min, self._cam_elevation - step)
        elif key == Qt.Key.Key_R:
            self.reset_camera()
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self._cam_distance = max(self._zoom_min_distance, self._cam_distance / 1.1)
        elif key == Qt.Key.Key_Minus:
            self._cam_distance = min(self._zoom_max_distance, self._cam_distance * 1.1)
        elif key == Qt.Key.Key_Q:
            right, _ = self._get_camera_axes()
            pan_amt = right * (-self._cam_distance * 0.05)
            self._cam_focal_point = (np.array(self._cam_focal_point) + pan_amt).tolist()
        elif key == Qt.Key.Key_E:
            right, _ = self._get_camera_axes()
            pan_amt = right * (self._cam_distance * 0.05)
            self._cam_focal_point = (np.array(self._cam_focal_point) + pan_amt).tolist()
        else:
            handled = False

        if handled:
            self._start_loop()
            event.accept()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        self._idle_timer.start()
        super().keyReleaseEvent(event)

    # --- Публичные доступы -------------------------------------------

    @property
    def current_model_path(self) -> str | None:
        """Текущий загруженный файл модели (read-only)."""
        return self._current_model_path

    def ensure_engine(self) -> bool:
        """Инициализировать движок, если ещё не создан. Вернёт True при успехе."""
        self._init_engine()
        return self.engine is not None

    def cleanup(self):
        self._render_timer.stop()
        self._idle_timer.stop()
        self.engine = None
        self._last_image = None

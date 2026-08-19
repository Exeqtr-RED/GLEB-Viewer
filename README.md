# GLEB Viewer — libf3d Embedded

F3D просмотрщик 3D-моделей, встроенный в PySide6 через **libf3d** (без внешнего f3d.exe).

## Отличия от subprocess-подхода

| | subprocess (старое) | libf3d (новое) |
|---|---|---|
| f3d.exe | Нужен рядом с программой | Не нужен |
| Запуск модели | ~5-10 сек (процесс + таймеры) | Мгновенно |
| Встраивание | win32gui SetParent + QTimer | Нативное окно libf3d |
| Скриншоты | Отдельный subprocess | `render_to_image()` |
| Завершение | QProcess.terminate() | `cleanup()` в том же процессе |

## Установка

### 1. Создать виртуальное окружение

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Установить зависимости

```powershell
pip install -r requirements.txt
```

### 3. Проверить

```powershell
python -c "import f3d; print('f3d', f3d.__version__)"
python -c "import PySide6; print('PySide6', PySide6.__version__)"
```

### 4. Запуск

```powershell
python main.py
```

Или **F5** в VS Code.

## Использование

1. **Файл → Открыть модель** (Ctrl+O) — выбрать .glb, .fbx, .obj и т.д.
2. **Настройки** — HDRI, AO, тон-маппинг, антиалиасинг
3. **Скриншот** (Ctrl+S) — сохранить текущий вид в PNG/JPG

## Поддерживаемые форматы

glTF/GLB, FBX, OBJ, STL, PLY, VTK, ABC, USD, 3DS, DAE, PBRt и другие (через VTK).

## Как это работает

```
┌─────────────────────────────────────┐
│  PySide6 MainWindow                │
│  ┌───────────────────────────────┐  │
│  │  F3DViewer (QWidget)          │  │
│  │  ┌─────────────────────────┐  │  │
│  │  │ libf3d native window    │  │  │
│  │  │ (HWND через SetParent)  │  │  │
│  │  │                         │  │  │
│  │  │  🎮 3D модель с мышью   │  │  │
│  │  └─────────────────────────┘  │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

- `libf3d` создаёт нативное окно с OpenGL-контекстом
- `F3DViewer` перехватывает HWND через `SetParent` в свой QWidget
- Вся интерактивность (вращение, масштабирование) работает через libf3d
- Никакого subprocess, никаких таймеров ожидания

## Структура

```
qt_f3d_embedded/
├── main.py                     # Точка входа
├── requirements.txt            # Зависимости
├── src/
│   ├── main_window.py          # Главное окно
│   ├── f3d_widget.py           # Ядро: libf3d → QWidget
│   └── f3d_settings_dialog.py  # Диалог настроек
├── .vscode/
│   ├── settings.json
│   ├── launch.json
│   └── tasks.json
└── hdri/                       # HDRI карты
```

## Интеграция в основной проект

Чтобы заменить subprocess-подход в основном qt_gleb_project:

1. `pip install f3d` — добавить в requirements.txt
2. Заменить `src/f3d/f3d_process_manager.py` → использовать `F3DViewer`
3. Удалить `src/f3d/window_embedder.py` (не нужен)
4. В `main_window.py`: заменить `F3DProcessManager` на `F3DViewer`
5. В `screenshot_worker.py`: использовать `f3d_widget.take_screenshot()`
6. Убрать зависимость от пути к `f3d.exe`

# ComicSplit — Техническая архитектура

**Версия:** 2.0 (июнь 2026)
**Отражает:** фактическую реализацию — split + anim + пресеты + Stage 2a (ExText) + **workspace project mode** (API v1.5)
> Исходная целевая спецификация (Go + Wails + gRPC) сохранена в `archive/ComicSplit_Specification_v2.0.md`.

---

## 1. Назначение проекта

**ComicSplit** — десктопная утилита Windows для автоматической нарезки страниц комикса на панели и последующего «оживления» панелей (апскейл, гармонизация 16:9, анимированный MP4). Опционально — извлечение текста (ExText / Story Analyzer Stage 2a).

Типичный сценарий использования:

```
CBZ / PNG страницы  →  PNG панели  →  апскейл  →  16:9  →  MP4 клипы  →  раскадровка
                                                   ↓
                                          ExText: bbox баблов + OCR
```

---

## 2. Целевое железо (hard constraint)

Все технологические решения приняты под конкретную машину разработчика:

| Параметр | Значение |
|----------|----------|
| CPU | AMD Ryzen 5 5600H (6 ядер / 12 потоков, 3.3 GHz, Zen 3) |
| GPU | AMD Radeon Graphics (iGPU, ~1 GB разделяемой VRAM) |
| RAM | 16 GB DDR4-3200 |
| Диск | 477 GB SSD (занято ~350 GB) |
| ОС | Windows 10/11 (64-bit) |

**Ключевые ограничения:**

- ❌ NVIDIA CUDA — нет; диффузионные модели (SD, SVD, AnimateDiff) — вне проекта
- ❌ ROCm на iGPU — официально не поддерживается на мобильных APU серии Ryzen 5000H
- ✅ ONNX Runtime CPU — основной inference backend
- ✅ NCNN + Vulkan — апскейл через AMD Radeon iGPU (Vulkan 1.3)
- ✅ 16 GB RAM — позволяет держать несколько лёгких моделей в памяти одновременно
- ✅ OpenGL (AMD драйверы) — рендеринг DepthFlow parallax

---

## 3. Фактическая архитектура (июнь 2026)

### Обзор компонентов

```
┌─────────────────────────────────────────────────────────────┐
│                    Интерфейсы пользователя                   │
│                                                             │
│  Gradio :7860          Web Editor :8000       CLI           │
│  (main.py)             (api/server.py          (pipeline.py │
│  Split / Upscale /     + frontend/index.html)  anim_pipeline│
│  Video; пресеты        + workspace.js           .py)        │
└──────────┬──────────────────┬──────────────────────────────┘
           │                  │
┌──────────▼──────────────────▼──────────────────────────────┐
│                     Ядро (Python 3.11)                      │
│                                                             │
│  pipeline.py          anim_pipeline.py                      │
│  (split ML)           (upscale → 16:9 → animate → MP4)     │
│                                                             │
│  utils/: config, anim_config, presets, io_helpers,         │
│          path_resolve, ui_tooltips, path_dialog,           │
│          models_registry, panel_detector,                  │
│          ui_state, workspace_paths, split_pages            │
└──────────┬──────────────────┬───────────────────────────────┘
           │                  │
┌──────────▼──────────┐   ┌──▼──────────────────────────────┐
│  Split моделей      │   │  Anim инструменты               │
│                     │   │                                  │
│  ONNX Runtime CPU   │   │  NCNN + Vulkan (AMD iGPU)        │
│  yolo_comic_int8    │   │  Real-ESRGAN / CUGAN / SPAN      │
│  yolo_manga_int8    │   │                                  │
│  mobilesam_*_int8   │   │  DepthFlow (OpenGL + CPU)        │
│                     │   │  OpenCV эффекты                  │
│  Story 2a bubbles:  │   │  TPSMM ONNX (motion transfer)    │
│  yolo_manga class 1 │   │  ffmpeg (MP4, concat)            │
│                     │   │                                  │
│  OCR: SiliconFlow   │   │                                  │
│  VLM (облако API)   │   │                                  │
└─────────────────────┘   └──────────────────────────────────┘
```

### Потоки данных

**Split:**
```
Вход (CBZ/PNG/папка)
  → io_helpers.load_source()
  → YOLO INT8 → bboxes
  → [Accurate] MobileSAM INT8 → маска/полигон
  → cv2 crop → PNG панели в output/ (или story_out/projects/<name>/panels/)
  → _visualization.jpg
```

**Anim:**
```
PNG панели (из output/ или project/panels/)
  → anim/upscale.py   (NCNN subprocess: realesrgan / realcugan / span)
  → anim/harmonize.py (OpenCV: blurred_pillarbox / dominant_color / smart_crop)
  → anim/animate_opencv.py | animate_depthflow.py | animate_tpsmm.py (driving MP4)
  → anim/render.py    (ffmpeg → MP4)
  → anim_pipeline.concat_storyboard() → storyboard.mp4
```

**Story 2a (ExText):**
```
PNG панели (рекомендуется upscaled ×2)
  → yolo_manga_int8 (tiled YOLO, class 1) → bbox баблов
  → crop bubble (+padding)
  → SiliconFlow VLM OCR (Qwen3-VL-8B)  [fallback: Paddle/EasyOCR]
  → stage_2a.json + Konva editor (bbox, text, reading_order)
```

---

## 4. Технологический стек

| Слой | Технология | Версия | Причина выбора |
|------|-----------|--------|----------------|
| Язык | Python | 3.11 | Единый язык, ML-экосистема, простая отладка |
| ML inference (split + Stage 2a) | ONNX Runtime | 1.26 | CPU-only, быстрая загрузка, кроссплатформа |
| ML inference (upscale) | NCNN + Vulkan | — | AMD iGPU через Vulkan, без CUDA |
| Детекция панелей | YOLOv11n-seg INT8 | — | ~3 MB, Ryzen 5600H ≈ 400–800 ms/стр. |
| Маски | MobileSAM INT8 | — | ~40 MB, контурная маска по bbox |
| Апскейл | Real-ESRGAN / CUGAN / SPAN | NCNN | Vulkan-ускорение на AMD iGPU |
| Параллакс | DepthFlow + Depth Anything V2 Small | pip | Лучший 2.5D parallax на CPU |
| Анимация (быстро) | OpenCV | 4.x | Без ML, мгновенно |
| Видео | ffmpeg | — | Кодирование H.264, concat |
| UI десктоп | Gradio | 5.12 | Браузерный UI, 0 настройки |
| UI веб-редактор | FastAPI + Vanilla JS + Konva | 9 | REST API + Canvas-редактор масок |
| OCR (Stage 2a) | SiliconFlow VLM (Qwen3-VL-8B) | API | Лучшее качество ru/en OCR на кропах |
| OCR (fallback) | PaddleOCR / EasyOCR | — | Только offline-режим (`paddle \| easyocr \| auto`) |
| Конфиг | YAML + dataclass + Pydantic | — | Простая валидация, пресеты |
| Тесты | pytest | — | ~68 тестов |
| Упаковка | PyInstaller | — | Spec есть, сборка вручную |

**Go компоненты (частично):**

| Компонент | Статус | Назначение |
|-----------|--------|------------|
| `cmd/comicsplit/` + `comicsplit.exe` | ✅ Работает | Batch split CBZ/папка/JPG |
| `ml_worker/main.py` | ✅ Работает | IPC subprocess Python |
| gRPC Go↔Python | ❌ Не реализовано | Планировалось в v2.0 |

---

## 5. Структура проекта

```
SPLIT_PANELS_DEV/
├── main.py                   # Gradio :7860 (Split / Upscale / Video)
├── pipeline.py               # Split ML + CLI
├── anim_pipeline.py          # Anim CLI: upscale → 16:9 → animate → MP4
├── config.yaml               # Split конфиг
├── config_animate.yaml       # Anim конфиг
├── config/
│   ├── presets.yaml          # Пресеты Стандарт / Качество
│   ├── presets.user.yaml     # Локальные правки (в .gitignore)
│   ├── models_registry.yaml  # Реестр моделей + статус установки
│   ├── story_stage_2a.yaml   # Stage 2a конфиг
│   └── ui_state.user.json    # Память UI (в .gitignore)
├── requirements.txt
│
├── anim/                     # Модули оживления
│   ├── upscale.py            # NCNN subprocess (realesrgan/cugan/span)
│   ├── harmonize.py          # OpenCV 16:9 (3 режима)
│   ├── animate_opencv.py     # zoom / shake / chromatic
│   ├── animate_depthflow.py  # DepthFlow parallax
│   ├── animate_tpsmm.py      # TPSMM motion transfer (mode tpsmm)
│   ├── render.py             # ffmpeg → MP4
│   └── anim_config.py        # AnimConfig dataclass
│
├── utils/
│   ├── config.py             # AppConfig + load_config
│   ├── anim_config.py        # AnimConfig + load_anim_config
│   ├── presets.py            # load / apply / snapshot пресетов
│   ├── io_helpers.py         # CBZ/CBR/ZIP/папка/imdecode
│   ├── path_resolve.py       # Кириллица, Windows пути
│   ├── ui_tooltips.py        # Тексты подсказок UI
│   ├── path_dialog.py        # Нативные диалоги выбора файла/папки
│   ├── models_registry.py    # Проверка установки моделей
│   ├── panel_detector.py     # Выбор comic / manga YOLO
│   ├── ui_state.py           # Память UI v1 (split/upscale/video/story2a + current_project)
│   ├── workspace_paths.py    # Пути project mode для export/upscale/video
│   ├── split_pages.py        # list_split_pages() для batch Split
│   ├── upscale_options.py    # Backend/model payload для upscale UI
│   └── gradio_ui_state.py    # Восстановление Gradio из ui_state
│
├── api/
│   ├── server.py             # FastAPI v1.5.0 (:8000)
│   └── story_stage_2a.py     # Story Analyzer Stage 2a API
├── story_analyzer/           # Story Analyzer (Stage 2a+)
│   ├── paths.py              # Layout workspace: story_out/projects/<name>/
│   ├── config.py             # Stage2aConfig, SiliconFlowOcrConfig
│   ├── schemas.py            # Bubble, Panel, Stage2aDocument (Pydantic)
│   ├── env_loader.py         # .env для API keys
│   ├── ocr_engine_ids.py     # OCR_ENGINES
│   ├── stages/               # bubble_detector, ocr_*, stage_2a_processor
│   └── providers/            # siliconflow_ocr
├── config/story_stage_2a.yaml
├── frontend/
│   ├── index.html            # Konva + вкладки Split/Upscale/Video/ExText
│   ├── ui_state.js           # localStorage + sync /api/ui/state
│   ├── workspace.js          # Project mode (combobox, layout, paths)
│   ├── panel_nav.js          # Batch Split: prev/next страниц
│   ├── reading_order.js      # Порядок чтения (Split панели + Stage 2a баблы)
│   └── story_2a.js           # UI ExText (Stage 2a)
│
├── models/                   # Split ONNX (не в git)
│   └── anim/                 # NCNN, MiDaS, TPSMM, ffmpeg (не в git)
│
├── scripts/
│   ├── split_models_craft_scripts/   # Скачивание + квантование split
│   ├── download_animate_models.ps1
│   ├── download_upscale_backends.ps1 # CUGAN + SPAN
│   ├── quantize_animate_models.py
│   ├── verify_upscale_backends.py
│   └── benchmark_upscale.ps1
│
├── cmd/comicsplit/           # Go CLI
├── ml_worker/main.py         # IPC Python
├── tests/                    # ~68 pytest тестов
├── packaging/comicsplit.spec # PyInstaller
└── spec_s/                   # Документация
```

---

## 6. Ключевые архитектурные решения и отступления от v2.0

| Решение v2.0 | Фактически | Причина |
|---|---|---|
| Wails desktop UI | Gradio + FastAPI/HTML | Gradio — быстрее MVP; Wails не начат |
| gRPC Go↔Python | subprocess JSON IPC | gRPC избыточен для объёма задач MVP |
| Go как оркестратор | Python как основной ЯП | ML-экосистема проще в Python |
| PyInstaller EXE | Spec есть, сборка вручную | Не приоритет для личного инструмента |
| OpenCV fast-path каскад | Только YOLO + SAM | Достаточно для текущих задач |
| Локальный OCR (EasyOCR) primary | SiliconFlow VLM OCR primary | Локальный OCR не дал качества на ru-комиксах |

---

## 7. Пресеты качества

Два пресета в `config/presets.yaml`, согласованы между Gradio и :8000.

| Пресет | ID | Split | Anim |
|--------|-----|-------|------|
| **Стандарт** | `standard` | YOLO без SAM, `confidence_threshold: 0.35` | `animevideov3`, OpenCV zoom, harmonize `auto` |
| **Качество** | `quality` | YOLO + SAM, порог `0.30` | x4plus-anime ×4, DepthFlow `dolly`, harmonize `blurred_pillarbox` |

**Критичные правила продукта:**

1. Пресеты **НЕ меняют** `panel_detector` (comic/manga) и backend апскейла — выбор пользователя.
2. TPSMM не в пресетах — по умолчанию `mode: opencv_zoom`; TPSMM только при явном выборе + driving MP4.
3. `anime_6B` (x4plus-anime) — только ×4 (×2 даёт артефакты; UI принудительно ставит ×4).
4. API: `GET /api/presets`, `GET /api/presets/{name}`, `POST /api/presets/apply`.

Локальные правки: `config/presets.user.yaml` (в `.gitignore`).

---

## 8. Workspace project mode

Единый проект на всех вкладках Split / Upscale / Video / ExText. Layout `story_out/projects/<имя>/`.

```text
story_out/projects/<Project_Name>/
├── panels/          ← Split (экспорт PNG)
├── upscale/         ← Upscale
├── video/           ← Video (клипы, storyboard)
└── stage_2a.json    ← ExText
```

| Режим | Поведение |
|-------|-----------|
| **Автономный** (чекбокс «Проект» выкл.) | Ручные пути, произвольный `output/` |
| **Проектный** (чекбокс вкл.) | Имя проекта обязательно; пути readonly; бэкенд resolve через `story_analyzer/paths.py` |

ExText в проектном режиме **не копирует** PNG (`copy_panels: false`) — читает из исходной папки. Подробно: [WORKSPACE_REFACTORING_REPORT.md](WORKSPACE_REFACTORING_REPORT.md).

---

## 9. API (FastAPI v1.5.0)

Префикс `/api`. Полный список эндпоинтов (источник: `api/server.py`, `api/story_stage_2a.py`):

### Core (split / anim)

| Метод | Путь | Назначение |
|-------|------|------------|
| POST | `/api/process` | Детекция панелей (`panel_detector`: comic \| manga) |
| POST | `/api/export` | Сохранить PNG (rect или polygon); `project_name`, `flat_export` |
| POST | `/api/upscale` | Апскейл (`backend`, CUGAN/SPAN поля); `project_name` |
| POST | `/api/animate` | Анимация → MP4 (`mode` incl. `tpsmm`, `tpsmm_driving_video`); `project_name` |
| GET | `/api/image` | Отдать изображение для Konva (`Cache-Control: no-store`) |
| GET | `/api/video` | Отдать MP4 для превью |

### Workspace

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/api/projects` | Список проектов в `story_out/projects/` |
| GET | `/api/projects/{name}/layout` | Пути `panels/`, `upscale/`, `video/`, `stage_2a.json` |
| POST | `/api/split/list_pages` | Список страниц из папки / файла / CBZ-ZIP |

### Опции / статус

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/api/split/options` | Детекторы comic/manga + статус моделей split |
| GET | `/api/upscale/options` | Backend: realesrgan \| realcugan \| span |
| GET | `/api/models/setup` | Статус установки всех моделей |
| GET | `/api/presets` | Список пресетов + snapshot текущих значений |
| GET | `/api/presets/{name}` | Значения пресета для UI |
| POST | `/api/presets/apply` | Применить пресет к конфигам |
| GET | `/api/tooltips` | Тексты подсказок для полей |
| POST | `/api/path/pick` | Нативный диалог (`kind`: file \| folder \| video \| save_file) |

### UI state

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/api/ui/state` | Память UI (split, upscale, video, story2a, global) |
| PUT | `/api/ui/state` | Частичное обновление настроек UI |
| POST | `/api/ui/state/reset` | Сброс секции UI |
| GET | `/api/ui/state/defaults` | Заводские значения по секциям |

### Story Stage 2a (ExText) — префикс `/api/story/stage_2a`

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/options` | OCR-движки, языки, preprocess, VLM-модель |
| POST | `/init` | Создать проект из папки (пустые баблы) |
| POST | `/process` | Batch: YOLO + OCR по папке |
| POST | `/sync_panels` | Sync PNG в `project/panels/` (replace) |
| GET | `/{project}?panels_dir=` | JSON + пути PNG с учётом папки UI |
| PUT | `/{project}` | Сохранение правок |
| POST | `/{project}/reocr` | Re-OCR одного бабла |
| POST | `/{project}/ocr_panel` | OCR всех баблов текущей панели |
| POST | `/{project}/detect_panel` | YOLO текущей панели (без OCR; `merge_mode`: append \| replace) |

---

## 10. Story Analyzer — ExText / Stage 2a

Расширение веб-редактора `:8000`: вкладка **ExText** — детекция speech bubbles, VLM OCR и **интерактивный HITL**.
Режимы **Ручной / Авто**: [STORY_ANALYZER_STAGE_2A_WORKFLOW.md](STORY_ANALYZER_STAGE_2A_WORKFLOW.md).

| Слой | Технология |
|------|------------|
| Детекция | ONNX CPU, `story_analyzer/stages/bubble_detector.py` (yolo_manga class 1, tiled) |
| OCR primary | SiliconFlow API, `story_analyzer/providers/siliconflow_ocr.py` |
| OCR fallback | PaddleOCR / EasyOCR (`ocr_engine: paddle \| easyocr \| auto`) |
| reading_order | `Bubble.reading_order`, `assign_bubble_reading_orders()`, `reading_order.js` |
| UI HITL | drag/resize bbox, chrome №/↻/×, detached text frame, ручной бабл; `workflow_mode` |
| Пути PNG | `panel_paths` + `panels_dir` query (`source_only`); `sync_panels` replace |
| Persist | `utils/ui_state.py` секция `story2a` |

**Split (та же вкладка :8000):** порядок панелей через `reading_order.js`; batch по папке/CBZ (`split-folder-path`, prev/next); **project mode** — единый проект на Split/Upscale/Video/ExText; **snap grid/objects (S1–S3)** — radio Выкл/Сетка/Объекты, шаг сетки 2–40 px, Arrow nudge, persist `snap_mode` — см. [Snap grid+Snap to objects/ROADMAP_STAGE_S_SNAP.md](Snap%20grid+Snap%20to%20objects/ROADMAP_STAGE_S_SNAP.md), [WORKSPACE_REFACTORING_REPORT.md](WORKSPACE_REFACTORING_REPORT.md).

Локальный PaddleOCR как основной OCR **заморожен** — см. `problems_fix/bubbles_detect_problems/LEGACY_LOCAL_OCR.md`.

---

## 11. Запуск (кратко)

```powershell
# Активация окружения
.\venv_311\Scripts\activate

# Gradio (все три вкладки)
$env:NO_PROXY = "127.0.0.1,localhost"
python main.py                                # → http://127.0.0.1:7860

# Веб-редактор
uvicorn api.server:app --reload --port 8000   # → http://127.0.0.1:8000

# CLI split
python pipeline.py exam_imgs output --order

# CLI anim
python anim_pipeline.py output\exam_imgs story_out --mode opencv_zoom

# Go batch split
.\comicsplit.exe --input exam_imgs --output panels --python .\venv_311\Scripts\python.exe --order
```

Подробно: [ComicSplit_Documentation.md](ComicSplit_Documentation.md).

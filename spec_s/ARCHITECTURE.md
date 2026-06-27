# ComicSplit — Техническая архитектура

**Версия:** 1.0 (июнь 2026)  
**Отражает:** фактическую реализацию MVP (split + anim + пресеты)  
> Исходная целевая спецификация (Go + Wails + gRPC) сохранена в `spec_s/archive/ComicSplit_Specification_v2_0.md`.

---

## 1. Назначение проекта

**ComicSplit** — десктопная утилита Windows для автоматической нарезки страниц комикса на панели и последующего «оживления» панелей (апскейл, гармонизация 16:9, анимированный MP4).

Типичный сценарий использования:

```
CBZ / PNG страницы  →  PNG панели  →  апскейл  →  16:9  →  MP4 клипы  →  раскадровка
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

## 3. Фактическая архитектура (MVP июнь 2026)

### Обзор компонентов

```
┌─────────────────────────────────────────────────────────────┐
│                    Интерфейсы пользователя                   │
│                                                             │
│  Gradio :7860          Web Editor :8000       CLI           │
│  (main.py)             (api/server.py          (pipeline.py │
│  Split / Upscale /     + frontend/index.html)  anim_pipeline│
│  Video; пресеты                                .py)         │
└──────────────────┬──────────────────┬──────────────────────┘
                   │                  │
┌──────────────────▼──────────────────▼──────────────────────┐
│                     Ядро (Python 3.11)                      │
│                                                             │
│  pipeline.py          anim_pipeline.py                      │
│  (split ML)           (upscale → 16:9 → animate → MP4)     │
│                                                             │
│  utils/: config, anim_config, presets, io_helpers,         │
│          path_resolve, ui_tooltips, path_dialog,           │
│          models_registry, panel_detector                   │
└──────────┬──────────────────────────┬───────────────────────┘
           │                          │
┌──────────▼──────────┐   ┌──────────▼──────────────────────┐
│  Split моделей      │   │  Anim инструменты               │
│                     │   │                                  │
│  ONNX Runtime CPU   │   │  NCNN + Vulkan (AMD iGPU)        │
│  yolo_comic_int8    │   │  Real-ESRGAN / CUGAN / SPAN      │
│  mobilesam_*_int8   │   │                                  │
│                     │   │  DepthFlow (OpenGL + CPU)        │
│                     │   │  OpenCV эффекты                  │
│                     │   │  TPSMM ONNX (motion transfer)    │
│                     │   │  ffmpeg (MP4, concat)            │
└─────────────────────┘   └──────────────────────────────────┘
```

### Потоки данных

**Split:**
```
Вход (CBZ/PNG/папка)
  → io_helpers.load_source()
  → YOLO INT8 → bboxes
  → [Accurate] MobileSAM INT8 → маска/полигон
  → cv2 crop → PNG панели в output/
  → _visualization.jpg
```

**Anim:**
```
PNG панели из output/
  → anim/upscale.py   (NCNN subprocess: realesrgan / realcugan / span)
  → anim/harmonize.py (OpenCV: blurred_pillarbox / dominant_color / smart_crop)
  → anim/animate_opencv.py | animate_depthflow.py | animate_tpsmm.py (driving MP4)
  → anim/render.py    (ffmpeg → MP4)
  → anim_pipeline.concat_storyboard() → storyboard.mp4
```

---

## 4. Технологический стек

| Слой | Технология | Версия | Причина выбора |
|------|-----------|--------|----------------|
| Язык | Python | 3.11 | Единый язык, ML-экосистема, простая отладка |
| ML inference (split) | ONNX Runtime | 1.18 | CPU-only, быстрая загрузка, кроссплатформа |
| ML inference (upscale) | NCNN + Vulkan | — | AMD iGPU через Vulkan, без CUDA |
| Детекция | YOLOv11n-seg INT8 | — | ~3 MB, Ryzen 5600H ≈ 400–800 ms/стр. |
| Маски | MobileSAM INT8 | — | ~40 MB, контурная маска по bbox |
| Апскейл | Real-ESRGAN / CUGAN / SPAN | NCNN | Vulkan-ускорение на AMD iGPU |
| Параллакс | DepthFlow + Depth Anything V2 Small | pip | Лучший 2.5D parallax на CPU |
| Анимация (быстро) | OpenCV | 4.x | Без ML, мгновенно |
| Видео | ffmpeg | — | Кодирование H.264, concat |
| UI десктоп | Gradio | 5.12 | Браузерный UI, 0 настройки |
| UI веб-редактор | FastAPI + Vanilla JS + Konva | 9 | REST API + Canvas-редактор масок |
| Конфиг | YAML + dataclass | — | Простая валидация, пресеты |
| Тесты | pytest | — | 41 тест в 10 файлах |
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
│   └── models_registry.yaml  # Реестр моделей + статус установки
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
│   ├── path_resolve.py       # Кириллика, Windows пути
│   ├── ui_tooltips.py        # Тексты подсказок UI
│   ├── path_dialog.py        # Нативные диалоги выбора файла/папки
│   ├── models_registry.py    # Проверка установки моделей
│   ├── panel_detector.py     # Выбор comic / manga YOLO
│   ├── ui_state.py           # Память UI v1 (split/upscale/video/story2a)
│   └── gradio_ui_state.py    # Восстановление Gradio из ui_state
│
├── api/
│   ├── server.py             # FastAPI v1.3.0 (:8000)
│   └── story_stage_2a.py     # Story Analyzer Stage 2a API
├── story_analyzer/           # Story Analyzer (Stage 2a+)
│   ├── stages/               # bubble_detector, ocr_*, stage_2a_processor
│   ├── providers/            # siliconflow_ocr
│   └── config.py
├── config/story_stage_2a.yaml
├── frontend/
│   ├── index.html            # Konva + вкладки Split/Upscale/Video/ExText
│   ├── ui_state.js           # localStorage + sync /api/ui/state
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
├── tests/                    # 41 pytest тест
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

---

## 7. API (FastAPI v1.3.0)

| Эндпоинт | Метод | Назначение |
|----------|-------|-----------|
| `/api/process` | POST | Детекция панелей (`panel_detector`: comic \| manga) |
| `/api/export` | POST | Сохранить PNG (rect или polygon) |
| `/api/upscale` | POST | Апскейл (`backend`, CUGAN/SPAN поля) |
| `/api/animate` | POST | Анимация → MP4 (`mode` incl. `tpsmm`, `tpsmm_driving_video`) |
| `/api/video` | GET | Отдать MP4 для превью |
| `/api/presets` | GET | Список пресетов |
| `/api/presets/{name}` | GET | Конкретный пресет |
| `/api/presets/apply` | POST | Применить пресет |
| `/api/tooltips` | GET | Тексты подсказок |
| `/api/path/pick` | POST | Нативный диалог (`kind`: file \| folder \| video) |
| `/api/split/options` | GET | Детекторы comic/manga + статус моделей |
| `/api/upscale/options` | GET | Backend: realesrgan \| realcugan \| span |
| `/api/models/setup` | GET | Статус установки всех моделей |
| `/api/ui/state` | GET/PUT | Память UI (split, upscale, video, story2a, global) |
| `/api/ui/state/reset` | POST | Сброс секции UI |
| `/api/story/stage_2a/*` | GET/POST/PUT | ExText (Stage 2a): init, process, sync_panels, ocr/detect panel, JSON |

Подробнее Stage 2a: [STORY_ANALYZER_STAGE_2A.md](STORY_ANALYZER_STAGE_2A.md).

---

## 9. Story Analyzer — ExText / Stage 2a (июнь 2026)

Расширение веб-редактора `:8000`: вкладка **ExText** — детекция speech bubbles, VLM OCR и **интерактивный HITL**.  
Режимы **Ручной / Авто**: [STORY_ANALYZER_STAGE_2A_WORKFLOW.md](STORY_ANALYZER_STAGE_2A_WORKFLOW.md).

```
panels/ (upscaled PNG)
  → yolo_manga_int8 (tiled YOLO, class 1)
  → crop bubble
  → SiliconFlow VLM OCR (Qwen3-VL-8B)  [default]
  → stage_2a.json + Konva editor (bbox, text, reading_order)
```

| Слой | Технология |
|------|------------|
| Детекция | ONNX CPU, `story_analyzer/stages/bubble_detector.py` |
| OCR primary | SiliconFlow API, `story_analyzer/providers/siliconflow_ocr.py` |
| OCR fallback | PaddleOCR / EasyOCR (`ocr_engine: paddle \| easyocr \| auto`) |
| reading_order | `Bubble.reading_order`, `assign_bubble_reading_orders()`, `reading_order.js` |
| UI HITL | drag/resize bbox, chrome №/↻/×, detached text frame, ручной бабл; `workflow_mode` |
| Пути PNG | `panel_paths` + `panels_dir` query (`source_only`); `sync_panels` replace |
| Persist | `utils/ui_state.py` секция `story2a`; явная очистка путей при reset/persist |
| Конфиг | `config/story_stage_2a.yaml`, секреты `.env` |
| Модули | `story_analyzer/`, `api/story_stage_2a.py`, `frontend/story_2a.js` |

**Split (та же вкладка :8000):** порядок панелей через `reading_order.js`; технические метаданные (`panel_id`, bbox, %) скрыты в sidebar — только № и «Панель».

**Следующий UX-шаг Split:** snap grid / snap to objects — блок S в [ROADMAP.md](ROADMAP.md).

Локальный PaddleOCR как основной OCR **заморожен** — см. `problems_fix/bubbles_detect_problems/LEGACY_LOCAL_OCR.md`.

---

## 10. Запуск (кратко)

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

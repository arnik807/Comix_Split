# ComicSplit — статус реализации

**Обновлено:** июнь 2026 (блок A закрыт; B1/B4 готовы; B2 интегрирован; R1 Stage 2a — интерактивный HITL ✅)  
**Установка и запуск:** [ComicSplit_Documentation.md](ComicSplit_Documentation.md)  
**Технологический стек и архитектура:** [ARCHITECTURE.md](ARCHITECTURE.md)

---

## Сводная таблица компонентов

| Компонент | Статус |
|-----------|--------|
| ML split (YOLO + SAM, CPU ONNX) | ✅ **Готово** |
| Пакетная обработка CBZ/ZIP/папка | ✅ **Готово** (`process_source`) |
| `config.yaml` + `config/presets.yaml` | ✅ **Готово** |
| Пресеты **Стандарт / Качество** (API + оба UI) | ✅ **Готово** (`utils/presets.py`) |
| Детектор манга-панелей (`yolo_manga_int8.onnx`) | ✅ **Готово** (`utils/panel_detector.py`) |
| Gradio (`:7860`) — Split / Upscale / Video | ✅ **Готово** (пресеты, tooltips, «Обзор…») |
| CLI split (`pipeline.py`) | ✅ **Готово** |
| CLI anim (`anim_pipeline.py`) | ✅ **Готово** |
| Anim модули (`anim/`: upscale, harmonize, opencv, depthflow, render) | ✅ **Готово** |
| Backend апскейла: Real-ESRGAN / Real-CUGAN / SPAN (NCNN) | ✅ **Готово** (`anim/upscale.py`) |
| Веб-редактор FastAPI + Konva (`:8000`) — Split / Upscale / Video / **Story 2a** | ✅ **Готово** |
| Память UI (localStorage + `ui_state.user.json`, секции split/upscale/video/story2a) | ✅ **Готово** (`utils/ui_state.py`, `frontend/ui_state.js`) |
| Split: порядок чтения панелей (№, reorder в sidebar и на канвасе) | ✅ **Готово** (`frontend/reading_order.js`) |
| Подсказки (tooltips) во всех настройках | ✅ **Готово** (`utils/ui_tooltips.py`) |
| Выбор путей (диалог + ручной ввод) | ✅ **Готово** (`utils/path_dialog.py`) |
| Реестр моделей + статус установки в UI | ✅ **Готово** (`config/models_registry.yaml`, `utils/models_registry.py`) |
| API v1.3 (presets, tooltips, path/pick, models/setup, split/options, upscale/options) | ✅ **Готово** |
| TPSMM animate (`mode: tpsmm` + driving MP4) | 🟡 **Готово в коде/UI** — медленно на CPU; сегментация (B3) опциональна |
| Go CLI (`comicsplit.exe`) | 🟡 **Частично** — CBZ/папка/JPG; CBR только Python |
| OpenCV fast-path каскад (split) | ❌ **Нет** |
| Wails desktop | ❌ **Нет** |
| gRPC Go↔Python | ❌ **Нет** |
| PyInstaller EXE | 🟡 Spec есть, сборка вручную |
| Benchmark < 600 ms/стр. | 🟡 Цель не закрыта |
| **Story Analyzer Stage 2a** (bbox + VLM OCR + интерактивный HITL) | 🟡 **Готово в коде/UI** — SiliconFlow VLM; formal ACCEPTANCE ⏳ |
| Split: snap grid / snap to objects | 📋 **В roadmap** — см. [ROADMAP.md](ROADMAP.md) блок S |

Подробнее: [STORY_ANALYZER_STAGE_2A.md](STORY_ANALYZER_STAGE_2A.md).

---

## Реализованные модули (файловая карта)

| Путь | Назначение |
|------|------------|
| `pipeline.py` | `analyze_page`, `process_page`, `process_source`, CLI split |
| `anim_pipeline.py` | CLI: upscale → harmonize 16:9 → animate → MP4 + storyboard |
| `anim/upscale.py` | NCNN subprocess (realesrgan / realcugan / span), ONNX fallback |
| `anim/harmonize.py` | OpenCV 16:9 (blurred_pillarbox / dominant_color / smart_crop) |
| `anim/animate_opencv.py` | opencv_zoom / opencv_shake / static |
| `anim/animate_depthflow.py` | DepthFlow parallax (dolly / zoom / orbital) |
| `anim/animate_tpsmm.py` | TPSMM motion transfer — ONNX CPU; режим `tpsmm` в `anim_pipeline.py` |
| `anim/render.py` | ffmpeg: кадры → MP4, concat storyboard |
| `config/presets.yaml` | Эталон пресетов Стандарт / Качество (split + anim) |
| `config/models_registry.yaml` | Реестр: путь, тип, backend, статус установки |
| `utils/config.py` | AppConfig, load_config() |
| `utils/anim_config.py` | AnimConfig, load_anim_config() |
| `utils/presets.py` | load / apply / snapshot / diff пресетов |
| `utils/ui_tooltips.py` | Тексты подсказок для Gradio и веб-UI |
| `utils/path_dialog.py` | Нативные диалоги Windows (tkinter) |
| `utils/models_registry.py` | Проверка наличия моделей перед запуском |
| `utils/panel_detector.py` | Выбор детектора `comic` \| `manga` |
| `utils/ui_state.py` | Память UI v1: split / upscale / video / story2a / global |
| `utils/gradio_ui_state.py` | Восстановление полей Gradio из `ui_state.user.json` |
| `frontend/ui_state.js` | localStorage + sync `PUT /api/ui/state` для :8000 |
| `frontend/reading_order.js` | Общий модуль порядка чтения (Split панели, Stage 2a баблы) |
| `utils/io_helpers.py` | CBZ, CBR, ZIP, папка, imdecode (кириллица) |
| `utils/path_resolve.py` | Пути с кириллицей и mojibake |
| `main.py` | Gradio 5.x, 3 вкладки |
| `api/server.py` v1.3.0 | FastAPI REST |
| `frontend/index.html` | Konva-редактор Split/Upscale/Video/Story 2a + пресеты + tooltips |
| `ml_worker/main.py` | IPC для Go |
| `cmd/comicsplit/` + `internal/*` | Go CLI |
| `scripts/split_models_craft_scripts/` | Скачивание + квантование split моделей |
| `scripts/download_animate_models.ps1` | Скачивание anim моделей |
| `scripts/download_upscale_backends.ps1` | CUGAN + SPAN |
| `scripts/quantize_animate_models.py` | INT8 квантование + verify |
| `scripts/verify_upscale_backends.py` | Проверка CUGAN/SPAN |
| `scripts/benchmark_upscale.ps1` | Бенчмарк всех NCNN backend |
| `tests/` | pytest (~67 тестов: split, anim, ui_state, stage 2a OCR/det) |
| `packaging/comicsplit.spec` | PyInstaller |
| `story_analyzer/stages/stage_2a_processor.py` | Stage 2a: detect + OCR → JSON |
| `story_analyzer/stages/bubble_detector.py` | Tiled YOLO manga class 1 |
| `story_analyzer/stages/ocr_reader.py` | Crop + engine routing |
| `story_analyzer/stages/ocr_engines.py` | paddle / easyocr / siliconflow / auto |
| `story_analyzer/providers/siliconflow_ocr.py` | SiliconFlow VLM OCR client |
| `story_analyzer/env_loader.py` | `.env` для API keys |
| `config/story_stage_2a.yaml` | Stage 2a конфиг |
| `api/story_stage_2a.py` | REST Stage 2a |
| `frontend/story_2a.js` | UI Konva Stage 2a |
| `scripts/diagnose_stage_2a.py` | Диагностика bbox + OCR |
| `scripts/test_siliconflow_api.py` | Smoke-test SiliconFlow |

---

## Пресеты качества

| Пресет | ID | Split | Anim |
|--------|-----|-------|------|
| **Стандарт** | `standard` | YOLO без SAM, порог 0.35 | animevideov3 ×2, OpenCV zoom |
| **Качество** | `quality` | YOLO + SAM, порог 0.30 | x4plus-anime ×4, blurred_pillarbox, DepthFlow dolly |

- Эталон: `config/presets.yaml`
- Локальные правки: `config/presets.user.yaml` (в `.gitignore`)
- API: `GET /api/presets`, `GET /api/presets/{name}`, `POST /api/presets/apply`

### Апскейл — важное

| ID в конфиге | NCNN флаг `-n` | Масштаб |
|---|---|---|
| `animevideov3` | `realesr-animevideov3` | ×2 или ×4 |
| `anime_6B` | `realesrgan-x4plus-anime` | **только ×4** (×2 даёт артефакты) |
| `cugan_se` | `models-se` | ×1–×4 (`-s`) |
| `spanx2_ch48` / `spanx4_ch48` | по имени модели | фиксировано по выбранным весам |

---

## Детекторы панелей

| Детектор | ID | Контент | Модель |
|----------|-----|---------|--------|
| Западный комикс | `comic` | Franco-Belgian, American, цветные комиксы | `yolo_comic_int8.onnx` |
| Манга | `manga` | Японская манга, Manga109 | `yolo_manga_int8.onnx` |

Манга-модель обнаруживает два класса (`panel`, `text bubble`); пайплайн использует только `panel`.  
Пресеты **не** меняют детектор — выбор сохраняется в сессии.

---

## Модели (не в git)

**Split** → `models/`:

```
yolo_comic_int8.onnx
yolo_manga_int8.onnx
mobilesam_encoder_int8.onnx
mobilesam_decoder_int8.onnx
```

**Anim** → `models/anim/`:

```
upscale/
  realesrgan-ncnn-vulkan.exe + models/*.bin   (Real-ESRGAN)
  realcugan/realcugan-ncnn-vulkan.exe + models-se/
  span/span-ncnn-vulkan.exe + models/
depth/
  midas_v21_small_256.onnx, *_int8.onnx
tpsmm/
  kp_detector.onnx, tpsmm_rel.onnx (+ INT8)
ffmpeg/bin/ffmpeg.exe
```

DepthFlow: `pip install depthflow` (кэш DA-V2 Small качается при первом запуске).

---

## Сопоставление: план MVP → факт

| Пункт исходного плана | Статус |
|----------------------|--------|
| Python 3.11 + ONNX Runtime CPU | ✅ |
| YOLO + MobileSAM (fast/accurate) | ✅ |
| CBZ/CBR/ZIP/папка (`io_helpers`) | ✅ |
| OpenCV fast-path каскад | ❌ |
| `process_source` + batch | ✅ |
| Gradio UI (3 вкладки) | ✅ |
| FastAPI + Konva + anim API | ✅ |
| Anim pipeline (upscale/video) | ✅ |
| Пресеты Стандарт / Качество | ✅ |
| Tooltips, path pickers | ✅ |
| Manga YOLO detector | ✅ |
| Backend CUGAN / SPAN | ✅ |
| TPSMM в anim_pipeline + UI/API | ✅ (B3 segment — в планах) |
| Benchmark < 600 ms/стр. | ❌ |
| PyInstaller EXE | 🟡 |
| Go orchestrator | 🟡 |
| Wails desktop | ❌ |
| gRPC Go↔Python | ❌ |

---

## Рабочие команды проверки

```powershell
.\venv_311\Scripts\activate
pip install -r requirements.txt

# Smoke split
python pipeline.py test_page.jpg output --order
python pipeline.py exam_imgs output --order

# Gradio
$env:NO_PROXY="127.0.0.1,localhost"; python main.py

# Веб-редактор
uvicorn api.server:app --port 8000

# Anim CLI
python anim_pipeline.py output\exam_imgs story_out --mode opencv_zoom --no-upscale

# Тесты
pytest -q

# Go CLI
go build -o comicsplit.exe ./cmd/comicsplit
.\comicsplit.exe --input exam_imgs --output panels --python .\venv_311\Scripts\python.exe --order

# Бенчмарк апскейла
.\scripts\benchmark_upscale.ps1 -Quick
```

---

## Известные ограничения

| Компонент | Ограничение |
|-----------|-------------|
| Gradio | Нет галереи превью; результат split — список путей в текстовом поле |
| DepthFlow | Первый запуск качает DA-V2 Small; на CPU/iGPU — минуты на панель 1920×1080 |
| TPSMM | Медленно на CPU; нужен driving MP4; сегментация персонажа (B3) улучшит качество |
| Веб `:8000` | Диалог «Обзор…» открывается на машине сервера; кириллические пути — через относительные |
| `anime_6B` | Только ×4; ×2 через этот backend даёт артефакты |
| Go CLI | CBR только через Python subprocess |
| Benchmark | Цель < 600 ms/стр. не достигнута в Accurate+SAM; Fast — зависит от страницы |
| Stage 2a OCR | Облако SiliconFlow по умолчанию; нужен API key и интернет; ~1–3 с/бабл |
| Stage 2a det | Manga YOLO class 1 — слабее на western comics; tiled YOLO частично компенсирует |
| Stage 2a UI | Текстовое окно бабла отделено от bbox; позиции в `S2.frameLayouts` (не в JSON) |
| PaddleOCR local | Fallback only; на ru-комиксах не годится как primary — см. LEGACY_LOCAL_OCR.md |
| Split snap | Не реализовано; следующий UX-шаг — блок S в ROADMAP |

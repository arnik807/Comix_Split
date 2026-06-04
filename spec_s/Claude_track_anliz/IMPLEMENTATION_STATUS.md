# ComicSplit — статус реализации

**Обновлено:** июнь 2026 (блок A закрыт; B1/B4 готовы; B2 код готов)  
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
| Веб-редактор FastAPI + Konva (`:8000`) — Split / Upscale / Video | ✅ **Готово** |
| Подсказки (tooltips) во всех настройках | ✅ **Готово** (`utils/ui_tooltips.py`) |
| Выбор путей (диалог + ручной ввод) | ✅ **Готово** (`utils/path_dialog.py`) |
| Реестр моделей + статус установки в UI | ✅ **Готово** (`config/models_registry.yaml`, `utils/models_registry.py`) |
| API v1.2+ (presets, tooltips, path/pick, models/setup, split/options, upscale/options) | ✅ **Готово** |
| TPSMM animate (код + UI) | 🟡 **[Unreleased]** — код и модели готовы, не в `anim_pipeline` |
| Go CLI (`comicsplit.exe`) | 🟡 **Частично** — CBZ/папка/JPG; CBR только Python |
| OpenCV fast-path каскад (split) | ❌ **Нет** |
| Wails desktop | ❌ **Нет** |
| gRPC Go↔Python | ❌ **Нет** |
| PyInstaller EXE | 🟡 Spec есть, сборка вручную |
| Benchmark < 600 ms/стр. | 🟡 Цель не закрыта |

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
| `anim/animate_tpsmm.py` | [Unreleased] Motion transfer — ONNX CPU |
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
| `utils/io_helpers.py` | CBZ, CBR, ZIP, папка, imdecode (кириллица) |
| `utils/path_resolve.py` | Пути с кириллицей и mojibake |
| `main.py` | Gradio 5.x, 3 вкладки |
| `api/server.py` v1.2+ | FastAPI REST |
| `frontend/index.html` | Konva-редактор + Upscale/Video + пресеты + tooltips |
| `ml_worker/main.py` | IPC для Go |
| `cmd/comicsplit/` + `internal/*` | Go CLI |
| `scripts/split_models_craft_scripts/` | Скачивание + квантование split моделей |
| `scripts/download_animate_models.ps1` | Скачивание anim моделей |
| `scripts/download_upscale_backends.ps1` | CUGAN + SPAN |
| `scripts/quantize_animate_models.py` | INT8 квантование + verify |
| `scripts/verify_upscale_backends.py` | Проверка CUGAN/SPAN |
| `scripts/benchmark_upscale.ps1` | Бенчмарк всех NCNN backend |
| `tests/` | **25 тестов** в 7 файлах |
| `packaging/comicsplit.spec` | PyInstaller |

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
| TPSMM / segment | 🟡 код готов |
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
| TPSMM | Не подключён к `anim_pipeline.py`; нужен driving video + желательно сегментация |
| Веб `:8000` | Диалог «Обзор…» открывается на машине сервера; кириллические пути — через относительные |
| `anime_6B` | Только ×4; ×2 через этот backend даёт артефакты |
| Go CLI | CBR только через Python subprocess |
| Benchmark | Цель < 600 ms/стр. не достигнута в Accurate+SAM; Fast — зависит от страницы |

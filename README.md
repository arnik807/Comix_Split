# ComicSplit

Автоматическая нарезка панелей комиксов (YOLO + MobileSAM) и **оживление** панелей (апскейл, 16:9, MP4). Windows, Python 3.11.

**Пресеты качества:** «Стандарт» (YOLO + videov3 ×2) и «Качество» (SAM + x4plus-anime ×4 + DepthFlow dolly) — Gradio :7860 и веб :8000 (Split / Upscale / Video / **ExText**). **Project mode** — единый проект на всех вкладках `:8000` (`story_out/projects/<имя>/`).

**ExText** — UI-название вкладки извлечения текста (Story Analyzer Stage 2a); в коде и API по-прежнему `story2a`, `stage_2a`.

**Детекторы split:** западный комикс (`comic`) или манга (`manga`). **Апскейл:** Real-ESRGAN / Real-CUGAN / SPAN (NCNN Vulkan). **Видео:** OpenCV, DepthFlow, TPSMM (нужен driving MP4).

---

## Быстрый старт

```powershell
# 1. Окружение
python -m venv venv_311
.\venv_311\Scripts\activate
pip install -r requirements.txt

# 2. Модели split
powershell -ExecutionPolicy Bypass -File scripts\split_models_craft_scripts\download_models.ps1
python scripts\split_models_craft_scripts\quantize_models.py

# 3. Модели anim (для апскейла и видео)
powershell -ExecutionPolicy Bypass -File scripts\download_animate_models.ps1
python scripts\quantize_animate_models.py --verify

# 4. PaddleOCR для ExText / Stage 2a (если models/paddleocr ещё пуста)
powershell -ExecutionPolicy Bypass -File scripts\install_paddle_ocr.ps1
```

### Gradio (Split + Upscale + Video)

```powershell
$env:NO_PROXY = "127.0.0.1,localhost"
python main.py
```

→ http://127.0.0.1:7860

### CLI split

```powershell
python pipeline.py test_page.jpg output --order
python pipeline.py exam_imgs output --order
```

→ PNG в `output\<имя_источника>\`

### Веб-редактор (Split / Upscale / Video / ExText)

```powershell
uvicorn api.server:app --reload --port 8000
```

→ http://127.0.0.1:8000

### CLI anim (из готовых панелей)

```powershell
python anim_pipeline.py output\exam_imgs story_out --mode opencv_zoom --scale 2
python anim_pipeline.py output\exam_imgs story_out --mode tpsmm --tpsmm-driving-video path\to\drive.mp4
```

→ `story_out/animated/*.mp4`, `story_out/storyboard.mp4`

---

## Документация

| Документ | Содержание |
|----------|------------|
| **[spec_s/ComicSplit_Documentation.md](spec_s/ComicSplit_Documentation.md)** | Руководство пользователя: установка, все интерфейсы, параметры |
| **[spec_s/ARCHITECTURE.md](spec_s/ARCHITECTURE.md)** | Технический стек, архитектура, API, структура проекта |
| **[spec_s/IMPLEMENTATION_STATUS.md](spec_s/IMPLEMENTATION_STATUS.md)** | Статус модулей, файловая карта, известные ограничения |
| **[spec_s/MODELS_SPECIFICATION.md](spec_s/MODELS_SPECIFICATION.md)** | Все модели: ссылки, параметры, оценка под Ryzen 5600H + AMD iGPU |
| **[spec_s/WORKSPACE_REFACTORING_REPORT.md](spec_s/WORKSPACE_REFACTORING_REPORT.md)** | Workspace project mode: единый проект, batch Split, API v1.5 |
| **[spec_s/ROADMAP.md](spec_s/ROADMAP.md)** | Roadmap: A/B/W блоки + **R1 ExText (Stage 2a)** 🟡 + **S snap** 📋 |
| **[spec_s/STORY_ANALYZER_STAGE_2A.md](spec_s/STORY_ANALYZER_STAGE_2A.md)** | ExText (Stage 2a): bbox + SiliconFlow VLM OCR |
| **[spec_s/STORY_ANALYZER_STAGE_2A_WORKFLOW.md](spec_s/STORY_ANALYZER_STAGE_2A_WORKFLOW.md)** | Режимы **Ручной / Авто**, кнопки, API по панели |
| [problems_fix/bubbles_detect_problems/](problems_fix/bubbles_detect_problems/) | Roadmap Stage 2a, LEGACY локального OCR |
| [CHANGELOG.md](CHANGELOG.md) | История изменений |
| [config.yaml](config.yaml) | Конфиг split |
| [config_animate.yaml](config_animate.yaml) | Конфиг anim |
| [config/presets.yaml](config/presets.yaml) | Пресеты Стандарт / Качество |
| [spec_s/README.md](spec_s/README.md) | Индекс `spec_s/` |
| **[spec_s/MODELS_SETUP_GUIDE.md](spec_s/MODELS_SETUP_GUIDE.md)** | Установка моделей (split, anim, ExText) |
| **[spec_s/WEB_LLM_GIT_WORKFLOW.md](spec_s/WEB_LLM_GIT_WORKFLOW.md)** | Web-LLM: GitHub + Sourcecraft, `REPO_MAP.md` |
| **[REPO_MAP.md](REPO_MAP.md)** | Дерево проекта + Raw-ссылки (`python scripts/generate_repo_map.py`) |
| [models/README.md](models/README.md) | Список файлов моделей |

---

## Структура (основное)

| Путь | Назначение |
|------|------------|
| `main.py` | Gradio :7860 |
| `pipeline.py` | Split ML + CLI |
| `anim_pipeline.py` | Anim CLI |
| `anim/` | upscale, harmonize, render, animate_* |
| `api/` + `frontend/` | Веб :8000 (FastAPI v1.5, workspace.js, panel_nav.js) |
| `utils/` | config, presets, io, paths, tooltips, path_dialog, models_registry, panel_detector, workspace_paths, split_pages |
| `config/presets.yaml` | Пресеты Стандарт / Качество |
| `models/` | Split ONNX (не в git) |
| `models/paddleocr/` | PaddleOCR whl (не в git) |
| `models/anim/` | NCNN, MiDaS, TPSMM, ffmpeg (не в git) |
| `spec_s/` | Документация (9 активных + archive/) |
| `story_analyzer/` | Stage 2a+ Story Analyzer (ExText) |
| `frontend/story_2a.js`, `reading_order.js`, `ui_state.js` | Веб :8000 ExText + persist |

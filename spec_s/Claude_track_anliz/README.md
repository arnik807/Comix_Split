# ComicSplit

Автоматическая нарезка панелей комиксов (YOLO + MobileSAM) и **оживление** панелей (апскейл, 16:9, MP4). Windows, Python 3.11.

**Пресеты качества:** «Стандарт» (YOLO + videov3 ×2) и «Качество» (SAM + x4plus-anime ×4 + DepthFlow dolly) — Gradio :7860 и веб :8000.

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

### Веб-редактор (Split / Upscale / Video)

```powershell
uvicorn api.server:app --reload --port 8000
```

→ http://127.0.0.1:8000

### CLI anim (из готовых панелей)

```powershell
python anim_pipeline.py output\exam_imgs story_out --mode opencv_zoom --scale 2
```

→ `story_out/animated/*.mp4`, `story_out/storyboard.mp4`

---

## Документация

| Документ | Содержание |
|----------|-----------|
| **[spec_s/ComicSplit_Documentation.md](spec_s/ComicSplit_Documentation.md)** | Руководство пользователя: установка, все интерфейсы, параметры |
| **[spec_s/ARCHITECTURE.md](spec_s/ARCHITECTURE.md)** | Технический стек, архитектура, API, структура проекта |
| **[spec_s/IMPLEMENTATION_STATUS.md](spec_s/IMPLEMENTATION_STATUS.md)** | Статус модулей, файловая карта, известные ограничения |
| **[spec_s/MODELS_SPECIFICATION.md](spec_s/MODELS_SPECIFICATION.md)** | Все модели: ссылки, параметры, оценка под Ryzen 5600H + AMD iGPU |
| **[spec_s/ROADMAP.md](spec_s/ROADMAP.md)** | Roadmap качества: блоки A ✅ B0/B1/B4 ✅ B2 🟡 B3 📋 |
| [CHANGELOG.md](CHANGELOG.md) | История изменений |
| [config.yaml](config.yaml) | Конфиг split |
| [config_animate.yaml](config_animate.yaml) | Конфиг anim |
| [config/presets.yaml](config/presets.yaml) | Пресеты Стандарт / Качество |

---

## Структура (основное)

| Путь | Назначение |
|------|-----------|
| `main.py` | Gradio :7860 |
| `pipeline.py` | Split ML + CLI |
| `anim_pipeline.py` | Anim CLI |
| `anim/` | upscale, harmonize, render, animate_* |
| `api/` + `frontend/` | Веб :8000 |
| `utils/` | config, presets, io, paths, tooltips, path_dialog, models_registry, panel_detector |
| `config/presets.yaml` | Пресеты Стандарт / Качество |
| `models/` | Split ONNX (не в git) |
| `models/anim/` | NCNN, MiDaS, TPSMM, ffmpeg (не в git) |
| `spec_s/` | Документация (5 файлов + archive/) |

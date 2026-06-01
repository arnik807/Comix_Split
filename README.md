# ComicSplit

Автоматическая нарезка панелей комиксов (YOLO + MobileSAM) и опциональное **оживление** панелей (апскейл, 16:9, MP4). Windows, Python 3.11.

**Полная документация:** [spec_s/ComicSplit_Documentation.md](spec_s/ComicSplit_Documentation.md)

## Быстрый старт

```powershell
python -m venv venv_311
.\venv_311\Scripts\activate
pip install -r requirements.txt
.\scripts\split_models_craft_scripts\download_models.ps1
python scripts\split_models_craft_scripts\quantize_models.py
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

### Anim (из готовых панелей)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\download_animate_models.ps1
python scripts\quantize_animate_models.py --verify

python anim_pipeline.py output\exam_imgs story_out --mode opencv_zoom --scale 2
```

→ `story_out/animated/*.mp4`, `story_out/storyboard.mp4`

## Документация

| Файл | Содержание |
|------|------------|
| [spec_s/ComicSplit_Documentation.md](spec_s/ComicSplit_Documentation.md) | **Руководство пользователя** |
| [spec_s/IMPLEMENTATION_STATUS.md](spec_s/IMPLEMENTATION_STATUS.md) | Статус модулей |
| [spec_s/comic_panel_animation_spec.md](spec_s/comic_panel_animation_spec.md) | Спека anim + статус |
| [spec_s/README.md](spec_s/README.md) | Индекс `spec_s/` |
| [CHANGELOG.md](CHANGELOG.md) | История изменений |
| [config.yaml](config.yaml) | Split |
| [config_animate.yaml](config_animate.yaml) | Anim |
| [models/README.md](models/README.md) | Краткий список файлов моделей |
| [spec_s/MODELS_SPECIFICATION.md](spec_s/MODELS_SPECIFICATION.md) | **Спека моделей** (ссылки, Ryzen 5600H, рекомендации) |

## Структура (основное)

| Путь | Назначение |
|------|------------|
| `main.py` | Gradio :7860 |
| `pipeline.py` | Split ML + CLI |
| `anim_pipeline.py` | Anim CLI |
| `anim/` | upscale, harmonize, render, animate_* |
| `api/` + `frontend/` | Веб :8000 |
| `utils/` | config, io, paths |

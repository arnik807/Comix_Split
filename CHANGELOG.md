# Changelog

Все значимые изменения проекта ComicSplit (`SPLIT_PANELS_DEV`).  
Формат ориентирован на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).

## [Unreleased]

### Добавлено (блок A — качество без новых моделей)

- Пресеты **Стандарт** / **Качество**: `config/presets.yaml`, `utils/presets.py`
- API v1.2: `GET /api/presets`, `GET /api/presets/{name}`, `POST /api/presets/apply`
- Расширены `POST /api/process` (пороги YOLO), `/api/upscale`, `/api/animate` (модель, GPU, harmonize, DepthFlow)
- Gradio (`main.py`): кнопки пресетов, пороги Split, модель/GPU апскейла, harmonize + intensity на Video
- Веб-редактор (:8000): секция пресетов, те же поля на вкладках Split / Upscale / Video
- `tests/test_presets.py` — round-trip standard ↔ quality
- `tests/test_smoke_exam_imgs.py` — smoke на `exam_imgs` (9 панелей Asterix-0004) + API TestClient
- Подсказки ко всем настройкам: `utils/ui_tooltips.py`, `GET /api/tooltips`, «!» в веб-UI, `info` в Gradio

### Планируется

- [ROADMAP_QUALITY_BOOST.md](spec_s/ROADMAP_QUALITY_BOOST.md) — блок B (новые модели)
- TPSMM в `anim_pipeline.py`
- `segment.py` для motion transfer
- OpenCV fast-path в split-каскаде
- Wails / gRPC (спека v2.0)

---

## [2026-05-31] — Anim MVP + веб/документация

### Добавлено

- Пайплайн anim: `anim/`, `anim_pipeline.py`, `config_animate.yaml`
- Gradio: вкладки **Upscale** и **Video** (`main.py`)
- Веб-редактор :8000: вкладки Split / Upscale / Video (`frontend/index.html`)
- API v1.1: `POST /api/upscale`, `POST /api/animate`, `GET /api/video`
- DepthFlow parallax (`anim/animate_depthflow.py`, CLI 0.9.x)
- Скрипты: `download_animate_models.ps1`, `quantize_animate_models.py`
- `tests/test_harmonize.py`, обновлённая документация в `spec_s/`

### Исправлено

- DepthFlow: вместо несуществующей команды `run` — цепочка `input → preset → main --render`
- Веб Split: экспорт по маске SAM только при включённом «Полигон» или после ручной правки (`polyEdited`)
- API детекция: `analyze_page` без записи в `out_ui/` (дублирующий экспорт при «Запустить детекцию» убран)
- Windows: `NO_COLOR`, `WINDOW_BACKEND=headless` для DepthFlow

### Документация

- `ComicSplit_Documentation.md` v1.2, `IMPLEMENTATION_STATUS.md`, `comic_panel_animation_spec.md` (блок статуса)
- `spec_s/MODELS_SPECIFICATION.md` — спека всех моделей, железо, рекомендации по качеству
- `README.md`, `spec_s/README.md`, `models/README.md`, `scripts/readme.md`
- Этот файл `CHANGELOG.md`

---

## [2026-05] — Split MVP (ранний май)

### Добавлено

- YOLO + MobileSAM ONNX (CPU), `pipeline.py`, `process_source`
- Gradio split (`main.py`, :7860)
- FastAPI + Konva редактор (:8000): детекция, rect/polygon, экспорт PNG
- Go CLI `comicsplit.exe`, `ml_worker`
- `utils/path_resolve.py` для кириллицы в путях
- `config.yaml`, pytest, `benchmark.py`
- `.gitignore` для крупных `models/**` (push >100 MB)

### Известные ограничения (на момент серии)

- Benchmark &lt;600 ms/стр. не достигнут на `exam_imgs`
- Gradio без галереи превью
- CBR только в Python CLI

---

## Ссылки

| Документ | Назначение |
|----------|------------|
| [spec_s/ComicSplit_Documentation.md](spec_s/ComicSplit_Documentation.md) | Руководство пользователя |
| [spec_s/IMPLEMENTATION_STATUS.md](spec_s/IMPLEMENTATION_STATUS.md) | Статус модулей |
| [spec_s/README.md](spec_s/README.md) | Индекс документации |

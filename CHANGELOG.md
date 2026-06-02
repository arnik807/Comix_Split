# Changelog

Все значимые изменения проекта ComicSplit (`SPLIT_PANELS_DEV`).  
Формат ориентирован на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).

## [Unreleased]

### Планируется

- [ROADMAP_QUALITY_BOOST.md](spec_s/ROADMAP_QUALITY_BOOST.md) — **блок B** (реестр моделей, manga YOLO, TPSMM в пайплайне)
- OpenCV fast-path в split-каскаде
- Wails / gRPC (спека v2.0)
- Опционально из блока A: `localStorage` для ручных настроек на :8000

---

## [2026-06-02] — Блок A: пресеты, UI, апскейл (финал)

### Добавлено

- Пресеты **Стандарт** / **Качество**: `config/presets.yaml`, `utils/presets.py`, `config/presets.user.yaml` (локально, в `.gitignore`)
- API **v1.2**: `GET /api/presets`, `GET /api/presets/{name}`, `POST /api/presets/apply`, `GET /api/tooltips`, `POST /api/path/pick`
- Расширены `POST /api/process` (пороги YOLO), `/api/upscale`, `/api/animate` (модель, GPU, harmonize, DepthFlow)
- Gradio и веб (:8000): паритет настроек Split / Upscale / Video; бейдж **MODE: STANDARD / QUALITY**
- Подсказки: `utils/ui_tooltips.py` — «!» в веб-UI, `info` в Gradio
- Выбор путей: `utils/path_dialog.py`, кнопки «Обзор…», drag-and-drop в Gradio
- Апскейл: `tile_size` в `config_animate.yaml`, передача `-t` в NCNN; бенчмарк `scripts/benchmark_upscale.ps1`
- Тесты: `tests/test_presets.py`, `tests/test_smoke_exam_imgs.py`, `tests/test_upscale.py`

### Изменено

- Модель `anime_6B` в UI: подпись **x4plus-anime (только ×4)**; пресет «Качество» — `scale: 4`; ×2 для этой модели отключён в UI
- `anim/upscale.py`: при `anime_6B` и scale 2/3 принудительно **×4** + предупреждение в лог (артефакты NCNN)
- Документация блока A: `ComicSplit_Documentation.md` v1.3, `MODELS_SPECIFICATION.md`, `ROADMAP_QUALITY_BOOST.md`, `IMPLEMENTATION_STATUS.md`

### Исправлено

- Gradio: `gr.File` без недопустимого `info`; подсказки через Markdown
- Веб: z-index и закрытие всплывающих подсказок
- Убраны лишние баннеры/серые «заблокированные» блоки — остался только бейдж режима

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
- API детекция: `analyze_page` без записи в `out_ui/`
- Windows: `NO_COLOR`, `WINDOW_BACKEND=headless` для DepthFlow

---

## [2026-05] — Split MVP (ранний май)

### Добавлено

- YOLO + MobileSAM ONNX (CPU), `pipeline.py`, `process_source`
- Gradio split (`main.py`, :7860)
- FastAPI + Konva редактор (:8000)
- Go CLI `comicsplit.exe`, `ml_worker`
- `utils/path_resolve.py`, `config.yaml`, pytest, `benchmark.py`

---

## Ссылки

| Документ | Назначение |
|----------|------------|
| [spec_s/ComicSplit_Documentation.md](spec_s/ComicSplit_Documentation.md) | Руководство пользователя |
| [spec_s/IMPLEMENTATION_STATUS.md](spec_s/IMPLEMENTATION_STATUS.md) | Статус модулей |
| [spec_s/ROADMAP_QUALITY_BOOST.md](spec_s/ROADMAP_QUALITY_BOOST.md) | Roadmap качества |
| [spec_s/README.md](spec_s/README.md) | Индекс документации |

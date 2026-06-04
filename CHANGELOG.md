# Changelog

Все значимые изменения проекта ComicSplit (`SPLIT_PANELS_DEV`).  
Формат ориентирован на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).

## [Unreleased]

### Изменено (документация)

- Консолидация `spec_s/`: 7 активных документов (`ARCHITECTURE`, `IMPLEMENTATION_STATUS`, `MODELS_SPECIFICATION`, `ROADMAP`, …) + `spec_s/archive/`
- Устаревшие файлы перенесены в архив (`SPLIT_DETECTORS.md`, `UPSCALE_UI_PARAMS.md`, `ROADMAP_QUALITY_BOOST.md` и др.)
- Исправлены статусы TPSMM (интегрирован в `anim_pipeline`), API v1.3, ~41 pytest

### Добавлено (B2 — TPSMM)

- `anim/animate_tpsmm.py`, режим `tpsmm` в `anim_pipeline.py`
- `config_animate.yaml`: `tpsmm_driving_video`, `tpsmm_mode`
- API / Gradio / :8000: режим TPSMM + driving MP4, предупреждение о скорости

### Добавлено (B1 — manga YOLO)

- Детекторы split: `comic` | `manga` — `utils/panel_detector.py`, `config.yaml`, `pipeline.py` (multi-class YOLO)
- Экспорт манги: `scripts/export_manga_yolo.py`, `scripts/export_manga_yolo.ps1` → `yolo_manga_int8.onnx`
- API: `GET /api/split/options`, поле `panel_detector` в `POST /api/process`
- Gradio + :8000: dropdown «Детектор панелей»; пресеты детектор не перезаписывают
- Док: [MODELS_SPECIFICATION.md](spec_s/MODELS_SPECIFICATION.md) §1.2; бенчмарк: `scripts/benchmark_split_detectors.py`
- Реестр: секция `split` в `models_registry.yaml`, статус в `GET /api/models/setup`

### Добавлено (подготовка апскейлеров, этап P1)

- Скачивание **Real-CUGAN** и **SPAN** NCNN Vulkan: `scripts/download_upscale_backends.ps1`
- Реестр моделей: `config/models_registry.yaml`, `utils/models_registry.py`
- Проверка: `scripts/verify_upscale_backends.py`, тесты `tests/test_models_registry.py`
- Документация: MODELS_SETUP_GUIDE §1b, MODELS_SPECIFICATION §2.2–2.3, ROADMAP v1.3

### Добавлено (интеграция B4)

- `anim/upscale.py`: backend realesrgan / realcugan / span
- API v1.3: `GET /api/upscale/options`, расширенные поля POST `/api/upscale` и `/api/animate`
- Gradio + :8000: выбор backend, модель, CUGAN noise/syncgap, подсказка если модель не установлена
- [MODELS_SPECIFICATION.md](spec_s/MODELS_SPECIFICATION.md) §2.2–2.3, тесты `tests/test_upscale_options.py`
- B4.4: `benchmark_upscale.py` — все backend через `anim/upscale.py`
- B0.3: `GET /api/models/setup`, блок «Скачать / проверить модели» в Gradio и :8000

### Планируется

- [ROADMAP_QUALITY_BOOST.md](spec_s/ROADMAP_QUALITY_BOOST.md) — **B2** TPSMM; **B1.4** benchmark после установки `yolo_manga_int8.onnx`
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
| [spec_s/ARCHITECTURE.md](spec_s/ARCHITECTURE.md) | Архитектура и API |
| [spec_s/IMPLEMENTATION_STATUS.md](spec_s/IMPLEMENTATION_STATUS.md) | Статус модулей |
| [spec_s/MODELS_SPECIFICATION.md](spec_s/MODELS_SPECIFICATION.md) | Модели и параметры |
| [spec_s/ROADMAP.md](spec_s/ROADMAP.md) | Roadmap качества |
| [spec_s/README.md](spec_s/README.md) | Индекс документации |

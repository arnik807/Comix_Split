# ComicSplit — статус реализации (июнь 2026)

Актуальный снимок кодовой базы `SPLIT_PANELS_DEV`. Установка и запуск: [ComicSplit_Documentation.md](ComicSplit_Documentation.md).

---

## Сводка

| Компонент | Статус |
|-----------|--------|
| ML split (YOLO + SAM, CPU ONNX) | **Готово** |
| Пакетная обработка CBZ/ZIP/папка | **Готово** (`process_source`) |
| `config.yaml` + `config/presets.yaml` | **Готово** |
| Пресеты **Стандарт / Качество** (API + оба UI) | **Готово** (`utils/presets.py`) |
| Gradio (`main.py`, :7860) — Split / Upscale / Video | **Готово** (пресеты, подсказки, «Обзор…») |
| Python CLI split (`pipeline.py`) | **Готово** |
| Anim CLI (`anim_pipeline.py`) | **Готово** |
| Anim модули (`anim/`: upscale, harmonize, opencv, depthflow, render) | **Готово** (TPSMM/segment — нет) |
| Веб-редактор (FastAPI + Konva, :8000) — Split / Upscale / Video | **Готово** (паритет с Gradio по настройкам) |
| Подсказки ко всем настройкам | **Готово** (`utils/ui_tooltips.py`, `GET /api/tooltips`) |
| Выбор путей (Windows-диалог + ручной ввод) | **Готово** (`utils/path_dialog.py`, `POST /api/path/pick`) |
| Go CLI (`comicsplit.exe`) | **Частично** (CBZ/папка/JPG; CBR только в Python) |
| OpenCV fast-path каскад | **Нет** |
| Wails desktop | **Нет** |
| gRPC Go↔Python | **Нет** |
| PyInstaller EXE | **Spec есть**, сборка вручную |
| Benchmark &lt;600 ms/стр. | **Не закрыт** |

---

## Реализованные модули

| Путь | Назначение |
|------|------------|
| `pipeline.py` | `analyze_page`, `process_page`, `process_source`, CLI split |
| `anim_pipeline.py` | CLI: upscale → harmonize 16:9 → animate → MP4 + storyboard |
| `anim/` | `upscale`, `harmonize`, `animate_opencv`, `animate_depthflow`, `render`, `io_utils` |
| `config.yaml` | Split: YOLO/SAM, порядок чтения, имена PNG |
| `config_animate.yaml` | Anim: upscale, harmonize, animation, render |
| `config/presets.yaml` | Пресеты `standard` / `quality` (split + anim) |
| `utils/config.py`, `utils/anim_config.py` | Загрузка конфигов |
| `utils/presets.py` | load / apply / snapshot пресетов |
| `utils/ui_tooltips.py` | Тексты подсказок для Gradio и веб-UI |
| `utils/path_dialog.py` | Нативные диалоги выбора файла/папки (tkinter) |
| `utils/io_helpers.py` | CBZ, CBR, ZIP, папка, imdecode для кириллицы |
| `utils/path_resolve.py` | Пути с кириллицей (API :8000) |
| `main.py` | Gradio 5.x, 3 вкладки, пресеты, tooltips, browse |
| `api/server.py` v1.2 | REST: process, export, upscale, animate, video, presets, tooltips, path/pick |
| `frontend/index.html` | Konva-редактор + Upscale/Video + пресеты + tooltips + «Обзор…» |
| `ml_worker/main.py` | IPC для Go |
| `cmd/comicsplit/` + `internal/*` | Go-оркестратор |
| `scripts/download_animate_models.ps1`, `quantize_animate_models.py` | Модели anim |
| `scripts/benchmark_upscale.ps1`, `benchmark_upscale.py` | Бенчмарк NCNN upscale |
| `scripts/split_models_craft_scripts/` | Модели split |
| `benchmark.py`, `yolo_test.py`, `sam_test.py` | QA split |
| `tests/` | pytest (**25** тестов в 7 файлах) |
| `packaging/comicsplit.spec` | PyInstaller |

---

## Пресеты качества (блок A)

| Пресет | ID | Split | Anim (кратко) |
|--------|-----|-------|---------------|
| **Стандарт** | `standard` | YOLO без SAM, порог 0.35 | animevideov3, OpenCV zoom |
| **Качество** | `quality` | YOLO + SAM, порог 0.30 | x4plus-anime (`anime_6B`) **×4**, blurred_pillarbox, DepthFlow dolly |

- Эталон: `config/presets.yaml`; опциональные локальные правки — `config/presets.user.yaml` (в `.gitignore`).
- API: `GET /api/presets`, `GET /api/presets/{name}`, `POST /api/presets/apply`.
- UI: кнопки «Стандарт» / «Качество»; бейдж **MODE: STANDARD** / **MODE: QUALITY**; расширенные поля видны только в режиме «Качество».

### Апскейл NCNN (важно)

| ID в конфиге | NCNN `-n` | Масштаб |
|--------------|-----------|---------|
| `animevideov3` | `realesr-animevideov3` | ×2 или ×4 (есть веса `*-x2/x3/x4.bin`) |
| `anime_6B` | `realesrgan-x4plus-anime` | **только ×4** (UI + `anim/upscale.py`; ×2 даёт артефакты) |

- `config_animate.yaml` → `upscale.tile_size` (0 = auto; 64/128/256 для AMD Vega).
- Бенчмарк: `scripts/benchmark_upscale.ps1 -Quick`.

---

## Веб-редактор (:8000) — детали

| Функция | Поведение |
|---------|-----------|
| `POST /api/process` | Только детекция в память (`analyze_page`), **файлы не пишет** |
| `POST /api/export` | PNG в папку пользователя (`output_dir/имя_страницы/`) |
| `POST /api/upscale` | Real-ESRGAN NCNN по папке панелей |
| `POST /api/animate` | `anim_pipeline.process_folder` |
| `GET /api/video` | Отдача MP4 для превью |
| `GET /api/presets`, `POST /api/presets/apply` | Пресеты качества |
| `GET /api/tooltips` | Тексты подсказок для полей UI |
| `POST /api/path/pick` | Нативный диалог выбора файла/папки на машине сервера |
| Split: Accurate (SAM) vs Полигон | SAM — контур при детекции; **маска при экспорте** только если включён «Полигон» или форма правилась вручную |
| Устаревшее | Папка `out_ui/` больше **не создаётся** API |

---

## Модели (не в git)

**Split** — `models/`:

- `yolo_comic_int8.onnx`
- `mobilesam_encoder_int8.onnx`
- `mobilesam_decoder_int8.onnx`

**Anim** — `models/anim/` (см. `models/README.md`, `scripts/MODELS_SETUP_GUIDE.md`):

- NCNN Real-ESRGAN / Real-CUGAN / SPAN — в `anim/upscale.py` (backend в UI, пресеты = Real-ESRGAN)
- MiDaS ONNX, TPSMM ONNX (INT8 опционально)
- `config/models_registry.yaml`, `utils/models_registry.py`
- `ffmpeg` в `models/anim/ffmpeg/bin/`
- DepthFlow — pip-пакет `depthflow` (не файл в `models/`)

---

## Тестовые данные в репозитории

| Путь | Содержание |
|------|------------|
| `test_page.jpg` | Одна страница для быстрого теста |
| `exam_imgs/` | 2 страницы Asterix для benchmark и smoke-тестов |
| `comic.cbz` | **Нет** — подставьте свой CBZ или `exam_imgs` |

---

## Roadmap (кратко)

| Фаза | Спека v2.0 | Факт (июнь 2026) |
|------|------------|------------------|
| 0 Спецификация | ✅ | ✅ |
| 1 Python PoC split | 🔄 | ~85% (anim-пайплайн добавлен отдельно) |
| 2 Go CLI | 📋 | Частично (`comicsplit.exe`) |
| 3 gRPC | 📋 | Нет |
| 4 UI | 📋 | Gradio + Konva :8000 (не Wails) |
| Anim (отдельная спека) | 📋 | MVP: NCNN upscale, harmonize, OpenCV/DepthFlow, ffmpeg |
| Блок A (пресеты + UI) | 📋 | ✅ закрыт — см. [ROADMAP_QUALITY_BOOST.md](ROADMAP_QUALITY_BOOST.md) |
| Блок B (новые модели) | 📋 | B4 ✅; B1 manga YOLO (код ✅); B2 TPSMM (код + UI ✅, модели на диске — download) |

---

## Известные ограничения

- Gradio: без галереи превью; результат split — текстовое поле с путями.
- DepthFlow: первый запуск качает depth-модель; на CPU/GPU долго на 1920×1080.
- TPSMM и `segment.py` из anim-спеки — **не подключены** к `anim_pipeline.py`.
- :8000 — при кириллице в путях предпочтительны относительные пути (`exam_imgs\...`); диалог «Обзор…» открывается на машине, где запущен uvicorn.
- Go CLI: subprocess Python; CBR только через `pipeline.py`.

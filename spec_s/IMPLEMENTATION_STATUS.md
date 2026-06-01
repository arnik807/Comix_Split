# ComicSplit — статус реализации (май 2026)

Актуальный снимок кодовой базы `SPLIT_PANELS_DEV`. Установка и запуск: [ComicSplit_Documentation.md](ComicSplit_Documentation.md).

---

## Сводка

| Компонент | Статус |
|-----------|--------|
| ML split (YOLO + SAM, CPU ONNX) | **Готово** |
| Пакетная обработка CBZ/ZIP/папка | **Готово** (`process_source`) |
| `config.yaml` | **Готово** |
| Gradio (`main.py`, :7860) — Split / Upscale / Video | **Готово** |
| Python CLI split (`pipeline.py`) | **Готово** |
| Anim CLI (`anim_pipeline.py`) | **Готово** |
| Anim модули (`anim/`: upscale, harmonize, opencv, depthflow, render) | **Готово** (TPSMM/segment — нет) |
| Веб-редактор (FastAPI + Konva, :8000) — Split / Upscale / Video | **Готово** |
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
| `utils/config.py`, `utils/anim_config.py` | Загрузка конфигов |
| `utils/io_helpers.py` | CBZ, CBR, ZIP, папка, imdecode для кириллицы |
| `utils/path_resolve.py` | Пути с кириллицей (API :8000) |
| `main.py` | Gradio 5.x, 3 вкладки |
| `api/server.py` v1.1 | REST: process, export, upscale, animate, video |
| `frontend/index.html` | Konva-редактор + вкладки Upscale/Video |
| `ml_worker/main.py` | IPC для Go |
| `cmd/comicsplit/` + `internal/*` | Go-оркестратор |
| `scripts/download_animate_models.ps1`, `quantize_animate_models.py` | Модели anim |
| `scripts/split_models_craft_scripts/` | Модели split |
| `benchmark.py`, `yolo_test.py`, `sam_test.py` | QA split |
| `tests/` | pytest (**13** тестов) |
| `packaging/comicsplit.spec` | PyInstaller |

---

## Веб-редактор (:8000) — детали

| Функция | Поведение |
|---------|-----------|
| `POST /api/process` | Только детекция в память (`analyze_page`), **файлы не пишет** |
| `POST /api/export` | PNG в папку пользователя (`output_dir/имя_страницы/`) |
| `POST /api/upscale` | Real-ESRGAN NCNN по папке панелей |
| `POST /api/animate` | `anim_pipeline.process_folder` |
| `GET /api/video` | Отдача MP4 для превью |
| Split: Accurate (SAM) vs Полигон | SAM — контур при детекции; **маска при экспорте** только если включён «Полигон» или форма правилась вручную |
| Устаревшее | Папка `out_ui/` больше **не создаётся** API (была служебной при `process_page` на детекции) |

---

## Модели (не в git)

**Split** — `models/`:

- `yolo_comic_int8.onnx`
- `mobilesam_encoder_int8.onnx`
- `mobilesam_decoder_int8.onnx`

**Anim** — `models/anim/` (см. `models/README.md`, `scripts/MODELS_SETUP_GUIDE.md`):

- NCNN Real-ESRGAN, MiDaS ONNX, TPSMM ONNX (INT8 опционально)
- `ffmpeg` в `models/anim/ffmpeg/bin/`
- DepthFlow — pip-пакет `depthflow` (не файл в `models/`)

---

## Тестовые данные в репозитории

| Путь | Содержание |
|------|------------|
| `test_page.jpg` | Одна страница для быстрого теста |
| `exam_imgs/` | 2 страницы Asterix для benchmark |
| `comic.cbz` | **Нет** — подставьте свой CBZ или `exam_imgs` |

---

## Roadmap (кратко)

| Фаза | Спека v2.0 | Факт (май 2026) |
|------|------------|-----------------|
| 0 Спецификация | ✅ | ✅ |
| 1 Python PoC split | 🔄 | ~85% (anim-пайплайн добавлен отдельно) |
| 2 Go CLI | 📋 | Частично (`comicsplit.exe`) |
| 3 gRPC | 📋 | Нет |
| 4 UI | 📋 | Gradio + Konva :8000 (не Wails) |
| Anim (отдельная спека) | 📋 | MVP: NCNN upscale, harmonize, OpenCV/DepthFlow, ffmpeg |

---

## Известные ограничения

- Gradio: без галереи превью; результат split — текстовое поле с путями.
- DepthFlow: первый запуск качает depth-модель; на CPU/GPU долго на 1920×1080.
- TPSMM и `segment.py` из anim-спеки — **не подключены** к `anim_pipeline.py`.
- :8000 — при кириллице в путях предпочтительны относительные пути (`exam_imgs\...`).
- Go CLI: subprocess Python; CBR только через `pipeline.py`.

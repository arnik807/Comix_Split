# ComicSplit — статус реализации (май 2026)

Актуальный снимок кодовой базы `SPLIT_PANELS_DEV`. Для установки и запуска см. [ComicSplit_Documentation.md](ComicSplit_Documentation.md).

---

## Сводка

| Компонент | Статус |
|-----------|--------|
| ML-пайплайн (YOLO + SAM, CPU ONNX) | **Готово** |
| Пакетная обработка CBZ/ZIP/папка | **Готово** (`process_source`) |
| Конфиг `config.yaml` | **Готово** |
| Gradio UI (`main.py`, :7860) | **Готово** |
| Python CLI (`pipeline.py`) | **Готово** |
| Редактор масок (FastAPI + Konva, :8000) | **Частично** (детекция, rect/polygon, export) |
| Go CLI (`comicsplit.exe`) | **Частично** (CBZ/папка/JPG; CBR только в Python) |
| OpenCV fast-path каскад | **Нет** |
| Wails desktop | **Нет** |
| gRPC Go↔Python | **Нет** |
| PyInstaller EXE | **Spec есть**, сборка вручную |
| Формальный benchmark &lt;600 ms/стр. | **Не закрыт** |

---

## Реализованные модули

| Путь | Назначение |
|------|------------|
| `pipeline.py` | `analyze_page`, `process_page`, `process_source`, CLI |
| `utils/config.py` | Загрузка `config.yaml` |
| `utils/io_helpers.py` | CBZ, CBR, ZIP, папка, одиночное изображение |
| `utils/path_resolve.py` | Пути с кириллицей и mojibake (API :8000) |
| `main.py` | Gradio 5.x |
| `api/server.py` + `frontend/index.html` | Редактор на :8000 |
| `ml_worker/main.py` | IPC для Go |
| `cmd/comicsplit/` + `internal/*` | Go-оркестратор |
| `benchmark.py`, `yolo_test.py`, `sam_test.py` | QA |
| `tests/` | pytest (9 тестов) |
| `packaging/comicsplit.spec` | PyInstaller |

---

## Модели (не в git)

После установки в `models/`:

- `yolo_comic_int8.onnx`
- `mobilesam_encoder_int8.onnx`
- `mobilesam_decoder_int8.onnx`

---

## Тестовые данные в репозитории

| Путь | Содержание |
|------|------------|
| `test_page.jpg` | Одна страница для быстрого теста |
| `exam_imgs/` | 2 страницы Asterix для benchmark |
| `comic.cbz` | **Нет** — в примерах команд подставьте свой файл или `exam_imgs` |

---

## Roadmap (кратко)

| Фаза | Спека v2.0 | Факт |
|------|------------|------|
| 0 Спецификация | ✅ | ✅ |
| 1 Python PoC | 🔄 | ~80% (нет полного edge-case QA) |
| 2 Go CLI | 📋 | Частично (`comicsplit.exe`) |
| 3 gRPC интеграция | 📋 | Нет |
| 4 Wails UI | 📋 | Konva в браузере вместо Wails |

---

## Известные ограничения

- Gradio: без галереи превью; результат — список путей в текстовом поле.
- :8000 — для путей с кириллицей предпочтительно `exam_imgs\file.jpg` или относительный путь.
- Go CLI: subprocess Python, последовательная нумерация панелей; `comic.cbz` должен существовать на диске.
- Скорость на больших страницах может превышать 600 ms (цель фазы 1 PoC).

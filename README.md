# ComicSplit

Автоматическая нарезка панелей комиксов на CPU (YOLO + опционально MobileSAM). Windows, Python 3.11.

**Полная документация:** [spec_s/ComicSplit_Documentation.md](spec_s/ComicSplit_Documentation.md) — установка, Gradio, CLI, выходные файлы, troubleshooting.

## Быстрый старт

```powershell
python -m venv venv_311
.\venv_311\Scripts\activate
pip install -r requirements.txt
.\scripts\download_models.ps1
python scripts\quantize_models.py
```

### Gradio (интерфейс в браузере)

```powershell
$env:NO_PROXY = "127.0.0.1,localhost"
python main.py
```

→ http://127.0.0.1:7860

### CLI (командная строка)

```powershell
python pipeline.py test_page.jpg output --order
python pipeline.py exam_imgs output --order
# или свой CBZ: python pipeline.py D:\comics\book.cbz output --order
```

→ PNG в `output\<имя_источника>\`

## Документация

| Файл | Содержание |
|------|------------|
| [spec_s/ComicSplit_Documentation.md](spec_s/ComicSplit_Documentation.md) | **Актуальное руководство** (Gradio, CLI, :8000, Go) |
| [spec_s/IMPLEMENTATION_STATUS.md](spec_s/IMPLEMENTATION_STATUS.md) | Статус модулей и фаз |
| [spec_s/ComicSplit_Specification_v2.0.md](spec_s/ComicSplit_Specification_v2.0.md) | Целевая архитектура (Go, Wails, gRPC) |
| [spec_s/README.md](spec_s/README.md) | Индекс документации |
| [config.yaml](config.yaml) | Параметры по умолчанию |
| [models/README.md](models/README.md) | Загрузка ONNX-моделей |

## Структура (основное)

- `main.py` — Gradio UI
- `pipeline.py` — ML и CLI
- `utils/` — config, чтение CBZ/папок
- `api/` + `frontend/` — опциональный редактор масок (порт 8000)

> **Архив gap-анализа.** Актуально: [ComicSplit_Documentation.md](ComicSplit_Documentation.md), [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).  
> Ниже — обновлённая таблица «спека v2.0 vs код» на **май 2026**.

# Сопоставление спецификации v2.0 с реализацией

| Пункт спецификации | Текущее состояние | Статус |
|-------------------|-------------------|--------|
| Python ML (YOLO + SAM, ONNX INT8) | `pipeline.py`, модели в `models/` | ✅ |
| Вход: CBZ, CBR, ZIP, папка | `utils/io_helpers.py` | ✅ |
| Выход PNG + `output_pattern` | `process_page` / `process_source` | ✅ |
| Трёхуровневый каскад OpenCV→YOLO→SAM | Только YOLO (+ опц. SAM) | ❌ OpenCV path |
| IPC subprocess (JSON) | `ml_worker/main.py` + Go | ✅ |
| gRPC Go↔Python | — | ❌ |
| Go CLI batch | `cmd/comicsplit`, `comicsplit.exe` | 🟡 |
| Параллелизм страниц | `max_workers` в config, ThreadPool в pipeline | ✅ |
| Gradio UI | `main.py`, :7860 | ✅ |
| Редактор масок Konva | `api/server.py`, `frontend/`, :8000 | 🟡 |
| Wails desktop | — | ❌ |
| `config.yaml` | `utils/config.py` | ✅ |
| Скрипты моделей | `download_models.ps1`, `quantize_models.py` | ✅ |
| pytest | `tests/test_*.py` | ✅ |
| PyInstaller | `packaging/comicsplit.spec` | 🟡 spec only |
| Benchmark &lt;600 ms, 85% quality | `benchmark.py`; цель не закрыта | 🟡 |

## Рекомендуемые проверки (актуальные команды)

```powershell
.\venv_311\Scripts\activate
pip install -r requirements.txt
python pipeline.py test_page.jpg output --order
python pipeline.py exam_imgs output --order
$env:NO_PROXY="127.0.0.1,localhost"; python main.py
uvicorn api.server:app --port 8000
pytest -q
go build -o comicsplit.exe ./cmd/comicsplit
.\comicsplit.exe --input exam_imgs --output panels --python .\venv_311\Scripts\python.exe --order
```

## Что остаётся по спеке v2.0

1. OpenCV fast-path для простых страниц  
2. gRPC вместо subprocess  
3. Wails вместо Gradio + отдельного :8000  
4. CBR в Go reader  
5. Формальный QA edge cases и стабильный benchmark SLA  

---

*Исторический текст чеклиста марта 2025 удалён как неактуальный; см. git history при необходимости.*

# Документация ComicSplit (`spec_s/`)

**Обновлено:** июнь 2026 (консолидация: 7 активных документов + `archive/`)

## Актуальные документы

| Документ | Для кого | Содержание |
|----------|----------|------------|
| **[ComicSplit_Documentation.md](ComicSplit_Documentation.md)** | Пользователь | Установка, Gradio, CLI, веб :8000, Go, параметры |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | Разработчик | Стек, потоки данных, API v1.3, структура проекта |
| **[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)** | Разработчик | Статус модулей, файловая карта, ограничения |
| **[MODELS_SPECIFICATION.md](MODELS_SPECIFICATION.md)** | ML / инференс | Все модели, ссылки, Ryzen 5600H + AMD iGPU |
| **[ROADMAP.md](ROADMAP.md)** | План работ | Блоки A, B0, B1, B4 ✅; B2 🟡; B3 📋 |

## Вне `spec_s/`

| Документ | Содержание |
|----------|------------|
| [../README.md](../README.md) | Быстрый старт |
| [../CHANGELOG.md](../CHANGELOG.md) | История изменений |
| [../scripts/MODELS_SETUP_GUIDE.md](../scripts/MODELS_SETUP_GUIDE.md) | Пошаговая установка моделей |
| [../models/README.md](../models/README.md) | Краткий список файлов в `models/` |

## Архив

Устаревшие и поглощённые документы: **[archive/](archive/)** (спека v2.0, MVP-план, `SPLIT_DETECTORS.md`, `UPSCALE_UI_PARAMS.md`, `ROADMAP_QUALITY_BOOST.md` и др.).

## Способы работы

| # | Задача | Команда |
|---|--------|---------|
| 1 | Split Gradio | `python main.py` → :7860 |
| 2 | Split CLI | `python pipeline.py <источник> output --order` |
| 3 | Редактор + anim | `uvicorn api.server:app --port 8000` |
| 4 | Anim CLI | `python anim_pipeline.py <panels_dir> story_out --mode opencv_zoom` |
| 5 | Go batch split | `.\comicsplit.exe --input exam_imgs --output panels ...` |

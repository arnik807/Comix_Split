# Документация ComicSplit (`spec_s/`)

**Обновлено:** июнь 2026 (консолидация + Story 2a HITL + Split reading_order + блок S snap)

## Актуальные документы

| Документ | Для кого | Содержание |
|----------|----------|------------|
| **[ComicSplit_Documentation.md](ComicSplit_Documentation.md)** | Пользователь | Установка, Gradio, CLI, веб :8000, Go, параметры |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | Разработчик | Стек, потоки данных, API v1.3, структура проекта |
| **[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)** | Разработчик | Статус модулей, файловая карта, ограничения |
| **[MODELS_SPECIFICATION.md](MODELS_SPECIFICATION.md)** | ML / инференс | Все модели, ссылки, Ryzen 5600H + AMD iGPU |
| **[ROADMAP.md](ROADMAP.md)** | План работ | Блоки A, B0, B1, B4 ✅; B2 🟡; B3 📋; **R1 Stage 2a** 🟡; **S snap** 📋 |
| **[STORY_ANALYZER_STAGE_2A.md](STORY_ANALYZER_STAGE_2A.md)** | Story Analyzer | Stage 2a: bbox + VLM OCR + интерактивный HITL |
| **[LLM_HANDOFF_CONTEXT.md](LLM_HANDOFF_CONTEXT.md)** | Handoff для LLM | Сводный контекст проекта для другой модели |

## Вне `spec_s/`

| Документ | Содержание |
|----------|------------|
| [../README.md](../README.md) | Быстрый старт |
| [../CHANGELOG.md](../CHANGELOG.md) | История изменений |
| [../scripts/MODELS_SETUP_GUIDE.md](../scripts/MODELS_SETUP_GUIDE.md) | Пошаговая установка моделей |
| [../models/README.md](../models/README.md) | Краткий список файлов в `models/` |
| [../problems_fix/bubbles_detect_problems/ROADMAP_STAGE_2A.md](../problems_fix/bubbles_detect_problems/ROADMAP_STAGE_2A.md) | Roadmap Stage 2a (пошагово) |
| [../problems_fix/bubbles_detect_problems/LEGACY_LOCAL_OCR.md](../problems_fix/bubbles_detect_problems/LEGACY_LOCAL_OCR.md) | Консервация локального OCR |

## Архив

Устаревшие и поглощённые документы: **[archive/](archive/)** (спека v2.0, MVP-план, `SPLIT_DETECTORS.md`, `UPSCALE_UI_PARAMS.md`, `ROADMAP_QUALITY_BOOST.md` и др.).

## Способы работы

| # | Задача | Команда |
|---|--------|---------|
| 1 | Split Gradio | `python main.py` → :7860 |
| 2 | Split CLI | `python pipeline.py <источник> output --order` |
| 3 | Редактор + anim + Story 2a | `uvicorn api.server:app --port 8000` |
| 4 | Anim CLI | `python anim_pipeline.py <panels_dir> story_out --mode opencv_zoom` |
| 5 | Go batch split | `.\comicsplit.exe --input exam_imgs --output panels ...` |

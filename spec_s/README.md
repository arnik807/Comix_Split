# Документация ComicSplit (`spec_s/`)

**Обновлено:** июнь 2026 (Workspace / project mode ✅; ExText UI + manual/auto workflow)

## Актуальные документы

| Документ | Для кого | Содержание |
|----------|----------|------------|
| **[ComicSplit_Documentation.md](ComicSplit_Documentation.md)** | Пользователь | Установка, Gradio, CLI, веб :8000, Go, параметры |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | Разработчик | Стек, потоки данных, API v1.3, структура проекта |
| **[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)** | Разработчик | Статус модулей, файловая карта, ограничения |
| **[MODELS_SPECIFICATION.md](MODELS_SPECIFICATION.md)** | ML / инференс | Все модели, ссылки, Ryzen 5600H + AMD iGPU |
| **[MODELS_SETUP_GUIDE.md](MODELS_SETUP_GUIDE.md)** | Установка | Split, anim, ExText — скачивание, INT8, verify |
| **[ROADMAP.md](ROADMAP.md)** | План работ | Блоки A, B0, B1, B4 ✅; B2 🟡; B3 📋; **R1 ExText** 🟡; **S snap** 📋 |
| **[STORY_ANALYZER_STAGE_2A.md](STORY_ANALYZER_STAGE_2A.md)** | Story Analyzer | ExText (Stage 2a): bbox + VLM OCR + HITL, API, пути PNG |
| **[STORY_ANALYZER_STAGE_2A_WORKFLOW.md](STORY_ANALYZER_STAGE_2A_WORKFLOW.md)** | Story Analyzer | Режимы **Ручной / Авто**, кнопки, API по панели |
| **[WORKSPACE_REFACTORING_SPEC.md](WORKSPACE_REFACTORING_SPEC.md)** | Workspace | Спека: единый проект, batch Split, dedup ExText |
| **[WORKSPACE_REFACTORING_REPORT.md](WORKSPACE_REFACTORING_REPORT.md)** | Workspace | Отчёт реализации project mode (API v1.5, UI combobox) |
| **[LLM_HANDOFF_CONTEXT.md](LLM_HANDOFF_CONTEXT.md)** | Handoff для LLM | Сводный контекст проекта для другой модели |
| **[WEB_LLM_GIT_WORKFLOW.md](WEB_LLM_GIT_WORKFLOW.md)** | Web-LLM + Git | REPO_MAP, push GitHub/Sourcecraft, команды |

> **ExText** — видимое имя вкладки на `:8000`. В коде, API и `ui_state` секция называется `story2a` (Stage 2a).

## Вне `spec_s/`

| Документ | Содержание |
|----------|------------|
| [../README.md](../README.md) | Быстрый старт |
| [../CHANGELOG.md](../CHANGELOG.md) | История изменений |
| [../models/README.md](../models/README.md) | Краткий список файлов в `models/` |
| [../problems_fix/bubbles_detect_problems/ROADMAP_STAGE_2A.md](../problems_fix/bubbles_detect_problems/ROADMAP_STAGE_2A.md) | Roadmap Stage 2a (пошагово) |
| [../problems_fix/bubbles_detect_problems/LEGACY_LOCAL_OCR.md](../problems_fix/bubbles_detect_problems/LEGACY_LOCAL_OCR.md) | Консервация локального OCR |

## Архив

Устаревшие и поглощённые документы: **[archive/](archive/)** (спека v2.0, MVP-план, `SPLIT_DETECTORS.md`, `UPSCALE_UI_PARAMS.md`, `ROADMAP_QUALITY_BOOST.md` и др.).

Черновики слияния: `Claude_track_anliz/`, `qwen_spec_for_*` — **целевые** спеки Story Analyzer; факт Stage 2a OCR — канон в `STORY_ANALYZER_STAGE_2A.md`.

## Способы работы

| # | Задача | Команда |
|---|--------|---------|
| 1 | Split Gradio | `python main.py` → :7860 |
| 2 | Split CLI | `python pipeline.py <источник> output --order` |
| 3 | Редактор + anim + ExText | `uvicorn api.server:app --port 8000` |
| 4 | Anim CLI | `python anim_pipeline.py <panels_dir> story_out --mode opencv_zoom` |
| 5 | Go batch split | `.\comicsplit.exe --input exam_imgs --output panels ...` |

# Stage 2a — документы (bubbles + OCR)

Индекс материалов по детекции speech bubbles и OCR в Story Analyzer R1.

## Актуальные (канон)

| Документ | Назначение |
|----------|------------|
| [../../spec_s/STORY_ANALYZER_STAGE_2A.md](../../spec_s/STORY_ANALYZER_STAGE_2A.md) | **Фактический стек и пайплайн** (SiliconFlow VLM + tiled YOLO) |
| [ROADMAP_STAGE_2A.md](ROADMAP_STAGE_2A.md) | Пошаговый roadmap: что сделано, что дальше |
| [ACCEPTANCE_CHECKLIST.md](ACCEPTANCE_CHECKLIST.md) | **Приёмка** Stage 2a: 10 панелей, det + VLM OCR *(если файла нет — см. этап 6 roadmap)* |
| [LEGACY_LOCAL_OCR.md](LEGACY_LOCAL_OCR.md) | Почему отказались от локального Paddle; как консервировать код |
| [../../scripts/diagnose_stage_2a_README.md](../../scripts/diagnose_stage_2a_README.md) | Запуск диагностики |

## Исторические / постановка

| Документ | Назначение |
|----------|------------|
| [bubbles_detect_problems.md](bubbles_detect_problems.md) | Исходная спецификация проблемы (локальный OCR) |
| [Qwen_fix.md](Qwen_fix.md), [Claude_fix.md](Claude_fix.md) | Заметки консультаций LLM |
| [../Распознавание текста как на Андроидсмартфоне_*.md](../) | Обоснование pivot на VLM OCR |

## Конфиг и код

- `config/story_stage_2a.yaml`
- `story_analyzer/` — processor, detector, OCR engines, SiliconFlow provider
- `utils/ui_state.py` — persist секции `story2a`
- `frontend/story_2a.js`, `frontend/reading_order.js`, `frontend/ui_state.js`
- `scripts/test_siliconflow_api.py`

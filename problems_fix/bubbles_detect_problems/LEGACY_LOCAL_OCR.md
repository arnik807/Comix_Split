# Stage 2a — консервация локального OCR-стека

**Статус:** направление **остановлено как основной путь** (июнь 2026)  
**Актуальный OCR:** SiliconFlow VLM — см. [../../spec_s/STORY_ANALYZER_STAGE_2A.md](../../spec_s/STORY_ANALYZER_STAGE_2A.md)

---

## 1. Что произошло

После реализации Stage 2a с **PaddleOCR** (и fallback **EasyOCR**) на кропах speech bubbles:

| Проблема | Итог итераций |
|----------|----------------|
| Recall bbox | Улучшен tiled YOLO (этап 2 roadmap) → ~80%+ на americ |
| OCR на найденных bbox | Пустой или «каша» текст; re-OCR не помогал |
| Preprocess ×3 + CLAHE + auto-invert | Без существенного эффекта |
| Paddle `det=False` → `det=True` + merge строк | Без существенного эффекта |
| План line-level + Otsu (этап 3 roadmap) | **Не реализовывался** — принято решение сменить стек до вложения в CRAFT/line pipeline |

**Вывод:** для ru-комиксов с мелким/стилизованным шрифтом классический det+rec на CPU **не конкурирует** с VLM по кропу (см. также `problems_fix/Распознавание текста как на Андроидсмартфоне_*.md`).

---

## 2. Что сохраняем (не выбрасываем)

| Компонент | Зачем оставить |
|-----------|----------------|
| `story_analyzer/stages/ocr_engines.py` — `PaddleOcrEngine`, `EasyOcrEngine` | Офлайн, `ocr_engine: paddle\|easyocr`, режим `auto` |
| `story_analyzer/stages/ocr_preprocess.py` | Preprocess для локальных движков |
| `models/paddleocr/` + `scripts/install_paddle_ocr.ps1` | Опциональная установка; не обязательна для siliconflow |
| `config/story_stage_2a.yaml` → `paddle_ocr_base_dir` | Конфиг fallback |
| `tests/test_ocr_preprocess.py` | Регресс preprocess и путей Paddle |
| Диагностика `crop_*_prep.jpg` | Сравнение локального preprocess vs raw для VLM |

**Принцип:** код локального OCR **не удаляем**, но **не развиваем** как основную линию без новых данных/метрик.

---

## 3. Что считаем тупиковой веткой (не развивать)

| Направление | Статус |
|-------------|--------|
| Этап 3 roadmap: line-level Paddle (det строк → trim → Otsu → rec-only) | ❌ отменён до реализации |
| Этап 4 roadmap: fallback EasyOCR после line-level Paddle | ❌ отменён как основная стратегия |
| Подбор preprocess (×4, adaptive threshold) как главный рычаг качества | ⏸ заморожено |
| CRAFT/DBNet + CRNN внутри bbox | 📋 идея в backlog, не приоритет |
| PaddleOCR как **default** в конфиге | ❌ заменён на `siliconflow` |

Эти пункты **не удалять из истории** — они задокументированы в [bubbles_detect_problems.md](bubbles_detect_problems.md) и старой версии [ROADMAP_STAGE_2A.md](ROADMAP_STAGE_2A.md) (git history).

---

## 4. Меры «аккуратного консервирования»

### 4.1 В коде

1. **Default:** `ocr_engine: siliconflow` в `config/story_stage_2a.yaml`.
2. **Явные id движков** в `story_analyzer/ocr_engine_ids.py` — без магических строк.
3. **Не смешивать** preprocess с VLM: `ocr_reader.py` отдаёт raw crop для `siliconflow`.
4. **Режим `auto`:** локальный Paddle → cloud только при пустом результате (компромисс offline/online).
5. **Не добавлять** новые зависимости в hot-path без `--optional` / отдельного extra в requirements.

### 4.2 В документации

1. Канон Stage 2a: `spec_s/STORY_ANALYZER_STAGE_2A.md`.
2. Этот файл — **LEGACY_LOCAL_OCR.md** — единственное место про «почему отказались».
3. `bubbles_detect_problems.md` — **историческая** постановка проблемы (не переписывать под новый стек целиком).
4. Спеки v4 / FREE в `spec_s/` — добавить отсылку «OCR: см. STORY_ANALYZER_STAGE_2A», не править 100+ страниц.

### 4.3 В репозитории (опционально, по желанию)

| Действие | Когда |
|----------|-------|
| Папка `story_analyzer/stages/_legacy/` | Если появятся большие dead modules — **пока не нужно** |
| `requirements-ocr-local.txt` | Вынести paddleocr/easyocr из основного `requirements.txt` — **рекомендация на будущее** |
| Git tag `stage-2a-local-ocr-last` | Если нужна точка отката — **по запросу пользователя** |
| Удалить `models/paddleocr/` | **Не делать** — занимает место, но нужен для offline |

### 4.4 В UI

- Hint показывает `ocr_engine` и модель VLM из `/options`.
- Re-OCR возвращает **фактический** `ocr_engine` (важно для `auto`).

---

## 5. Когда снова трогать локальный OCR

Имеет смысл **только если**:

- появится **новая** локальная VLM/ocr-модель под CPU ONNX с приемлемым качеством;
- пользователь явно выберет `ocr_engine: paddle` и примет качество;
- нужен полностью offline pipeline без API.

Иначе — инвестиции в **детекцию bbox** (ogkalu, fine-tune YOLO) и **облачный OCR**, не в PP-OCR line pipeline.

---

## 6. Чеклист «консервация выполнена»

- [x] Default OCR → siliconflow
- [x] Код paddle/easyocr остаётся, помечен fallback в конфиге
- [x] Документ LEGACY (этот файл)
- [x] Канон STORY_ANALYZER_STAGE_2A.md
- [x] Roadmap Stage 2a переписан под новый стек
- [ ] ACCEPTANCE_CHECKLIST на 10 панелях с VLM — **следующий шаг пользователя**

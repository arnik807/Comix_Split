# Roadmap: Stage 2a — детекция баблов и OCR

**Проект:** ComicSplit, `D:\DEVELOP\COMICS\SPLIT_PANELS_DEV`  
**Канон стека:** [../../spec_s/STORY_ANALYZER_STAGE_2A.md](../../spec_s/STORY_ANALYZER_STAGE_2A.md)  
**Консервация локального OCR:** [LEGACY_LOCAL_OCR.md](LEGACY_LOCAL_OCR.md)

**Цель:** recall баблов ≥80% на тестовых панелях; **читаемый** OCR на большинстве найденных bbox.

---

## Стек (актуально, июнь 2026)

| # | Компонент | Роль |
|---|-----------|------|
| 1 | `yolo_manga_int8.onnx` | Детекция bbox (class 1), **tiled** inference 640 / overlap 20% |
| 2 | **SiliconFlow VLM** `Qwen/Qwen3-VL-8B-Instruct` | **Основной OCR** по кропу бабла |
| 3 | PaddleOCR / EasyOCR | **Офлайн fallback** (`paddle`, `easyocr`, локальная часть `auto`) |

*(Опционально позже: `ogkalu/comic-text-and-bubble-detector` — если recall bbox <80% на manga.)*

**Смена стратегии OCR:** этапы 3–4 старого roadmap (line-level Paddle + EasyOCR fallback) **отменены** — см. [LEGACY_LOCAL_OCR.md](LEGACY_LOCAL_OCR.md).

---

## Этап 0 — Подготовка ✅

- Тестовые наборы: `exam_img/americ_comix_1/americ_comix__upscaled`, `exam_img/manga_test_1/manga_test_1_upscaled`
- Проект в ASCII-пути `D:\DEVELOP\COMICS\SPLIT_PANELS_DEV`
- `.env` с `SILICONFLOW_API_KEY`; smoke: `python scripts/test_siliconflow_api.py`

---

## Этап 1 — Диагностика ✅

- `scripts/diagnose_stage_2a.py` + [../../scripts/diagnose_stage_2a_README.md](../../scripts/diagnose_stage_2a_README.md)
- Вывод: det слабый на full-panel 640; OCR локальный — каша

**Ваш результат:** «Этап 1 готов» — bbox мало, OCR пустой на видимом тексте.

---

## Этап 2 — Детекция: tiled YOLO ✅ (код)

- `bubble_detector.py`: tiled 640, overlap 20%, merge NMS
- `filter_contained: false`, `conf: 0.12`, `min_area: 32`
- Unit-тесты NMS/tiles

**Ваш шаг:** diagnose v2 + UI `test_v2` → сравнить bbox с v1.

| Метрика | Ожидание |
|---------|----------|
| Americ | bbox заметно больше (~80%+ recall) |
| Manga | улучшение, но не финал |

---

## Этап 3 — OCR: SiliconFlow VLM ✅ (код)

**Вместо** line-level Paddle (старый план):

1. `story_analyzer/providers/siliconflow_ocr.py` — JPEG → `/chat/completions`
2. `ocr_engines.py`: `siliconflow`, `auto`
3. `config/story_stage_2a.yaml`: `ocr_engine: siliconflow`
4. `ocr_reader.py`: raw crop для VLM; preprocess только для локальных движков
5. API/UI: `ocr_engine` в re-OCR и `/options`

**Ваш шаг:**

```powershell
# 1. Проверка API
python scripts\test_siliconflow_api.py --vision debug\stage_2a\americ_v2\003_p003_panel\crop_00_raw.jpg

# 2. Diagnose с VLM (медленнее — облако)
.\venv_311\Scripts\python.exe scripts\diagnose_stage_2a.py `
  --panels "exam_img\americ_comix_1\americ_comix__upscaled" `
  --label americ_vlm --limit 5

# 3. UI: uvicorn → Story 2a, новый project test_vlm
```

Напишите в чат:

- Читаем ли текст в `crop_*_result.txt` vs старые прогоны;
- 2–3 примера удачных / неудачных `bubble_id`;
- Приемлема ли скорость (~1–3 с/бабл).

---

## Этап 4 — Интерактивный HITL + валидация 🟡

**Цель:** стабильный workflow «авто + ручная правка» с полноценным редактором.

### 4.0 — Интерактивный UI ✅ (код, подтверждено пользователем)

| # | Задача | Статус |
|---|--------|--------|
| 4.0.1 | Bbox drag/resize (как Split rect) | ✅ |
| 4.0.2 | Chrome на рамке: № / re-OCR / удалить | ✅ |
| 4.0.3 | `reading_order` баблов + общий `reading_order.js` | ✅ |
| 4.0.4 | Detached text frame (`#s2a-bubble-frame`) | ✅ |
| 4.0.5 | Ручной бабл «+ Добавить» без рисования rect | ✅ |
| 4.0.6 | Persist `story2a` в ui_state; fix reload paths | ✅ |
| 4.0.7 | Split: порядок панелей № в sidebar и на канвасе | ✅ |
| 4.0.8 | UX cleanup: скрыть `panel_id`/bbox/% в sidebar | ✅ |

### 4.1 — Валидация ⏳

| # | Задача | Статус |
|---|--------|--------|
| 4.1 | Прогон 10 панелей americ + manga через UI | ⏳ |
| 4.2 | Re-OCR на проблемных баблах | ⏳ |
| 4.3 | A/B: `siliconflow` vs `auto` (offline fallback) | ⏳ |
| 4.4 | Чеклист formal ACCEPTANCE (этап 6) | ⏳ |

---

## Этап 5 — Детекция ogkalu (опционально) 📋

**Только если** после этапа 3 recall bbox на manga <80%.

1. `scripts/download_comic_bubble_detector.ps1`
2. Backend `manga_yolo | ogkalu | both` в `bubble_detector.py`
3. Diagnose `--backend both`

**Не начинать**, пока не оценён VLM-OCR на текущих bbox.

---

## Этап 6 — Фиксация и приёмка 📋

1. Финальный `config/story_stage_2a.yaml` по вашему выбору (`siliconflow` / `auto`).
2. [ACCEPTANCE_CHECKLIST.md](ACCEPTANCE_CHECKLIST.md) — 10 панелей, метрики recall + OCR.
3. Обновление `spec_s/IMPLEMENTATION_STATUS.md` — Stage 2a ✅ после вашего «принято».

**Критерии успеха** (из постановки проблемы):

- Recall bbox ≥80% на тестовом наборе
- ≥70% баблов с непустым читаемым `raw_text` (ru/en)
- Latency приемлема (облако: минуты на batch, не часы)
- UI: правка bbox + текста + порядок чтения работает

---

## Текущий статус

| Этап | Статус |
|------|--------|
| 0 | ✅ |
| 1 | ✅ |
| 2 | ✅ код; ⏳ ваш compare v2 |
| 3 | ✅ код SiliconFlow; ⏳ ваш прогон vlm |
| 4.0 | ✅ интерактивный HITL |
| 4.1 | ⏳ валидация (10 панелей) |
| 5 | 📋 опционально |
| 6 | 📋 formal ACCEPTANCE |

**Следующий шаг:** formal ACCEPTANCE (этап 6) **или** блок **S** Split snap — см. [../../spec_s/ROADMAP.md](../../spec_s/ROADMAP.md).

---

## Файлы

| Область | Пути |
|---------|------|
| Детекция | `bubble_detector.py`, `pipeline.py`, `config/story_stage_2a.yaml` |
| OCR cloud | `providers/siliconflow_ocr.py`, `ocr_engines.py`, `ocr_reader.py` |
| OCR legacy | `ocr_preprocess.py`, `models/paddleocr/` — см. LEGACY |
| API/UI | `api/story_stage_2a.py`, `frontend/story_2a.js`, `frontend/reading_order.js`, `frontend/ui_state.js` |
| Диагностика | `scripts/diagnose_stage_2a.py`, `scripts/test_siliconflow_api.py` |
| Доки | `spec_s/STORY_ANALYZER_STAGE_2A.md`, этот roadmap, LEGACY |

---

## Шпаргалка

| После | Вы делаете | Пишете |
|-------|------------|--------|
| Этап 2 | diagnose v2, UI test_v2 | bbox больше/нет |
| Этап 3 | diagnose vlm, UI test_vlm | OCR читаем/нет + примеры |
| Этап 4.0 | интерактивный редактор | «работает» / правки |
| Этап 4.1 | 10 панелей + re-OCR | «Этап 4 готов» |
| Этап 6 | чеклист | «принято» / правки |

**После backend-изменений:** перезапуск uvicorn.  
**Сравнение прогонов:** новые имена project (`test_v2`, `test_vlm`, …).

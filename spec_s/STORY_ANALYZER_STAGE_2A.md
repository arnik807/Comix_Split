# Story Analyzer — Stage 2a (актуальное состояние)

**Обновлено:** июнь 2026  
**Проект:** `D:\DEVELOP\COMICS\SPLIT_PANELS_DEV`  
**UI-название вкладки:** **ExText** (внутренние id: `story2a`, `stage_2a`, `story_2a.js`)  
**Roadmap этапа:** [../problems_fix/bubbles_detect_problems/ROADMAP_STAGE_2A.md](../problems_fix/bubbles_detect_problems/ROADMAP_STAGE_2A.md)  
**Режимы Ручной/Авто:** [STORY_ANALYZER_STAGE_2A_WORKFLOW.md](STORY_ANALYZER_STAGE_2A_WORKFLOW.md)  
**Консервация локального OCR:** [../problems_fix/bubbles_detect_problems/LEGACY_LOCAL_OCR.md](../problems_fix/bubbles_detect_problems/LEGACY_LOCAL_OCR.md)

---

## 1. Назначение

Stage 2a — первый контентный этап Story Analyzer (R1):

1. На каждой **апскейленной** панели найти speech bubbles (bbox).
2. Распознать текст внутри (ru + en).
3. Сохранить `story_out/projects/<project>/stage_2a.json`.
4. Ручная правка bbox, текста и **порядка чтения** в UI (`frontend/story_2a.js`, Konva).

---

## 2. Текущий стек (июнь 2026)

| Слой | Технология | Где | Статус |
|------|------------|-----|--------|
| **Детекция bbox** | `yolo_manga_int8.onnx`, class 1 = text_bubble | Локально, ONNX CPU | ✅ tiled inference |
| **OCR (основной)** | **SiliconFlow VLM** `Qwen/Qwen3-VL-8B-Instruct` | Облако, `api.siliconflow.com/v1` | ✅ интегрирован |
| **OCR (офлайн)** | PaddleOCR / EasyOCR | Локально, CPU | 🟡 fallback, см. LEGACY |
| **Режим auto** | Paddle → SiliconFlow при пустом тексте | `ocr_engine: auto` | ✅ |
| **Preprocess** | ×3, CLAHE, auto-invert | Только для локальных движков | ✅ |
| **UI / API** | FastAPI + Konva | `:8000`, вкладка **ExText** | ✅ интерактивный HITL |
| **workflow_mode** | `manual` (default) \| `auto` | Ручной: рамки → OCR по панели; Авто: batch YOLO+OCR | ✅ |
| **reading_order** | Поле `Bubble.reading_order` + авто-сортировка | `schemas.py`, `stage_2a_processor.py` | ✅ |

**Ключевое решение:** классический локальный OCR (Paddle det+rec на кропе бабла) **не дал приемлемого качества** на ru-комиксах после итераций preprocess и tiled YOLO. Основной путь — **VLM OCR по кропу** (аналог «Google Lens / Android»).

---

## 3. Пайплайн

```
Папка PNG-панелей (рекомендуется upscaled ×2)
        │
        ▼
process_panels_dir()  —  story_analyzer/stages/stage_2a_processor.py
        │
        ├─► imread (alpha → белый фон, composite_alpha_on_white)
        │
        ├─► detect_text_bubbles()  —  bubble_detector.py
        │       • yolo_manga_int8.onnx, bubble_class_id=1
        │       • tiled: 640 px, overlap 20%, merge NMS
        │       • conf 0.12, min_area 32, filter_contained=false
        │
        ├─► для каждого bbox:
        │       crop_with_padding (+12 px)
        │       ocr_bubble_crop()  —  ocr_reader.py
        │         • siliconflow: raw crop → JPEG base64 → /chat/completions
        │         • paddle/easyocr/auto: preprocess → локальный движок
        │
        └─► Stage2aDocument → stage_2a.json
```

---

## 4. Конфигурация

Файл: `config/story_stage_2a.yaml`

```yaml
stage_2a:
  ocr_engine: siliconflow   # siliconflow | paddle | easyocr | auto
  siliconflow:
    base_url: "https://api.siliconflow.com/v1"
    vlm_model: "Qwen/Qwen3-VL-8B-Instruct"
  bubble_detect:
    tiled: true
    tile_size: 640
    tile_overlap: 0.2
    filter_contained: false
  confidence_threshold: 0.12
  min_bubble_area_px: 32
```

Секреты: `.env` в корне проекта (не в git):

```env
SILICONFLOW_API_KEY=sk-...
# опционально:
# SILICONFLOW_BASE_URL=https://api.siliconflow.com/v1
# SILICONFLOW_VLM_MODEL=Qwen/Qwen3-VL-8B-Instruct
```

Проверка API:

```powershell
python scripts\test_siliconflow_api.py
python scripts\test_siliconflow_api.py --vision debug\stage_2a\...\crop_00_raw.jpg
```

---

## 5. API

Префикс: `/api/story/stage_2a`

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/options` | движки OCR, языки, preprocess, модель VLM |
| POST | `/init` | создать проект из папки панелей (пустые `bubbles`, sync PNG в project) |
| POST | `/process` | batch: YOLO + OCR по всей папке → JSON |
| POST | `/sync_panels` | скопировать PNG из `panels_dir` в `project/panels/` (`replace`, удаляет старые файлы) |
| GET | `/{project}?panels_dir=` | чтение JSON + `panel_paths` с учётом папки UI |
| PUT | `/{project}` | сохранение правок (`output_path` опционально) |
| POST | `/{project}/reocr` | один бабл; body: `bubble_id`, `bbox`, опц. `panel_abs_path` |
| POST | `/{project}/ocr_panel` | OCR всех баблов **текущей** панели (ручной режим) |
| POST | `/{project}/detect_panel` | YOLO только текущей панели, без OCR (`merge_mode`: append \| replace) |

### 5.1. Пути к PNG (`panel_paths`)

При запросе с непустым `panels_dir` (UI или query):

1. PNG берутся **только** из указанной папки (`source_only` — без fallback на старые копии в `project/panels/`).
2. «Загрузить проект» в UI сначала вызывает `POST /sync_panels`, затем `GET /{project}?panels_dir=…`.
3. Смена поля «Папка панелей» при открытом проекте сбрасывает сессию редактора (`clearSession`); нужно создать/загрузить проект заново.

Ответы `init`, `process`, `GET /{project}` содержат массив `panel_paths`: `{ panel_id, image_path, abs_path }`.

Превью в Konva: `/api/image?path=…&v=<cache_bust>` (`Cache-Control: no-store`).

---

## 6. Ключевые файлы кода

| Путь | Роль |
|------|------|
| `story_analyzer/stages/stage_2a_processor.py` | orchestration |
| `story_analyzer/stages/bubble_detector.py` | tiled YOLO |
| `story_analyzer/stages/ocr_reader.py` | crop + engine routing |
| `story_analyzer/stages/ocr_engines.py` | paddle / easyocr / siliconflow / auto |
| `story_analyzer/providers/siliconflow_ocr.py` | VLM client |
| `story_analyzer/env_loader.py` | загрузка `.env` |
| `story_analyzer/schemas.py` | `Bubble`, `Panel`, `Stage2aDocument`; поле `reading_order` |
| `story_analyzer/config.py` | `Stage2aConfig`, `SiliconFlowOcrConfig` |
| `config/story_stage_2a.yaml` | настройки |
| `scripts/diagnose_stage_2a.py` | диагностика bbox + OCR |
| `scripts/test_siliconflow_api.py` | smoke-test API |
| `frontend/story_2a.js` | UI Konva Stage 2a |
| `frontend/reading_order.js` | Общий модуль № / reorder (Split + Stage 2a) |
| `frontend/ui_state.js` | Persist секции `story2a` |
| `utils/ui_state.py` | Схема v1, merge story2a без затирания путей |
| `api/story_stage_2a.py` | REST |

---

## 7. Интерактивный UI (HITL, июнь 2026)

Вкладка **ExText** на `:8000` — полноценный редактор поверх Konva.  
Режимы и кнопки: [STORY_ANALYZER_STAGE_2A_WORKFLOW.md](STORY_ANALYZER_STAGE_2A_WORKFLOW.md).

### 7.1. Навигация и sidebar

| Элемент | Поведение |
|---------|-----------|
| **Режим** | Radio **Ручной** \| **Авто** (`workflow_mode`, persist) |
| Проект | Имя + папка панелей; persist в `ui_state.story2a` |
| **Создать из папки** | `POST /init` — список панелей без баблов |
| **Загрузить проект** | sync + `GET /{project}?panels_dir=` |
| Навигация | «Панель N / M» (без `panel_id` в UI) |
| Список баблов | Строка: **№ · точка · превью текста**; `panel_id` / `bubble_id` — только в tooltip |
| Кнопки ↑↓ / клик по № | Изменение `reading_order` через `reading_order.js` |

### 7.2. Bbox на канвасе

| Действие | Реализация |
|----------|------------|
| Drag / resize | Угловые handles (как Split rect) |
| Title bar на рамке | **№** (popup с номером) · **↻** (re-OCR) · **×** (удалить) |
| Ручной бабл | «+ Добавить бабл» → рамка ~10–40% панели, без рисования rect |
| Re-OCR | `POST /{project}/reocr` с актуальным bbox и `panel_abs_path` |

Sidebar-кнопки «Пропустить» / «Перераспознать» **убраны** — действия на chrome рамки.

### 7.3. Текстовое окно (detached frame)

Текст бабла показывается в **`#s2a-bubble-frame`** — отдельно от bbox:

- drag за title bar chrome;
- resize за угол;
- позиции хранятся в `S2.frameLayouts` (**только client-side**, не в `stage_2a.json` и не в `ui_state`);
- в `stage_2a.json` сохраняются только bbox и текст.

### 7.4. Порядок чтения

- При batch OCR: `assign_bubble_reading_orders()` — эвристика LTR (как split-панели).
- Ручная правка: popup №, кнопки ↑↓ в sidebar; `reading_order` пишется в JSON.
- Общий модуль: `frontend/reading_order.js` (тот же для Split-панелей на вкладке Split).

### 7.5. Persist UI state

Секция `story2a` в `config/ui_state.user.json`:

- `project`, `panels_dir`, `output_json_path`, `workflow_mode` (`manual` \| `auto`);
- сброс **↺ Сброс ExText** → заводские значения + `clearSession()` редактора;
- пустая строка в `panels_dir` / `project` при persist — **явная очистка** поля (не «оставить старое»);
- merge-логика `_merge_section_paths` для split / upscale / video / story2a.

---

## 8. Результаты на сегодня

| Метрика | Состояние |
|---------|-----------|
| Recall bbox (americ, tiled YOLO) | ~80%+ на тестовых панелях |
| Recall bbox (manga) | лучше v1, но нестабильно |
| OCR локальный (Paddle/EasyOCR) | ❌ непригоден как основной путь |
| OCR SiliconFlow VLM | ✅ читаемый ru-текст на пробных кропах (~2 с/бабл) |
| Интерактивный HITL | ✅ bbox, текст, порядок — подтверждено пользователем |
| Formal ACCEPTANCE | ⏳ не пройдена end-to-end |

---

## 9. Ограничения

- **Интернет + API-ключ** обязательны при `ocr_engine: siliconflow`.
- **Base URL:** `https://api.siliconflow.com/v1` (`.cn` давал 401 в тестах).
- **Latency:** облачный OCR ~1–3 с на бабл; batch 10 панелей × N баблов — минуты.
- **Стоимость:** зависит от тарифа SiliconFlow; учитывать при больших проектах.
- **Детектор:** manga YOLO class 1 — слабее на западных комиксах; этап ogkalu — опционально (см. roadmap).
- **Пути:** репозиторий и `PADDLE_OCR_BASE_DIR` — только ASCII (Windows + Paddle C++).
- **Snap grid/objects:** не реализовано; запланировано в [ROADMAP.md](ROADMAP.md) блок S (опц. S6 для Stage 2a).

---

## 10. Связь со спеками v4 / FREE

Документы `spec_s/qwen_spec_for_*` и `Claude_track_anliz/` описывают **целевую** Story Analyzer (стадии 2a–7). Для **фактической реализации Stage 2a OCR** канон — **этот файл** и `ROADMAP_STAGE_2A.md`. В спеках v4 по-прежнему указан EasyOCR — это **устаревший план OCR**, не текущий код.

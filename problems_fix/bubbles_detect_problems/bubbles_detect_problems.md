# ComicSplit — Stage 2a: Bubble Detection & OCR  
## Спецификация проблемы (для консультации с LLM)

> **⚠️ Июнь 2026 — статус:** OCR **переведён на SiliconFlow VLM** (`Qwen/Qwen3-VL-8B-Instruct`).  
> Актуальный стек и пайплайн: [../../spec_s/STORY_ANALYZER_STAGE_2A.md](../../spec_s/STORY_ANALYZER_STAGE_2A.md)  
> Roadmap: [ROADMAP_STAGE_2A.md](ROADMAP_STAGE_2A.md) · Консервация локального OCR: [LEGACY_LOCAL_OCR.md](LEGACY_LOCAL_OCR.md)  
> **UI:** вкладка **ExText** на `:8000`; режимы **Ручной / Авто** — [STORY_ANALYZER_STAGE_2A_WORKFLOW.md](../../spec_s/STORY_ANALYZER_STAGE_2A_WORKFLOW.md)  
> **Ниже — исходная постановка проблемы** (локальный Paddle/EasyOCR), сохранена для контекста.

**Проект:** ComicSplit / Story Analyzer R1  
**Модуль:** Stage 2a — детекция speech bubbles + OCR  
**Репозиторий:** `SPLIT_PANELS_DEV` (Windows, Python 3.11, CPU ONNX)  
**UI:** FastAPI `:8000` + Konva (`frontend/story_2a.js`)  
**Дата постановки:** июнь 2026  

---

## 1. Контекст и цель

ComicSplit — пайплайн для комиксов:

1. **Split** — нарезка страницы на панели (YOLO + MobileSAM, ONNX CPU)  
2. **Upscale** — апскейл панелей (Real-ESRGAN NCNN Vulkan, ×2)  
3. **Stage 2a** — на каждой панели найти **speech bubbles** (bbox) и распознать **текст внутри** (ru + en)  
4. Выход: `story_out/projects/<project>/stage_2a.json` + копии панелей в `panels/`  
5. Редактор: bbox на canvas, inline-правка текста, ручное добавление/удаление баблов, re-OCR одного бабла  

**Целевой контент:** русские и смешанные ru/en комиксы; также тесты на манге и западных комиксах.

---

## 2. Текущий пайплайн Stage 2a

```
Папка PNG-панелей (желательно upscaled)
        │
        ▼
┌───────────────────────────────────────┐
│  process_panels_dir()                 │
│  story_analyzer/stages/stage_2a_      │
│  processor.py                         │
└───────────────────────────────────────┘
        │
        ├─► imread (OpenCV, alpha → белый фон если composite_alpha_on_white)
        │
        ├─► detect_text_bubbles()  — bubble_detector.py
        │       • Модель: yolo_manga_int8.onnx (ONNX CPU)
        │       • num_classes=2: class 0 = panel, class 1 = text_bubble
        │       • bubble_class_id = 1
        │       • inference через pipeline._run_yolo():
        │         resize панели → 640×640 (stretch)
        │         NMS, conf/iou из config
        │         координаты масштабируются обратно на размер панели
        │       • min_bubble_area_px фильтр
        │
        ├─► для каждого bbox:
        │       crop_with_padding (+12 px)
        │       ocr_bubble_crop() — ocr_reader.py
        │         preprocess_bubble_crop():
        │           ×3 upscale (INTER_CUBIC)
        │           CLAHE (LAB)
        │           auto-invert если mean(gray) < 128
        │         OCR engine (config: paddle | easyocr)
        │
        └─► Stage2aDocument → stage_2a.json
```

### OCR (PaddleOCR, основной движок)

- **PaddlePaddle 3.0.0 + PaddleOCR 2.10.0**, CPU  
- Модели в `models/paddleocr/` (whl/det, whl/rec/cyrillic, whl/cls)  
- `PADDLE_OCR_BASE_DIR` → относительный путь `models/paddleocr` (из-за бага Paddle C++: не читает пути с кириллицей на Windows)  
- Init: `lang='ru'` → внутри Paddle мапится на `cyrillic` rec + `ml` det  
- Вызов: **`det=True, rec=True, cls=False`** на кропе бабла  
- Строки сортируются по Y, склеиваются через `\n`  

### Конфиг (`config/story_stage_2a.yaml`)

```yaml
stage_2a:
  bubble_class_id: 1
  confidence_threshold: 0.15      # было 0.25
  iou_threshold: 0.45
  ocr_engine: paddle
  paddle_ocr_base_dir: "models/paddleocr"
  ocr_languages: ["ru", "en"]
  composite_alpha_on_white: true
  crop_padding_px: 12
  min_bubble_area_px: 64
  ocr_preprocess:
    enabled: true
    upscale_factor: 3
    contrast: clahe
    invert: auto
    dark_background_threshold: 128
```

### API

| Endpoint | Назначение |
|----------|------------|
| `POST /api/story/stage_2a/process` | batch: папка панелей → JSON |
| `GET/PUT /api/story/stage_2a/{project}` | чтение/сохранение правок |
| `POST .../reocr` | перераспознать один бабл по bbox |

---

## 3. Наблюдаемая проблема

**Симптомы после прогона Stage 2a (механика работает, качество — нет):**

| # | Симптом | Детали |
|---|---------|--------|
| 1 | **>50% баблов не найдены** | YOLO возвращает мало bbox; часть панелей почти без баблов |
| 2 | **Найденные баблы — пустой текст** | В UI белый overlay inline-редактора без текста; `raw_text` ≈ `""` |
| 3 | **Re-OCR не помогает заметно** | Кнопка «Перераспознать бабл» — без существенного улучшения |
| 4 | **Пробелы в inline-редакторе** | Исправлено (см. §4) |

**Что НЕ является проблемой:**

- Сервер, API, сохранение JSON, Konva bbox, ручное добавление баблов — работают  
- PaddleOCR инициализируется (после переноса проекта в ASCII-путь `D:\DEVELOP\COMICS\...`)  
- Pipeline **не «выключен»** — детекция и OCR вызываются, но результат плохой  

---

## 4. Меры, которые уже применяли

### 4.1 Инфраструктура / окружение

- Установка PaddleOCR через `scripts/install_paddle_ocr.ps1`  
- Перенос проекта: `D:\DEVELOP\Видеомонтаж\...` → `D:\DEVELOP\COMICS\SPLIT_PANELS_DEV` (ASCII-путь)  
- Кэш моделей: `models/paddleocr/` вместо `~/.paddleocr` (кириллица в `C:\Users\Николай\` ломала Paddle Inference)  

### 4.2 Preprocess + OCR

- Модуль `ocr_preprocess.py`: ×3 upscale, CLAHE, auto-invert  
- Абстракция `ocr_engines.py`: EasyOCR / PaddleOCR, fallback EasyOCR при ошибке init Paddle  
- **Итерация 1:** Paddle `det=False` (rec-only на весь кроп) → почти всегда пусто  
- **Итерация 2:** Paddle `det=True` + сортировка строк по Y → **без улучшения** по отзыву пользователя  

### 4.3 Детекция баблов

- `confidence_threshold`: 0.25 → **0.15** → **без заметного прироста**  

### 4.4 UI

- Inline contenteditable + textarea; исправлен глобальный перехват **Space** (pan/zoom в Split-редакторе блокировал пробелы в Stage 2a)  

### 4.5 Входные данные (рекомендация пользователю)

- Прогон на **апскейленных** панелях (Real-ESRGAN ×2), не на сыром split — рекомендовано, но улучшение OCR всё равно недостаточное  

---

## 5. Гипотезы корневых причин

### 5.1 Детекция (YOLO)

1. **Resize 640×640** — вся панель (после upscale часто 1000–3000 px) сжимается в 640; мелкие speech bubbles занимают **2–10 px** в tensor → пропуск  
2. **Домен модели** — `yolo_manga_int8` (Manga109, class 1 = text_bubble); слабый recall на западных комиксах и нестандартных «облаках»  
3. **`_filter_contained`** в `pipeline._run_yolo` — удаляет вложенные bbox (overlap 70%); может резать перекрывающиеся баблы  
4. **`min_bubble_area_px: 64`** — отсекает очень мелкие bbox после resize  

### 5.2 OCR (Paddle)

1. **Кроп = весь бабл**, не строка текста — даже с `det=True` на фоне 80–90% белого det может не найти строки  
2. **Мелкий текст** — даже ×3 upscale может быть мало для cyrillic PP-OCRv3/v4  
3. **Preprocess** — CLAHE + auto-invert не всегда подходит (чёрный текст на белом без invert; тонкие линии шрифта)  
4. **`det=False` ранее** — принципиально неверный режим для multi-line bubble (уже исправлено, эффекта нет)  
5. **EasyOCR не используется** как fallback при пустом Paddle — не пробовали  

### 5.3 Данные / workflow

- Неясно, всегда ли пользователь подаёт upscaled панели  
- Смешение manga detector + western comic content  
- Нет сохранённых debug-артефактов (overlay bbox, кропы до/после preprocess) — сложно локализовать, где ломается  

---

## 6. Перспективные шаги (ещё не реализованы)

### Приоритет A — быстрые инженерные правки

| # | Мера | Ожидаемый эффект |
|---|------|------------------|
| A1 | **YOLO input 1280** (или multi-scale 640+1280) только для bubble pass | ↑ recall мелких баблов |
| A2 | **conf → 0.10**, `min_bubble_area_px → 32` | ↑ recall, ↑ false positives |
| A3 | **Отключить `_filter_contained`** для bubble detection | меньше потерь вложенных bbox |
| A4 | **Trim white margins** внутри bbox перед OCR | det видит текст, не белое поле |
| A5 | **upscale_factor: 4** + adaptive threshold / Otsu | ↑ OCR на мелком тексте |
| A6 | **Fallback:** если Paddle пуст → EasyOCR на том же кропе | разные движки на разных стилях |
| A7 | **Two-stage OCR:** det=True → crop каждой строки → rec-only per line | классический pipeline для comics OCR |

### Приоритет B — диагностика

| # | Мера |
|---|------|
| B1 | Скрипт `diagnose_stage_2a.py`: overlay bbox, dump crops raw/preprocessed, log scores |
| B2 | A/B: split vs upscaled vs upscaled×2 на одной панели |
| B3 | A/B: paddle vs easyocr vs оба |

### Приоритет C — модель / архитектура

| # | Мера |
|---|------|
| C1 | Отдельная модель **balloon/speech bubble detection** (не manga panel YOLO class 1) |
| C2 | Fine-tune YOLO на своих размеченных баблах (ru comics) |
| C3 | Cloud fallback (DeepSeek-OCR, Gemini Vision) для пустых bbox |
| C4 | **CRAFT/DBNet det** внутри bbox + CRNN/Paddle rec (разделить det bubble и det text) |

---

## 7. Ключевые файлы

| Путь | Роль |
|------|------|
| `story_analyzer/stages/stage_2a_processor.py` | orchestration |
| `story_analyzer/stages/bubble_detector.py` | YOLO manga class 1 |
| `story_analyzer/stages/ocr_reader.py` | crop + preprocess + engine |
| `story_analyzer/stages/ocr_preprocess.py` | CLAHE, upscale, invert |
| `story_analyzer/stages/ocr_engines.py` | EasyOCR / PaddleOCR |
| `pipeline.py` | `_run_yolo`, resize 640, NMS, `_filter_contained` |
| `models/yolo_manga_int8.onnx` | детектор (2 класса) |
| `models/paddleocr/whl/` | Paddle det/rec/cls |
| `config/story_stage_2a.yaml` | настройки |
| `frontend/story_2a.js` | UI Konva + re-OCR |
| `api/story_stage_2a.py` | REST API |

---

## 8. Железо и ограничения

- **CPU-only** для YOLO, SAM, Paddle, EasyOCR (Ryzen 5600H)  
- **GPU:** Real-ESRGAN NCNN Vulkan (AMD iGPU) — только upscale, не Stage 2a  
- **Windows 10**, пути без кириллицы обязательны для Paddle C++  
- Модели **не в git** (`models/`)  

---

## 9. Вопросы к консультирующей LLM

1. Для **comic speech bubble OCR** на CPU: оптимальная схема — один YOLO bbox → какой det+rec stack (Paddle/EasyOCR/CRAFT+CRNN)?  
2. Как поднять recall **мелких баблов** при YOLO inference на full panel resize 640 — multi-scale, tile, или отдельная balloon model?  
3. Имеет ли смысл **manga text_bubble class 1** для western/ru comics или нужен другой датасет/модель?  
4. Какой **preprocess** для «белый фон + чёрный текст + мелкий шрифт + возможен bold/outline»?  
5. Рекомендуемый **fallback chain** (Paddle → EasyOCR → cloud) и критерии переключения?  
6. Нужен ли **line-level** pipeline (segment lines inside bubble) vs whole-bubble crop для PP-OCRv4 cyrillic?  

---

## 10. Критерии успеха

- **Recall баблов:** ≥80% ручных баблов на тестовом наборе (10 панелей)  
- **OCR:** ≥70% баблов с непустым `raw_text`, пригодным для правки (не идеальный, но читаемый ru/en)  
- **Latency:** приемлемо на CPU (<30 с на 10 панелей с OCR)  
- **Workflow:** автомат + ручная доработка bbox/текста в UI  

---

*Документ подготовлен для внешней консультации. Скопируйте целиком в другой чат LLM.*
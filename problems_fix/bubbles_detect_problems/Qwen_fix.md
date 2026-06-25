# Анализ проблем Stage 2a и рекомендации

Изучил документ `bubbles_detect_problems.md`. Проблема действительно в **двух независимых узких местах**: детекция (YOLO) и распознавание (OCR). Разберу каждую с конкретными рекомендациями.

---

## 🎯 Две корневые причины, которые нужно решать параллельно

### Причина 1: YOLO теряет recall из-за resize 640×640

Это **главная проблема детекции**. Панель после upscale часто 1000-3000 px, а её сжимают в 640. Мелкий бабл (100 px на оригинале) становится 20 px на тензоре — это на грани видимости YOLOv11n.

**Доказательство:** снижение `confidence_threshold` с 0.25 до 0.15 не дало эффекта → модель физически не видит мелкие объекты, порог тут ни при чём.

### Причина 2: OCR не "осознаёт" текст — это классический OCR

PaddleOCR и EasyOCR видят **буквы**, а не **слова**. Поэтому "he" и "ing" смешиваются, `rn` читается как `m`, `cl` как `d`. Без языковой модели или VLM-подхода качество на комиксах принципиально ограничено.

---

## 🔧 Приоритет A — быстрые инженерные правки (делать прямо сейчас)

### A.1 Детекция: multi-scale YOLO + отключение фильтра

**Критически важно.** Текущий single-scale 640 — это провал.

```python
# bubble_detector.py — заменить single inference на multi-scale

def detect_text_bubbles_multiscale(panel_bgr, model, scales=(640, 1280)):
    """Запуск YOLO на двух масштабах, объединение bbox через NMS"""
    all_boxes = []
    h, w = panel_bgr.shape[:2]
    
    for scale in scales:
        # Запуск на scale×scale
        boxes, scores = _run_yolo_at_scale(panel_bgr, model, scale)
        all_boxes.extend(zip(boxes, scores))
    
    # Масштабирование обратно к оригинальному размеру
    # NMS с мягким порогом (iou=0.6) чтобы сохранить перекрывающиеся
    return nms_merged(all_boxes, iou_thresh=0.6)
```

**Конфиг изменения:**
```yaml
stage_2a:
  yolo_scales: [640, 1280]       # было: только 640
  confidence_threshold: 0.12     # чуть ниже
  min_bubble_area_px: 32         # было 64
  filter_contained: false        # отключить! В комиксах баблы часто перекрываются
```

**Ожидаемый эффект:** recall поднимется с ~50% до 75-85%.

### A.2 Детекция: пробовать оба детектора

`yolo_manga_int8` обучена на Manga109 — слабый recall на западных/ru комиксах.

```python
# bubble_detector.py — ensemble из двух моделей
def detect_text_bubbles_ensemble(panel_bgr, manga_model, comic_model):
    boxes_manga = detect_with_model(panel_bgr, manga_model)
    boxes_comic = detect_with_model(panel_bgr, comic_model)
    
    # Union с NMS
    return merge_boxes(boxes_manga + boxes_comic, iou=0.5)
```

Для **ru/en комиксов** manga-детектор часто пропускает нестандартные "облачка" — comic-детектор их ловит.

### A.3 OCR: line-level pipeline вместо whole-bubble

**Это ключевая проблема качества.** Текущий `det=True` на целом бабле с 80% белого фона — Paddle просто не находит строки.

```python
# ocr_reader.py — two-stage pipeline
def ocr_bubble_crop(crop_bgr):
    # Stage 1: найти строки текста внутри бабла
    lines = detect_text_lines(crop_bgr)  # Paddle det на целом кропе
    
    if not lines:
        # Fallback: весь кроп как одна строка
        return ocr_single_line(crop_bgr)
    
    # Stage 2: OCR каждой строки отдельно (rec-only)
    texts = []
    for line_bbox in lines:
        line_crop = crop_with_padding(crop_bgr, line_bbox, pad=4)
        line_crop = preprocess_line(line_crop)  # upscale ×4, Otsu
        text = paddle_rec_only(line_crop)       # rec без det
        texts.append(text)
    
    return "\n".join(texts)
```

**Почему это работает:** когда Paddle видит только строку (без белого фона вокруг), rec работает на порядок лучше.

### A.4 OCR: trim white margins + upscale ×4 + Otsu

```python
# ocr_preprocess.py — агрессивный preprocess для строки
def preprocess_line(line_crop_bgr):
    gray = cv2.cvtColor(line_crop_bgr, cv2.COLOR_BGR2GRAY)
    
    # 1. Trim белых полей (находим tight bbox по тексту)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    coords = cv2.findNonZero(thresh)
    if coords is not None:
        x, y, w, h = cv2.boundingRect(coords)
        gray = gray[max(0,y-4):y+h+4, max(0,x-4):x+w+4]
    
    # 2. Upscale ×4 (было ×3 — недостаточно для мелкого cyrillic)
    upscaled = cv2.resize(gray, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    
    # 3. Otsu binarization (адаптивная, не CLAHE)
    binary = cv2.threshold(upscaled, 0, 255, 
                           cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    
    return binary
```

**Почему Otsu вместо CLAHE:** на комиксах с чётким чёрным текстом на белом фоне Otsu даёт бинарное изображение, идеальное для OCR. CLAHE полезен для сканов с неравномерным освещением, но на чистых баблах он только шумит.

### A.5 Ensemble Paddle + EasyOCR

Они дополняют друг друга: Paddle лучше на cyrillic, EasyOCR — на латинице и смешанных текстах.

```python
def ocr_ensemble(line_crop):
    text_paddle = paddle_rec(line_crop)
    text_easyocr = easyocr_rec(line_crop)
    
    # Если один пустой — берём другой
    if not text_paddle.strip():
        return text_easyocr
    if not text_easyocr.strip():
        return text_paddle
    
    # Если оба есть — берём более длинный (эвристика)
    return text_paddle if len(text_paddle) >= len(text_easyocr) else text_easyocr
```

---

## 🧪 Приоритет B — диагностика (обязательно до и после правок)

Без диагностики вы будете гадать. Нужен скрипт:

```python
# scripts/diagnose_stage_2a.py
def diagnose_panel(panel_path, output_dir):
    """Генерирует diagnostic-артефакты для одной панели"""
    panel = cv2.imread(panel_path)
    
    # 1. Overlay bbox на панель (все найденные + scores)
    boxes = detect_text_bubbles_multiscale(panel, model)
    overlay = draw_boxes_with_scores(panel, boxes)
    cv2.imwrite(f"{output_dir}/overlay.jpg", overlay)
    
    # 2. Dump каждого кропа: raw → preprocessed → OCR result
    for i, box in enumerate(boxes):
        crop = crop_with_padding(panel, box, pad=12)
        cv2.imwrite(f"{output_dir}/crop_{i}_raw.jpg", crop)
        
        lines = detect_text_lines(crop)
        for j, line_bbox in enumerate(lines):
            line = crop_with_padding(crop, line_bbox, pad=4)
            preprocessed = preprocess_line(line)
            cv2.imwrite(f"{output_dir}/crop_{i}_line_{j}_raw.jpg", line)
            cv2.imwrite(f"{output_dir}/crop_{i}_line_{j}_prep.jpg", preprocessed)
            
            text = paddle_rec_only(preprocessed)
            with open(f"{output_dir}/crop_{i}_line_{j}_text.txt", "w") as f:
                f.write(text)
```

**Что это даст:** за 5 минут на 10 панелях вы увидите:
- Где YOLO пропускает (мелкие? перекрывающиеся? нестандартной формы?)
- Где preprocess ломает картинку (CLAHE слишком агрессивно? invert не нужен?)
- Где Paddle/EasyOCR расходится

---

## 🚀 Приоритет C — VLM-подход (фундаментальное решение проблемы "неосознания")

### C.1 PaddleOCR-VL-1.5 как fallback (главная рекомендация)

Это **VLM**, а не классический OCR. Она "видит" бабл и понимает текст **как слово**, а не как набор букв.

- **Ссылка:** [PaddlePaddle/PaddleOCR-VL-1.5](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.5)
- **SiliconFlow API:** есть (был в вашем списке моделей)
- **Размер:** 0.9B (можно запустить локально через ONNX, если экспортируется)
- **Точность:** 94.5% на OmniDocBench

**Fallback-логика:**
```python
def ocr_with_vlm_fallback(line_crop, original_text):
    # Если классический OCR дал грязный результат
    if is_low_quality(original_text):  # эвристика: много спецсимволов, короткие "слова"
        # VLM понимает контекст
        return vlm_ocr_via_api(line_crop)  
    return original_text

def is_low_quality(text):
    words = text.split()
    if len(words) < 2:
        return True
    # Много "слов" из 1-2 букв или со спецсимволами
    bad_words = sum(1 for w in words if len(w) <= 2 or any(c in w for c in "!?.,;:@#$%"))
    return bad_words / len(words) > 0.4
```

### C.2 Language model post-processing

После OCR прогонять через маленькую LM для исправления опечаток:

```python
# Быстрый вариант: pyspellchecker
from spellchecker import SpellChecker
spell_ru = SpellChecker(language='ru')
spell_en = SpellChecker(language='en')

def postprocess_ocr(text, lang='auto'):
    words = text.split()
    corrected = []
    for w in words:
        if lang == 'auto':
            # Автоопределение языка по слову
            spell = spell_ru if any('\u0400' <= c <= '\u04FF' for c in w) else spell_en
        else:
            spell = spell_ru if lang == 'ru' else spell_en
        
        correction = spell.correction(w)
        corrected.append(correction if correction else w)
    return " ".join(corrected)
```

**Плюсы:** бесплатно, быстро, локально.
**Минусы:** не понимает контекст, может "исправить" правильное слово.

### C.3 LLM-based correction (качественнее)

Отправлять распознанный текст + картинку бабла в Qwen2.5-VL-3B (бесплатный SiliconFlow):

```
Prompt: "Это распознанный текст из бабла комикса: '{ocr_text}'. 
В картинке видны ошибки OCR. Исправь их, сохраняя смысл и стиль речи персонажа. 
Верни только исправленный текст."
```

**Плюсы:** понимает контекст, исправляет "rn"→"m", "he"→"the".
**Минусы:** медленнее, требует API.

---

## 📊 Рекомендуемый итоговый пайплайн

```
Панель PNG
    │
    ▼
┌──────────────────────────────────────────┐
│ 1. Multi-scale YOLO [640, 1280]          │
│    + ensemble manga+comic                │
│    + filter_contained=false              │
│    + min_area=32                         │
└──────────────────────────────────────────┘
    │
    ▼ для каждого bbox
┌──────────────────────────────────────────┐
│ 2. Crop + trim white margins             │
│    + line detection (Paddle det)         │
└──────────────────────────────────────────┘
    │
    ▼ для каждой строки
┌──────────────────────────────────────────┐
│ 3. Upscale ×4 + Otsu                     │
│    + Ensemble Paddle+EasyOCR (rec-only)  │
└──────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────┐
│ 4. Quality check                         │
│    ├─ OK → spellcheck → output           │
│    └─ Low quality → VLM fallback         │
│       (PaddleOCR-VL-1.5 API)             │
└──────────────────────────────────────────┘
```

---

## 🎯 План действий (что делать завтра)

### День 1: Диагностика
1. Написать `diagnose_stage_2a.py`
2. Прогнать на 5-10 панелях из `manga_test_1` и `americ_comix_1`
3. **Собрать статистику:**
   - Сколько bbox на панель в среднем
   - Какие баблы пропускаются (мелкие/перекрывающиеся/нестандартные)
   - На каких кропах Paddle даёт пусто

### День 2-3: Детекция (A.1, A.2)
1. Multi-scale YOLO [640, 1280]
2. Отключить `_filter_contained`
3. `min_bubble_area_px: 32`, `confidence: 0.12`
4. Ensemble manga+comic (если комиксы смешанные)
5. **Прогнать диагностику снова** — оценить прирост recall

### День 4-5: OCR (A.3, A.4, A.5)
1. Line-level pipeline
2. Trim white margins + upscale ×4 + Otsu
3. Ensemble Paddle+EasyOCR
4. **A/B тест** до/после на тех же панелях

### День 6+: VLM fallback (C.1)
1. Подключить PaddleOCR-VL-1.5 через SiliconFlow
2. Добавить quality check и fallback-логику
3. **Финальный прогон** на полном тестовом наборе

---

## ❓ Вопросы к вам для уточнения

Чтобы дать более точные рекомендации, уточните:

1. **Какой контент преобладает в тестах?** 
   - Manga (чёрно-белая, японский/ru-перевод)
   - Western comics (цветные, en/ru)
   - Смешанное

2. **Есть ли размеченные данные?** 
   - Если да (хотя бы 50-100 баблов с bbox) — можно fine-tune YOLO
   - Если нет — только ensemble и engineering

3. **Готовы ли вы на SiliconFlow API для VLM fallback?**
   - Это даёт +20-30% к качеству на сложных случаях
   - Стоимость: ~$0.001/бабл (копейки)

4. **Какой целевой latency?**
   - <30 сек на 10 панелей (быстро) — классический pipeline
   - 1-3 мин на 10 панелей (качественно) — с VLM fallback

---

**Главное:** не пытайтесь чинить OCR без детекции. Сначала добейтесь recall ≥80% на bbox (multi-scale YOLO + отключение фильтра), потом уже улучшайте текст. Иначе вы будете отлаживать OCR на 20% найденных баблов, а 80% просто потеряете.

С чего начинаем — с диагностики или сразу с multi-scale YOLO?
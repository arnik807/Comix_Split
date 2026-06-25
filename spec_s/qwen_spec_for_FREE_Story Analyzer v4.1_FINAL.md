# 📄 Спецификация: Story Analyzer v4.1 (Финальная синергическая версия)

**Версия:** 4.1  
**Дата:** Июнь 2026  
**Статус:** Готово к реализации  
**Целевое железо:** AMD Ryzen 5 5600H, 16 GB RAM, AMD Radeon iGPU (Vulkan), Windows 10/11  
**Связанные документы:** [ARCHITECTURE.md](ARCHITECTURE.md), [MODELS_SPECIFICATION.md](MODELS_SPECIFICATION.md), [STORY_ANALYZER_ROADMAP_v4.md](STORY_ANALYZER_ROADMAP_v4.md)

> **⚠️ Stage 2a OCR (фактическая реализация, июнь 2026):** в коде основной OCR — **SiliconFlow VLM** (`Qwen/Qwen3-VL-8B-Instruct`), не EasyOCR из § Stage 2a ниже. Канон: [STORY_ANALYZER_STAGE_2A.md](STORY_ANALYZER_STAGE_2A.md) · [LEGACY_LOCAL_OCR.md](../problems_fix/bubbles_detect_problems/LEGACY_LOCAL_OCR.md)

---

## 🎯 Преамбула: что объединено в этой версии

Эта спецификация — результат синтеза двух параллельных веток проектирования:
- **Ветка A (моя v3.3):** акцент на Tabbed UI, Pipeline/Sandbox/Standalone режимы, DSL-макросы с выделением+оборачиванием, двухуровневый AI-волшебник, глобальная библиотека голосов
- **Ветка B (v4.0 другой LLM):** детальное описание каждого Stage с входом/выходом/JSON-схемами, конкретные алгоритмы (антигаллюцинация через rapidfuzz), конфиг-структура, retry-политика, roadmap R0-R7 с промптами

**Ключевой принцип v4.1:** каждый Stage описан **полностью автономно** — можно открыть описание Stage N, не читая остальную спеку, и работать над ним как над отдельным проектом.

---

## Часть I. Глобальные архитектурные принципы

### 1.1 Модульность и JSON-контракты

Каждый этап — автономный модуль:

```
Вход (JSON от предыдущего этапа) → Обработка → Выход (Обновлённый JSON + Assets)
```

Любой этап можно запустить отдельно, передав ему JSON предыдущего этапа. Промежуточные файлы:

```
story_out/projects/<project_name>/
├── stage_2a.json
├── stage_2b.json
├── stage_3.json
├── stage_4_story_analysis.json
├── stage_5_video_script.json
├── stage_6_video_script_audio.json
├── stage_6_voice_assignments.json
├── panels/                    # PNG из ComicSplit
├── audio/                     # WAV/MP3 из Stage 6
└── nle_export/                # FCPXML/OTIO/EDL из Stage 7
```

### 1.2 Human-in-the-Loop (HITL)

Каждый этап = независимая вкладка интерфейса. Принимает JSON от предыдущего этапа, позволяет визуально редактировать данные, сохраняет валидный JSON для следующего этапа.

**Глобальные правила навигации (низ каждой вкладки):**

```
[ ← Назад ]   [ 💾 Сохранить и проверить JSON ]   [ Далее → ]
```

«Сохранить» запускает Pydantic-валидацию выходного JSON по схеме этапа. При нарушении схемы — подсветка проблемных полей, переход блокируется.

Промежуточные файлы позволяют перезапустить любой этап без потери данных выше по пайплайну.

### 1.3 Группировка вкладок

```
[ Split ] [ Upscale ] [ Video ] [ 📖 Story Analyzer ▾ ] [ 🎙️ Voice Library ]
                                   ├─ Stage 2a: OCR баблов
                                   ├─ Stage 2b: Визуальные описания
                                   ├─ Stage 3: Перевод
                                   ├─ Stage 4: Анализ сюжета
                                   ├─ Stage 5: Сценарий
                                   ├─ Stage 6: Студия озвучки
                                   └─ Stage 7: Сборка / Экспорт NLE
```

`🎙️ Voice Library` — отдельная top-level вкладка (не часть пайплайна Story Analyzer), доступна всегда, независимо от текущего проекта.

### 1.4 Pipeline / Sandbox / Standalone режимы (per-tab)

Каждая Stage-вкладка имеет переключатель режима в верхнем баннере:

| Режим | Баннер | Источник/назначение данных |
|---|---|---|
| **Pipeline** (по умолчанию) | 🔗 Проект: `<project_name>` / Stage N | `story_out/projects/<project_name>/stageN.json`, строгая Pydantic-валидация |
| **Sandbox** | 🧪 Песочница — результат не входит в пайплайн | `story_out/sandbox/<stage_id>/<session_id>/`, валидация мягкая (предупреждения, не блокировки) |
| **Standalone** | 📂 Автономный экспорт | Пользовательские данные, экспорт без связи с пайплайном |

**Почему per-tab:** Stage 6 (TTS-студия) и Stage 2b (Captioning) одинаково полезны как самостоятельные инструменты в любой момент.

**В Sandbox-режиме:**
- Загрузка произвольных файлов (любые PNG/JSON), не привязанных к конкретному проекту
- Кнопка «💾 Сохранить и проверить JSON» превращается в «📤 Экспортировать результат»
- Кнопка «Далее →» скрыта (нет следующего этапа в изоляции)
- При успехе — кнопка «📥 Импортировать в пайплайн»

### 1.5 API Key Management + Retry

**Конфигурация (`config/story_analyzer.yaml`):**

```yaml
providers:
  siliconflow:
    base_url: "https://api.siliconflow.cn/v1"
    api_key_env: "SILICONFLOW_API_KEY"
    models:
      vlm: "Qwen/Qwen2.5-VL-3B-Instruct"
      llm_economy: "Qwen/Qwen2.5-7B-Instruct"
      llm_quality: "Qwen/Qwen3.5-122B-A10B"
      translation: "tencent/Hunyuan-MT-7B"
      tts: "FunAudioLLM/CosyVoice2-0.5B"
  openrouter:
    base_url: "https://openrouter.ai/api/v1"
    api_key_env: "OPENROUTER_API_KEY"
    models:
      llm_economy: "qwen/qwen-2.5-7b-instruct:free"

active_provider: siliconflow

retry:
  max_attempts: 3
  backoff_base_s: 4
  backoff_max_s: 30

tts_wizard:
  tier1:
    enabled: true
    model_path: "models/story/rubert_tiny2_emotion_int8.onnx"
  tier2:
    enabled: true
    provider: siliconflow
    model: "Qwen/Qwen2.5-7B-Instruct"
```

**`.env` (в `.gitignore`):**

```bash
SILICONFLOW_API_KEY=sk-xxxxxxxx
OPENROUTER_API_KEY=
```

**Retry-политика (обязательна для всех API-вызовов):**

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(cfg.retry.max_attempts),
    wait=wait_exponential(
        multiplier=cfg.retry.backoff_base_s,
        max=cfg.retry.backoff_max_s
    ),
)
def call_provider_api(provider, model, payload): ...
```

**Индикатор статуса API в UI:**

| Иконка | Значение |
|---|---|
| 🟢 | Ключ найден, последний вызов успешен |
| 🟡 | Ключ найден, последний вызов — retry в процессе |
| 🔴 | Ключ отсутствует или последний вызов завершился ошибкой |
| ⚪ | Локальный режим, API не используется |

---

## Часть II. Детальное описание этапов (Stages)

> **Принцип автономности:** каждый Stage ниже можно читать и реализовывать независимо от других. Вход/выход чётко определены через JSON-схемы.

---

### STAGE 1: Local Preprocessing ✅ (уже реализовано)

**Назначение:** Нарезка страниц комикса на панели с сохранением PNG и метаданных.

**Статус:** ✅ Готово в ComicSplit MVP (`pipeline.py`)

**Вход:** Страница комикса (JPG/PNG/CBZ/ZIP/папка)

**Процесс:**
1. YOLO detection → bbox панелей
2. [Accurate] MobileSAM → уточнение маски/полигона
3. Crop → PNG с альфа-каналом
4. Сохранение метаданных

**Выход:**
- `panels/panel_XXX.png` — PNG панели
- `panels_metadata.json` — метаданные

**JSON-схема выхода (`panels_metadata.json`):**

```json
{
  "source": "comic.cbz",
  "total_pages": 24,
  "total_panels": 156,
  "panels": [
    {
      "panel_id": "001",
      "page": 1,
      "image_path": "panels/001_page_001_panel_01.png",
      "bbox": [10, 20, 500, 600],
      "polygon": [[10, 20], [500, 20], [500, 600], [10, 600]],
      "reading_order": 1
    }
  ]
}
```

**Критерий успеха:**
- ✅ PNG панели с альфа-каналом
- ✅ `panels_metadata.json` с bbox и reading_order
- ✅ Визуализация `_visualization.jpg` для каждой страницы

---

### STAGE 2a: Bubble Detection & Local OCR

**Назначение:** Точное извлечение текста из баблов с возможностью ручной коррекции.

#### Вход

`panels_metadata.json` + папка `panels/` из Stage 1.

#### Технологии

| Модель | Ссылка | Роль | Оценка |
|---|---|---|---|
| **YOLO Manga INT8** | [HF: leoxs22/manga-panel-detector-yolo26n](https://huggingface.co/leoxs22/manga-panel-detector-yolo26n) | Детекция баблов (класс `1 = text_bubble`). **Уже есть в проекте.** | ⭐⭐⭐ ONNX CPU, ~300мс/панель |
| **EasyOCR** | [GitHub: JaidedAI/EasyOCR](https://github.com/JaidedAI/EasyOCR) | OCR кропа бабла | ⭐⭐⭐ CPU, ~200мс/бабл |

#### UI вкладки «Stage 2a: OCR Корректор»

- **Центр:** Canvas (Konva.js) с текущей панелью.
- **Поверх изображения:** bbox-прямоугольники вокруг баблов.
- **Клик по bbox:** `contentEditable` поле прямо на канвасе с распознанным текстом.
- **Кнопки:**
  - `[Пропустить бабл]` — удалить из JSON
  - `[Добавить бабл вручную]` — нарисовать новый bbox
  - Dropdown типа: `speech` / `thought` / `sfx` / `narration`

#### Выходной JSON (`stage_2a.json`)

```json
{
  "project": "asterix_01",
  "panels": [
    {
      "panel_id": "001",
      "image_path": "panels/001.png",
      "bubbles": [
        {
          "bubble_id": "001_b1",
          "bbox": [10, 20, 100, 50],
          "raw_text": "We must leave!",
          "corrected_text": "We must leave!",
          "type": "speech"
        }
      ]
    }
  ]
}
```

#### Критерий успеха

- ✅ JSON содержит `corrected_text` для всех баблов
- ✅ UI редактирует текст без перезагрузки страницы
- ✅ Ручное добавление бабла создаёт корректную запись
- ✅ Dropdown типа работает для каждого бабла

---

### STAGE 2b: Visual Captioning

**Назначение:** Текстовое описание визуального ряда (действия, эмоции, фон) — то, чего нет в OCR.

**Обоснование:** Комикс — визуальный медиум. Немые панели, мимика, экшен-сцены, смена локации несут сюжетную информацию, которой в тексте баблов нет вообще. Без этого Stage 4 работает вслепую.

#### Вход

`stage_2a.json` + папка `panels/` из Stage 1.

#### Технологии

| Модель | Ссылка | Роль | Оценка |
|---|---|---|---|
| **Florence-2-large** (локально) | [HF: microsoft/Florence-2-large](https://huggingface.co/microsoft/Florence-2-large) | Локальный caption, task `DETAILED_CAPTION`, ~800MB | ⭐⭐ ONNX CPU, ~5-10с/панель |
| **Qwen2.5-VL-3B-Instruct** (облако) | [SiliconFlow](https://cloud.siliconflow.cn/models) | Облачный caption, быстрее и точнее | ⭐⭐⭐ API, ~1-2с/панель |

**Промпт:**
```
Describe the visual action, characters, expressions, and setting in this comic panel in 1-2 sentences. Ignore text.
```

#### UI вкладки «Stage 2b: Визуальные описания»

- **Макет:** Сетка (Grid) миниатюр панелей (300px шириной), несколько рядов.
- **Под каждой миниатюрой:** `textarea` со сгенерированным описанием.
- **Кнопка 🔄 `[Перегенерировать]`:** повторный вызов с уточняющим промптом, не сбрасывает остальные карточки.
- **Ручное редактирование** текста.
- **Миниатюры:** уменьшенные превью (не 1:1), сами PNG остаются в `panels/`.

#### Выходной JSON (`stage_2b.json`)

Добавляет `"visual_caption"` к каждой панели из `stage_2a.json`:

```json
{
  "project": "asterix_01",
  "panels": [
    {
      "panel_id": "001",
      "image_path": "panels/001.png",
      "bubbles": [...],
      "visual_caption": "Two men in armor stand in a dark corridor, one pointing urgently toward an exit."
    }
  ]
}
```

#### Критерий успеха

- ✅ Сетка без лагов на 20+ панелях
- ✅ Поле описания редактируемо
- ✅ Перегенерация одной карточки не трогает остальные
- ✅ Описание не содержит текст из баблов

---

### STAGE 3: Translation (опционально)

**Назначение:** Перевод реплик баблов и визуальных описаний на целевой язык.

#### Вход

`stage_2b.json` (или `stage_2a.json` если caption не нужен).

#### Технологии

| Модель | Ссылка | Роль | Оценка |
|---|---|---|---|
| **Hunyuan-MT-7B** | [SiliconFlow: tencent/Hunyuan-MT-7B](https://cloud.siliconflow.cn/models) | Перевод, лидер WMT25, 33 языка, FREE | ⭐⭐⭐ API, бесплатно, 32K контекст |

#### UI вкладки «Stage 3: Перевод»

- **Макет:** Split-view (две колонки).
  - **Слева:** оригинал (read-only или с пометкой "source").
  - **Справа:** переведённый текст в редактируемом поле.
- **Чекбокс `[x] Не переводить (SFX/звук)]`:** рядом с каждым баблом (для звуковых эффектов типа "BAM!").
- **Кнопка `[Применить ко всем неотредактированным]`:** массовая обработка.

#### Выходной JSON (`stage_3.json`)

Добавляет `"text_ru"` к баблам, `"caption_ru"` к панелям; `"skip_translation": true` для отмеченных SFX:

```json
{
  "project": "asterix_01",
  "panels": [
    {
      "panel_id": "001",
      "image_path": "panels/001.png",
      "bubbles": [
        {
          "bubble_id": "001_b1",
          "bbox": [10, 20, 100, 50],
          "raw_text": "We must leave!",
          "corrected_text": "We must leave!",
          "text_ru": "Мы должны уходить!",
          "type": "speech",
          "skip_translation": false
        }
      ],
      "visual_caption": "Two men in armor stand in a dark corridor...",
      "caption_ru": "Двое мужчин в доспехах стоят в тёмном коридоре..."
    }
  ]
}
```

#### Критерий успеха

- ✅ Массовый перевод работает за один батч-вызов
- ✅ Чекбоксы исключают строки из API-запроса
- ✅ Помеченные SFX остаются без перевода (копия оригинала)
- ✅ Итоговый JSON валиден

---

### STAGE 4: Story Understanding

**Назначение:** Анализ сюжета — персонажи, роли, ключевые события, эмоциональный тон, связи между панелями.

#### Вход

`stage_3.json` (или `stage_2b.json` если перевод не нужен).

**Важно:** промпт включает **и текст, и `visual_caption`** для каждой панели — модель не работает вслепую.

#### Технологии

| Модель | Ссылка | Роль | Оценка |
|---|---|---|---|
| **Qwen2.5-7B-Instruct** | [SiliconFlow](https://cloud.siliconflow.cn/models) | ECONOMY, FREE | ⭐⭐⭐ API, бесплатно |
| **Qwen3.5-122B-A10B** | [SiliconFlow](https://cloud.siliconflow.cn/models) | QUALITY, MoE, 256K контекст | ⭐⭐⭐⭐ API, ~$0.04/комикс |

#### UI вкладки «Stage 4: Анализ сюжета»

- **Слева:** сворачиваемый список панелей (`corrected_text` + `visual_caption`) — для контекста.
- **Справа:** форма с полями LLM-результата:
  - `Список персонажей` (теги, редактируемые)
  - `Краткий сюжет` (textarea)
  - `Ключевые события` (список с добавлением/удалением)
  - `Эмоциональный тон` (textarea)
- **Кнопка `[✅ Проверить JSON-схему]`:** запускает антигаллюцинационный чекер.

#### Антигаллюцинационный чекер

```python
from rapidfuzz import fuzz

def check_character_hallucinations(story_analysis: dict, panels: list[dict]) -> dict:
    """
    Помечает персонажей из story_analysis, имена которых
    не встречаются ни в corrected_text/text_ru, ни в visual_caption/caption_ru
    ни одной из панелей (с учётом алиасов и нечёткого сравнения).
    """
    source_text = " ".join(
        p.get("text_ru") or b["corrected_text"]
        for p in panels for b in p["bubbles"]
    ) + " ".join(p.get("caption_ru") or p["visual_caption"] for p in panels)
    
    source_lower = source_text.lower()
    
    for char in story_analysis["characters"]:
        names_to_check = [char["name"]] + char.get("aliases", [])
        found = any(
            fuzz.partial_ratio(name.lower(), source_lower) > 80
            for name in names_to_check
        )
        char["hallucinated"] = not found
    
    return story_analysis
```

Персонажи с `"hallucinated": true` подсвечиваются красной рамкой и значком ⚠️, с подсказкой «Имя не найдено в исходном тексте — проверьте или удалите».

#### Выходной JSON (`stage_4_story_analysis.json`)

```json
{
  "characters": [
    {
      "name": "Астерикс",
      "aliases": ["Asterix"],
      "role": "protagonist",
      "description": "Галл в крылатом шлеме",
      "hallucinated": false
    }
  ],
  "plot_summary": "...",
  "key_events": ["...", "..."],
  "emotional_tone": "..."
}
```

#### Критерий успеха

- ✅ LLM возвращает валидный JSON по схеме
- ✅ Ручное добавление/удаление персонажа работает и пересчитывает `hallucinated` при следующей проверке
- ✅ Персонаж, не упомянутый в исходных текстах, подсвечивается автоматически
- ✅ Промпт содержит **и текст, и visual_caption** — модель не работает вслепую

---

### STAGE 5: Script Generation

**Назначение:** Превратить анализ в покадровый сценарий для видео.

#### Вход

`stage_4_story_analysis.json` + `stage_3.json` (для контекста панелей).

#### Технологии

**Follow-up запрос** к той же модели, что в Stage 4 (для сохранения контекста и стиля).

#### UI вкладки «Stage 5: Сценарий»

- **Макет:** Список «Сцен» (карточки), каждая привязана к диапазону `panel_ids`.
- **Элементы сцены:**
  - `Текст рассказчика` (textarea)
  - `Диалоги`: динамический список строк:
    - Dropdown `[Персонаж]` (из Stage 4, включая голосовые профили из библиотеки)
    - Поле `[Текст реплики]`
    - Dropdown `[Эмоция]`: `neutral`, `angry`, `whisper`, `sad`, `happy`
  - `Оценочная длительность` (число, сек) — справочно; в Stage 7 пересчитывается по реальному аудио
- **Кнопки:**
  - `[+ Добавить реплику]`
  - `[🗑 Удалить]`

#### Выходной JSON (`stage_5_video_script.json`)

```json
{
  "scenes": [
    {
      "scene_id": "sc01",
      "panel_ids": ["001", "002"],
      "narrator_text": "...",
      "dialogues": [
        {
          "line_id": "sc01_d1",
          "character": "Астерикс",
          "text": "Мы должны уходить!",
          "emotion": "angry",
          "marked_text": null
        }
      ],
      "estimated_duration_s": 5.0
    }
  ]
}
```

`marked_text` — заполняется на Stage 6 после применения макросов/AI-волшебника.

#### Критерий успеха

- ✅ Динамическое добавление/удаление реплик в UI без перезагрузки
- ✅ Итоговый JSON строго соответствует схеме
- ✅ Follow-up сохраняет стиль/имена персонажей из Stage 4 без расхождений

---

### STAGE 6: Voice Synthesis (TTS) — Мини-студия озвучки

**Назначение:** Генерация аудио для каждой реплики/нарратора с предпрослушиванием, разметкой интонации и управлением голосами.

Это самый богатый по функционалу этап. Включает три подмодуля: **Макро-редактор** (§6.1), **AI-волшебник** (§6.2), **Voice Library** (§6.3).

#### Вход

`stage_5_video_script.json` + `stage_4_story_analysis.json` (для имён персонажей).

#### 6.1 Технологии TTS

| Модель | Ссылка | Роль | Оценка |
|---|---|---|---|
| **Edge TTS** | [GitHub: rany2/edge-tts](https://github.com/rany2/edge-tts) | Основной, бесплатный, отличные русские голоса | ⭐⭐⭐ Бесплатно, быстро |
| **CosyVoice2-0.5B** | [SiliconFlow](https://cloud.siliconflow.cn/models) | TTS с эмоциями и клонированием голоса (QUALITY) — **только через API** | ⭐⭐⭐⭐ API, ~$0.05/комикс |

⚠️ **Важно:** CosyVoice2 не имеет локального ONNX-экспорта. Локальный PyTorch-инференс требует ~8GB RAM при загрузке — рискованно на 16GB. Используется только через SiliconFlow API.

#### 6.2 DSL-макросы и SSML-трансляция

Простой DSL, парсится перед отправкой в Edge TTS / CosyVoice2 и транслируется в SSML.

| Макрос | SSML-результат | Кнопка тулбара |
|---|---|---|
| `[pause:0.5s]` | `<break time="500ms"/>` | ⏸ Пауза |
| `{whisper}...{/whisper}` | `<prosody volume="x-soft" rate="slow">...</prosody>` | 🤫 Шёпот |
| `{shout}...{/shout}` | `<prosody rate="fast" pitch="+20%">...</prosody>` | 📢 Крик |
| `{sad}...{/sad}` | `<prosody rate="slow" pitch="-10%">...</prosody>` | 😢 Грусть |
| `{happy}...{/happy}` | `<prosody rate="medium" pitch="+10%">...</prosody>` | 😊 Радость |
| `{slow}...{/slow}` | `<prosody rate="slow">...</prosody>` | 🐢 Медленно |
| `{fast}...{/fast}` | `<prosody rate="fast">...</prosody>` | ⚡ Быстро |
| `{emphasis}...{/emphasis}` | `<emphasis level="strong">...</emphasis>` | **B** Акцент |

**Ключевая механика:**
1. Пользователь **выделяет текст мышью** в textarea
2. Нажимает кнопку тулбара
3. JavaScript получает `window.getSelection()` → оборачивает выделение в макрос
4. Textarea обновляется

**Пример:**
```
Подожди... [pause:0.5s] {whisper}ты слышишь это?{/whisper} {shout}БЕГИ!{/shout}
```

**Таблица эмоция → макрос:**

| Эмоция (dropdown) | Автоматически применяемый макрос |
|---|---|
| `neutral` | без обёртки |
| `angry` | `{shout}...{/shout}` |
| `whisper` | `{whisper}...{/whisper}` |
| `sad` | `{sad}...{/sad}` |
| `happy` | `{happy}...{/happy}` |

При смене dropdown «Эмоция» — текст автоматически переоборачивается (с сохранением вложенных ручных макросов).

#### 6.3 AI-волшебник разметки TTS (двухуровневый)

Кнопка 🪄 рядом с каждой строкой в Stage 6. Открывает попап:

```
┌──────────────────────────────────────────────┐
│ Опишите тон/настроение свободно:              │
│ ┌────────────────────────────────────────────┐│
│ │ он нервничает, говорит тихо, оглядываясь    ││
│ └────────────────────────────────────────────┘│
│                                                │
│  Уровень: [⚡ Быстро (локально)] [🧠 Умно (облако)] │
│                                                │
│              [ Применить разметку ]           │
└──────────────────────────────────────────────┘
```

**Уровень 1 — локальный (по умолчанию, всегда доступен):**

| Модель | Ссылка | Роль | Оценка |
|---|---|---|---|
| **ruBERT-tiny2 emotion** | [HF: cointegrated/rubert-tiny2-cedr-emotion-detection](https://huggingface.co/cointegrated/rubert-tiny2-cedr-emotion-detection) | Классификация эмоции по свободному описанию (~29M, ONNX) | ⭐⭐⭐ CPU, миллисекунды |

Классы CEDR (`joy`, `sadness`, `surprise`, `fear`, `anger`, `neutral`) маппятся на макросы. Текст оборачивается в найденный макрос. Без интернета, без API-ключа, мгновенно.

**Уровень 2 — облачный/локальный LLM (опционально):**

Использует ту же провайдер-абстракцию, что и Stage 4/5. В попапе — два dropdown:
- **Провайдер:** `SiliconFlow` / `OpenRouter` / `Локальная модель (Ollama)`
- **Модель:** список из конфига + `llm_economy`/`llm_quality`

LLM получает: правила макросов + свободное описание + профиль персонажа из Voice Library → возвращает `marked_text`.

**Промпт-шаблон:**

```
Ты — редактор разметки для TTS. Доступные макросы: [pause:Xs], {whisper}, {shout},
{sad}, {happy}, {slow}, {fast}, {emphasis}.

Профиль персонажа: {character_style_description}
Примеры предыдущих реплик этого персонажа:
{example_lines}

Описание тона для текущей реплики: "{user_free_text}"
Текст реплики: "{original_text}"

Верни только текст реплики с применёнными макросами, без пояснений.
```

#### 6.4 UI вкладки «Stage 6: Мини-студия озвучки»

**Таблица строк сценария (нарратор + все диалоги):**

| Колонка | Содержимое |
|---|---|
| Сцена / Персонаж | sc01 / Астерикс |
| Текст | поле с макро-тулбаром |
| Голос | dropdown — голоса из Voice Library |
| Эмоция | dropdown (синхронизирован с Stage 5) |
| 🪄 AI-волшебник | кнопка — открывает попап разметки |
| ▶️ Прослушать | генерирует/кэширует и проигрывает превью |
| Статус | ⚪ не сгенерировано / 🟡 генерация / 🟢 готово |

**Toggle над таблицей:**
- `[ Текст сценария ]` / `[ Оригинальные реплики ]`
- Переключает источник текста между `dialogues[].text` (Stage 5, LLM-интерпретация) и `bubbles[].text_ru`/`corrected_text` (Stage 2a/3, дословный перевод).
- Переключение не теряет разметку — макросы применяются к выбранному источнику отдельно.

**Блок «Клонирование голоса» (если выбран CosyVoice2):**
- Поле загрузки `.wav` (3 сек)
- Поле «Текст референсного аудио» (обязательно — без него клонирование работает плохо)
- Кнопка `[Сохранить как пресет]` → создаёт запись в Voice Library

**Автосопоставление голосов** при первом открытии вкладки (через `voice_library.match`):
- Для каждого персонажа из Stage 4, у которого нет `voice_profile_id`:
  1. Поиск по точному совпадению `character_name` в библиотеке
  2. Если не найдено — fuzzy-поиск (`rapidfuzz`, порог > 75)
  3. Если найдено — предложение в UI: «Найден похожий голос: Астерикс (из проекта galls_01) — использовать?»
  4. Если не найдено — назначается дефолтный голос Edge TTS по полу/роли, помечается `"pending": true`

#### Выходные JSON

**`stage_6_video_script_audio.json`:**

```json
{
  "lines": [
    {
      "line_id": "sc01_d1",
      "marked_text": "{shout}Мы должны уходить![/shout]",
      "voice_profile_id": 42,
      "audio_file_path": "story_out/projects/asterix_01/audio/sc01_d1.wav",
      "actual_duration_ms": 1850
    }
  ]
}
```

**`stage_6_voice_assignments.json`:**

```json
{
  "Астерикс": {"voice_profile_id": 42, "project_overrides": {"default_macros": ["{fast}"]}},
  "Обеликс": {"voice_profile_id": null, "pending": true}
}
```

#### Критерий успеха

- ✅ Все реплики озвучены
- ✅ `actual_duration_ms` записан для каждой
- ✅ Смена toggle источника текста корректно подменяет содержимое без потери уже применённых макросов
- ✅ Автосопоставление голосов из библиотеки работает при наличии похожих профилей
- ✅ Клонирование голоса CosyVoice2 работает с reference text

---

### STAGE 7: Timing-Aware A/V Assembly & NLE Export

**Назначение:** Финальная сборка видео **ИЛИ** экспорт проекта для профессионального монтажа.

#### Вход

`stage_6_video_script_audio.json` + `stage_5_video_script.json` + папка `panels/`.

#### Технологии

| Инструмент | Ссылка | Роль |
|---|---|---|
| **pydub** / **ffprobe** | — | Измерение реальной длины аудио |
| **anim_pipeline.py** | существующий | Рендер панели с точной `--duration` |
| **opentimelineio** | [PyPI](https://pypi.org/project/OpenTimelineIO/) | Генерация FCPXML/EDL/OTIO для NLE |

#### Расчёт длительности панели

```python
длительность_панели = длина_аудио_нарратора
                     + сумма(длина_аудио_диалогов на этой панели)
                     + 0.5с (переход)
```

`estimated_duration_s` из Stage 5 **игнорируется** — используется только реальная длина аудио.

#### UI вкладки «Stage 7: Финальная сборка»

- **Radio:** `[ 🎬 Авто-рендер MP4 ]` / `[ 🎞 Экспорт в видеоредактор (NLE) ]`
- **Если NLE:** dropdown `DaVinci Resolve / Adobe Premiere / Final Cut Pro (все через FCPXML)` / `Любой NLE (EDL)`
- **Прогресс-бар, лог консоли, кнопка `[ 🚀 Запустить сборку ]`**

#### Логика NLE-экспорта (через OpenTimelineIO)

```python
import opentimelineio as otio

# Создаём таймлайн с треками:
timeline = otio.schema.Timeline(name="ComicSplit Project")
track_panels = otio.schema.Track(kind=otio.schema.TrackKind.Video)
track_narrator = otio.schema.Track(kind=otio.schema.TrackKind.Audio)
track_characters = otio.schema.Track(kind=otio.schema.TrackKind.Audio)

for scene in script["scenes"]:
    # Видеоклип
    video_clip = otio.schema.Clip(
        name=f"scene_{scene['scene_id']}",
        media_reference=otio.schema.ExternalReference(
            target_url=f"assets/sc{scene['scene_id']:02d}.mp4"
        ),
        source_range=otio.opentime.TimeRange(
            duration=otio.opentime.from_seconds(scene["actual_duration"])
        )
    )
    track_panels.append(video_clip)
    
    # Аудиоклипы нарратора и персонажей
    # ... (аналогично, с теми же временными диапазонами)

timeline.tracks.extend([track_panels, track_narrator, track_characters])

# Экспорт в три формата одной строкой:
otio.adapters.write_to_file(timeline, "project.fcpxml", adapter_name="fcp_xml")
otio.adapters.write_to_file(timeline, "project.edl", adapter_name="cmx_3600")
otio.adapters.write_to_file(timeline, "project.otio")
```

Все медиафайлы (панели MP4, аудио WAV) копируются в `nle_export/assets/` с плоской структурой имён (`sc01_p001.mp4`, `sc01_narrator.wav`, `sc01_d1_asterix.wav`), пути в OTIO — абсолютные к этой папке.

#### Выход

- **AUTO-режим:** `final_video.mp4` + `storyboard.mp4`
- **NLE-режим:** `nle_export/` (`project.fcpxml`, `project.edl`, `project.otio`, `assets/`)

#### Критерий успеха

- ✅ AUTO-режим выдаёт `final_video.mp4` с длительностями панелей, точно соответствующими сумме аудио
- ✅ NLE-режим — `project.fcpxml` импортируется в DaVinci Resolve без «offline media»
- ✅ Клипы на таймлайне имеют правильные длительности и совпадающий A/V таймкод

---

## Часть III. Специальные модули

### 3.1 Голосовая библиотека (Voice Library)

#### Назначение

Накопительная база голосов и характеров персонажей, переиспользуемая между проектами.

#### Хранение

**Глобальная SQLite-база:** `config/voice_library.db` (в `.gitignore`)

```sql
CREATE TABLE voice_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_name   TEXT NOT NULL,
    display_name     TEXT,
    tts_engine       TEXT NOT NULL,        -- 'edge_tts' | 'cosyvoice2_api'
    voice_id         TEXT,                  -- 'ru-RU-DmitryNeural'
    cloned_ref_audio TEXT,                  -- путь к .wav
    cloned_ref_text  TEXT,                  -- транскрипция референса
    default_macros   TEXT,                  -- JSON: ["{shout}", "{emphasis}"]
    style_description TEXT,                 -- "грубый, ворчливый старик"
    example_lines    TEXT,                  -- JSON: [{"text": "...", "marked_text": "..."}]
    tags             TEXT,                  -- JSON: ["villain", "comic_relief"]
    source_project   TEXT,                  -- проект, где профиль создан
    created_at       TEXT,
    last_used_at     TEXT,
    use_count         INTEGER DEFAULT 0
);
```

#### UI вкладки «🎙️ Voice Library»

- **Список профилей:** карточки (имя персонажа, движок, тег-чипы, ▶️ превью голоса, счётчик использований, дата последнего использования)
- **Поиск/фильтр:** по имени, тегам, движку
- **Действия на карточке:** `[Редактировать]`, `[Дублировать]`, `[Удалить]`, `[Использовать для персонажа →]`
- **Создание нового профиля:** форма с полями таблицы; для `cosyvoice2_api` — загрузка референс-аудио + текст референса

---

### 3.2 Sandbox → Pipeline импорт

#### Сценарий

Пользователь в режиме 🧪 Sandbox на вкладке Stage 2b обработал произвольные изображения, отредактировал описания, результат понравился.

#### Механизм

**Кнопка «📥 Импортировать в проект»** (видна только в Sandbox-режиме, после успешного экспорта):

**Модал выбора:**
- **Целевой проект:** dropdown (список из `story_out/projects/`)
- **Целевой этап:** предзаполнен по текущей вкладке, изменяемо
- **Сопоставление панелей:** если имена файлов в Sandbox совпадают с `panel_id` в целевом проекте — автосопоставление. Иначе — таблица ручного маппинга.

**Валидация:** результат проверяется по Pydantic-схеме целевого этапа.

**Подтверждение записи:**
- Если `stageN.json` целевого проекта существует — создаётся `.bak`-копия, затем merge (по `panel_id`: новые данные заменяют старые поля)
- Если не существует — создаётся новый файл

**Лог операции:** `story_out/projects/<project>/import_log.json` (источник, дата, какие панели затронуты)

#### Ограничения

- Импорт возможен только «вперёд по пайплайну или на тот же этап»
- Если целевой проект уже прошёл более поздние этапы — предупреждение: «Этапы 3–7 могут устареть. Пересчитать?»

---

## Часть IV. Roadmap реализации (R0-R7)

### Карта зависимостей

```
R0 Инфраструктура (config, providers, retry, sandbox-toggle)
  │
  ├─► R1 Stage 2a (YOLO bubble + EasyOCR + Konva-редактор)
  │     │
  │     ▼
  ├─► R2 Stage 2b (Florence-2 / Qwen-VL + grid UI)
  │     │
  │     ▼
  ├─► R3 Stage 3 (перевод, split-view)
  │     │
  │     ▼
  ├─► R4 Stage 4 (анализ сюжета + проверка галлюцинаций)
  │     │
  │     ▼
  ├─► R5 Stage 5 (сценарий, карточки сцен)
  │     │
  │     ▼
  ├─► R6a Voice Library (SQLite + UI) ──┐
  ├─► R6b Макро-редактор + SSML        ─┤
  ├─► R6c AI-волшебник (2 уровня)      ─┤
  │                                     ▼
  │                              R6 Stage 6 (студия озвучки)
  │                                     │
  │                                     ▼
  └────────────────────────────► R7 Stage 7 (OTIO сборка/экспорт)
```

---

### R0 — Инфраструктура (фундамент)

**Что входит:**
- `config/story_analyzer.yaml` + `.env` (провайдеры, retry, tts_wizard)
- Provider-абстракция (ABC-класс) с SiliconFlow + OpenRouter
- Retry-декоратор (`tenacity`) на всех вызовах API
- Индикатор статуса API (🟢🟡🔴⚪) — общий компонент UI
- Per-tab Sandbox/Pipeline toggle (баннер)
- Группировка вкладок: `📖 Story Analyzer ▾` + отдельная `🎙️ Voice Library`

**Success criteria:**
- ✅ `config/story_analyzer.yaml` загружается, `.env` читает ключ
- ✅ Тестовый вызов SiliconFlow с искусственным 429 → 3 retry с экспоненциальной задержкой
- ✅ Переключение Sandbox/Pipeline меняет источник чтения/записи файлов
- ✅ В навигации видна группа с 7 под-вкладками-заглушками

**Промпт для реализации:**

> Создай `config/story_analyzer.yaml` по структуре из §1.5 спеки v4.1, модуль `utils/story_providers.py` с ABC-классом `LLMProvider` (методы `chat()`, `vision_chat()`) и реализациями `SiliconFlowProvider`, `OpenRouterProvider`, обёрнутыми retry-декоратором `tenacity`. Добавь общий Gradio/HTML-компонент баннера Sandbox/Pipeline и группу навигации `📖 Story Analyzer ▾` с 7 под-вкладками-заглушками плюс отдельную вкладку `🎙️ Voice Library`.

---

### R1 — Stage 2a: Bubble Detection & Local OCR

**Backend:**
- Эндпоинт принимает путь к папке панелей
- `yolo_manga_int8.onnx` → bbox класса `1 = text_bubble` на каждой панели
- Кроп каждого bbox → EasyOCR → `raw_text`
- Сборка `stage_2a.json` по схеме из §II

**Frontend:**
- Konva-канвас с панелью + отрисовка bbox
- Клик по bbox → `contentEditable` поле с `corrected_text`
- Dropdown типа бабла
- Кнопки «Пропустить бабл» / «Добавить бабл вручную»

**Success criteria:**
- ✅ Загрузка папки с 5 панелями → `stage_2a.json` с bbox, `raw_text` и редактируемым `corrected_text`
- ✅ Ручное добавление бабла создаёт корректную запись

**Промпт для реализации:**

> Создай backend-эндпоинт `/api/story/stage_2a/process`, принимающий путь к папке панелей. Используй `yolo_manga_int8.onnx` (класс 1) для поиска баблов, кропни их и распознай через EasyOCR. Верни JSON по схеме `stage_2a.json`. На фронтенде (Konva) сделай отрисовку bbox поверх панели и inline-редактирование `corrected_text` по клику, плюс dropdown типа бабла и кнопки пропуска/добавления вручную.

---

### R2 — Stage 2b: Visual Captioning

**Backend:**
- Для каждой панели: вызов Florence-2 (локально, ONNX) ИЛИ Qwen2.5-VL-3B (SiliconFlow)
- Переключатель backend в конфиге
- Запись `visual_caption` → `stage_2b.json`

**Frontend:**
- Grid миниатюр (300px) панелей
- `textarea` с описанием под каждой миниатюрой
- Кнопка 🔄 «Перегенерировать» — повторный вызов, не сбрасывает остальные карточки

**Success criteria:**
- ✅ Обработка 5 панелей → `stage_2b.json` с непустым `visual_caption`
- ✅ Перегенерация одной карточки не трогает остальные
- ✅ Grid рендерится без лагов на 20+ панелях

**Промпт для реализации:**

> Создай backend-эндпоинт `/api/story/stage_2b/process`, который для каждой панели из `stage_2a.json` вызывает выбранный backend (Florence-2 ONNX локально или Qwen2.5-VL-3B через `SiliconFlowProvider`) с промптом "Describe the visual action, characters, expressions, and setting in this comic panel in 1-2 sentences. Ignore text.", сохраняет результат в `visual_caption`. На фронтенде — grid миниатюр 300px с textarea под каждой и кнопкой перегенерации для отдельной карточки без сброса остальных.

---

### R3 — Stage 3: Translation

**Backend:**
- Вызов Hunyuan-MT-7B через provider (с retry)
- Батч-перевод всех `corrected_text` + `visual_caption`, кроме помеченных `skip_translation: true`

**Frontend:**
- Split-view: оригинал слева (read-only), перевод справа (editable)
- Чекбокс «Не переводить (SFX/звук)» на каждом бабле
- Кнопка «Применить ко всем неотредактированным»

**Success criteria:**
- ✅ Перевод всех непомеченных строк работает за один батч-вызов
- ✅ Помеченные SFX остаются без перевода (копия оригинала)
- ✅ Итоговый `stage_3.json` валиден

**Промпт для реализации:**

> Создай эндпоинт `/api/story/stage_3/translate`, который батчем отправляет в Hunyuan-MT-7B (через `SiliconFlowProvider`) все `corrected_text`/`visual_caption` из `stage_2b.json`, кроме помеченных `skip_translation`. Запиши результаты в `text_ru`/`caption_ru` → `stage_3.json`. Фронтенд: split-view оригинал/перевод, чекбокс SFX на каждой строке, кнопка массового применения перевода к неотредактированным полям.

---

### R4 — Stage 4: Story Understanding

**Backend:**
- Промпт со всеми панелями (`text_ru` + `caption_ru`) → Qwen2.5-7B-Instruct (ECONOMY) или Qwen3.5-122B-A10B (QUALITY)
- Pydantic-схема для `stage_4_story_analysis.json`
- Функция `check_character_hallucinations()` из §II (rapidfuzz)

**Frontend:**
- Слева — список панелей (контекст), справа — форма результата
- Персонажи с `hallucinated: true` — красная рамка + ⚠️
- Кнопка «Проверить JSON-схему»

**Success criteria:**
- ✅ LLM возвращает валидный JSON по схеме
- ✅ Ручное добавление/удаление персонажа работает и пересчитывает `hallucinated`
- ✅ Персонаж, не упомянутый в исходных текстах, подсвечивается автоматически

**Промпт для реализации:**

> Реализуй эндпоинт `/api/story/stage_4/analyze`, который отправляет в LLM (модель выбирается между ECONOMY/QUALITY) промпт со всеми `text_ru` + `caption_ru` из `stage_3.json` и просит вернуть JSON по схеме `stage_4_story_analysis.json` (персонажи с алиасами, plot_summary, key_events, emotional_tone). После получения ответа примени `check_character_hallucinations()` (алгоритм из §II, `rapidfuzz.partial_ratio > 80`). На фронтенде — форма с тегами персонажей (красная рамка + ⚠️ для `hallucinated: true`), редактируемые списки событий, кнопка ручной валидации.

---

### R5 — Stage 5: Script Generation

**Backend:**
- Follow-up промпт к той же LLM-сессии что в R4
- Pydantic-схема `stage_5_video_script.json`

**Frontend:**
- Карточки сцен, привязанные к `panel_ids`
- На карточке: `narrator_text`, динамический список диалогов, `estimated_duration_s`
- Кнопки добавления/удаления реплик

**Success criteria:**
- ✅ Динамическое добавление/удаление диалогов в UI без перезагрузки
- ✅ Итоговый JSON строго соответствует схеме
- ✅ Follow-up сохраняет стиль/имена персонажей из Stage 4

**Промпт для реализации:**

> Реализуй эндпоинт `/api/story/stage_5/generate_script`, который делает follow-up запрос к той же модели/провайдеру, что использовался в Stage 4 (передай `story_analysis.json` как контекст), и просит сгенерировать `stage_5_video_script.json` по схеме (scenes[].narrator_text, dialogues[] с character/text/emotion, estimated_duration_s). На фронтенде — карточки сцен с динамическими списками диалогов (добавление/удаление строк), привязка к `panel_ids`.

---

### R6a — Voice Library (SQLite + UI)

**Backend:**
- Создание `config/voice_library.db` по схеме из §III.1
- CRUD-эндпоинты: `GET/POST/PUT/DELETE /api/voice_library/profiles`
- Эндпоинт автосопоставления: `POST /api/voice_library/match` (rapidfuzz, порог 75)

**Frontend:**
- Вкладка `🎙️ Voice Library`: карточки профилей с превью, тегами, поиском/фильтром
- Форма создания/редактирования профиля (с условными полями для `cosyvoice2_api`)
- Действия: редактировать / дублировать / удалить / «использовать для персонажа →»

**Success criteria:**
- ✅ Создание профиля сохраняется в SQLite и переживает перезапуск
- ✅ Поиск по тегам/имени работает
- ✅ `match`-эндпоинт находит профиль из другого проекта по похожему имени (порог 75)

**Промпт для реализации:**

> Создай SQLite-базу `config/voice_library.db` по схеме из §III.1 (таблица `voice_profiles`), модуль `utils/voice_library.py` с CRUD-функциями и эндпоинтом `match(character_name, aliases)` на `rapidfuzz.partial_ratio` (порог 75). Создай новую вкладку `🎙️ Voice Library` с карточками профилей (превью аудио, теги, поиск), формой создания/редактирования (включая поля референс-аудио и транскрипции для `cosyvoice2_api`) и кнопкой "Использовать для персонажа" с выбором проекта и персонажа.

---

### R6b — Макро-редактор текста для TTS

**Backend:**
- Парсер макросов из §6.2 → транслятор в SSML (функция `macros_to_ssml(text: str) -> str`)
- Таблица эмоция→макрос — применяется при смене dropdown «Эмоция»

**Frontend:**
- Тулбар кнопок над текстовым полем: выделение текста → оборачивание в макрос
- Визуальная подсветка примененных макросов в textarea
- При смене dropdown «Эмоция» — автооборачивание (с уважением к существующим ручным макросам)

**Success criteria:**
- ✅ Применение макроса к выделенному фрагменту корректно вкладывается
- ✅ `macros_to_ssml()` на тестовых строках даёт валидный SSML, который Edge TTS принимает без ошибок

**Промпт для реализации:**

> Реализуй функцию `macros_to_ssml(text: str) -> str`, транслирующую DSL-макросы из §6.2 (`[pause:Xs]`, `{whisper}`, `{shout}`, `{sad}`, `{happy}`, `{slow}`, `{fast}`, `{emphasis}`) в валидный SSML для `edge-tts`. Добавь на фронтенде тулбар кнопок над текстовым полем: выделение текста → оборачивание в выбранный макрос с проверкой корректной вложенности тегов. Реализуй автооборачивание текста при смене dropdown «Эмоция» по таблице из §6.2, сохраняя уже присутствующие ручные макросы.

---

### R6c — AI-волшебник разметки TTS (двухуровневый)

**Backend (Tier 1):**
- Экспорт `cointegrated/rubert-tiny2-cedr-emotion-detection` в ONNX INT8 → `models/story/rubert_tiny2_emotion_int8.onnx`
- Inference-функция: свободный текст → класс эмоции CEDR → макрос

**Backend (Tier 2):**
- Эндпоинт `/api/story/tts_wizard/mark`, принимает: `original_text`, `user_free_text`, `tier` (1|2), `voice_profile_id`
- При `tier=2`: использует provider/model из конфига, подставляет профиль из Voice Library

**Frontend:**
- Попап 🪄 на каждой строке Stage 6: textarea свободного описания + toggle Tier 1/Tier 2
- При Tier 2 — dropdown провайдера и модели
- Результат подставляется в текстовое поле реплики

**Success criteria:**
- ✅ Tier 1 работает offline и возвращает результат < 100мс
- ✅ Tier 2 корректно подставляет профиль персонажа и возвращает текст с валидными макросами
- ✅ Смена провайдера/модели в попапе не требует перезапуска приложения

**Промпт для реализации:**

> Экспортируй `cointegrated/rubert-tiny2-cedr-emotion-detection` в ONNX INT8, сохрани в `models/story/rubert_tiny2_emotion_int8.onnx`. Реализуй функцию `tier1_mark(free_text: str) -> str` — классификация CEDR → маппинг на макрос из §6.2 → обёртка `original_text`. Реализуй эндпоинт `/api/story/tts_wizard/mark` с `tier=2`, использующий провайдер/модель из конфига, промпт-шаблон из §6.3, подстановку `style_description`/`example_lines` из Voice Library по `voice_profile_id`. На фронтенде — попап 🪄 с textarea, toggle Tier 1/2 и dropdown провайдера/модели для Tier 2.

---

### R6 — Stage 6: Voice Synthesis (объединение R6a–R6c)

**Backend:**
- Эндпоинт `/api/story/stage_6/synthesize`: принимает `marked_text`, `voice_profile_id`, движок
- Генерация аудио → сохранение в `story_out/projects/<project>/audio/`
- Измерение `actual_duration_ms` через `pydub.AudioSegment`
- Обновление `stage_6_video_script_audio.json` и `stage_6_voice_assignments.json`

**Frontend:**
- Таблица строк сценария с колонками из §6.4
- Toggle «Текст сценария / Оригинальные реплики»
- Автосопоставление голосов при первом открытии вкладки
- Кнопка ▶️ «Прослушать» — генерация + проигрывание в `<audio>`

**Success criteria:**
- ✅ Все реплики озвучены
- ✅ `actual_duration_ms` записан для каждой
- ✅ Смена toggle источника текста корректно подменяет содержимое без потери уже применённых макросов
- ✅ Автосопоставление голосов из библиотеки работает при наличии похожих профилей

**Промпт для реализации:**

> Реализуй эндпоинт `/api/story/stage_6/synthesize`, принимающий `marked_text`, `voice_profile_id` и движок (`edge_tts` через `pip install edge-tts` или `cosyvoice2_api` через SiliconFlow с reference audio+text). Сохрани аудио в `story_out/projects/<project>/audio/`, измерь длительность через `pydub`, обнови `stage_6_video_script_audio.json`. На фронтенде — таблица строк сценария с колонками, toggle источника текста, и автосопоставление голосов при открытии вкладки через `/api/voice_library/match`.

---

### R7 — Stage 7: Timing-Aware A/V Assembly & NLE Export

**Backend:**
- Расчёт длительности панели по формуле из §II (нарратор + диалоги + 0.5с)
- Вызов `anim_pipeline.py` с точной `--duration` для каждой панели
- Режим AUTO: ffmpeg-сборка `final_video.mp4` + `storyboard.mp4`
- Режим NLE: построение `opentimelineio.schema.Timeline`, экспорт в `.fcpxml`/`.edl`/`.otio`, копирование ассетов в `nle_export/assets/`

**Frontend:**
- Radio: Авто-рендер MP4 / Экспорт NLE
- Если NLE: dropdown целевого формата
- Прогресс-бар, лог консоли, кнопка запуска

**Success criteria:**
- ✅ AUTO-режим выдаёт `final_video.mp4` с длительностями панелей, точно соответствующими сумме аудио
- ✅ NLE-режим — `project.fcpxml` импортируется в DaVinci Resolve без «offline media»

**Промпт для реализации:**

> Реализуй эндпоинт `/api/story/stage_7/assemble`. Сначала рассчитай длительность каждой панели по формуле (длина аудио нарратора + сумма длин аудио диалогов + 0.5с), используя `pydub`/`ffprobe` на файлах из `stage_6_video_script_audio.json`. Для режима AUTO — вызови `anim_pipeline.py` с этой `--duration` для каждой панели и собери `final_video.mp4` + `storyboard.mp4`. Для режима NLE — построй `opentimelineio.schema.Timeline` с треками Panels/Narrator/Characters, где `source_range` каждого клипа равен рассчитанной длительности, и экспортируй через `otio.adapters.write_to_file()` в `.fcpxml`, `.edl` и `.otio`, скопировав ассеты в `nle_export/assets/` с плоскими именами. На фронтенде — radio-выбор режима, dropdown формата NLE, прогресс-бар и лог.

---

### Итоговый порядок выполнения

```
R0 → R1 → R2 → R3 → R4 → R5 → (R6a, R6b, R6c параллельно) → R6 → R7
```

**R6a/R6b/R6c не зависят друг от друга** и от R1–R5 напрямую (кроме общего провайдера из R0) — можно разрабатывать в любом порядке или параллельно, но все три нужны для полноценного R6.

---

## Часть V. Сводные таблицы

### 5.1 Реестр моделей Story Analyzer

| Stage | Модель | Тип | Локально/API |
|---|---|---|---|
| 2a | YOLO Manga INT8 | Детекция баблов | Локально (ONNX CPU) |
| 2a | EasyOCR | OCR | Локально (CPU) |
| 2b | Florence-2-large | Visual captioning | Локально (ONNX CPU) — опция |
| 2b | Qwen2.5-VL-3B-Instruct | Visual captioning | API SiliconFlow — рекомендуется |
| 3 | Hunyuan-MT-7B | Перевод | API SiliconFlow (FREE) |
| 4/5 | Qwen2.5-7B-Instruct | Анализ/сценарий ECONOMY | API SiliconFlow (FREE) |
| 4/5 | Qwen3.5-122B-A10B | Анализ/сценарий QUALITY | API SiliconFlow |
| 6 | Edge TTS | TTS основной | API (бесплатный, MS Edge) |
| 6 | CosyVoice2-0.5B | TTS с клонированием | API SiliconFlow только |
| 5/6 (wizard) | ruBERT-tiny2 emotion | Классификация эмоций | Локально (ONNX CPU) |
| 5/6 (wizard) | Qwen2.5-7B-Instruct | AI-разметка TTS | API/локально, настраиваемо |
| 7 | OpenTimelineIO | Генерация NLE-проектов | Локально (pip) |

### 5.2 Оценка стоимости и производительности (100 страниц / ~500 панелей)

| Стратегия | Время | Стоимость | Качество |
|---|---|---|---|
| **ECONOMY** (всё бесплатное + AI-помощник rubert) | 40-60 мин | **$0** | ⭐⭐⭐⭐ |
| **QUALITY** (122B + CosyVoice + RAG-lite) | 15-25 мин | **~$0.15** | ⭐⭐⭐⭐⭐ |
| **MAXIMUM** (флагманские модели + MOSS-TTSD) | 10-15 мин | **~$0.50** | ⭐⭐⭐⭐⭐ |

### 5.3 Управление рисками

| Риск | Вероятность | Митигация |
|---|---|---|
| Rate limits SiliconFlow | Средняя | Tenacity retry + Semaphore(3) |
| Галлюцинации LLM в Stage 4 | Средняя | Антигаллюцинатор + валидация |
| Рассинхрон аудио/видео | Низкая | Stage 7 измеряет реальные `.mp3` через PyDub |
| CosyVoice2 без reference text | Высокая | Обязательное поле в UI + валидация |
| FCPXML невалиден | Низкая | OpenTimelineIO вместо Jinja2 |
| Локальный CosyVoice2 ONNX | Высокая | Удалён из спеки — только API |
| Путаница Pipeline/Sandbox/Standalone | Средняя | Изолированные папки + явный импорт |
| Потеря библиотеки голосов | Средняя | Регулярный бэкап `library.db` + экспорт в JSON |

---

## ✅ Резюме

Спецификация **v4.1** — финальная синергическая версия, объединяющая:

1. ✅ **Архитектурные принципы:** Tabbed UI, Pipeline/Sandbox/Standalone, JSON-контракты, HITL
2. ✅ **Автономность этапов:** каждый Stage описан полностью самодостаточно
3. ✅ **Технологический стек:** SiliconFlow API, Florence-2/Qwen-VL, Edge TTS/CosyVoice2, OpenTimelineIO
4. ✅ **Специальные модули:** Voice Library (SQLite), DSL-макросы, AI-волшебник (2 уровня)
5. ✅ **Roadmap R0-R7:** с промптами для реализации и критериями успеха
6. ✅ **Управление рисками:** retry, антигаллюцинация, валидация

**Рекомендуемый порядок реализации:**

| Неделя | Блок | Ключевые задачи |
|---|---|---|
| **1** | R0 + R1 | Инфраструктура + Stage 2a (OCR) |
| **2** | R2 + R3 | Stage 2b (Captioning) + Stage 3 (Translation) |
| **3** | R4 + R5 | Stage 4 (Story) + Stage 5 (Script) |
| **4** | R6a + R6b + R6c | Voice Library + DSL + AI-волшебник (параллельно) |
| **5** | R6 + R7 | Stage 6 (TTS Studio) + Stage 7 (Assembly/NLE) |

**Готовность к реализации:** 100%

---

**С какого блока начинаем?**
- **A.** R0 (Инфраструктура: config, providers, retry, UI-компоненты)
- **B.** R1 (Stage 2a: YOLO bubble + EasyOCR + Konva)
- **C.** R6a (Voice Library: SQLite + UI) — можно параллельно с R1
- **D.** Другой блок по вашему выбору

Жду команды 🚀
# Спецификация модуля Story Analyzer (v4.0)

**Версия документа:** 4.0
**Дата:** Июнь 2026
**Статус:** Готово к реализации (MVP)
**Целевое железо:** AMD Ryzen 5 5600H, 16 GB RAM, AMD Radeon iGPU (Vulkan), Windows 10/11, без CUDA
**Стратегия:** Гибридная (бесплатные облачные API + локальные ONNX/CPU инструменты)
**Связанные документы:** [ARCHITECTURE.md](ARCHITECTURE.md), [MODELS_SPECIFICATION.md](MODELS_SPECIFICATION.md), [STORY_ANALYZER_ROADMAP_v4.md](STORY_ANALYZER_ROADMAP_v4.md)

---

## Что нового в v4.0 относительно v3.0

| # | Изменение | Зачем |
|---|-----------|-------|
| 1 | Stage 7: `opentimelineio` вместо ручного Jinja2-шаблона FCPXML | Гарантированно валидный таймлайн, импорт без ошибок |
| 2 | Stage 6: поле reference text для клонирования голоса | CosyVoice2 без текста референса клонирует плохо |
| 3 | CosyVoice2 — только через API, без "локального ONNX" | Локального экспорта не существует; PyTorch на 16GB рискован |
| 4 | Везде, где есть облачный API: retry с exponential backoff | Бесплатные модели SiliconFlow имеют rate limit 5–20 RPM |
| 5 | Управление API-ключами: `config/story_analyzer.yaml` + `.env` | Раньше не было описано вообще |
| 6 | Stage 4: конкретный алгоритм проверки на галлюцинации персонажей | Раньше — просто "подсветка красным" без механизма |
| 7 | Группировка вкладок: `📖 Story Analyzer` как top-level с под-вкладками | 10 вкладок в одном ряду — плохой UX |
| 8 | **Новое:** Макро-редактор текста для TTS + таблица SSML | Кнопки разметки настроения/интонации |
| 9 | **Новое:** Двухуровневый AI-волшебник TTS-разметки (локальный + облачный, с переключением провайдера/модели) | Авто-разметка по свободному описанию |
| 10 | **Новое:** Глобальная библиотека голосовых профилей (SQLite) | Накопление и переиспользование голосов персонажей между проектами |
| 11 | **Новое:** Режим Sandbox / Pipeline на каждой вкладке + явный импорт из Sandbox в проект | Автономное использование вкладок без жёсткой привязки к пайплайну |
| 12 | Stage 6: toggle "текст сценария / оригинальные реплики" | Возможность озвучить дословный перевод вместо LLM-интерпретации |

---

## 1. Архитектурные принципы

### 1.1 Модульность и JSON-контракты

Каждый этап — автономный модуль:

```
Вход (JSON/Assets) → Обработка → Выход (Обновлённый JSON + Новые Assets)
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
├── stage_6_voice_assignments.json   # ссылки на voice_library.db
├── panels/                          # PNG из ComicSplit
├── audio/                           # WAV/MP3 из Stage 6
└── nle_export/                      # FCPXML/OTIO/EDL из Stage 7
```

### 1.2 Human-in-the-Loop (HITL)

Каждый этап = независимая вкладка интерфейса. Принимает JSON от предыдущего этапа, позволяет визуально редактировать данные, сохраняет валидный JSON для следующего этапа.

**Глобальные правила навигации (низ каждой вкладки):**

```
[ ← Назад ]   [ 💾 Сохранить и проверить JSON ]   [ Далее → ]
```

- «Сохранить» запускает Pydantic-валидацию выходного JSON по схеме этапа.
- При нарушении схемы — подсветка проблемных полей, переход блокируется.
- Промежуточные файлы позволяют перезапустить любой этап без потери данных выше по пайплайну.

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

`🎙️ Voice Library` — отдельная top-level вкладка (не часть пайплайна Story Analyzer), доступна всегда, независимо от текущего проекта. См. §6.

### 1.4 Режим Sandbox / Pipeline (per-tab)

Каждая Stage-вкладка имеет переключатель режима в верхнем баннере:

| Режим | Баннер | Источник/назначение данных |
|-------|--------|----------------------------|
| **Pipeline** (по умолчанию) | 🔗 `Проект: <project_name> / Stage N` | `story_out/projects/<project_name>/stageN.json`, строгая Pydantic-валидация |
| **Sandbox** | 🧪 `Песочница — результат не входит в пайплайн` | `story_out/sandbox/<stage_id>/<session_id>/`, валидация мягкая (предупреждения, не блокировки) |

**Почему per-tab, а не global:** Stage 6 (TTS-студия) и Stage 2b (Captioning) одинаково полезны как самостоятельные инструменты в любой момент. Stage 4/5/7 почти бессмысленны без остального пайплайна — но запрет на их Sandbox-режим не нужен, пусть пользователь решает.

**В Sandbox-режиме:**
- Загрузка произвольных файлов (любые PNG/JSON), не привязанных к конкретному проекту.
- Кнопка «💾 Сохранить и проверить JSON» превращается в «📤 Экспортировать результат» — скачивание файла, без блокировки перехода.
- Кнопка «Далее →» скрыта (нет следующего этапа в изоляции).

**Импорт результата Sandbox в проект** — см. §7.

---

## 2. Управление API-провайдерами и ключами

### 2.1 Конфигурация

`config/story_analyzer.yaml` (в репозитории, без ключей):

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

active_provider: siliconflow   # дефолт; каждый stage может переопределить

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

`.env` (в `.gitignore`):

```
SILICONFLOW_API_KEY=sk-xxxxxxxx
OPENROUTER_API_KEY=
```

### 2.2 Индикатор статуса API в UI

В каждой вкладке, использующей облачный API — иконка в углу:

| Иконка | Значение |
|--------|----------|
| 🟢 | Ключ найден, последний вызов успешен |
| 🟡 | Ключ найден, последний вызов — retry в процессе |
| 🔴 | Ключ отсутствует или последний вызов завершился ошибкой после всех retry |
| ⚪ | Локальный режим, API не используется |

Клик по иконке → модал с настройками провайдера/модели для этого этапа (переопределяет `active_provider` локально).

### 2.3 Retry-политика (обязательна для всех API-вызовов)

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

При батч-обработке (Stage 2b, Stage 4 по многим панелям) — прогресс-бар показывает текущий retry-статус: `Панель 12/50 (повтор 2/3, ожидание 8с)`.

---

## 3. Детальное описание этапов (Stages)

### STAGE 1: Local Preprocessing ✅ (уже реализовано)

- **Вход:** Страница комикса (JPG/PNG)
- **Процесс:** YOLO detection → reading order → crop → PNG
- **Выход:** `panels/panel_XXX.png` + `panels_metadata.json` (`panel_id`, `page`, `image_path`, `bbox`)
- **Источник:** `pipeline.py` (существующий ComicSplit)

---

### STAGE 2a: Bubble Detection & Local OCR

**Цель:** точное извлечение текста из баблов с возможностью ручной коррекции.

**Технологии:**

| Модель | Ссылка | Роль | Оценка |
|--------|--------|------|--------|
| YOLO Manga INT8 | [HF: leoxs22/manga-panel-detector-yolo26n](https://huggingface.co/leoxs22/manga-panel-detector-yolo26n) | Детекция баблов (класс `1 = text_bubble`), уже в проекте | ⭐⭐⭐ ONNX CPU, ~300мс/панель |
| EasyOCR | [GitHub: JaidedAI/EasyOCR](https://github.com/JaidedAI/EasyOCR) | OCR кропа бабла | ⭐⭐⭐ CPU, ~200мс/бабл |

**UI вкладки «Stage 2a: OCR Корректор»:**

- Центр: Canvas (Konva.js) с текущей панелью.
- Поверх изображения — bbox-прямоугольники вокруг баблов.
- Клик по bbox → `contentEditable` поле прямо на канвасе с распознанным текстом.
- Кнопки: `[Пропустить бабл]`, `[Добавить бабл вручную]`, `[Тип: speech/thought/sfx/narration]` (dropdown на каждом bbox).

**Выходной JSON (`stage_2a.json`):**

```json
{
  "project": "asterix_01",
  "panels": [{
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
  }]
}
```

**Критерий успеха:** JSON содержит `corrected_text` для всех баблов; UI редактирует текст без перезагрузки страницы.

---

### STAGE 2b: Visual Captioning

**Цель:** текстовое описание визуального ряда (действия, эмоции, фон) — то, чего нет в OCR.

**Технологии:**

| Модель | Ссылка | Роль | Оценка |
|--------|--------|------|--------|
| Florence-2-large (Local) | [HF: microsoft/Florence-2-large](https://huggingface.co/microsoft/Florence-2-large) | Локальный caption, task `DETAILED_CAPTION`, ~800MB | ⭐⭐ ONNX CPU, ~5–10с/панель |
| Qwen2.5-VL-3B-Instruct (Cloud) | [SiliconFlow](https://cloud.siliconflow.cn/models) | Облачный caption, быстрее и точнее | ⭐⭐⭐ API, ~1–2с/панель |

**Промпт:** *"Describe the visual action, characters, expressions, and setting in this comic panel in 1-2 sentences. Ignore text."*

**UI вкладки «Stage 2b: Визуальные описания»:**

- Сетка миниатюр панелей (300px), несколько рядов.
- Под каждой миниатюрой — `textarea` со сгенерированным описанием.
- Кнопка 🔄 `[Перегенерировать]` (тот же запрос с уточняющим промптом).
- Ручное редактирование текста.
- Для миниатюр — уменьшенные превью (не 1:1), сами PNG остаются в `panels/`.

**Выходной JSON (`stage_2b.json`):** добавляет `"visual_caption"` к каждой панели (наследует структуру `stage_2a.json`).

**Критерий успеха:** сетка без лагов; поле описания редактируемо; перегенерация не сбрасывает остальные данные.

---

### STAGE 3: Translation (опционально)

**Цель:** перевод реплик баблов и визуальных описаний на целевой язык.

**Технологии:**

| Модель | Ссылка | Роль | Оценка |
|--------|--------|------|--------|
| Hunyuan-MT-7B | [SiliconFlow: tencent/Hunyuan-MT-7B](https://cloud.siliconflow.cn/models) | Перевод, лидер WMT25, 33 языка, FREE | ⭐⭐⭐ API, бесплатно, 32K контекст |

**UI вкладки «Stage 3: Перевод»:**

- Split-view: слева оригинал (read-only), справа перевод (редактируемый).
- Чекбокс `[x] Не переводить (SFX/звук)` рядом с каждым баблом.
- Кнопка `[Применить ко всем неотредактированным]`.

**Выходной JSON (`stage_3.json`):** добавляет `"text_ru"` к баблам, `"caption_ru"` к панелям; `"skip_translation": true` для отмеченных SFX (текст копируется без перевода).

**Критерий успеха:** массовый перевод работает; чекбоксы исключают строки из API-запроса; JSON валиден.

---

### STAGE 4: Story Understanding

**Цель:** анализ сюжета — персонажи, роли, ключевые события, эмоциональный тон, связи между панелями.

**Технологии:**

| Модель | Ссылка | Роль | Оценка |
|--------|--------|------|--------|
| Qwen2.5-7B-Instruct | [SiliconFlow](https://cloud.siliconflow.cn/models) | ECONOMY, FREE | ⭐⭐⭐ API, бесплатно |
| Qwen3.5-122B-A10B | [SiliconFlow](https://cloud.siliconflow.cn/models) | QUALITY, MoE, 256K контекст | ⭐⭐⭐⭐ API, ~$0.04/комикс |

**Вход:** `stage_3.json` (или `stage_2b.json` если перевод не нужен) — промпт включает **и текст, и `visual_caption`** для каждой панели.

**UI вкладки «Stage 4: Анализ сюжета»:**

- Слева: сворачиваемый список панелей (`corrected_text` + `visual_caption`) — для контекста.
- Справа: форма с полями LLM-результата:
  - `Список персонажей` (теги, редактируемые)
  - `Краткий сюжет` (textarea)
  - `Ключевые события` (список с добавлением/удалением)
  - `Эмоциональный тон` (textarea)
- Кнопка `[ ✅ Проверить JSON-схему ]`.

**Алгоритм проверки на галлюцинации персонажей:**

```python
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

Используется `rapidfuzz` (лёгкая чистая Python-библиотека, без ML). В UI персонажи с `"hallucinated": true` подсвечиваются красной рамкой и значком ⚠️, с подсказкой «Имя не найдено в исходном тексте — проверьте или удалите».

**Выходной JSON (`stage_4_story_analysis.json`):**

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

**Критерий успеха:** LLM возвращает валидный JSON; ручное добавление/удаление персонажа работает; галлюцинации помечены автоматически.

---

### STAGE 5: Script Generation

**Цель:** превратить анализ в покадровый сценарий для видео.

**Технологии:** та же модель, что в Stage 4 (follow-up prompt, общий контекст и стиль).

**UI вкладки «Stage 5: Сценарий»:**

- Список «Сцен» (карточки), каждая привязана к диапазону `panel_ids`.
- На карточке:
  - `Текст рассказчика` (textarea)
  - `Диалоги` — динамический список строк: dropdown «Персонаж» (из Stage 4, включая голосовые профили из библиотеки — см. §6), поле «Текст реплики», dropdown «Эмоция» (`neutral`, `angry`, `whisper`, `sad`, `happy`)
  - Кнопки `[+ Добавить реплику]`, `[🗑 Удалить]`
  - `Оценочная длительность` (число, сек) — справочно; в Stage 7 пересчитывается по реальному аудио

**Выходной JSON (`stage_5_video_script.json`):**

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

`marked_text` — заполняется на Stage 6 после применения макросов/AI-волшебника (см. §5).

**Критерий успеха:** динамическое добавление/удаление реплик в UI; итоговый JSON строго соответствует схеме.

---

### STAGE 6: Voice Synthesis (TTS) — Мини-студия озвучки

**Цель:** генерация аудио для каждой реплики/нарратора с предпрослушиванием, разметкой интонации и управлением голосами.

**Технологии:**

| Модель | Ссылка | Роль | Оценка |
|--------|--------|------|--------|
| Edge TTS | [GitHub: rany2/edge-tts](https://github.com/rany2/edge-tts) | Основной, бесплатный, `pip install edge-tts`, отличные русские голоса (`ru-RU-DmitryNeural`, `ru-RU-SvetlanaNeural`) | ⭐⭐⭐ Бесплатно, быстро, требует интернет |
| CosyVoice2-0.5B (Cloud) | [SiliconFlow: FunAudioLLM/CosyVoice2-0.5B](https://cloud.siliconflow.cn/models) | TTS с эмоциями и клонированием голоса (QUALITY) — **только через API** | ⭐⭐⭐⭐ API, ~$0.05/комикс, 150ms latency |

> **Важно:** CosyVoice2 не имеет локального ONNX-экспорта. Локальный PyTorch-инференс требует ~8GB RAM при загрузке — рискованно на 16GB вместе с остальным пайплайном. Используется только через SiliconFlow API.

**UI вкладки «Stage 6: Мини-студия озвучки»** — таблица строк сценария (нарратор + все диалоги):

| Колонка | Содержимое |
|---------|-----------|
| Сцена / Персонаж | `sc01 / Астерикс` |
| Текст | поле с макро-тулбаром (см. §4) |
| Голос | dropdown — голоса из Voice Library (см. §6), с быстрым поиском по имени персонажа |
| Эмоция | dropdown (синхронизирован с Stage 5, можно менять здесь) |
| 🪄 AI-волшебник | кнопка — открывает попап разметки (см. §5) |
| ▶️ Прослушать | генерирует/кэширует и проигрывает превью |
| Статус | ⚪ не сгенерировано / 🟡 генерация / 🟢 готово |

**Toggle над таблицей:** `[ Текст сценария ]` / `[ Оригинальные реплики ]` — переключает источник текста между `dialogues[].text` (Stage 5, LLM-интерпретация) и `bubbles[].text_ru`/`corrected_text` (Stage 2a/3, дословный перевод). Переключение не теряет разметку — макросы применяются к выбранному источнику отдельно.

**Блок «Клонирование голоса»** (если выбран CosyVoice2):

- Поле загрузки `.wav` (3 сек)
- **Поле «Текст референсного аудио»** (обязательно — без него клонирование работает плохо)
- Кнопка `[Сохранить как пресет]` → создаёт запись в Voice Library (§6)

**Выходной JSON (`stage_6_video_script_audio.json`):** к каждой реплике добавляется:

```json
{
  "line_id": "sc01_d1",
  "marked_text": "{shout}Мы должны уходить![/shout]",
  "voice_profile_id": 42,
  "audio_file_path": "story_out/projects/asterix_01/audio/sc01_d1.wav",
  "actual_duration_ms": 1850
}
```

**Критерий успеха:** аудио генерируется и проигрывается без перезагрузки страницы; `actual_duration_ms` измерен через `pydub`; путь и длительность записаны в JSON.

---

### STAGE 7: Timing-Aware A/V Assembly & NLE Export

**Цель:** финальная сборка видео ИЛИ экспорт проекта для профессионального монтажа.

**Технологии:**

| Инструмент | Ссылка | Роль |
|-----------|--------|------|
| `pydub` / `ffprobe` | — | Измерение реальной длины аудио |
| `anim_pipeline.py` | существующий | Рендер панели с точной `--duration` |
| `opentimelineio` | [PyPI: OpenTimelineIO](https://pypi.org/project/OpenTimelineIO/) | Генерация FCPXML/EDL/OTIO для NLE |

**Расчёт длительности панели:**

```
длительность_панели = длина_аудио_нарратора
                     + сумма(длина_аудио_диалогов на этой панели)
                     + 0.5с (переход)
```

`estimated_duration_s` из Stage 5 **игнорируется** — используется только реальная длина аудио.

**UI вкладки «Stage 7: Финальная сборка»:**

- Radio: `[ 🎬 Авто-рендер MP4 ]` / `[ 🎞 Экспорт в видеоредактор (NLE) ]`
- Если NLE: dropdown `DaVinci Resolve / Adobe Premiere / Final Cut Pro (все через FCPXML)` / `Любой NLE (EDL)`
- Прогресс-бар, лог консоли, кнопка `[ 🚀 Запустить сборку ]`

**Логика NLE-экспорта (через OTIO):**

1. Создаётся таймлайн `opentimelineio.schema.Timeline` с треками: `Panels` (видео), `Narrator` (аудио), `Characters` (аудио).
2. Для каждой сцены/панели: видеоклип = MP4 из `anim_pipeline.py` с `source_range`, равным `actual_duration_ms` соответствующего аудио.
3. Аудиоклипы нарратора и персонажей размещаются на параллельных аудиотреках с теми же временными диапазонами.
4. Экспорт:
   ```python
   otio.adapters.write_to_file(timeline, "project.fcpxml", adapter_name="fcp_xml")
   otio.adapters.write_to_file(timeline, "project.edl",   adapter_name="cmx_3600")
   otio.adapters.write_to_file(timeline, "project.otio")
   ```
5. Все медиафайлы (панели MP4, аудио WAV) копируются в `nle_export/assets/` с плоской структурой имён (`sc01_p001.mp4`, `sc01_narrator.wav`, `sc01_d1_asterix.wav`), пути в OTIO — абсолютные к этой папке.

**Выход:** `final_video.mp4` + `storyboard.mp4` **ИЛИ** `nle_export/` (`project.fcpxml`, `project.edl`, `project.otio`, `assets/`).

**Критерий успеха:** `project.fcpxml` импортируется в DaVinci Resolve без ошибок «offline media»; все клипы на таймлайне с правильными длительностями и синхронизацией A/V.

---

## 4. Макро-редактор текста для TTS

### 4.1 Синтаксис макросов

Простой DSL, парсится перед отправкой в Edge TTS / CosyVoice2 и транслируется в SSML.

| Макрос | SSML-результат | Кнопка тулбара |
|--------|----------------|----------------|
| `[pause:0.5s]` | `<break time="500ms"/>` | ⏸ Пауза |
| `{whisper}...{/whisper}` | `<prosody volume="x-soft" rate="slow">...</prosody>` | 🤫 Шёпот |
| `{shout}...{/shout}` | `<prosody rate="fast" pitch="+20%">...</prosody>` | 📢 Крик |
| `{sad}...{/sad}` | `<prosody rate="slow" pitch="-10%">...</prosody>` | 😢 Грусть |
| `{happy}...{/happy}` | `<prosody rate="medium" pitch="+10%">...</prosody>` | 😊 Радость |
| `{slow}...{/slow}` | `<prosody rate="slow">...</prosody>` | 🐢 Медленно |
| `{fast}...{/fast}` | `<prosody rate="fast">...</prosody>` | ⚡ Быстро |
| `{emphasis}...{/emphasis}` | `<emphasis level="strong">...</emphasis>` | **B** Акцент |

> **Примечание по Edge TTS:** `edge-tts` поддерживает ограниченное подмножество SSML — `prosody` (rate/pitch/volume) и `break` работают надёжно; `emphasis` поддерживается частично и может игнорироваться некоторыми голосами. Для CosyVoice2 (через SiliconFlow API) проверяется отдельно при подключении — таблица единая, но рантайм-применимость помечается в UI значком ⚠️ при выборе Edge TTS как движка.

### 4.2 Тулбар над текстовым полем

Выделяешь фрагмент текста → жмёшь кнопку макроса → текст оборачивается в соответствующие теги. Аналог панели Markdown-разметки, но для голоса. Доступен на Stage 5 (по желанию) и обязателен на Stage 6.

### 4.3 Таблица эмоция → макрос (для синхронизации с dropdown «Эмоция» из Stage 5/6)

| Эмоция (dropdown) | Автоматически применяемый макрос |
|--------------------|-----------------------------------|
| `neutral` | без обёртки |
| `angry` | `{shout}...{/shout}` |
| `whisper` | `{whisper}...{/whisper}` |
| `sad` | `{sad}...{/sad}` |
| `happy` | `{happy}...{/happy}` |

При смене dropdown «Эмоция» в Stage 6 — текст автоматически переоборачивается (с сохранением вложенных ручных макросов, если есть).

---

## 5. AI-волшебник разметки TTS (двухуровневый)

### 5.1 Концепция

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

### 5.2 Уровень 1 — локальный (по умолчанию, всегда доступен)

| Модель | Ссылка | Роль | Оценка |
|--------|--------|------|--------|
| ruBERT-tiny2 emotion | [HF: cointegrated/rubert-tiny2-cedr-emotion-detection](https://huggingface.co/cointegrated/rubert-tiny2-cedr-emotion-detection) | Классификация эмоции по свободному описанию (~29M, ONNX) | ⭐⭐⭐ CPU, миллисекунды |

Классы CEDR (`joy`, `sadness`, `surprise`, `fear`, `anger`, `neutral`) маппятся на макросы из §4.3 (приблизительное соответствие: `fear`→`whisper`, `surprise`→`happy` или `shout` по интенсивности, `anger`→`shout`). Текст оборачивается в найденный макрос. Без интернета, без API-ключа, мгновенно.

### 5.3 Уровень 2 — облачный/локальный LLM (опционально, переключаемо)

Использует ту же провайдер-абстракцию, что и Stage 4/5. В попапе — два dropdown:

- **Провайдер:** `SiliconFlow` / `OpenRouter` / `Локальная модель (Ollama)`
- **Модель:** список из `config/story_analyzer.yaml → providers.<provider>.models` + дополнительно `llm_economy`/`llm_quality`

LLM получает: правила макросов (§4.1) + свободное описание пользователя + **профиль персонажа из Voice Library** (если назначен — стиль, примеры прошлых реплик, см. §6) → возвращает `marked_text`.

**Промпт-шаблон (упрощённо):**

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

### 5.4 Конфигурация (фрагмент `config/story_analyzer.yaml`, см. §2.1)

```yaml
tts_wizard:
  tier1:
    enabled: true
    model_path: "models/story/rubert_tiny2_emotion_int8.onnx"
  tier2:
    enabled: true
    provider: siliconflow
    model: "Qwen/Qwen2.5-7B-Instruct"
```

Если `tier2.enabled: false` — кнопка «🧠 Умно (облако)» скрыта, доступен только Tier 1.

---

## 6. Библиотека голосовых профилей (Voice Library)

### 6.1 Назначение

Накопительная база голосов и характеров персонажей, переиспользуемая между проектами (разными комиксами). При появлении нового персонажа в новом проекте — система предлагает похожие профили из библиотеки (по имени, тегам, стилю).

### 6.2 Хранение

**Глобальная SQLite-база** — `config/voice_library.db` (в `.gitignore`, личные данные пользователя; шаблон пустой базы — в репозитории как `config/voice_library.template.db`).

```sql
CREATE TABLE voice_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_name   TEXT NOT NULL,
    display_name     TEXT,
    tts_engine       TEXT NOT NULL,        -- 'edge_tts' | 'cosyvoice2_api'
    voice_id         TEXT,                  -- 'ru-RU-DmitryNeural' и т.п.
    cloned_ref_audio TEXT,                  -- путь к .wav (для cosyvoice2_api)
    cloned_ref_text  TEXT,                  -- транскрипция референса
    default_macros   TEXT,                  -- JSON: ["{shout}", "{emphasis}"]
    style_description TEXT,                 -- "грубый, ворчливый старик"
    example_lines    TEXT,                  -- JSON: [{"text":"...", "marked_text":"..."}]
    tags             TEXT,                  -- JSON: ["villain", "comic_relief"]
    source_project   TEXT,                  -- проект, где профиль создан
    created_at       TEXT,
    last_used_at     TEXT,
    use_count         INTEGER DEFAULT 0
);
```

**Связь с проектом:** `story_out/projects/<project>/stage_6_voice_assignments.json`:

```json
{
  "Астерикс": { "voice_profile_id": 42, "project_overrides": { "default_macros": ["{fast}"] } },
  "Обеликс":  { "voice_profile_id": null, "pending": true }
}
```

`project_overrides` — локальные правки для конкретного комикса без изменения глобального профиля (например, в этой истории персонаж более уставший).

### 6.3 UI вкладки «🎙️ Voice Library»

- **Список профилей** — карточки: имя персонажа, движок (Edge TTS / CosyVoice2), тег-чипы, ▶️ превью голоса (короткая фраза «Привет, я ...»), счётчик использований, дата последнего использования.
- **Поиск/фильтр:** по имени, тегам, движку.
- **Действия на карточке:** `[Редактировать]`, `[Дублировать]`, `[Удалить]`, `[Использовать для персонажа →]` (открывает селектор: текущий проект → персонаж).
- **Создание нового профиля:** форма с полями таблицы из §6.2; для `cosyvoice2_api` — загрузка референс-аудио + текст референса (обязательно).

### 6.4 Автоматическое сопоставление при первом запуске Stage 6

Для каждого персонажа из `stage_4_story_analysis.json`, у которого нет `voice_profile_id`:

1. Поиск по точному совпадению `character_name` в библиотеке.
2. Если не найдено — fuzzy-поиск (`rapidfuzz`, порог > 75) по имени и алиасам.
3. Если найдено — предложение в UI: «Найден похожий голос: *Астерикс (из проекта galls_01)* — использовать?» с кнопками `[Да]` / `[Создать новый]`.
4. Если не найдено совсем — назначается дефолтный голос Edge TTS по полу/роли (грубая heuristic по `role` из Stage 4: `protagonist`→`ru-RU-DmitryNeural`, и т.п.), помечается `"pending": true` для ручной проверки.

---

## 7. Импорт результата Sandbox в проект

### 7.1 Сценарий

Пользователь в режиме 🧪 Sandbox на вкладке Stage 2b обработал произвольные изображения, отредактировал описания, результат понравился.

### 7.2 Механизм

Кнопка **«📥 Импортировать в проект»** (видна только в Sandbox-режиме, после успешного экспорта):

1. **Модал выбора:**
   - `Целевой проект:` dropdown (список из `story_out/projects/`)
   - `Целевой этап:` предзаполнен по текущей вкладке (Stage 2b), изменяемо
2. **Сопоставление панелей:** если имена файлов в Sandbox (`panel_017.png`) совпадают с `panel_id` в `stage_2a.json` целевого проекта — автосопоставление. Иначе — таблица ручного маппинга `sandbox_file → target_panel_id` (или опция «Добавить как новые панели»).
3. **Валидация:** результат проверяется по Pydantic-схеме целевого этапа (та же, что в Pipeline-режиме).
4. **Подтверждение записи:**
   - Если `stageN.json` целевого проекта существует — создаётся `.bak`-копия, затем merge (по `panel_id`: новые данные заменяют старые поля, остальное сохраняется).
   - Если не существует — создаётся новый файл.
5. Лог операции пишется в `story_out/projects/<project>/import_log.json` (источник, дата, какие панели затронуты) — для отладки и возможного ручного откатa через `.bak`.

### 7.3 Ограничения

- Импорт возможен только «вперёд по пайплайну или на тот же этап» (нельзя импортировать в Stage 2a результат, рассчитанный для Stage 5 — типы данных не совпадут, схема отклонит).
- Если целевой проект уже прошёл более поздние этапы (например, есть `stage_5_video_script.json`), импорт в `stage_2b.json` — с предупреждением: «Этапы 3–7 могут устареть относительно новых данных. Пересчитать?» с кнопкой быстрого перехода на Stage 3.

---

## 8. Сводный реестр моделей Story Analyzer

| Stage | Модель | Тип | Локально/API |
|-------|--------|-----|---------------|
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
| 5/6 (wizard) | Qwen2.5-7B-Instruct (повторно) | AI-разметка TTS | API/локально, настраиваемо |
| 7 | OpenTimelineIO | Генерация NLE-проектов | Локально (pip) |

---

## 9. Зависимости (добавить в `requirements.txt`)

```
edge-tts
easyocr
pydub
opentimelineio
rapidfuzz
tenacity
# опционально, если включён локальный Florence-2:
# transformers (только для экспорта в ONNX, инференс — onnxruntime)
```

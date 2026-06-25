# Story Analyzer — Roadmap реализации (v4.0)

**Связано:** [STORY_ANALYZER_SPEC_v4.md](STORY_ANALYZER_SPEC_v4.md)

> **⚠️ R1 Stage 2a OCR:** фактическая реализация — SiliconFlow VLM, не EasyOCR. Оперативный roadmap: [../../problems_fix/bubbles_detect_problems/ROADMAP_STAGE_2A.md](../../problems_fix/bubbles_detect_problems/ROADMAP_STAGE_2A.md) · канон: [../../STORY_ANALYZER_STAGE_2A.md](../../STORY_ANALYZER_STAGE_2A.md)

**Принцип:** каждый блок — минимальный самодостаточный шаг с явным критерием успеха и промптом для реализации. Порядок учитывает зависимости (инфраструктура → контент-стейджи → TTS-блок → сборка).

---

## Карта зависимостей

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
  │                              R6 Stage 6 (студия озвучки, объединяет R6a-c)
  │                                     │
  │                                     ▼
  └────────────────────────────► R7 Stage 7 (OTIO сборка/экспорт)
```

---

## R0 — Инфраструктура (фундамент)

**Что входит:**
- `config/story_analyzer.yaml` + `.env` (провайдеры, retry, tts_wizard)
- Provider-абстракция (ABC-класс из v2.0) с SiliconFlow + OpenRouter
- Retry-декоратор (`tenacity`) на всех вызовах API
- Индикатор статуса API (🟢🟡🔴⚪) — общий компонент UI
- Per-tab Sandbox/Pipeline toggle (баннер) — общий компонент, переиспользуется во всех Stage-вкладках
- Группировка вкладок: `📖 Story Analyzer ▾` с под-навигацией + отдельная `🎙️ Voice Library`

**Success criteria:**
- `config/story_analyzer.yaml` загружается, `.env` читает ключ из переменной окружения.
- Тестовый вызов SiliconFlow с искусственным 429 → 3 retry с экспоненциальной задержкой, видны в логе.
- Переключение Sandbox/Pipeline на любой будущей вкладке меняет источник чтения/записи файлов (можно проверить на заглушке).
- В навигации видна группа `📖 Story Analyzer` с 7 пустыми под-вкладками-заглушками + отдельная вкладка `🎙️ Voice Library`.

**Промпт для реализации:**
> «Создай `config/story_analyzer.yaml` по структуре из §2.1 спеки v4.0, модуль `utils/story_providers.py` с ABC-классом `LLMProvider` (методы `chat()`, `vision_chat()`) и реализациями `SiliconFlowProvider`, `OpenRouterProvider`, обёрнутыми retry-декоратором `tenacity` с параметрами из конфига. Добавь общий Gradio/HTML-компонент баннера Sandbox/Pipeline для вкладок и группу навигации `📖 Story Analyzer ▾` с 7 под-вкладками-заглушками плюс отдельную вкладку `🎙️ Voice Library`.»

---

## R1 — Stage 2a: Bubble Detection & Local OCR

**Backend:**
- Эндпоинт принимает путь к папке панелей.
- `yolo_manga_int8.onnx` → bbox класса `1 = text_bubble` на каждой панели.
- Кроп каждого bbox → EasyOCR → `raw_text`.
- Сборка `stage_2a.json` по схеме из спеки (§3, Stage 2a).

**Frontend:**
- Konva-канвас с панелью + отрисовка bbox.
- Клик по bbox → `contentEditable` поле с `corrected_text`.
- Dropdown типа бабла (`speech`/`thought`/`sfx`/`narration`).
- Кнопки «Пропустить бабл» / «Добавить бабл вручную».

**Success criteria:** загрузка папки с 5 панелями → `stage_2a.json` с bbox, `raw_text` и редактируемым `corrected_text` для каждого бабла; ручное добавление бабла создаёт корректную запись.

**Промпт для реализации:**
> «Создай backend-эндпоинт `/api/story/stage_2a/process`, принимающий путь к папке панелей. Используй `yolo_manga_int8.onnx` (класс 1) для поиска баблов, кропни их и распознай через EasyOCR. Верни JSON по схеме `stage_2a.json` из спеки v4.0 §3. На фронтенде (Konva) сделай отрисовку bbox поверх панели и inline-редактирование `corrected_text` по клику, плюс dropdown типа бабла и кнопки пропуска/добавления вручную.»

---

## R2 — Stage 2b: Visual Captioning

**Backend:**
- Для каждой панели: вызов Florence-2 (локально, ONNX) ИЛИ Qwen2.5-VL-3B (SiliconFlow, через provider из R0) с промптом из спеки.
- Переключатель backend в конфиге (`config_animate.yaml` или `story_analyzer.yaml`).
- Запись `visual_caption` → `stage_2b.json`.

**Frontend:**
- Grid миниатюр (300px) панелей.
- `textarea` с описанием под каждой миниатюрой.
- Кнопка 🔄 «Перегенерировать» — повторный вызов с уточняющим промптом, не сбрасывает остальные карточки.

**Success criteria:** обработка 5 панелей → `stage_2b.json` с непустым `visual_caption` для каждой; перегенерация одной карточки не трогает остальные; grid рендерится без лагов на 20+ панелях.

**Промпт для реализации:**
> «Создай backend-эндпоинт `/api/story/stage_2b/process`, который для каждой панели из `stage_2a.json` вызывает выбранный backend (Florence-2 ONNX локально или Qwen2.5-VL-3B через `SiliconFlowProvider` из R0) с промптом `"Describe the visual action, characters, expressions, and setting in this comic panel in 1-2 sentences. Ignore text."`, сохраняет результат в `visual_caption`. На фронтенде — grid миниатюр 300px с textarea под каждой и кнопкой перегенерации для отдельной карточки без сброса остальных.»

---

## R3 — Stage 3: Translation

**Backend:**
- Вызов Hunyuan-MT-7B через provider (с retry из R0).
- Батч-перевод всех `corrected_text` + `visual_caption`, кроме помеченных `skip_translation: true`.

**Frontend:**
- Split-view: оригинал слева (read-only), перевод справа (editable).
- Чекбокс «Не переводить (SFX/звук)» на каждом бабле.
- Кнопка «Применить ко всем неотредактированным».

**Success criteria:** перевод всех непомеченных строк работает за один батч-вызов (или с пагинацией при больших объёмах); помеченные SFX остаются без перевода в `text_ru` (копия оригинала); итоговый `stage_3.json` валиден.

**Промпт для реализации:**
> «Создай эндпоинт `/api/story/stage_3/translate`, который батчем отправляет в Hunyuan-MT-7B (через `SiliconFlowProvider`) все `corrected_text`/`visual_caption` из `stage_2b.json`, кроме помеченных `skip_translation`. Запиши результаты в `text_ru`/`caption_ru` → `stage_3.json`. Фронтенд: split-view оригинал/перевод, чекбокс SFX на каждой строке, кнопка массового применения перевода к неотредактированным полям.»

---

## R4 — Stage 4: Story Understanding

**Backend:**
- Промпт со всеми панелями (`text_ru` + `caption_ru`) → Qwen2.5-7B-Instruct (ECONOMY) или Qwen3.5-122B-A10B (QUALITY), выбор модели в UI.
- Pydantic-схема для `stage_4_story_analysis.json`.
- Функция `check_character_hallucinations()` из спеки §3 (Stage 4) — `rapidfuzz`.

**Frontend:**
- Слева — список панелей (контекст), справа — форма результата (персонажи-теги, сюжет, события).
- Персонажи с `hallucinated: true` — красная рамка + ⚠️ с подсказкой.
- Кнопка «Проверить JSON-схему».

**Success criteria:** LLM возвращает валидный JSON по схеме; ручное добавление/удаление персонажа работает и пересчитывает `hallucinated` при следующей проверке; персонаж, не упомянутый в исходных текстах, подсвечивается автоматически.

**Промпт для реализации:**
> «Реализуй эндпоинт `/api/story/stage_4/analyze`, который отправляет в LLM (модель выбирается между ECONOMY/QUALITY) промпт со всеми `text_ru` + `caption_ru` из `stage_3.json` и просит вернуть JSON по схеме `stage_4_story_analysis.json` (персонажи с алиасами, plot_summary, key_events, emotional_tone). После получения ответа примени `check_character_hallucinations()` (алгоритм из спеки v4.0 §3, `rapidfuzz.partial_ratio > 80`). На фронтенде — форма с тегами персонажей (красная рамка + ⚠️ для `hallucinated: true`), редактируемые списки событий, кнопка ручной валидации.»

---

## R5 — Stage 5: Script Generation

**Backend:**
- Follow-up промпт к той же LLM-сессии что в R4 (тот же провайдер/модель для консистентности стиля).
- Pydantic-схема `stage_5_video_script.json`.

**Frontend:**
- Карточки сцен, привязанные к `panel_ids`.
- На карточке: `narrator_text`, динамический список диалогов (персонаж/текст/эмоция), `estimated_duration_s`.
- Кнопки добавления/удаления реплик.
- (Опционально) макро-тулбар из R6b, если уже реализован — иначе просто текстовые поля.

**Success criteria:** динамическое добавление/удаление диалогов в UI без перезагрузки; итоговый `stage_5_video_script.json` строго соответствует схеме; follow-up сохраняет стиль/имена персонажей из Stage 4 без расхождений.

**Промпт для реализации:**
> «Реализуй эндпоинт `/api/story/stage_5/generate_script`, который делает follow-up запрос к той же модели/провайдеру, что использовался в Stage 4 (передай `story_analysis.json` как контекст), и просит сгенерировать `stage_5_video_script.json` по схеме из спеки v4.0 (`scenes[].narrator_text`, `dialogues[]` с `character`/`text`/`emotion`, `estimated_duration_s`). На фронтенде — карточки сцен с динамическими списками диалогов (добавление/удаление строк), привязка к `panel_ids`.»

---

## R6a — Voice Library (SQLite + UI)

**Backend:**
- Создание `config/voice_library.db` по схеме §6.2 (миграция/инициализация при первом запуске).
- CRUD-эндпоинты: `GET/POST/PUT/DELETE /api/voice_library/profiles`.
- Эндпоинт автосопоставления: `POST /api/voice_library/match` (принимает имя персонажа + алиасы, возвращает кандидатов через `rapidfuzz`).

**Frontend:**
- Вкладка `🎙️ Voice Library`: карточки профилей с превью (▶️), тегами, поиском/фильтром.
- Форма создания/редактирования профиля (с условными полями для `cosyvoice2_api`: референс-аудио + текст).
- Действия: редактировать / дублировать / удалить / «использовать для персонажа →» (селектор проект+персонаж).

**Success criteria:** создание профиля сохраняется в SQLite и переживает перезапуск приложения; поиск по тегам/имени работает; `match`-эндпоинт находит профиль из другого проекта по похожему имени персонажа (порог 75).

**Промпт для реализации:**
> «Создай SQLite-базу `config/voice_library.db` по схеме из спеки v4.0 §6.2 (таблица `voice_profiles`), модуль `utils/voice_library.py` с CRUD-функциями и эндпоинтом `match(character_name, aliases)` на `rapidfuzz.partial_ratio` (порог 75). Создай новую вкладку `🎙️ Voice Library` с карточками профилей (превью аудио, теги, поиск), формой создания/редактирования (включая поля референс-аудио и транскрипции для `cosyvoice2_api`) и кнопкой "Использовать для персонажа" с выбором проекта и персонажа.»

---

## R6b — Макро-редактор текста для TTS

**Backend:**
- Парсер макросов из §4.1 → транслятор в SSML (функция `macros_to_ssml(text: str) -> str`).
- Таблица эмоция→макрос из §4.3 — применяется при смене dropdown «Эмоция».

**Frontend:**
- Тулбар кнопок над текстовым полем (Stage 5 опционально, Stage 6 обязательно): выделение текста → оборачивание в макрос.
- Визуальная подсветка примененных макросов в textarea (например, цветные скобки или badge).
- При смене dropdown «Эмоция» — автооборачивание (с уважением к существующим ручным макросам).

**Success criteria:** применение макроса к выделенному фрагменту корректно вкладывается (не разрывает существующие теги); `macros_to_ssml()` на тестовых строках со всеми макросами из таблицы даёт валидный SSML, который Edge TTS принимает без ошибок.

**Промпт для реализации:**
> «Реализуй функцию `macros_to_ssml(text: str) -> str`, транслирующую DSL-макросы из спеки v4.0 §4.1 (`[pause:Xs]`, `{whisper}`, `{shout}`, `{sad}`, `{happy}`, `{slow}`, `{fast}`, `{emphasis}`) в валидный SSML для `edge-tts`. Добавь на фронтенде тулбар кнопок над текстовым полем: выделение текста → оборачивание в выбранный макрос с проверкой корректной вложенности тегов. Реализуй автооборачивание текста при смене dropdown «Эмоция» по таблице §4.3, сохраняя уже присутствующие ручные макросы.»

---

## R6c — AI-волшебник разметки TTS (двухуровневый)

**Backend (Tier 1):**
- Экспорт `cointegrated/rubert-tiny2-cedr-emotion-detection` в ONNX INT8 → `models/story/rubert_tiny2_emotion_int8.onnx`.
- Inference-функция: свободный текст → класс эмоции CEDR → макрос (по маппингу из §5.2).

**Backend (Tier 2):**
- Эндпоинт `/api/story/tts_wizard/mark`, принимает: `original_text`, `user_free_text`, `tier` (1|2), `voice_profile_id` (опц.).
- При `tier=2`: использует provider/model из `config/story_analyzer.yaml → tts_wizard.tier2` (с возможностью переопределения в попапе), подставляет `style_description` и `example_lines` из Voice Library, формирует промпт из §5.3.

**Frontend:**
- Попап 🪄 на каждой строке Stage 6: textarea свободного описания + toggle Tier 1/Tier 2.
- При Tier 2 — dropdown провайдера и модели (синхронизированы с конфигом, с возможностью временной замены на сессию).
- Результат подставляется в текстовое поле реплики (через макро-парсер из R6b).

**Success criteria:** Tier 1 работает offline и возвращает результат < 100мс; Tier 2 корректно подставляет профиль персонажа (если назначен) и возвращает текст с валидными макросами; смена провайдера/модели в попапе не требует перезапуска приложения.

**Промпт для реализации:**
> «Экспортируй `cointegrated/rubert-tiny2-cedr-emotion-detection` в ONNX INT8, сохрани в `models/story/rubert_tiny2_emotion_int8.onnx`. Реализуй функцию `tier1_mark(free_text: str) -> str` — классификация CEDR → маппинг на макрос из спеки v4.0 §5.2 → обёртка `original_text`. Реализуй эндпоинт `/api/story/tts_wizard/mark` с `tier=2`, использующий провайдер/модель из `config/story_analyzer.yaml → tts_wizard.tier2` (с возможностью переопределения из запроса), промпт-шаблон из §5.3, подстановку `style_description`/`example_lines` из Voice Library по `voice_profile_id`. На фронтенде — попап 🪄 с textarea, toggle Tier 1/2 и dropdown провайдера/модели для Tier 2.»

---

## R6 — Stage 6: Voice Synthesis (объединение R6a–R6c)

**Backend:**
- Эндпоинт `/api/story/stage_6/synthesize`: принимает `marked_text` (после макросов/волшебника), `voice_profile_id`, движок (`edge_tts`/`cosyvoice2_api`).
- Генерация аудио → сохранение в `story_out/projects/<project>/audio/`.
- Измерение `actual_duration_ms` через `pydub.AudioSegment`.
- Обновление `stage_6_video_script_audio.json` и `stage_6_voice_assignments.json`.

**Frontend:**
- Таблица строк сценария (нарратор + диалоги) с колонками из спеки §3 Stage 6.
- Toggle «Текст сценария / Оригинальные реплики» (источник `dialogues[].text` vs `bubbles[].text_ru`).
- Автосопоставление голосов при первом открытии вкладки (через `voice_library.match` из R6a) — UI-предложения «Найден похожий голос... использовать?».
- Кнопка ▶️ «Прослушать» — генерация + проигрывание в `<audio>`.

**Success criteria:** все реплики озвучены; `actual_duration_ms` записан для каждой; смена toggle источника текста корректно подменяет содержимое без потери уже применённых макросов для другого источника (хранятся раздельно); автосопоставление голосов из библиотеки работает при наличии похожих профилей.

**Промпт для реализации:**
> «Реализуй эндпоинт `/api/story/stage_6/synthesize`, принимающий `marked_text`, `voice_profile_id` и движок (`edge_tts` через `pip install edge-tts` или `cosyvoice2_api` через SiliconFlow с reference audio+text). Сохрани аудио в `story_out/projects/<project>/audio/`, измерь длительность через `pydub`, обнови `stage_6_video_script_audio.json`. На фронтенде — таблица строк сценария с колонками (сцена/персонаж, текст с макро-тулбаром из R6b, голос из Voice Library, эмоция, кнопка 🪄 из R6c, ▶️ прослушать, статус), toggle источника текста (сценарий/оригинал), и автосопоставление голосов при открытии вкладки через `/api/voice_library/match`.»

---

## R7 — Stage 7: Timing-Aware A/V Assembly & NLE Export

**Backend:**
- Расчёт длительности панели по формуле из спеки §3 Stage 7 (нарратор + диалоги + 0.5с).
- Вызов `anim_pipeline.py` с точной `--duration` для каждой панели.
- Режим AUTO: ffmpeg-сборка `final_video.mp4` + `storyboard.mp4` (как в текущем `anim_pipeline`).
- Режим NLE: построение `opentimelineio.schema.Timeline` (треки Panels/Narrator/Characters), экспорт в `.fcpxml`/`.edl`/`.otio`, копирование ассетов в `nle_export/assets/` с плоскими именами.

**Frontend:**
- Radio: Авто-рендер MP4 / Экспорт NLE.
- Если NLE: dropdown целевого формата (DaVinci Resolve/Premiere/Final Cut → FCPXML; «Любой NLE» → EDL).
- Прогресс-бар, лог консоли, кнопка запуска.

**Success criteria:** AUTO-режим выдаёт `final_video.mp4` с длительностями панелей, точно соответствующими сумме аудио; NLE-режим — `project.fcpxml` импортируется в DaVinci Resolve без «offline media», клипы на таймлайне имеют правильные длительности и совпадающий A/V таймкод.

**Промпт для реализации:**
> «Реализуй эндпоинт `/api/story/stage_7/assemble`. Сначала рассчитай длительность каждой панели по формуле (длина аудио нарратора + сумма длин аудио диалогов + 0.5с), используя `pydub`/`ffprobe` на файлах из `stage_6_video_script_audio.json`. Для режима AUTO — вызови `anim_pipeline.py` с этой `--duration` для каждой панели и собери `final_video.mp4`+`storyboard.mp4` как сейчас. Для режима NLE — построй `opentimelineio.schema.Timeline` с треками Panels/Narrator/Characters, где `source_range` каждого клипа равен рассчитанной длительности, и экспортируй через `otio.adapters.write_to_file()` в `.fcpxml`, `.edl` и `.otio`, скопировав ассеты в `nle_export/assets/` с плоскими именами. На фронтенде — radio-выбор режима, dropdown формата NLE, прогресс-бар и лог.»

---

## Итоговый порядок выполнения

```
R0 → R1 → R2 → R3 → R4 → R5 → (R6a, R6b, R6c параллельно) → R6 → R7
```

R6a/R6b/R6c не зависят друг от друга и от R1–R5 напрямую (кроме общего провайдера из R0) — можно разрабатывать в любом порядке или параллельно, но все три нужны для полноценного R6.

Понял задачу. Создаю финальную спецификацию v4.1 + промпт-документ для внедрения в кодовую базу.

---

# 📄 Спецификация: Story Analyzer v4.1 (Финальная синергическая версия)

**Версия:** 4.1  
**Дата:** Июнь 2026  
**Статус:** Готово к реализации  
**Целевое железо:** AMD Ryzen 5 5600H, 16 GB RAM, AMD Radeon iGPU (Vulkan), Windows 10/11  
**Связанные документы:** [ARCHITECTURE.md](ARCHITECTURE.md), [MODELS_SPECIFICATION.md](MODELS_SPECIFICATION.md), [STORY_ANALYZER_ROADMAP_v4.md](STORY_ANALYZER_ROADMAP_v4.md)

---

## 🎯 Преамбула: что объединено в этой версии
## 🎯 Преамбула: что объединено в этой версии

Эта спецификация — результат синтеза трёх веток проектирования:

| Ветка | Источник | Ключевые фичи |
|---|---|---|
| **A** | Наша v3.3 | Tabbed UI, Pipeline/Sandbox/Standalone, DSL-макросы, AI-волшебник, Voice Library |
| **B** | Ревью другой LLM | Stage 2b (visual captioning), timing-aware assembly, OTIO, retry policy, API key management |
| **C** | Последние обсуждения | Выбор проекта в Split, пакетная обработка, reference-based подход, консистентность UI |

**Ключевой принцип v4.1:** каждый Stage описан **полностью автономно** — можно открыть описание Stage N, не читая остальную спеку, и работать над ним как над отдельным проектом. При этом все этапы связаны через **единую систему проектов** и **консистентный UI**.

---

## Часть I. Архитектурные принципы

### 1.1 Модульность и JSON-контракты

Каждый этап — автономный модуль:

```
Вход (JSON/Assets) → Обработка → Выход (Обновлённый JSON + Новые Assets)
```

Любой этап можно запустить отдельно, передав ему JSON предыдущего этапа. Промежуточные файлы:

```
story_out/projects/<project_name>/
├── project.json                    # метаданные проекта
├── references.json                 # ссылки на панели (reference-based)
├── stage_2a.json
├── stage_2b.json
├── stage_3.json
├── stage_4_story_analysis.json
├── stage_5_video_script.json
├── stage_6_video_script_audio.json
├── stage_6_voice_assignments.json
├── panels/                         # PNG из ComicSplit (оригиналы)
├── audio/                          # WAV/MP3 из Stage 6
└── nle_export/                     # FCPXML/OTIO/EDL из Stage 7
```

### 1.2 Human-in-the-Loop (HITL)

Каждый этап = независимая вкладка интерфейса. Принимает JSON от предыдущего этапа, позволяет визуально редактировать данные, сохраняет валидный JSON для следующего этапа.

**Глобальные правила навигации (низ каждой вкладки):**

```
[ ← Назад ]   [ 💾 Сохранить и проверить JSON ]   [ Далее → ]
```

«Сохранить» запускает Pydantic-валидацию выходного JSON по схеме этапа. При нарушении схемы — подсветка проблемных полей, переход блокируется.

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

### 1.4 Режимы работы вкладок: Pipeline / Sandbox / Standalone

Каждая Stage-вкладка имеет переключатель режима в верхнем баннере:

| Режим | Баннер | Источник/назначение данных |
|---|---|---|
| **Pipeline** (по умолчанию) | 🔗 Проект: `<project_name>` / Stage N | `story_out/projects/<project_name>/stageN.json`, строгая Pydantic-валидация |
| **Sandbox** | 🧪 Песочница — результат не входит в пайплайн | `story_out/sandbox/<stage_id>/<session_id>/`, валидация мягкая |
| **Standalone** | 📂 Автономный экспорт | Пользовательские данные, экспорт без связи с пайплайном |

**В Sandbox-режиме:**
- Загрузка произвольных файлов (любые PNG/JSON), не привязанных к конкретному проекту
- Кнопка «💾 Сохранить и проверить JSON» превращается в «📤 Экспортировать результат»
- Кнопка «Далее →» скрыта
- Импорт результата Sandbox в проект — см. §7

### 1.5 Reference-based подход (устранение дублирования)

**Проблема:** ранее ExtText копировал панели в папку проекта, создавая дубликаты.

**Решение:** Split сохраняет панели в `output/<project_name>/`, ExtText создаёт `references.json` со ссылками на оригиналы.

**Структура `references.json`:**

```json
{
  "project": "СоколГлаз",
  "source_type": "folder",
  "source_path": "output/СоколГлаз",
  "panels": [
    {
      "panel_id": "001_p001_panel",
      "source_path": "output/СоколГлаз/001_p001_panel.png",
      "checksum": "abc123...",
      "created_at": "2026-06-14T10:00:00"
    }
  ]
}
```

**Преимущества:**
- ✅ Нет дублирования данных
- ✅ Экономия дискового пространства
- ✅ Быстрое создание проекта
- ✅ Если файл удалён — показываем "Media Offline" (как в видеоредакторах)

**Дополнительно:** кнопка "📦 Экспортировать проект с файлами" → копирует всё в одну папку (для бэкапа/передачи).

### 1.6 Система управления проектами

**Глобальный реестр проектов:** `config/projects.json`

```json
{
  "projects": [
    {
      "name": "СоколГлаз",
      "path": "story_out/projects/СоколГлаз",
      "created_at": "2026-06-14T10:00:00",
      "last_modified": "2026-06-14T15:30:00",
      "pages_count": 24,
      "panels_count": 156,
      "source_type": "folder",
      "source_path": "output/СоколГлаз"
    }
  ]
}
```

**UI:** dropdown с autocomplete во всех вкладках (Split, Upscale, Video, Stage 2a-7).

**Механика:**
- Пользователь начинает вводить имя → показываются совпадения
- Если имя не найдено → создаётся новый проект
- Если выбрано существующее → загружается контекст проекта

---

## Часть II. Детальное описание этапов

### STAGE 1: Split (уже реализовано, но с изменениями)

**Назначение:** Нарезка страниц комикса на панели + выбор проекта + пакетная обработка.

**Изменения в v4.1:**
1. Добавлен dropdown выбора проекта (аналогично ExtText)
2. Пакетная обработка с grid миниатюр (аналогично ExtText)
3. Сохранение в `output/<project_name>/` (reference-based)
4. Убран чекбокс "Сохранить в YAML" (спрятан в расширенные настройки)

**UI вкладки Split:**

```
┌─────────────────────────────────────────────────────────────┐
│ Проект: [dropdown ▼] [+ Создать]                            │
├─────────────────────────────────────────────────────────────┤
│ Источник: [Обзор...] [путь к папке/CBZ]                     │
│ Детектор: [comic ▼]  Режим: [Стандарт/Качество]             │
│ [Запустить обработку]                                       │
├─────────────────────────────────────────────────────────────┤
│ Grid миниатюр страниц (как в ExtText):                      │
│ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐                            │
│ │ IMG │ │ IMG │ │ IMG │ │ IMG │  ← миниатюры страниц       │
│ └─────┘ └─────┘ └─────┘ └─────┘                            │
│ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐                            │
│ │ IMG │ │ IMG │ │ IMG │ │ IMG │                            │
│ └─────┘ └─────┘ └─────┘ └─────┘                            │
├─────────────────────────────────────────────────────────────┤
│ Клик по странице → Konva-канвас с детекцией панелей         │
│ (существующий функционал Split-редактора)                   │
└─────────────────────────────────────────────────────────────┘
```

**Backend логика:**

```python
# api/split_refactored.py
from fastapi import APIRouter, UploadFile, File, Form
from pathlib import Path
from utils.project_manager import ProjectManager
import pipeline

router = APIRouter(prefix="/api/split", tags=["split"])
pm = ProjectManager()

@router.post("/process_batch")
async def process_batch(
    project_name: str = Form(...),
    source_path: str = Form(...),
    detector: str = Form("comic"),
    quality_mode: str = Form("fast")
):
    """Пакетная обработка с сохранением в контексте проекта"""
    
    # 1. Получаем/создаём проект
    project = pm.get_project(project_name)
    if not project:
        project = pm.create_project(project_name)
    
    project_dir = Path(project["path"])
    panels_dir = project_dir / "panels"
    panels_dir.mkdir(exist_ok=True)
    
    # 2. Обновляем метаданные проекта
    pm.update_project(
        project_name,
        source_type="folder" if Path(source_path).is_dir() else "cbz",
        source_path=source_path
    )
    
    # 3. Запускаем split (существующий pipeline.py)
    # ВАЖНО: сохраняем панели в папку проекта
    result = pipeline.process_source(
        source=source_path,
        output_dir=str(panels_dir),
        detector=detector,
        quality_mode=quality_mode,
        order=True
    )
    
    # 4. Обновляем счётчики
    panels_count = len(list(panels_dir.glob("*.png")))
    pm.update_project(project_name, panels_count=panels_count)
    
    # 5. Возвращаем список панелей для grid UI
    panels = [
        {
            "panel_id": p.stem,
            "image_path": str(p.relative_to(project_dir)),
            "page": int(p.stem.split('_')[1]) if '_page_' in p.stem else 0
        }
        for p in sorted(panels_dir.glob("*.png"))
    ]
    
    return {
        "status": "success",
        "project": project_name,
        "panels": panels,
        "panels_count": panels_count
    }

@router.get("/{project_name}/panels")
def get_project_panels(project_name: str):
    """Получение списка панелей проекта (для grid UI)"""
    project = pm.get_project(project_name)
    if not project:
        return {"error": "Project not found"}
    
    project_dir = Path(project["path"])
    panels_dir = project_dir / "panels"
    
    if not panels_dir.exists():
        return {"panels": []}
    
    panels = [
        {
            "panel_id": p.stem,
            "image_path": str(p.relative_to(project_dir)),
            "thumbnail_url": f"/api/image?path={p}"
        }
        for p in sorted(panels_dir.glob("*.png"))
    ]
    
    return {"panels": panels}
```

**Frontend (Split вкладка):**

```javascript
// frontend/split_refactored.js
class SplitTab {
    constructor() {
        this.projectSelector = new ProjectSelector('project-selector-container', {
            onProjectChange: (projectName) => this.onProjectSelected(projectName)
        });
        this.currentProject = null;
        this.panelsGrid = null;
    }
    
    onProjectSelected(projectName) {
        this.currentProject = projectName;
        if (projectName) {
            this.loadProjectPanels();
        }
    }
    
    async loadProjectPanels() {
        const response = await fetch(`/api/split/${this.currentProject}/panels`);
        const data = await response.json();
        
        this.renderPanelsGrid(data.panels);
    }
    
    renderPanelsGrid(panels) {
        const gridContainer = document.getElementById('panels-grid');
        
        if (panels.length === 0) {
            gridContainer.innerHTML = '<p>Нет панелей. Запустите обработку.</p>';
            return;
        }
        
        gridContainer.innerHTML = `
            <div class="panels-grid">
                ${panels.map(p => `
                    <div class="panel-thumbnail" data-panel-id="${p.panel_id}">
                        <img src="${p.thumbnail_url}" alt="${p.panel_id}">
                        <div class="panel-label">${p.panel_id}</div>
                    </div>
                `).join('')}
            </div>
        `;
        
        // Клик по миниатюре → открытие в Konva-редакторе
        gridContainer.querySelectorAll('.panel-thumbnail').forEach(el => {
            el.addEventListener('click', () => {
                const panelId = el.dataset.panelId;
                this.openPanelInEditor(panelId);
            });
        });
    }
    
    async processBatch() {
        if (!this.currentProject) {
            alert('Выберите или создайте проект');
            return;
        }
        
        const sourcePath = document.getElementById('source-path').value;
        const detector = document.getElementById('detector-select').value;
        const qualityMode = document.getElementById('quality-mode').value;
        
        const formData = new FormData();
        formData.append('project_name', this.currentProject);
        formData.append('source_path', sourcePath);
        formData.append('detector', detector);
        formData.append('quality_mode', qualityMode);
        
        const response = await fetch('/api/split/process_batch', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            alert(`Обработано ${result.panels_count} панелей`);
            this.loadProjectPanels();  // обновляем grid
        } else {
            alert('Ошибка обработки');
        }
    }
    
    openPanelInEditor(panelId) {
        // Существующая логика Split-редактора (Konva)
        // Открывает панель в канвасе для ручной правки
    }
}
```

**Критерий успеха:**
- ✅ Split использует `ProjectSelector` (аналогично ExtText)
- ✅ Пакетная обработка сохраняет в `story_out/projects/<project>/panels/`
- ✅ Grid миниатюр отображает панели проекта
- ✅ Клик по миниатюре открывает в Konva-редакторе
- ✅ UI консистентен с ExtText

---

### STAGE 2a: Bubble Detection & Local OCR

**Назначение:** Точное извлечение текста из баблов с возможностью ручной коррекции.

**Технологии:**

| Модель | Ссылка | Роль | Оценка |
|---|---|---|---|
| **YOLO Manga INT8** | [HF: leoxs22/manga-panel-detector-yolo26n](https://huggingface.co/leoxs22/manga-panel-detector-yolo26n) | Детекция баблов (класс `1 = text_bubble`), уже в проекте | ⭐⭐⭐ ONNX CPU, ~300мс/панель |
| **EasyOCR** | [GitHub: JaidedAI/EasyOCR](https://github.com/JaidedAI/EasyOCR) | OCR кропа бабла | ⭐⭐⭐ CPU, ~200мс/бабл |

**UI вкладки «Stage 2a: OCR Корректор»:**

- **Центр:** Canvas (Konva.js) с текущей панелью
- **Поверх изображения:** bbox-прямоугольники вокруг баблов
- **Клик по bbox:** `contentEditable` поле прямо на канвасе с распознанным текстом
- **Кнопки:** `[Пропустить бабл]`, `[Добавить бабл вручную]`, `[Тип: speech/thought/sfx/narration]` (dropdown на каждом bbox)

**Выходной JSON (`stage_2a.json`):**

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

**Критерий успеха:** JSON содержит `corrected_text` для всех баблов; UI редактирует текст без перезагрузки страницы.

---

### STAGE 2b: Visual Captioning (НОВЫЙ, критический этап)

**Назначение:** Текстовое описание визуального ряда (действия, эмоции, фон) — то, чего нет в OCR.

**Обоснование:** Комикс — визуальный медиум. Немые панели, мимика персонажей, экшен-сцены, смена локации несут сюжетную информацию, которой в тексте баблов нет вообще. Без этого Stage 4 работает вслепую.

**Технологии:**

| Модель | Ссылка | Роль | Оценка |
|---|---|---|---|
| **Florence-2-large (Local)** | [HF: microsoft/Florence-2-large](https://huggingface.co/microsoft/Florence-2-large) | Локальный caption, task `DETAILED_CAPTION`, ~800MB | ⭐⭐ ONNX CPU, ~5–10с/панель |
| **Qwen2.5-VL-3B-Instruct (Cloud)** | [SiliconFlow](https://cloud.siliconflow.cn/models) | Облачный caption, быстрее и точнее | ⭐⭐⭐ API, ~1–2с/панель |

**Промпт:** "Describe the visual action, characters, expressions, and setting in this comic panel in 1-2 sentences. Ignore text."

**UI вкладки «Stage 2b: Визуальные описания»:**

- Сетка миниатюр панелей (300px), несколько рядов
- Под каждой миниатюрой — `textarea` со сгенерированным описанием
- Кнопка 🔄 `[Перегенерировать]` (тот же запрос с уточняющим промптом)
- Ручное редактирование текста
- Для миниатюр — уменьшенные превью (не 1:1), сами PNG остаются в `panels/`

**Выходной JSON (`stage_2b.json`):** добавляет `"visual_caption"` к каждой панели (наследует структуру `stage_2a.json`).

**Критерий успеха:** сетка без лагов; поле описания редактируемо; перегенерация не сбрасывает остальные данные.

---

### STAGE 3: Translation (опционально)

**Назначение:** Перевод реплик баблов и визуальных описаний на целевой язык.

**Технологии:**

| Модель | Ссылка | Роль | Оценка |
|---|---|---|---|
| **Hunyuan-MT-7B** | [SiliconFlow: tencent/Hunyuan-MT-7B](https://cloud.siliconflow.cn/models) | Перевод, лидер WMT25, 33 языка, FREE | ⭐⭐⭐ API, бесплатно, 32K контекст |

**UI вкладки «Stage 3: Перевод»:**

- Split-view: слева оригинал (read-only), справа перевод (редактируемый)
- Чекбокс `[x] Не переводить (SFX/звук)` рядом с каждым баблом
- Кнопка `[Применить ко всем неотредактированным]`

**Выходной JSON (`stage_3.json`):** добавляет `"text_ru"` к баблам, `"caption_ru"` к панелям; `"skip_translation": true` для отмеченных SFX (текст копируется без перевода).

**Критерий успеха:** массовый перевод работает; чекбоксы исключают строки из API-запроса; JSON валиден.

---

### STAGE 4: Story Understanding

**Назначение:** Анализ сюжета — персонажи, роли, ключевые события, эмоциональный тон, связи между панелями.

**Технологии:**

| Модель | Ссылка | Роль | Оценка |
|---|---|---|---|
| **Qwen2.5-7B-Instruct** | [SiliconFlow](https://cloud.siliconflow.cn/models) | ECONOMY, FREE | ⭐⭐⭐ API, бесплатно |
| **Qwen3.5-122B-A10B** | [SiliconFlow](https://cloud.siliconflow.cn/models) | QUALITY, MoE, 256K контекст | ⭐⭐⭐⭐ API, ~$0.04/комикс |

**Вход:** `stage_3.json` (или `stage_2b.json` если перевод не нужен) — промпт включает и текст, и `visual_caption` для каждой панели.

**UI вкладки «Stage 4: Анализ сюжета»:**

- Слева: сворачиваемый список панелей (`corrected_text` + `visual_caption`) — для контекста
- Справа: форма с полями LLM-результата:
  - `Список персонажей` (теги, редактируемые)
  - `Краткий сюжет` (textarea)
  - `Ключевые события` (список с добавлением/удалением)
  - `Эмоциональный тон` (textarea)
- Кнопка `[✅ Проверить JSON-схему]`

**Алгоритм проверки на галлюцинации персонажей:**

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

**Назначение:** Превратить анализ в покадровый сценарий для видео.

**Технологии:** та же модель, что в Stage 4 (follow-up prompt, общий контекст и стиль).

**UI вкладки «Stage 5: Сценарий»:**

- Список «Сцен» (карточки), каждая привязана к диапазону `panel_ids`
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

`marked_text` — заполняется на Stage 6 после применения макросов/AI-волшебника (см. §4).

**Критерий успеха:** динамическое добавление/удаление реплик в UI; итоговый JSON строго соответствует схеме.

---

### STAGE 6: Voice Synthesis (TTS) — Мини-студия озвучки

**Назначение:** Генерация аудио для каждой реплики/нарратора с предпрослушиванием, разметкой интонации и управлением голосами.

**Технологии:**

| Модель | Ссылка | Роль | Оценка |
|---|---|---|---|
| **Edge TTS** | [GitHub: rany2/edge-tts](https://github.com/rany2/edge-tts) | Основной, бесплатный, `pip install edge-tts`, отличные русские голоса (`ru-RU-DmitryNeural`, `ru-RU-SvetlanaNeural`) | ⭐⭐⭐ Бесплатно, быстро, требует интернет |
| **CosyVoice2-0.5B (Cloud)** | [SiliconFlow: FunAudioLLM/CosyVoice2-0.5B](https://cloud.siliconflow.cn/models) | TTS с эмоциями и клонированием голоса (QUALITY) — **только через API** | ⭐⭐⭐⭐ API, ~$0.05/комикс, 150ms latency |

⚠️ **Важно:** CosyVoice2 не имеет локального ONNX-экспорта. Локальный PyTorch-инференс требует ~8GB RAM при загрузке — рискованно на 16GB вместе с остальным пайплайном. Используется только через SiliconFlow API.

**UI вкладки «Stage 6: Мини-студия озвучки» — таблица строк сценария (нарратор + все диалоги):**

| Колонка | Содержимое |
|---|---|
| Сцена / Персонаж | sc01 / Астерикс |
| Текст | поле с макро-тулбаром (см. §4) |
| Голос | dropdown — голоса из Voice Library (см. §6), с быстрым поиском по имени персонажа |
| Эмоция | dropdown (синхронизирован с Stage 5, можно менять здесь) |
| 🪄 AI-волшебник | кнопка — открывает попап разметки (см. §5) |
| ▶️ Прослушать | генерирует/кэширует и проигрывает превью |
| Статус | ⚪ не сгенерировано / 🟡 генерация / 🟢 готово |

**Toggle над таблицей:** `[ Текст сценария ]` / `[ Оригинальные реплики ]` — переключает источник текста между `dialogues[].text` (Stage 5, LLM-интерпретация) и `bubbles[].text_ru`/`corrected_text` (Stage 2a/3, дословный перевод). Переключение не теряет разметку — макросы применяются к выбранному источнику отдельно.

**Блок «Клонирование голоса» (если выбран CosyVoice2):**

- Поле загрузки `.wav` (3 сек)
- Поле «Текст референсного аудио» (обязательно — без него клонирование работает плохо)
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

**Назначение:** Финальная сборка видео ИЛИ экспорт проекта для профессионального монтажа.

**Технологии:**

| Инструмент | Ссылка | Роль |
|---|---|---|
| **pydub** / **ffprobe** | — | Измерение реальной длины аудио |
| **anim_pipeline.py** | существующий | Рендер панели с точной `--duration` |
| **opentimelineio** | [PyPI: OpenTimelineIO](https://pypi.org/project/OpenTimelineIO/) | Генерация FCPXML/EDL/OTIO для NLE |

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

**Выход:** `final_video.mp4` + `storyboard.mp4` ИЛИ `nle_export/` (`project.fcpxml`, `project.edl`, `project.otio`, `assets/`).

**Критерий успеха:** `project.fcpxml` импортируется в DaVinci Resolve без ошибок «offline media»; все клипы на таймлайне с правильными длительностями и синхронизацией A/V.

---

## Часть III. Специальные модули

### 3.1 Макро-редактор текста для TTS

#### 3.1.1 Синтаксис макросов

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

**Примечание по Edge TTS:** `edge-tts` поддерживает ограниченное подмножество SSML — `prosody` (rate/pitch/volume) и `break` работают надёжно; `emphasis` поддерживается частично и может игнорироваться некоторыми голосами. Для CosyVoice2 (через SiliconFlow API) проверяется отдельно при подключении — таблица единая, но рантайм-применимость помечается в UI значком ⚠️ при выборе Edge TTS как движка.

#### 3.1.2 Тулбар над текстовым полем

Выделяешь фрагмент текста → жмёшь кнопку макроса → текст оборачивается в соответствующие теги. Аналог панели Markdown-разметки, но для голоса. Доступен на Stage 5 (по желанию) и обязателен на Stage 6.

#### 3.1.3 Таблица эмоция → макрос (для синхронизации с dropdown «Эмоция» из Stage 5/6)

| Эмоция (dropdown) | Автоматически применяемый макрос |
|---|---|
| `neutral` | без обёртки |
| `angry` | `{shout}...{/shout}` |
| `whisper` | `{whisper}...{/whisper}` |
| `sad` | `{sad}...{/sad}` |
| `happy` | `{happy}...{/happy}` |

При смене dropdown «Эмоция» в Stage 6 — текст автоматически переоборачивается (с сохранением вложенных ручных макросов, если есть).

---

### 3.2 AI-волшебник разметки TTS (двухуровневый)

#### 3.2.1 Концепция

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

#### 3.2.2 Уровень 1 — локальный (по умолчанию, всегда доступен)

| Модель | Ссылка | Роль | Оценка |
|---|---|---|---|
| **ruBERT-tiny2 emotion** | [HF: cointegrated/rubert-tiny2-cedr-emotion-detection](https://huggingface.co/cointegrated/rubert-tiny2-cedr-emotion-detection) | Классификация эмоции по свободному описанию (~29M, ONNX) | ⭐⭐⭐ CPU, миллисекунды |

Классы CEDR (`joy`, `sadness`, `surprise`, `fear`, `anger`, `neutral`) маппятся на макросы из §4.3 (приблизительное соответствие: `fear` → `whisper`, `surprise` → `happy` или `shout` по интенсивности, `anger` → `shout`). Текст оборачивается в найденный макрос. Без интернета, без API-ключа, мгновенно.

#### 3.2.3 Уровень 2 — облачный/локальный LLM (опционально, переключаемо)

Использует ту же провайдер-абстракцию, что и Stage 4/5. В попапе — два dropdown:

- **Провайдер:** `SiliconFlow` / `OpenRouter` / `Локальная модель (Ollama)`
- **Модель:** список из `config/story_analyzer.yaml → providers.<provider>.models` + дополнительно `llm_economy`/`llm_quality`

LLM получает: правила макросов (§4.1) + свободное описание пользователя + профиль персонажа из Voice Library (если назначен — стиль, примеры прошлых реплик, см. §6) → возвращает `marked_text`.

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

#### 3.2.4 Конфигурация (фрагмент `config/story_analyzer.yaml`, см. §2.1)

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

### 3.3 Библиотека голосовых профилей (Voice Library)

#### 3.3.1 Назначение

Накопительная база голосов и характеров персонажей, переиспользуемая между проектами (разными комиксами). При появлении нового персонажа в новом проекте — система предлагает похожие профили из библиотеки (по имени, тегам, стилю).

#### 3.3.2 Хранение

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
    example_lines    TEXT,                  -- JSON: [{"text": "...", "marked_text": "..."}]
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
  "Астерикс": {"voice_profile_id": 42, "project_overrides": {"default_macros": ["{fast}"]}},
  "Обеликс": {"voice_profile_id": null, "pending": true}
}
```

`project_overrides` — локальные правки для конкретного комикса без изменения глобального профиля (например, в этой истории персонаж более уставший).

#### 3.3.3 UI вкладки «🎙️ Voice Library»

- **Список профилей** — карточки: имя персонажа, движок (Edge TTS / CosyVoice2), тег-чипы, ▶️ превью голоса (короткая фраза «Привет, я ...»), счётчик использований, дата последнего использования
- **Поиск/фильтр:** по имени, тегам, движку
- **Действия на карточке:** `[Редактировать]`, `[Дублировать]`, `[Удалить]`, `[Использовать для персонажа →]` (открывает селектор: текущий проект → персонаж)
- **Создание нового профиля:** форма с полями таблицы из §6.2; для `cosyvoice2_api` — загрузка референс-аудио + текст референса (обязательно)

#### 3.3.4 Автоматическое сопоставление при первом запуске Stage 6

Для каждого персонажа из `stage_4_story_analysis.json`, у которого нет `voice_profile_id`:

1. Поиск по точному совпадению `character_name` в библиотеке
2. Если не найдено — fuzzy-поиск (`rapidfuzz`, порог > 75) по имени и алиасам
3. Если найдено — предложение в UI: «Найден похожий голос: Астерикс (из проекта galls_01) — использовать?» с кнопками `[Да]` / `[Создать новый]`
4. Если не найдено совсем — назначается дефолтный голос Edge TTS по полу/роли (грубая heuristic по `role` из Stage 4: `protagonist`→`ru-RU-DmitryNeural`, и т.п.), помечается `"pending": true` для ручной проверки

---

### 3.4 Импорт результата Sandbox в проект

#### 3.4.1 Сценарий

Пользователь в режиме 🧪 Sandbox на вкладке Stage 2b обработал произвольные изображения, отредактировал описания, результат понравился.

#### 3.4.2 Механизм

**Кнопка «📥 Импортировать в проект»** (видна только в Sandbox-режиме, после успешного экспорта):

**Модал выбора:**

- **Целевой проект:** dropdown (список из `story_out/projects/`)
- **Целевой этап:** предзаполнен по текущей вкладке (Stage 2b), изменяемо
- **Сопоставление панелей:** если имена файлов в Sandbox (`panel_017.png`) совпадают с `panel_id` в `stage_2a.json` целевого проекта — автосопоставление. Иначе — таблица ручного маппинга `sandbox_file → target_panel_id` (или опция «Добавить как новые панели»)

**Валидация:** результат проверяется по Pydantic-схеме целевого этапа (та же, что в Pipeline-режиме).

**Подтверждение записи:**

- Если `stageN.json` целевого проекта существует — создаётся `.bak`-копия, затем merge (по `panel_id`: новые данные заменяют старые поля, остальное сохраняется)
- Если не существует — создаётся новый файл

**Лог операции** пишется в `story_out/projects/<project>/import_log.json` (источник, дата, какие панели затронуты) — для отладки и возможного ручного откатa через `.bak`.

#### 3.4.3 Ограничения

- Импорт возможен только «вперёд по пайплайну или на тот же этап» (нельзя импортировать в Stage 2a результат, рассчитанный для Stage 5 — типы данных не совпадут, схема отклонит)
- Если целевой проект уже прошёл более поздние этапы (например, есть `stage_5_video_script.json`), импорт в `stage_2b.json` — с предупреждением: «Этапы 3–7 могут устареть относительно новых данных. Пересчитать?» с кнопкой быстрого перехода на Stage 3

---

## Часть IV. Управление API-провайдерами и ключами

### 4.1 Конфигурация

**`config/story_analyzer.yaml`** (в репозитории, без ключей):

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

**`.env`** (в `.gitignore`):

```bash
SILICONFLOW_API_KEY=sk-xxxxxxxx
OPENROUTER_API_KEY=
```

### 4.2 Индикатор статуса API в UI

В каждой вкладке, использующей облачный API — иконка в углу:

| Иконка | Значение |
|---|---|
| 🟢 | Ключ найден, последний вызов успешен |
| 🟡 | Ключ найден, последний вызов — retry в процессе |
| 🔴 | Ключ отсутствует или последний вызов завершился ошибкой после всех retry |
| ⚪ | Локальный режим, API не используется |

Клик по иконке → модал с настройками провайдера/модели для этого этапа (переопределяет `active_provider` локально).

### 4.3 Retry-политика (обязательна для всех API-вызовов)

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
| 5/6 (wizard) | Qwen2.5-7B-Instruct (повторно) | AI-разметка TTS | API/локально, настраиваемо |
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

## Часть VI. Зависимости (добавить в `requirements.txt`)

```txt
edge-tts
easyocr
pydub
opentimelineio
rapidfuzz
tenacity
# опционально, если включён локальный Florence-2:
# transformers (только для экспорта в ONNX, инференс — onnxruntime)
```

---

## ✅ Резюме

Спецификация **v4.1** — финальная синергическая версия, объединяющая:

1. ✅ **Архитектурные принципы:** Tabbed UI, Pipeline/Sandbox/Standalone, JSON-контракты, HITL, reference-based подход
2. ✅ **Система управления проектами:** dropdown с autocomplete во всех вкладках, `config/projects.json`
3. ✅ **Автономность этапов:** каждый Stage описан полностью самодостаточно
4. ✅ **Технологический стек:** SiliconFlow API, Florence-2/Qwen-VL, Edge TTS/CosyVoice2, OpenTimelineIO
5. ✅ **Специальные модули:** Voice Library (SQLite), DSL-макросы, AI-волшебник (2 уровня)
6. ✅ **Консистентность UI:** Split и ExtText используют одинаковые паттерны (ProjectSelector, grid миниатюр)
7. ✅ **Управление рисками:** retry, антигаллюцинация, валидация

**Рекомендуемый порядок реализации:**

| Неделя | Блок | Ключевые задачи |
|---|---|---|
| **1** | R0 + R1 | Инфраструктура (ProjectManager, API keys, retry) + Split рефакторинг (выбор проекта, пакетная обработка) |
| **2** | R2 + R3 | Stage 2a (OCR) + Stage 2b (Visual Captioning) + Stage 3 (Translation) |
| **3** | R4 + R5 | Stage 4 (Story) + Stage 5 (Script) + антигаллюцинатор |
| **4** | R6a + R6b + R6c | Voice Library + DSL-макросы + AI-волшебник (параллельно) |
| **5** | R6 + R7 | Stage 6 (TTS Studio) + Stage 7 (Assembly/NLE) + интеграционное тестирование |

**Готовность к реализации:** 100%

---

---

# 📋 Промпт-документ для внедрения в кодовую базу

**Для:** Локальная LLM в IDE  
**Проект:** ComicSplit / Story Analyzer  
**Задача:** Внедрить изменения из спецификации v4.1 в существующую кодовую базу  
**Принцип:** КОНСИСТЕНТНОСТЬ ВО ВСЁМ — от фронтенда до бэкенда

---

## 🎯 Общий план внедрения

Внедрение разделено на **7 блоков** (R0-R7), каждый блок — самодостаточный шаг с явным критерием успеха.

**Порядок выполнения:** R0 → R1 → R2 → R3 → R4 → R5 → (R6a, R6b, R6c параллельно) → R6 → R7

---

## 📦 Блок R0: Инфраструктура (фундамент)

### Задача
Создать систему управления проектами, конфигурацию API-провайдеров, retry-политику, UI-компоненты для выбора проекта.

### Файлы для создания/изменения

#### 1. `utils/project_manager.py` (НОВЫЙ)

**Назначение:** Управление проектами (создание, получение, обновление, список).

**Код:**

```python
"""
utils/project_manager.py
Управление проектами Story Analyzer
"""
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import json

class ProjectManager:
    """Управление проектами ComicSplit"""
    
    def __init__(self, base_dir: str = "story_out/projects"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.projects_file = self.base_dir / "projects.json"
        self._load_projects()
    
    def _load_projects(self):
        """Загрузка списка проектов"""
        if self.projects_file.exists():
            with open(self.projects_file, 'r', encoding='utf-8') as f:
                self.projects = json.load(f)
        else:
            self.projects = []
    
    def _save_projects(self):
        """Сохранение списка проектов"""
        with open(self.projects_file, 'w', encoding='utf-8') as f:
            json.dump(self.projects, f, ensure_ascii=False, indent=2)
    
    def create_project(self, name: str) -> Dict:
        """Создание нового проекта"""
        project_dir = self.base_dir / name
        project_dir.mkdir(parents=True, exist_ok=True)
        
        project = {
            "name": name,
            "path": str(project_dir),
            "created_at": datetime.now().isoformat(),
            "last_modified": datetime.now().isoformat(),
            "source_type": None,  # 'folder', 'cbz', 'single_image'
            "source_path": None,
            "pages_count": 0,
            "panels_count": 0
        }
        
        self.projects.append(project)
        self._save_projects()
        return project
    
    def get_project(self, name: str) -> Optional[Dict]:
        """Получение проекта по имени"""
        for p in self.projects:
            if p["name"] == name:
                return p
        return None
    
    def list_projects(self) -> List[str]:
        """Список имён проектов"""
        return [p["name"] for p in self.projects]
    
    def update_project(self, name: str, **kwargs):
        """Обновление метаданных проекта"""
        project = self.get_project(name)
        if project:
            project.update(kwargs)
            project["last_modified"] = datetime.now().isoformat()
            self._save_projects()
    
    def get_project_dir(self, name: str) -> Path:
        """Получение пути к папке проекта"""
        project = self.get_project(name)
        if project:
            return Path(project["path"])
        raise ValueError(f"Project '{name}' not found")
```

**Куда вставить:** Создать новый файл `utils/project_manager.py`

---

#### 2. `utils/story_providers.py` (НОВЫЙ)

**Назначение:** Абстракция API-провайдеров с retry-политикой.

**Код:**

```python
"""
utils/story_providers.py
Абстракция API-провайдеров для Story Analyzer
"""
import os
import requests
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import yaml

class LLMProvider(ABC):
    """Абстрактный класс для LLM-провайдеров"""
    
    @abstractmethod
    def chat(self, messages: list, model: str, **kwargs) -> str:
        """Текстовый запрос"""
        pass
    
    @abstractmethod
    def vision_chat(self, image_path: str, prompt: str, model: str, **kwargs) -> str:
        """Визуальный запрос (VLM)"""
        pass

class SiliconFlowProvider(LLMProvider):
    """SiliconFlow API провайдер"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.siliconflow.cn/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.api_url = f"{base_url}/chat/completions"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=4, max=30),
        retry=retry_if_exception_type(requests.exceptions.HTTPError)
    )
    def chat(self, messages: list, model: str, **kwargs) -> str:
        """Текстовый запрос"""
        response = requests.post(
            self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": messages,
                **kwargs
            }
        )
        
        if response.status_code == 429:
            raise requests.exceptions.HTTPError("Rate limited")
        response.raise_for_status()
        
        return response.json()["choices"][0]["message"]["content"]
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=4, max=30),
        retry=retry_if_exception_type(requests.exceptions.HTTPError)
    )
    def vision_chat(self, image_path: str, prompt: str, model: str, **kwargs) -> str:
        """Визуальный запрос (VLM)"""
        import base64
        
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode()
        
        response = requests.post(
            self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_b64}"
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ],
                **kwargs
            }
        )
        
        if response.status_code == 429:
            raise requests.exceptions.HTTPError("Rate limited")
        response.raise_for_status()
        
        return response.json()["choices"][0]["message"]["content"]

class OpenRouterProvider(LLMProvider):
    """OpenRouter API провайдер (заглушка)"""
    
    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        self.api_key = api_key
        self.base_url = base_url
        # TODO: реализовать аналогично SiliconFlowProvider
    
    def chat(self, messages: list, model: str, **kwargs) -> str:
        raise NotImplementedError("OpenRouter provider not implemented yet")
    
    def vision_chat(self, image_path: str, prompt: str, model: str, **kwargs) -> str:
        raise NotImplementedError("OpenRouter provider not implemented yet")

def load_provider_config() -> Dict:
    """Загрузка конфигурации провайдеров"""
    config_path = Path("config/story_analyzer.yaml")
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}

def get_provider(provider_name: str = None) -> LLMProvider:
    """Получение провайдера по имени"""
    config = load_provider_config()
    
    if provider_name is None:
        provider_name = config.get("active_provider", "siliconflow")
    
    provider_config = config.get("providers", {}).get(provider_name, {})
    api_key_env = provider_config.get("api_key_env", "")
    api_key = os.getenv(api_key_env, "")
    
    if not api_key:
        raise ValueError(f"API key not found for provider '{provider_name}'. Set {api_key_env} environment variable.")
    
    if provider_name == "siliconflow":
        return SiliconFlowProvider(api_key, provider_config.get("base_url"))
    elif provider_name == "openrouter":
        return OpenRouterProvider(api_key, provider_config.get("base_url"))
    else:
        raise ValueError(f"Unknown provider: {provider_name}")
```

**Куда вставить:** Создать новый файл `utils/story_providers.py`

---

#### 3. `config/story_analyzer.yaml` (НОВЫЙ)

**Назначение:** Конфигурация Story Analyzer (провайдеры, retry, tts_wizard).

**Код:**

```yaml
# config/story_analyzer.yaml
# Конфигурация Story Analyzer

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

**Куда вставить:** Создать новый файл `config/story_analyzer.yaml`

---

#### 4. `.env` (ИЗМЕНИТЬ)

**Назначение:** Добавить переменные окружения для API-ключей.

**Код (добавить в конец файла):**

```bash
# Story Analyzer API keys
SILICONFLOW_API_KEY=
OPENROUTER_API_KEY=
```

**Куда вставить:** Добавить в существующий файл `.env` (или создать, если не существует)

---

#### 5. `requirements.txt` (ИЗМЕНИТЬ)

**Назначение:** Добавить новые зависимости.

**Код (добавить в конец файла):**

```txt
# Story Analyzer dependencies
edge-tts
easyocr
pydub
opentimelineio
rapidfuzz
tenacity
PyYAML
```

**Куда вставить:** Добавить в существующий файл `requirements.txt`

---

#### 6. `frontend/components/project_selector.js` (НОВЫЙ)

**Назначение:** UI-компонент для выбора/создания проекта (dropdown с autocomplete).

**Код:**

```javascript
// frontend/components/project_selector.js
// UI-компонент для выбора/создания проекта

class ProjectSelector {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.onProjectChange = options.onProjectChange || (() => {});
        this.currentProject = null;
        this.projects = [];
        this.render();
        this.loadProjects();
    }
    
    async render() {
        this.container.innerHTML = `
            <div class="project-selector">
                <label>Проект:</label>
                <input type="text" id="project-input" placeholder="Начните вводить имя проекта..." autocomplete="off">
                <div id="project-dropdown" class="project-dropdown" style="display: none;"></div>
                <button id="create-project-btn" style="display: none;">+ Создать</button>
            </div>
        `;
        
        this.attachEvents();
    }
    
    attachEvents() {
        const input = document.getElementById('project-input');
        const dropdown = document.getElementById('project-dropdown');
        const createBtn = document.getElementById('create-project-btn');
        
        // Ввод текста → показ dropdown
        input.addEventListener('input', (e) => {
            const value = e.target.value.trim();
            this.filterProjects(value);
        });
        
        // Клик вне dropdown → скрыть
        document.addEventListener('click', (e) => {
            if (!this.container.contains(e.target)) {
                dropdown.style.display = 'none';
            }
        });
        
        // Кнопка создания проекта
        createBtn.addEventListener('click', async () => {
            const projectName = input.value.trim();
            if (projectName) {
                await this.createProject(projectName);
                input.value = '';
                dropdown.style.display = 'none';
                createBtn.style.display = 'none';
            }
        });
    }
    
    async loadProjects() {
        try {
            const response = await fetch('/api/projects/');
            const data = await response.json();
            this.projects = data.projects || [];
        } catch (error) {
            console.error('Failed to load projects:', error);
            this.projects = [];
        }
    }
    
    filterProjects(query) {
        const dropdown = document.getElementById('project-dropdown');
        const createBtn = document.getElementById('create-project-btn');
        
        if (!query) {
            dropdown.style.display = 'none';
            createBtn.style.display = 'none';
            return;
        }
        
        const filtered = this.projects.filter(p => 
            p.toLowerCase().includes(query.toLowerCase())
        );
        
        if (filtered.length > 0) {
            dropdown.innerHTML = filtered.map(p => `
                <div class="project-option" data-project="${p}">${p}</div>
            `).join('');
            dropdown.style.display = 'block';
            
            // Клик по опции → выбор проекта
            dropdown.querySelectorAll('.project-option').forEach(el => {
                el.addEventListener('click', () => {
                    const projectName = el.dataset.project;
                    this.selectProject(projectName);
                    dropdown.style.display = 'none';
                    createBtn.style.display = 'none';
                });
            });
        } else {
            dropdown.style.display = 'none';
            createBtn.style.display = 'inline-block';
        }
    }
    
    selectProject(projectName) {
        this.currentProject = projectName;
        document.getElementById('project-input').value = projectName;
        this.onProjectChange(projectName);
    }
    
    async createProject(projectName) {
        try {
            const response = await fetch(`/api/projects/${encodeURIComponent(projectName)}`, {
                method: 'POST'
            });
            
            if (response.ok) {
                await this.loadProjects();
                this.selectProject(projectName);
                alert(`Проект "${projectName}" создан`);
            } else {
                alert('Ошибка создания проекта');
            }
        } catch (error) {
            console.error('Failed to create project:', error);
            alert('Ошибка создания проекта');
        }
    }
}

// Экспорт для использования в других модулях
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ProjectSelector;
}
```

**Куда вставить:** Создать новый файл `frontend/components/project_selector.js`

---

#### 7. `api/project_api.py` (НОВЫЙ)

**Назначение:** REST API для управления проектами.

**Код:**

```python
# api/project_api.py
# REST API для управления проектами

from fastapi import APIRouter, HTTPException
from utils.project_manager import ProjectManager

router = APIRouter(prefix="/api/projects", tags=["projects"])
pm = ProjectManager()

@router.get("/")
def list_projects():
    """Список всех проектов"""
    return {"projects": pm.list_projects()}

@router.post("/{name}")
def create_project(name: str):
    """Создание нового проекта"""
    if pm.get_project(name):
        raise HTTPException(400, f"Project '{name}' already exists")
    project = pm.create_project(name)
    return project

@router.get("/{name}")
def get_project(name: str):
    """Получение информации о проекте"""
    project = pm.get_project(name)
    if not project:
        raise HTTPException(404, f"Project '{name}' not found")
    return project

@router.put("/{name}")
def update_project(name: str, updates: dict):
    """Обновление метаданных проекта"""
    pm.update_project(name, **updates)
    return {"status": "updated"}
```

**Куда вставить:** Создать новый файл `api/project_api.py`

---

#### 8. `api/server.py` (ИЗМЕНИТЬ)

**Назначение:** Подключить новый роутер проектов.

**Код (добавить в начало файла, после импортов):**

```python
from api.project_api import router as project_router
app.include_router(project_router)
```

**Куда вставить:** Добавить в существующий файл `api/server.py` после строки `app = FastAPI()`

---

#### 9. `frontend/index.html` (ИЗМЕНИТЬ)

**Назначение:** Подключить компонент ProjectSelector в Split вкладку.

**Код (добавить в `<head>`):**

```html
<script src="components/project_selector.js"></script>
```

**Код (добавить в Split вкладку, в начало):**

```html
<div id="project-selector-container"></div>
<script>
    const splitTab = new SplitTab();
    // ProjectSelector уже инициализируется в SplitTab constructor
</script>
```

**Куда вставить:** Добавить в существующий файл `frontend/index.html`

---

### Критерий успеха R0

- ✅ `config/story_analyzer.yaml` загружается, `.env` читает ключ из переменной окружения
- ✅ Тестовый вызов SiliconFlow с искусственным 429 → 3 retry с экспоненциальной задержкой, видны в логе
- ✅ В навигации видна группа `📖 Story Analyzer` с 7 пустыми под-вкладками-заглушками + отдельная вкладка `🎙️ Voice Library`
- ✅ Dropdown выбора проекта работает в Split вкладке

---

## 📦 Блок R1: Split рефакторинг (выбор проекта, пакетная обработка)

### Задача
Добавить выбор проекта в Split вкладку, реализовать пакетную обработку с grid миниатюр (аналогично ExtText).

### Файлы для создания/изменения

#### 1. `api/split_refactored.py` (НОВЫЙ)

**Назначение:** API для пакетной обработки Split с сохранением в контексте проекта.

**Код:** (см. Часть II, STAGE 1, Backend логика)

**Куда вставить:** Создать новый файл `api/split_refactored.py`

---

#### 2. `frontend/split_refactored.js` (НОВЫЙ)

**Назначение:** Frontend для Split вкладки с ProjectSelector и grid миниатюр.

**Код:** (см. Часть II, STAGE 1, Frontend)

**Куда вставить:** Создать новый файл `frontend/split_refactored.js`

---

#### 3. `api/server.py` (ИЗМЕНИТЬ)

**Назначение:** Подключить новый роутер Split.

**Код (добавить):**

```python
from api.split_refactored import router as split_refactored_router
app.include_router(split_refactored_router)
```

**Куда вставить:** Добавить в `api/server.py`

---

#### 4. `frontend/index.html` (ИЗМЕНИТЬ)

**Назначение:** Подключить новый Split frontend.

**Код (добавить в `<head>`):**

```html
<script src="split_refactored.js"></script>
```

**Куда вставить:** Добавить в `frontend/index.html`

---

### Критерий успеха R1

- ✅ Split использует `ProjectSelector` (аналогично ExtText)
- ✅ Пакетная обработка сохраняет в `story_out/projects/<project>/panels/`
- ✅ Grid миниатюр отображает панели проекта
- ✅ Клик по миниатюре открывает в Konva-редакторе
- ✅ UI консистентен с ExtText

---

## 📦 Блоки R2-R7

Остальные блоки (R2-R7) реализуются аналогично — каждый блок создаёт/изменяет файлы для соответствующего Stage.

**Подробное описание каждого блока:** см. [STORY_ANALYZER_ROADMAP_v4.md](STORY_ANALYZER_ROADMAP_v4.md)

**Промпты для реализации каждого блока:** см. Часть III спецификации v4.1

---

## ✅ Финальная проверка

После внедрения всех блоков:

1. **Запустить приложение:**
   ```bash
   uvicorn api.server:app --reload --port 8000
   ```

2. **Проверить вкладки:**
   - Split: выбор проекта, пакетная обработка, grid миниатюр
   - Stage 2a-7: все вкладки работают, JSON-контракты валидны
   - Voice Library: создание профилей, поиск, использование

3. **Протестировать сквозной пайплайн:**
   - Создать проект в Split
   - Пройти через все этапы до Stage 7
   - Получить финальное видео или NLE-экспорт

---

**Документ готов к передаче в локальную LLM для внедрения.** 🚀
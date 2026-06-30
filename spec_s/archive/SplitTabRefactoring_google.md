
Понял тебя на 100%. Мы приводим весь проект к единому UX/UI стандарту, где вкладка ExText (её карусель, логика навигации и пакетная загрузка) становится эталоном для вкладки Split. Консистентность (единообразие) — это признак зрелого софта.

Ниже я подготовил **Master Prompt / Архитектурный Roadmap**. Это технический документ, написанный специально для LLM (меня или другого ИИ-агента). В нем нет "воды", только строгие директивы, архитектурные правила и конкретные шаги с привязкой к файлам из твоей Карты Репозитория. 

Можешь просто скопировать этот текст в новую сессию (или отправить мне же в следующем запросе), и ИИ сразу начнет выдавать точный код.

***

```markdown
# MASTER PROMPT: Архитектурный рефакторинг Comix_Split (Workspace & Консистентность)

## 🎯 Глобальная цель
Перевести приложение из набора разрозненных утилит в единый пайплайн с гибридной логикой: «Автономный режим» vs «Режим Проекта». 
Обеспечить 100% UI/UX консистентность: вкладка `Split` должна унаследовать механику навигации и пакетной загрузки от вкладки `ExText` (Stage 2a). Устранить дублирование данных (Data Duplication).

## 🏗️ Архитектурный стандарт (Workspace Paradigm)
1. **Единый источник истины (Single Source of Truth):** 
   Внедряется глобальная директория `WORKSPACE_DIR` (задается в `config.yaml` или хардкодом `story_out/projects/`).
2. **Структура проекта:**
   Каждый проект внутри Workspace имеет жесткую структуру:
   `WORKSPACE_DIR / [Project_Name] /`
   ├── `panels/`   (результат вкладки Split)
   ├── `upscale/`  (результат вкладки Upscale)
   ├── `video/`    (результат вкладки Video)
   └── `stage_2a.json` (результат вкладки ExText)
3. **Отмена копирования:** Вкладка `ExText` больше НЕ копирует файлы. Она читает картинки напрямую из `panels/` (или `upscale/`) и пишет относительные пути в JSON.

## 🎨 UI/UX Стандарт
1. **Project Selector (Datalist):** На каждой вкладке вместо чекбокса "Сохранить в YAML" появляется чекбокс "Проект". При его активации появляется поле ввода с выпадающим списком (`<input list="projects_list">`), подтягивающим существующие проекты с бэкенда.
2. **Навигация:** Механика загрузки папки в `Split` должна визуально и функционально копировать `ExText`:
   - Кнопка загрузки папки.
   - Карусель/Слайдер с центральным изображением.
   - Кнопки навигации `<- [Стр X из Y] ->`.

---

====================================================


## 🛠️ Roadmap реализации (Поэтапный план для LLM)

### Фаза 1: Бэкенд и Глобальный State (State Management)
**Файлы:** `api/server.py`, `utils/ui_state.py`, `config.yaml`
- [ ] Добавить в бэкенд глобальную константу `WORKSPACE_DIR`.
- [ ] Написать эндпоинт `GET /api/projects` для сканирования папки Workspace и возврата списка имен существующих проектов (для `<datalist>`).
- [ ] В `ui_state.py` добавить глобальное поле `current_project` (string | null), чтобы вкладки могли шарить между собой выбранный проект.

### Фаза 2: Рефакторинг вкладки Split (UI & Пакетная обработка)
**Файлы:** `frontend/index.html`, `frontend/ui_state.js`, `api/server.py`
- [ ] В `index.html` (вкладка Split) заменить одиночный File Input на выбор директории (`webkitdirectory`).
- [ ] Скопировать верстку карусели (стрелки навигации, счетчик) из секции ExText во вкладку Split.
- [ ] Заменить чекбокс YAML на чекбокс "Проект" + поле ввода `<datalist id="projects_list">`.
- [ ] В JS: реализовать логику перелистывания страниц (массив загруженных файлов).
- [ ] Изменить эндпоинт запуска Split в `server.py`: он должен принимать `project_name` (опционально) и массив файлов/папку. 
- [ ] Логика бэкенда Split: Если передан `project_name`, сохранять нарезанные панели в `WORKSPACE_DIR / [Project_Name] / panels / {page_num}_{panel_num}.png`.

### Фаза 3: Вкладки Upscale и Video (Транзит контекста)
**Файлы:** `frontend/index.html`, API эндпоинты апскейла/анимации.
- [ ] Добавить чекбокс "Проект" + `<datalist>` в UI.
- [ ] JS логика: при включении чекбокса "Проект", поля "Input directory" и "Output directory" блокируются (hide/disable). Бэкенд автоматически берет файлы из `[Project]/panels` и сохраняет в `[Project]/upscale` (или `video`).

### Фаза 4: Рефакторинг ExText (Stage 2a) - Устранение дублей
**Файлы:** `api/story_stage_2a.py`, `story_analyzer/stages/stage_2a_processor.py`, `frontend/story_2a.js`
- [ ] Убрать из эндпоинта `/api/story/stage_2a/init` логику копирования (`shutil.copy`). 
- [ ] Научить парсер читать исходники напрямую из `WORKSPACE_DIR/[Project]/panels`.
- [ ] Исправить генерацию путей в `stage_2a.json`. Поле `image_path` должно быть относительным (например, `"panels/001_panel.png"`), чтобы проект оставался портативным (можно было перенести папку на другой диск без поломки JSON).

## 📌 Правила для LLM при написании кода:
- Следовать принципу **DRY (Don't Repeat Yourself)**. Если JS-логика карусели повторяется в Split и ExText, вынести её в общий модуль во фронтенде.
- Писать асинхронный код в FastAPI.
- При ответе выдавать только те блоки кода, которые были изменены, с четким указанием пути к файлу и окружающих строк (Context lines).
```

***

**Как тебе такой документ?** Он покрывает все краевые случаи (например, блокировку ручных путей, если выбран проект). Если утверждаешь, давай команду — с какой Фазы (1, 2, 3 или 4) я должен начать выдавать тебе готовый код?

=========================================

Понял тебя на 100%. Команда принята. 

Я провел аналитику архитектуры и подготовил **Интеграционный Манифест**. Это пошаговый технический документ-инструкция, написанный мной специально для твоего локального ИИ-агента (Cursor / Roo Code).

Твоя задача сейчас — просто скопировать всё, что находится внутри блока ниже, и скормить это твоему локальному ИИ с командой: *"Выполни этот манифест, шаг за шагом внедряя код в файлы проекта"*.

***

# 🛠️ ИНТЕГРАЦИОННЫЙ МАНИФЕСТ: Workspace & Консистентность (Для локальной LLM)

**Контекст для LLM:**
Привет! Ты выступаешь в роли Senior AI Developer. Твоя задача — провести рефакторинг кодовой базы `Comix_Split` согласно этому документу. Мы переводим приложение на архитектуру единого Workspace (без дублирования данных) и приводим UI вкладки Split к пакетной логике (с каруселью, как в ExText).
Следуй инструкциям ниже, находи указанные блоки в файлах и вноси изменения. Сохраняй консистентность стилей проекта.

---

### ФАЗА 1: Бэкенд — Глобальный Workspace и API проектов
**1. Файл:** `utils/config.py` (или `api/server.py`, где хранятся глобальные пути)
**Действие:** Добавить определение глобальной рабочей директории.
**Код для добавления:**
```python
import os
from pathlib import Path

# Глобальная директория для всех проектов
WORKSPACE_DIR = Path("story_out/projects")
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
```

**2. Файл:** `api/server.py`
**Действие:** Добавить новый эндпоинт для получения списка проектов.
**Код для добавления (в секцию с эндпоинтами):**
```python
@app.get("/api/projects")
async def get_projects():
    """Сканирует WORKSPACE_DIR и возвращает список существующих проектов."""
    if not WORKSPACE_DIR.exists():
        return {"projects": []}
    
    projects = [d.name for d in WORKSPACE_DIR.iterdir() if d.is_dir()]
    return {"projects": sorted(projects)}
```

---

### ФАЗА 2: Фронтенд HTML — Единый UI проектов и Карусель Split
**Файл:** `frontend/index.html`

**1. Действие:** Добавить `<datalist>` глобально в конец `<body>` (перед скриптами).
**Код для добавления:**
```html
<!-- Глобальный список проектов для автодополнения -->
<datalist id="projects_list"></datalist>
```

**2. Действие:** Вкладка **Split**. Удалить чекбокс "Сохранить в YAML" и добавить интерфейс Проекта + выбор папки.
**Заменить секцию загрузки файла на:**
```html
<div class="project-settings-bar">
    <label>
        <input type="checkbox" id="split_use_project" onchange="toggleProjectMode('split')">
        Создать / Работать в проекте
    </label>
    <input type="text" id="split_project_name" list="projects_list" placeholder="Название проекта" style="display: none;">
</div>

<div class="batch-upload-section">
    <label>Загрузить папку с комиксом:</label>
    <input type="file" id="split_folder_input" webkitdirectory directory multiple accept="image/*">
</div>

<!-- Карусель Split (консистентна с ExText) -->
<div id="split_carousel" class="carousel-container" style="display: none;">
    <button id="split_btn_prev" onclick="splitCarouselPrev()">&lt;</button>
    <img id="split_preview_img" src="" alt="Preview">
    <button id="split_btn_next" onclick="splitCarouselNext()">&gt;</button>
    <div id="split_counter">0 / 0</div>
</div>
```

**3. Действие:** Вкладки **Upscale** и **Video**. Заменить чекбоксы "Save to YAML" на выбор проекта.
**Добавить в начало панелей настроек Upscale и Video:**
```html
<div class="project-settings-bar">
    <label>
        <input type="checkbox" id="upscale_use_project" onchange="toggleProjectMode('upscale')">
        Использовать текущий проект
    </label>
    <input type="text" id="upscale_project_name" list="projects_list" placeholder="Выберите проект" style="display: none;">
</div>
```
*(То же самое сделать для вкладки Video, заменив `upscale` на `video`)*.

---

### ФАЗА 3: Фронтенд JavaScript — Логика карусели и путей
**Файл:** `frontend/ui_state.js` (или основной JS файл)

**Действие:** Добавить логику работы с проектами и каруселью.
**Код для добавления:**
```javascript
// Глобальный State
let currentProject = "";
let splitBatchFiles = [];
let splitCurrentIndex = 0;

// Загрузка проектов при старте
async function loadProjectsList() {
    try {
        const response = await fetch('/api/projects');
        const data = await response.json();
        const datalist = document.getElementById('projects_list');
        datalist.innerHTML = '';
        data.projects.forEach(proj => {
            let option = document.createElement('option');
            option.value = proj;
            datalist.appendChild(option);
        });
    } catch (e) { console.error("Ошибка загрузки списка проектов", e); }
}

// Управление отображением поля проекта и блокировкой ручных путей
function toggleProjectMode(tab) {
    const cb = document.getElementById(`${tab}_use_project`);
    const input = document.getElementById(`${tab}_project_name`);
    
    if (cb.checked) {
        input.style.display = 'inline-block';
        if (currentProject) input.value = currentProject;
        
        // Для Upscale/Video блокируем ручные пути
        if (tab === 'upscale' || tab === 'video') {
            document.getElementById(`${tab}_input_dir`).disabled = true;
            document.getElementById(`${tab}_output_dir`).disabled = true;
        }
    } else {
        input.style.display = 'none';
        if (tab === 'upscale' || tab === 'video') {
            document.getElementById(`${tab}_input_dir`).disabled = false;
            document.getElementById(`${tab}_output_dir`).disabled = false;
        }
    }
}

// Карусель Split
document.getElementById('split_folder_input')?.addEventListener('change', function(e) {
    splitBatchFiles = Array.from(e.target.files).filter(f => f.type.startsWith('image/'));
    splitBatchFiles.sort((a, b) => a.name.localeCompare(b.name));
    
    if (splitBatchFiles.length > 0) {
        document.getElementById('split_carousel').style.display = 'flex';
        splitCurrentIndex = 0;
        updateSplitCarousel();
    }
});

function updateSplitCarousel() {
    if (splitBatchFiles.length === 0) return;
    const file = splitBatchFiles[splitCurrentIndex];
    document.getElementById('split_preview_img').src = URL.createObjectURL(file);
    document.getElementById('split_counter').innerText = `${splitCurrentIndex + 1} / ${splitBatchFiles.length}`;
}

function splitCarouselPrev() {
    if (splitCurrentIndex > 0) { splitCurrentIndex--; updateSplitCarousel(); }
}
function splitCarouselNext() {
    if (splitCurrentIndex < splitBatchFiles.length - 1) { splitCurrentIndex++; updateSplitCarousel(); }
}

// Синхронизация имени проекта при вводе
document.querySelectorAll('input[list="projects_list"]').forEach(el => {
    el.addEventListener('change', (e) => { currentProject = e.target.value; });
});

window.addEventListener('DOMContentLoaded', loadProjectsList);
```

---

### ФАЗА 4: Бэкенд — Устранение дублирования данных (ExText / Stage 2a)
**1. Файл:** `api/story_stage_2a.py` (эндпоинт `/api/story/stage_2a/init`)
**Действие:** Удалить логику копирования `shutil.copy` и перенаправить чтение.
**Логика изменений:**
- Вместо копирования файлов из `source_dir` в папку проекта, эндпоинт должен просто устанавливать рабочую директорию на `WORKSPACE_DIR / project / "panels"` (или "upscale").
- Файлы никуда не перемещаются. Json создается прямо в `WORKSPACE_DIR / project / stage_2a.json`.

**2. Файл:** `story_analyzer/stages/stage_2a_processor.py` (Генерация JSON)
**Действие:** Записывать относительные пути.
**Найти блок формирования `image_path` и изменить на:**
```python
# Вместо абсолютного пути или копирования, пишем относительный путь от корня проекта
relative_img_path = f"panels/{image_file.name}"
panel_data = {
    "panel_id": panel_id,
    "image_path": relative_img_path,
    "bubbles": []
}
```

---
**Завершение (Инструкция для LLM):** 
Пожалуйста, пройдись по указанным файлам. Убедись, что новые пути не ломают существующие эндпоинты (если эндпоинту `split` передали `project_name`, переопредели его `output_dir` на `WORKSPACE_DIR / project_name / "panels"` на бэкенде). После внесения изменений выведи список обновленных файлов.
```

***

### Что дальше?
Просто кидай этот промпт в свою локальную IDE (Roo Code / Cursor). Она прочитает его как техническое задание, найдет нужные файлы через `REPO_MAP.md` и перепишет логику. 

Я буду здесь и продолжу трекать этот Roadmap. Если во время внедрения у твоей локальной LLM возникнут ошибки импортов или конфликты в `server.py` — кидай ошибки сюда, я мгновенно помогу их разрешить. Работаем!

=========================================

Понял тебя на 100%. Это финальный и очень правильный штрих. Передача высокоуровневого контекста (намерения) — это именно то, что отличает механическое переписывание кода от осмысленного рефакторинга. Если LLM понимает *зачем* она это делает, она сама найдет и исправит мелкие нестыковки в коде, которые мы могли упустить.

Вот сжатый, но максимально емкий документ с контекстом. Скопируй его и передай локальной LLM вместе с предыдущим манифестом.

***

```markdown
# 🧠 КОНТЕКСТ И ПРЕДПОСЫЛКИ РЕФАКТОРИНГА: Comix_Split (Workspace Paradigm)

## 📖 Историческая справка (Почему мы это делаем)
Изначально приложение `Comix_Split` строилось как набор независимых утилит (Вкладки: Split -> Upscale -> Video -> ExText). Каждая вкладка требовала ручного ввода путей (input/output) и ничего не знала о соседних. 
В процессе развития мы внедрили "Проекты", но только на финальном этапе (вкладка ExText), что привело к архитектурным проблемам: дублированию файлов (копирование картинок при создании проекта) и рассинхронизации UI. Опция "Сохранить пресет в YAML" оказалась невостребованной и лишь перегружала интерфейс.

## 🎯 Архитектурное видение (Что мы строим)
Мы переводим приложение на **Гибридную Workspace-архитектуру**. 
Приложение должно работать в двух режимах:
1. **Автономный режим (Без проекта):** Вкладка работает как независимая утилита (ручные пути).
2. **Конвейерный режим (В рамках проекта):** Глобальный стейт. Пользователь создает "Проект" на первой вкладке (Split), а остальные вкладки автоматически подхватывают его имя и сами вычисляют пути (`[Workspace]/[Project_Name]/panels`, `../upscale` и т.д.).

## ⚔️ Главные боли, которые мы решаем (Focus Points для LLM)

1. **Отсутствие консистентности UI:** Вкладка `ExText` умеет работать с папками (batch) и имеет удобную карусель просмотра. Вкладка `Split` работает по одному файлу. 
   👉 *Решение:* Полностью скопировать механику пакетной загрузки и карусель из ExText во вкладку Split. Привести UI к единому стандарту.

2. **Бесполезный чекбокс YAML:** Во всех вкладках висит чекбокс "Сохранить в YAML", который больше не нужен.
   👉 *Решение:* Заменить его на чекбокс "Создать/Работать в проекте" + поле ввода с выпадающим списком (`<datalist>`) существующих проектов.

3. **Жесткое дублирование данных (Data Duplication):** Сейчас при инициализации `Stage 2a` (ExText) бэкенд физически копирует картинки в новую папку проекта. Это избыточно, так как проект теперь создается еще на этапе Split.
   👉 *Решение:* Внедрить принцип Single Source of Truth (Единый источник истины). ExText больше ничего не копирует. Он читает готовые файлы напрямую из `[Project]/panels` или `[Project]/upscale`, а в итоговый `stage_2a.json` пишет строго *относительные* пути (например, `"image_path": "panels/page1.png"`), чтобы проект можно было перемещать в ОС без поломки ссылок.

## 🤖 Инструкция для ИИ
Используй этот контекст для правильной интерпретации "Интеграционного манифеста". Если при внесении правок ты встретишь старый код, который противоречит парадигме **Workspace** или **Отсутствию дублирования**, — смело рефактори его в угоду консистентности.
```

***

**Твой идеальный промпт для ввода в Cursor / Roo Code теперь выглядит так:**
> "Привет. Изучи два документа ниже. Первый — это контекст и предпосылки задачи. Второй — это Интеграционный манифест с конкретными кусками кода. Твоя задача: изучить материал, проанализировать текущую кодовую базу и выполнить все правки строго по манифесту, сохраняя консистентность проекта." + *(вставляешь оба текста)*.

Мы упаковали задачу идеально. Можешь запускать свою LLM в бой! Если что-то пойдет не так или LLM запнется на интеграции FastAPI — я здесь, сразу кидай логи ошибок.
# Workspace & UI консистентность — синтезированная спецификация

**Версия:** 1.0  
**Дата:** июнь 2026  
**Статус:** Готово к реализации  
**Источники:** `SplitTabRefactoring_google.md` (основа), `SplitTabRefactoring.md` v4.1 (выборочно)  
**Связанные документы:** [ARCHITECTURE.md](ARCHITECTURE.md), [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md), [STORY_ANALYZER_STAGE_2A.md](STORY_ANALYZER_STAGE_2A.md)

---

## 1. Зачем этот документ

Приложение выросло из **набора независимых вкладок** (Split → Upscale → Video → ExText). ExText уже умеет проекты и пакетную навигацию; Split — нет. ExText **копирует** PNG в `project/panels/`, хотя Split мог бы писать туда сразу.

**Цель синтеза:** один осознанный план внедрения **только по болям Google-дока**, без Story Analyzer 2b–7, Voice Library, OTIO и прочего из v4.1.

---

## 2. Боли → решения (scope)

| # | Боль | Решение |
|---|------|---------|
| 1 | Split — одна страница, ExText — папка + навигация | Пакет страниц в Split + prev/next как у ExText, **Konva сохраняется** |
| 2 | Нет единого «Проекта» между вкладками | Глобальный `current_project` + `<datalist>` на всех вкладках |
| 3 | Чекбокс «Сохранить в YAML» перегружает UI | Оставить **только в блоке пресетов** (он уже там); не дублировать на каждой вкладке |
| 4 | ExText копирует PNG (`sync_panels_to_project`) | Читать из `panels/` проекта; в JSON — **относительные** пути |
| 5 | Upscale/Video — ручные input/output | В режиме проекта — авто-пути из workspace |

### Вне scope (не делать в этом цикле)

- Stage 2b–7, Sandbox/Standalone, `references.json` с checksum
- Новые файлы `split_refactored.*`, `project_manager.py` (дублируют `story_analyzer/paths.py`)
- `webkitdirectory` / загрузка папки в браузер (ломает CBZ, кириллицу, `pickPath`)
- Полный roadmap v4.1

### Из v4.1 взять выборочно

- Grid миниатюр **панелей** после экспорта (опционально, фаза 2b)
- Pydantic-валидация при сохранении ExText (уже есть — не трогать)
- Критерии успеха R1 как чеклист приёмки

---

## 3. Архитектура Workspace

### 3.1 Единый источник истины

Использовать **существующий** модуль, не дублировать:

```text
story_analyzer/paths.py
  STORY_PROJECTS_ROOT = story_out/projects/
  project_dir(name)   → story_out/projects/<sanitized_name>/
  panels_dir(name)    → .../panels/
  stage_2a_json_path  → .../stage_2a.json
```

Константу `WORKSPACE_DIR` в коде **не вводить** — импортировать `STORY_PROJECTS_ROOT` / `project_dir` / `panels_dir`.

### 3.2 Структура проекта

```text
story_out/projects/<Project_Name>/
├── panels/          ← Split (экспорт PNG)
├── upscale/         ← Upscale (режим проекта)
├── video/           ← Video (клипы, storyboard; режим проекта)
└── stage_2a.json    ← ExText
```

Имена папок фиксированы. Санитизация имени — `sanitize_project_name()` (кириллица → `_`, как сейчас).

### 3.3 Два режима работы (гибрид)

| Режим | Поведение |
|-------|-----------|
| **Автономный** (чекбокс «Проект» выкл.) | Как сейчас: ручные пути, произвольный `out-dir` |
| **Проектный** (чекбокс вкл.) | Имя проекта обязательно; пути вычисляет бэкенд/JS; поля input/output **readonly** |

Проект создаётся **лениво**: при первом экспорте Split или init ExText — `mkdir` для `project_dir` и подпапок.

### 3.4 Глобальный state

| Поле | Где хранить | Назначение |
|------|-------------|------------|
| `current_project` | `ui_state.global` + `localStorage` | Шарится между вкладками |
| `use_project` | секции `split` / `upscale` / `video` / `story2a` | Включён ли проектный режим на вкладке |

Файлы: `utils/ui_state.py`, `frontend/ui_state.js`, `config/ui_state.user.json`.

---

## 4. UI-стандарт

### 4.1 Project bar (на каждой вкладке)

Единый паттерн (стили — как у существующих `.trow` / `.path-row`):

```html
<div class="project-bar" data-tab="split">
  <label class="trow">
    <span class="tlbl">Работать в проекте</span>
    <label class="tog"><input type="checkbox" id="split-use-project"><span class="sl"></span></label>
  </label>
  <label class="lbl">Проект</label>
  <input type="text" id="split-project" list="projects-datalist" class="inp" placeholder="СоколГлаз" disabled />
</div>
<datalist id="projects-datalist"></datalist>
```

**ID по вкладкам:**

| Вкладка | checkbox | project input | panels/source | output |
|---------|----------|---------------|---------------|--------|
| Split | `split-use-project` | `split-project` | `img-path` + **новое** `split-folder-path` | `out-dir` |
| Upscale | `up-use-project` | `up-project` | `up-panels` | `up-output` |
| Video | `vid-use-project` | `vid-project` | `vid-panels` | `vid-output` |
| ExText | `s2a-use-project` | `s2a-project` (уже есть) | `s2a-panels-dir` | `s2a-json-path` |

При включении проекта: синхронизировать все `*-project` с `current_project`; при смене имени на одной вкладке — обновлять остальные и `global.current_project`.

### 4.2 Навигация Split ≈ ExText

**Не** карусель `<img>` из File API. **Да:**

- Источник пакета: **папка или CBZ** через `pickPath` / существующий API (как Upscale), поле `split-folder-path`
- Список страниц с сервера или из индекса после scan
- В sidebar: `◀ Пред.` / `След. ▶` + счётчик `Стр. 3 / 24` — **те же классы кнопок**, что `s2a-prev` / `s2a-next` / `#s2a-panel-nav`
- Центр: **существующий Konva** (`#kv`, `runDetection()`, `exportPanels()`)

Логика prev/next — вынести в общий модуль `frontend/panel_nav.js` (DRY с ExText), если дублирование > 30 строк.

### 4.3 ExText без изменения канваса

ExText уже имеет навигацию по **панелям**. Меняется только:

- источник PNG (workspace `panels/` вместо copy);
- автозаполнение `s2a-panels-dir` в проектном режиме;
- опционально: тот же `<datalist>` для имени проекта.

---

## 5. Roadmap реализации

### Фаза 1 — Backend + API проектов + global state

**Файлы:** `story_analyzer/paths.py`, `api/server.py`, `utils/ui_state.py`, `frontend/ui_state.js`

**Задачи:**

1. Добавить хелперы (если нет):

```python
# story_analyzer/paths.py
def upscale_dir(project: str) -> Path: ...
def video_dir(project: str) -> Path: ...
def ensure_project_layout(project: str) -> Path:
    """mkdir panels/, upscale/, video/; return project_dir."""
```

2. Эндпоинт списка проектов (скан директорий, без `projects.json`):

```http
GET /api/projects → { "projects": ["СоколГлаз", "test_2a", ...] }
```

Реализация: `[d.name for d in STORY_PROJECTS_ROOT.iterdir() if d.is_dir() and not d.name.startswith('.')]`, сортировка.

3. Опционально:

```http
GET /api/projects/{name}/layout → { "panels": "...", "upscale": "...", "video": "...", "stage_2a_json": "..." }
```

4. В `default_global()` добавить `"current_project": ""`.
5. В `ui_state.js`: `collectGlobal()` / `applyGlobal()` — поле `current_project`; при старте `loadProjectsDatalist()`.

**Критерий успеха:**

- [ ] `GET /api/projects` возвращает реальные папки из `story_out/projects/`
- [ ] `current_project` переживает перезагрузку страницы
- [ ] `<datalist id="projects-datalist">` заполняется при загрузке

---

### Фаза 2 — Split: проект + пакет страниц + навигация

**Файлы:** `frontend/index.html`, `frontend/ui_state.js`, `frontend/panel_nav.js` (новый, опционально), `api/server.py`

**Задачи:**

1. **UI:** project bar в `#tab-split`; поле «Папка/CBZ с страницами» (`split-folder-path` + `pickPath` folder/file).
2. **Пакет:** эндпоинт или reuse:

```http
POST /api/split/list_pages
{ "source_path": "exam_imgs/mycomic" }  → { "pages": ["page001.jpg", ...], "resolved_path": "..." }
```

Использовать `utils/io_helpers` + `pipeline` там, где уже есть list images / CBZ.

3. **Навигация:** массив `splitPagePaths[]`, индекс `splitPageIndex`; prev/next переключают `img-path` и вызывают `runDetection()` или только `initCanvas` если панели уже правились (см. §5.1).
4. **Экспорт в проект:** если `split-use-project` и `split-project`:

   - `out-dir` = `panels_dir(project)` (readonly, показать пользователю);
   - `ensure_project_layout(project)` перед export;
   - после export — подставить путь в `up-panels`, `vid-panels`, `s2a-panels-dir` если их проектный режим вкл.

5. **Автономный режим:** без изменений (текущий flow).

**§5.1 Сохранение правок при листании страниц**

Минимальная стратегия v1: при prev/next **предупреждать**, если есть несохранённые панели на текущей странице, или auto-export в temp.  
Целевая v1.1 (из v4.1): кэш `{ pagePath → panels[] }` в памяти до финального export batch.

**Критерий успеха:**

- [ ] Split: checkbox проекта + datalist
- [ ] Пакет из папки/CBZ, prev/next по страницам
- [ ] Konva-редактор работает как сейчас
- [ ] Export в `story_out/projects/<name>/panels/` в проектном режиме
- [ ] После export ExText может открыть те же PNG без ручного пути

---

### Фаза 3 — Upscale & Video: транзит контекста

**Файлы:** `frontend/index.html`, `frontend/ui_state.js`, `api/server.py` (эндпоинты upscale/video)

**Задачи:**

1. Project bar на `#tab-upscale` и `#tab-video` (`up-use-project`, `vid-use-project`).
2. При включённом проекте:

   | Вкладка | Input (readonly) | Output (readonly) |
   |---------|------------------|-------------------|
   | Upscale | `panels_dir(project)` | `upscale_dir(project)` |
   | Video | `upscale_dir(project)` или `panels_dir` если upscale пуст | `video_dir(project)` |

   Приоритет input для Video: если в `upscale/` есть PNG — брать оттуда, иначе `panels/`.

3. Бэкенд: принимать опциональный `project_name`; если передан — игнорировать/переопределять `panels_dir`/`output_dir` после resolve.

4. После успешного Upscale в проекте — предложить подставить `s2a-panels-dir` = upscale (toast или auto).

**Критерий успеха:**

- [ ] В проектном режиме ручные пути заблокированы
- [ ] Upscale пишет в `<project>/upscale/`
- [ ] Video пишет в `<project>/video/`
- [ ] Имя проекта совпадает с Split/ExText

---

### Фаза 4 — ExText: убрать дублирование

**Файлы:** `story_analyzer/stages/stage_2a_processor.py`, `api/story_stage_2a.py`, `frontend/story_2a.js`

**Задачи:**

1. **`sync_panels_to_project`:** новый параметр `copy: bool = False` по умолчанию в проектном режиме; при `copy=False` — только `ensure_project_layout` + чтение из переданной папки (должна быть `panels/` проекта или symlink).

2. **`/init` и `/run`:** если `panels_dir` указывает на `project/panels` — **не копировать**.

3. **`image_path` в JSON:** всегда относительный от корня проекта:

```json
"image_path": "panels/001_p001_panel.png"
```

(resolver: `project_dir / panel.image_path`)

4. **`resolve_panel_display_path`:** при `source_only=True` и project mode — только `project_dir / image_path`; fallback на copy убрать для новых проектов.

5. **UI:** `s2a-use-project`; при вкл. — `s2a-panels-dir` = auto `panels/` (или `upscale/` если пользователь выбрал upscaled source); `s2a-json-path` = default `stage_2a_json_path`.

6. **Миграция старых JSON:** если `image_path` абсолютный — читать как сейчас; при save — нормализовать в относительный.

**Критерий успеха:**

- [ ] Init ExText для проекта после Split **не создаёт дубликаты** PNG
- [ ] JSON переносим: копия папки проекта на другой диск работает
- [ ] Существующие проекты с копиями в `panels/` продолжают открываться
- [ ] `source_only` / `boundPanelsDir` не регрессируют (см. fix mixed PNG)

---

## 6. API — сводка изменений

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/api/projects` | Список имён проектов |
| GET | `/api/projects/{name}/layout` | Пути подпапок (опционально) |
| POST | `/api/split/list_pages` | Индекс страниц для пакетного Split |
| POST | `/api/export` | + опц. `project_name` → output override |
| POST | upscale/video endpoints | + опц. `project_name` |

Существующие `/api/story/stage_2a/*` — расширить флагом `use_project_layout: bool`, не ломать контракт.

---

## 7. Правила для LLM / разработчика

1. **Редактировать существующие файлы**, не создавать параллельные `*_refactored.*`.
2. **DRY:** общая навигация → `panel_nav.js`; пути → `story_analyzer/paths.py`.
3. **pickPath + server-side paths** для кириллицы и CBZ; не `webkitdirectory`.
4. **Не ломать** Gradio `:7860` — изменения `ui_state` должны быть backward-compatible (`UI_STATE_VERSION` bump при необходимости).
5. **Тесты:** добавить/обновить `tests/test_stage_2a*.py`, новый `tests/test_workspace_paths.py` для layout и `GET /api/projects`.
6. При противоречии с Workspace — **рефакторить старый код**, не добавлять второй путь.

---

## 8. Порядок внедрения и оценка

| Шаг | Фаза | Оценка | Риск |
|-----|------|--------|------|
| 1 | Фаза 1 | 0.5–1 день | Низкий |
| 2 | Фаза 4 (только `copy=False` + relative paths) | 1 день | Средний — ExText |
| 3 | Фаза 2 | 2–3 дня | Средний — Split batch + Konva |
| 4 | Фаза 3 | 1–2 дня | Низкий |

**Рекомендация:** Фаза 1 → **4** (dedup) → **2** (Split) → **3** (Upscale/Video), чтобы ExText сразу читал то, что Split пишет.

---

## 9. Чеклист приёмки (сквозной сценарий)

1. Создать проект «test_ws» на Split (проектный режим).
2. Обработать папку из 3+ страниц, prev/next, правка bbox, export.
3. Открыть ExText → тот же проект → init/load без copy → OCR.
4. Upscale в проекте → PNG в `upscale/`.
5. Video в проекте → выход в `video/`.
6. Перезапуск UI → `current_project` и datalist на месте.
7. Автономный режим Split без проекта — старый сценарий с `output/` работает.

---

## 10. Открытые решения (уточнить перед кодом)

| # | Вопрос | Рекомендация по умолчанию |
|---|--------|---------------------------|
| A | Video input: `panels/` или `upscale/`? | `upscale/` если не пуст, иначе `panels/` |
| B | Санитизация «СоколГлаз» → `_____` — OK? | Да, как `sanitize_project_name`; UI показывает введённое имя, путь — sanitized |
| C | Удалять `sync_panels` совсем или оставить флаг для legacy? | Флаг `copy=True` только для явного «Импорт из внешней папки» |
| D | Grid миниатюр панелей после Split (v4.1)? | **Post-MVP** — после фазы 2 |

Если пункты A–C устраивают — **можно начинать Фазу 1 без дополнительных вопросов.**

---

## 11. Связь с другими документами

| Документ | Роль после принятия этого spec |
|----------|--------------------------------|
| `SplitTabRefactoring_google.md` | Исторический промпт; superseded by этот файл |
| `SplitTabRefactoring.md` | Backlog Story Analyzer 2b–7; **не** часть текущего scope |
| [WEB_LLM_GIT_WORKFLOW.md](WEB_LLM_GIT_WORKFLOW.md) | После merge — обновить REPO_MAP |

**Документ готов к передаче в Cursor / локальную LLM:** «Реализуй фазы 1→4 по `spec_s/WORKSPACE_REFACTORING_SPEC.md`».

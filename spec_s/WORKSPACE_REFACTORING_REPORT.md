# Workspace & project mode — реализация и отчёт

**Версия:** 1.1 (июнь 2026)  
**Статус:** ✅ Реализовано (API v1.5, UI combobox)  
**Связанные документы:** [ARCHITECTURE.md](ARCHITECTURE.md), [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md), [ComicSplit_Documentation.md](ComicSplit_Documentation.md)

---

## 1. Боли → решения (scope)

| # | Боль | Решение | Статус |
|---|------|---------|--------|
| 1 | Split — одна страница; ExText — папка + навигация | Пакет страниц в Split + prev/next (`POST /api/split/list_pages`), Konva без изменений | ✅ |
| 2 | Нет единого «Проекта» между вкладками | `current_project` в `ui_state`; combobox «Имя проекта»; чекбокс **«Проект»**; `workspace.js` | ✅ |
| 3 | ExText копирует PNG (`sync_panels_to_project`) | `copy_panels: false` в проектном режиме; относительные `image_path` при save | ✅ |
| 4 | Upscale/Video — ручные пути | Проектный режим блокирует пути; API `project_name` → `panels/` / `upscale/` / `video/` | ✅ |

### Вне scope (не делали)

- Stage 2b–7, Sandbox/Standalone, `references.json` с checksum
- `webkitdirectory` / загрузка папки в браузер
- Grid миниатюр панелей после Split (post-MVP)

---

## 2. Архитектура Workspace

### 2.1 Единый источник истины

```text
story_analyzer/paths.py
  STORY_PROJECTS_ROOT = story_out/projects/
  project_dir(name)   → story_out/projects/<sanitized_name>/
  panels_dir(name)    → .../panels/
  upscale_dir(name)   → .../upscale/
  video_dir(name)     → .../video/
  stage_2a_json_path  → .../stage_2a.json
  ensure_project_layout(name) → mkdir всех подпапок
```

### 2.2 Структура проекта

```text
story_out/projects/<Project_Name>/
├── panels/          ← Split (экспорт PNG)
├── upscale/         ← Upscale (режим проекта)
├── video/           ← Video (клипы, storyboard)
└── stage_2a.json    ← ExText
```

### 2.3 Два режима работы

| Режим | Поведение |
|-------|-----------|
| **Автономный** (чекбокс «Проект» выкл.) | Ручные пути, произвольный `output/` |
| **Проектный** (чекбокс вкл.) | Имя проекта обязательно; пути вычисляет бэкенд; поля readonly |

Проект создаётся **лениво**: при первом экспорте Split или init ExText.

### 2.4 Глобальный state

| Поле | Где | Назначение |
|------|-----|-----------|
| `current_project` | `ui_state.global` + `localStorage` | Шарится между вкладками |
| `use_project` | секции `split` / `upscale` / `video` / `story2a` | Вкл/выкл на вкладке |

---

## 3. Изменённые / новые файлы

### Backend

| Файл | Изменение |
|------|-----------|
| `story_analyzer/paths.py` | `upscale_dir`, `video_dir`, `ensure_project_layout`, `list_workspace_projects`, `should_sync_panels` |
| `utils/workspace_paths.py` | **новый** — resolve путей для export/upscale/video |
| `utils/split_pages.py` | **новый** — `list_split_pages()` (папка, файл, CBZ/ZIP) |
| `api/server.py` | v1.5.0: `GET /api/projects`, `GET /api/projects/{name}/layout`, `POST /api/split/list_pages`; `project_name` в export/upscale/animate |
| `story_analyzer/stages/stage_2a_processor.py` | dedup, `normalize_document_image_paths`, `copy_panels` |
| `api/story_stage_2a.py` | поле `copy_panels` в init/process/sync |
| `utils/ui_state.py` | `current_project`, `use_project`, `project` в секциях |

### Frontend

| Файл | Изменение |
|------|-----------|
| `frontend/workspace.js` | **новый** — project mode, combobox, layout, авто-пути |
| `frontend/panel_nav.js` | **новый** — prev/next для страниц Split |
| `frontend/ui_state.js` | persist/restore workspace fields |
| `frontend/index.html` | project bars, split batch UI, hooks export/upscale/video |
| `frontend/story_2a.js` | `copy_panels: false` при `s2a-use-project` |

### Tests

| Файл | Изменение |
|------|-----------|
| `tests/test_workspace_paths.py` | **новый** — layout, list_pages, should_sync |

---

## 4. API (workspace)

```
GET  /api/projects                       → { "projects": ["СоколГлаз", ...] }
GET  /api/projects/{name}/layout         → { "panels": "...", "upscale": "...", "video": "...", "stage_2a_json": "..." }
POST /api/split/list_pages               → { "pages": [...], "resolved_path": "..." }
POST /api/export                         + project_name, flat_export
POST /api/upscale                        + project_name
POST /api/animate                        + project_name
POST /api/story/stage_2a/init           + copy_panels (optional)
POST /api/story/stage_2a/process        + copy_panels (optional)
```

---

## 5. Чеклист ручного теста

1. **Split, проект:** включить **«Проект»**, имя `test_ws`, папка со страницами → «Загрузить список страниц» → prev/next → детекция → export.
2. **ExText:** тот же проект → «Создать из папки» — **без** дублирования PNG.
3. **Upscale/Video:** project mode — пути readonly, выход в `upscale/` и `video/`.
4. **Combobox:** клик по полю → полный список проектов; Enter → подтверждение.
5. **Перезагрузка** `:8000` — имя проекта и список на месте.
6. **Автономный Split** (без проекта) — export в `output/` как раньше.

---

## 6. Ограничения v1 (осознанно)

- При prev/next **нет** auto-export правок страницы — перед сменой страницы экспортируйте вручную.
- CBZ: при `list_pages` архив распаковывается в `story_out/.split_cache/`.
- Video UI в проектном режиме показывает `panels/` до запуска; бэкенд при `project_name` сам выберет `upscale/` если там есть PNG.
- Grid миниатюр панелей — **не** делали (post-MVP).

---

## 7. Исторический контекст

Исходная спека: `WORKSPACE_REFACTORING_SPEC.md` (фазы 1–4, UI-стандарт, API). Спека полностью реализована и удалена. Конечный результат документа — §§1–6 выше. Подробный промпт и эволюцию решений см. в [archive/](archive/).

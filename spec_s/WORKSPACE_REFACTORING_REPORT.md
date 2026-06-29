# Отчёт: Workspace refactoring (Google-док / WORKSPACE_REFACTORING_SPEC)

**Дата:** июнь 2026  
**Статус:** реализовано и проверено в UI

---

## Сводка по болям Google-док

| # | Боль | Статус | Что сделано |
|---|------|--------|-------------|
| 1 | Split — одна страница; ExText — папка + навигация | ✅ | Папка/CBZ через `split-folder-path` + `POST /api/split/list_pages`; prev/next (`split-page-prev/next`); Konva без изменений |
| 2 | Нет единого «Проекта» между вкладками | ✅ | `current_project` в `ui_state`; combobox «Имя проекта» (как `select.inp`); чекбокс **«Проект»**; `frontend/workspace.js` |
| 3 | Чекбокс «Сохранить в YAML» перегружает UI | ✅ | Не трогали — остаётся **только** в блоке пресетов (как в spec) |
| 4 | ExText копирует PNG | ✅ | `copy_panels: false` в проектном режиме; `should_sync_panels()` / `panels_dir_is_source()`; относительные `image_path` при save |
| 5 | Upscale/Video — ручные пути | ✅ | Проектный режим блокирует пути; API `project_name` → `panels/` / `upscale/` / `video/` |

---

## Изменённые / новые файлы

### Backend
| Файл | Изменение |
|------|-----------|
| `story_analyzer/paths.py` | `upscale_dir`, `video_dir`, `ensure_project_layout`, `list_workspace_projects`, `should_sync_panels`, … |
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

## API (новое / расширенное)

```
GET  /api/projects
GET  /api/projects/{name}/layout
POST /api/split/list_pages          { "source_path": "..." }
POST /api/export                    + project_name, flat_export
POST /api/upscale                   + project_name
POST /api/animate                   + project_name
POST /api/story/stage_2a/init       + copy_panels (optional)
POST /api/story/stage_2a/process    + copy_panels (optional)
```

---

## Структура workspace

```
story_out/projects/<Project>/
├── panels/      ← Split export (проектный режим)
├── upscale/     ← Upscale
├── video/       ← Video
└── stage_2a.json
```

---

## Сценарий ручного теста (чеклист)

1. **Split, проект:** включить **«Проект»**, имя `test_ws`, папка со страницами → «Загрузить список страниц» → prev/next → детекция → export.
2. **ExText:** тот же проект, **«Проект»** → «Создать из папки» — **без** дублирования PNG (размер `panels/` не удваивается).
3. **Upscale/Video:** project mode — пути readonly, выход в `upscale/` и `video/`.
4. **Combobox:** при выбранном имени клик по полю показывает **полный** список проектов; Enter — подтверждение нового имени.
5. **Перезагрузка** `:8000` — имя проекта и список на месте.
6. **Автономный Split** (без проекта) — export в `output/` как раньше.

---

## Ограничения v1 (осознанно)

- При prev/next **нет** auto-export правок страницы — перед сменой страницы экспортируйте вручную (spec §5.1).
- CBZ: при `list_pages` архив **распаковывается** в `story_out/.split_cache/` (server-side).
- Video UI в проектном режиме показывает `panels/` до запуска; бэкенд при `project_name` сам выберет `upscale/` если там есть PNG.
- Grid миниатюр панелей — **не** делали (post-MVP).
- `pytest` в текущем shell не запускался (нет `numpy`/`cv2` в системном Python) — тесты добавлены, прогон в вашем venv.

---

## Что проверить при обсуждении

- Устраивает ли flat export `{pageStem}_{nnn}_{panel_id}_panel.png` в `panels/`?
- Нужен ли prompt «несохранённые панели» при prev/next?
- Санитизация имени проекта (кириллица → `_`) — OK?

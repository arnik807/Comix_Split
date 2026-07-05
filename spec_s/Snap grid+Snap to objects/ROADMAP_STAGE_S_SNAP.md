# ComicSplit — Блок S: Snap grid / Snap to objects (Split, :8000)

**Статус:** ✅ **Закрыт** (S1–S3 + доработки, приёмка 5 июля 2026)  
**Версия:** 1.2 (5 июля 2026)  
**Родитель:** [ROADMAP.md](../ROADMAP.md) → блок **S**  
**Код:** rect-режим Split, Konva (`frontend/index.html`); persist — `ui_state`  
**Вне scope:** полигон-вершины (S6), ExText bbox (S6), новые API-эндпоинты

---

## 1. Проблема

В rect-режиме Split правка bbox шла без привязки — соседние панели расходились на 1–5 px, ручная подгонка на тачпаде была медленной и неточной.

## 2. Решение (UI)

Секция **③ Режим редактирования** — radio **Выкл / Сетка / Объекты**:

| Режим | Поведение |
|-------|-----------|
| **Выкл** | Как до блока S (дефолт) |
| **Сетка** | Округление до шага (дефолт 8 px, слайдер **2–40 px**) |
| **Объекты** | Магнит к краям соседних панелей и страницы, порог **8 px** (`SNAP_OBJECT_THRESHOLD`) |

Только **rect-режим** (не полигон). Persist: `ui_state.split.snap_mode`, `snap_grid_step`.

## 3. Карта интеграции (факт)

| Слой | Файл | Реализация |
|------|------|------------|
| UI | `frontend/index.html` | `#split-snap-mode`, `#split-snap-step`, `S.snapMode`, `S.snapGridStep` |
| Snap-модуль | `frontend/index.html` | `_snapCandidates`, `_bestSnapOrigin1D`, `applySnapMoveOrigin`, `applySnap`, `nudgeSelectedPanel` |
| Drag/resize | `renderRectPanel()` | move → `applySnapMoveOrigin`; corner → `applySnap` |
| Persist JS | `frontend/ui_state.js` | collect/apply + `SECTION_ENUM_FIELDS.split` |
| Persist PY | `utils/ui_state.py` | `default_split()`, `_merge_split()` |
| Tooltips | `utils/ui_tooltips.py` | `snap_mode`, `snap_grid_step` |
| Экспорт (fix) | `frontend/index.html`, `frontend/workspace.js`, `utils/workspace_paths.py` | свой `out-dir` не затирается project layout |
| Тесты | `tests/test_ui_state.py` | дефолты и patch `snap_mode` |

## 4. Алгоритмы

### 4.1. Grid (S2)

`Math.round(coord / step) * step` — на move для origin; на resize для угла.

### 4.2. Objects (S3)

**Кандидаты:** `0`, `imgW`/`imgH`, все `x1,x2,y1,y2` чужих панелей.

**Move (drag / стрелки):** `applySnapMoveOrigin(nx1, ny1, w, h, …)` — одна точка top-left, фиксированный размер. На каждой оси `_bestSnapOrigin1D` проверяет **leading** (`origin`) и **trailing** (`origin + size`) края; ближайший snap в пределах порога. Симметричное прилипание сверху/снизу и слева/справа.

**Resize:** `applySnap(ix, iy)` на двигаемый угол.

**Стрелки:** `snapNudgeStep()` — grid: шаг сетки; objects/off: 1 px. Отлипание: `_snapEdgeEscape` + `nudgeDx`/`nudgeDy` (только стрелки; drag — `axisDelta=0`).

### 4.3. Горячие клавиши

| Клавиша | Действие |
|---------|----------|
| Arrow↑↓←→ | Nudge выбранной панели (rect, не в input, не poly) |
| Delete | Удалить панель |
| + / − / 0 | Zoom канвы |

### 4.4. Backlog (не в S1–S3)

| # | Задача | Статус |
|---|--------|--------|
| S4 | Guide-lines | 📋 |
| S5 | Shift-bypass | 📋 |
| S6 | Snap для ExText / полигона | 📋 |

## 5. Критерии приёмки — ✅ пройдены (05.07.2026)

1. Radio + persist + сброс Split  
2. Сетка: координаты кратны шагу  
3. Объекты: стык соседних панелей ±0 px; все стороны симметрично  
4. Выкл: регрессия  
5. Полигон не затронут  
6. Экспорт: формат API прежний; произвольная папка `out-dir` сохраняется  
7. Стрелки + отлипание от края  
8. `tests/test_ui_state.py` — pass  

## 6. Коммит (рекомендуемый message)

```
feat: snap grid/objects в Split (:8000) — S1–S3, стрелки, export path fix
```

Сопутствующие файлы: см. [S1_S3_SNAP_IMPLEMENTATION_PACKAGE.md](S1_S3_SNAP_IMPLEMENTATION_PACKAGE.md).

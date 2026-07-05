# Блок S1–S3 — пакет реализации и reference

**Статус:** ✅ **Внедрено и принято** (5 июля 2026)  
**Спека этапа:** [ROADMAP_STAGE_S_SNAP.md](ROADMAP_STAGE_S_SNAP.md)

**Дефолты:** `snap_mode: off`, `snap_grid_step: 8`, порог objects: `8 px` (константа).

---

## Актуальный snap-модуль (`frontend/index.html`)

```text
SNAP_OBJECT_THRESHOLD = 8

_snapCandidates(excludePanelId)     → { xs, ys }  // страница + края других панелей
_snapNearest(raw, candidates, t, axisDelta)      // resize + legacy point snap
_snapEdgeEscape(edge, candidate, axisDelta)     // отлипание при nudge
_bestSnapOrigin1D(origin, size, candidates, t, axisDelta)  // leading/trailing на одной оси
applySnapMoveOrigin(nx1, ny1, w, h, panelId, nudgeDx, nudgeDy)  // move (drag + стрелки)
applySnap(ix, iy, panelId, nudgeDx, nudgeDy)    // resize угол
setSnapMode(mode)                   // radio onchange
snapNudgeStep()                     // шаг для Arrow keys
nudgeSelectedPanel(dx, dy)          // keydown Arrow↑↓←→
```

**Вызовы:**

| Операция | Функция |
|----------|---------|
| `box.on('dragmove')` | `applySnapMoveOrigin(..., 0, 0)` |
| `handles[i].on('dragmove')` | `applySnap(rawX, rawY, …)` |
| `keydown` Arrow | `nudgeSelectedPanel(dx, dy)` |

**Persist:** `snap_mode` ∈ `off|grid|objects`, `snap_grid_step` ∈ 2–40.

---

## Дополнительно в этом релизе (не в исходном MVP-патче)

| Пункт | Файлы |
|-------|--------|
| UI scale sidebar | `frontend/index.html` — `--fs-base: 15px`, `--fw: 380px` |
| Экспорт в свою папку | `exportPanels()` без `applyProjectPaths`; `resolve_export_output_dir`; `workspace.js` — `out-dir` редактируемый |
| Симметричный object-snap | `_bestSnapOrigin1D` (не `applySnapMoveBBox` — давал дрожание) |
| Отлипание стрелкой | `_snapEdgeEscape` + `nudgeDx`/`nudgeDy` |

---

## Изменённые файлы (коммит)

| Файл | Суть |
|------|------|
| `frontend/index.html` | Snap-модуль, UI, стрелки, CSS scale |
| `frontend/ui_state.js` | `snap_mode`, `snap_grid_step`, enum merge |
| `frontend/workspace.js` | `out-dir` в project mode |
| `utils/ui_state.py` | дефолты, `_merge_split()` |
| `utils/ui_tooltips.py` | подсказки snap |
| `utils/workspace_paths.py` | приоритет явного `output_dir` |
| `tests/test_ui_state.py` | snap defaults + patch |
| `tests/test_workspace_paths.py` | `resolve_export_output_dir` (если env с numpy) |

---

## Чек-лист приёмки — ✅

1. Выкл = поведение до патча  
2. Сетка, шаг 8 (и 2, 3…) — координаты кратны шагу  
3. Объекты — стык с любой стороны; верхняя/нижняя панель симметрично  
4. F5 — режим и шаг восстанавливаются  
5. ↺ Сброс Split → Выкл / 8  
6. Полигон без snap  
7. Экспорт в указанную папку  
8. Стрелки + отлипание от края  
9. pytest `test_ui_state.py` — ok  

---

## Исторические патчи (архив)

Ниже — исходные diff-блоки на момент первого внедрения (5.07.2026). **Канон — секция «Актуальный snap-модуль» выше**, не дословные фрагменты патчей (move использует `applySnapMoveOrigin`, не `applySnap(nx1,ny1)`).

### Файл 1/4: `frontend/index.html`

#### 1.1 — состояние `S`

```javascript
    snapMode: 'off',
    snapGridStep: 8,
```

#### 1.2 — UI секция ③

Radio `name="split-snap-mode"`, `<details>` шаг сетки `#split-snap-step` min=2 max=40.

#### 1.3–1.6

Snap-хелперы, `clearSplitEditorState` сброс snap — см. код в репозитории.

### Файлы 2–4

`frontend/ui_state.js`, `utils/ui_state.py`, `utils/ui_tooltips.py` — как в таблице «Изменённые файлы».

---

## Промпт для LLM (архив)

Использовать только при повторном порте на другую ветку. Актуальный контекст — `ROADMAP_STAGE_S_SNAP.md` + reference выше.

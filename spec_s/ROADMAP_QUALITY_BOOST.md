# Roadmap: раскрытие потенциала качества ComicSplit

**Версия:** 1.3 (2 июня 2026)  
**Целевое железо:** Ryzen 5 5600H, AMD Radeon iGPU, 16 GB RAM, Windows, без CUDA  
**Опора:** [MODELS_SPECIFICATION.md](MODELS_SPECIFICATION.md), [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)

> **Блок A закрыт (02.06.2026).** Идёт **подготовка моделей** (Real-CUGAN, SPAN) → затем интеграция в UI (блок B).

### Принцип расширения (без замены)

Новые апскейлеры — **дополнение** к Real-ESRGAN: dropdown в режиме «Качество», пресеты `standard`/`quality` **не меняем**, пока бенчмарк на Vega не покажет выигрыш. Depth Anything V2 для parallax уже в DepthFlow (MiDaS ONNX — задел TPSMM, не задача апскейла).

---

## Цель

Пошагово поднять качество выхода (PNG панелей, апскейл, MP4) **без смены железа**, с упором на:

1. **Блок A** — выжать максимум из уже скачанных моделей (конфиги + UI + **обратимые пресеты**).
2. **Блок B** — новые модели (скачать → подготовить → встроить → переключать в UI).

Оба интерфейса должны вести себя одинаково по смыслу: **Gradio (:7860)** и **веб-редактор (:8000)**.

---

## Принцип: пресеты и обратимость

Пользователь не должен вручную править YAML. Нужна пара режимов с **одной кнопкой туда-обратно**:

| Пресет | ID | Смысл |
|--------|-----|--------|
| **Стандарт** | `standard` | Текущие дефолты (быстро, предсказуемо) |
| **Качество** | `quality` | Рекомендации из MODELS_SPECIFICATION (медленнее, лучше картинка/видео) |

**Обратимость:**

- Переключатель или Radio: `Стандарт ⟷ Качество`.
- При переключении UI **подставляет** значения полей; при возврате — **восстанавливает** сохранённый снимок `standard` (не «забытые» ручные правки — опционально: «Сбросить к стандарту» / «Применить качество»).
- Опционально: `config/presets.yaml` в репозитории + `config/presets.user.yaml` (локальные правки, в `.gitignore`).

```mermaid
stateDiagram-v2
  [*] --> Standard
  Standard --> Quality: Применить «Качество»
  Quality --> Standard: Вернуть «Стандарт»
  Standard --> Custom: Ручная правка полей
  Quality --> Custom: Ручная правка полей
  Custom --> Standard: Сброс
```

---

## Содержимое пресетов (эталон)

### Split (`config.yaml` + UI)

| Параметр | Стандарт | Качество |
|----------|----------|----------|
| `quality_mode` | `fast` | `accurate` |
| `reading_order` | `true` | `true` |
| `confidence_threshold` | `0.35` | `0.30` (чуть больше панелей) |
| UI: экспорт по маске | только при «Полигон» | то же (логика уже есть) |

### Anim (`config_animate.yaml` + UI)

| Параметр | Стандарт | Качество |
|----------|----------|----------|
| `upscale.model` | `animevideov3` | `anime_6B` (NCNN `realesrgan-x4plus-anime`) |
| `upscale.scale` | `2` | `4` (×2 для x4plus-anime не использовать) |
| `upscale.gpu_id` | `0` | `0` |
| `harmonize.mode` | `auto` | `blurred_pillarbox` (или `auto`) |
| `animation.mode` | `opencv_zoom` | `depthflow` |
| `animation.depthflow_animation` | `zoom` | `dolly` |
| `animation.duration` | `3` | `3` |
| `animation.fps` | `24` | `24` |
| `animation.intensity` | `0.3` | `0.4` |

### Веб Split (дополнительно к YAML)

| UI | Стандарт | Качество |
|----|----------|----------|
| Accurate (SAM) | выкл | вкл |
| Полигон | выкл | по желанию (не обязательно) |

---

## Блок A — потенциал имеющихся моделей

**Результат блока:** все значимые параметры доступны в Gradio и :8000; пресеты Стандарт/Качество работают; документация обновлена.

### Этап A0 — Инфраструктура пресетов (1–2 дня)

| # | Задача | Где |
|---|--------|-----|
| A0.1 | Файл `config/presets.yaml` (`standard`, `quality`) для split + anim | `config/presets.yaml` |
| A0.2 | `utils/presets.py`: load, apply, diff, snapshot текущего UI → dict | `utils/presets.py` |
| A0.3 | API `GET/POST /api/presets`, `POST /api/presets/apply?name=quality\|standard` | `api/server.py` |
| A0.4 | Сохранение «последних ручных» в `localStorage` / Gradio session | — отложено |

**Критерий готовности:** из CLI/API можно применить пресет и получить те же значения, что в таблице выше.

---

### Этап A1 — Split: настройки в UI (2–3 дня) ✅

**Сделано:** SAM, reading order, RTL, пороги YOLO, пресеты, tooltips, path pickers.

| # | Задача | Gradio | Web :8000 |
|---|--------|--------|-----------|
| A1.1 | Пресет «Стандарт / Качество» + подсказка | ✓ | ✓ (шапка или секция Split) |
| A1.2 | `quality_mode` fast/accurate ↔ чекбокс Accurate | ✓ | ✓ (связать с `use-sam`) |
| A1.3 | `confidence_threshold`, `iou_threshold` (слайдеры, «Дополнительно») | ✓ | ✓ (свёрнутый блок) |
| A1.4 | Подсказка: SAM ≠ экспорт маски; полигон отдельно | ✓ | ✓ (уже частично) |
| A1.5 | Передача порогов в `POST /api/process` (расширить schema) | — | ✓ |

**Критерий:** переключение пресета меняет чекбоксы; повторное «Стандарт» возвращает исходные значения.

---

### Этап A2 — Anim: настройки в UI (2–3 дня) ✅

**Сделано:** модель/GPU апскейла, harmonize, DepthFlow, intensity; ограничение ×4 для x4plus-anime; `tile_size` в конфиге.

| # | Задача | Gradio | Web :8000 |
|---|--------|--------|-----------|
| A2.1 | Пресет «Стандарт / Качество» на вкладках Upscale/Video | ✓ | ✓ |
| A2.2 | Выбор модели апскейла: `animevideov3` / `anime_6B` | ✓ Dropdown | ✓ |
| A2.3 | `gpu_id`: 0 (Vulkan) / -1 (CPU) | ✓ | ✓ |
| A2.4 | Harmonize: mode, blur_sigma, vignette (секция Video) | ✓ | ✓ |
| A2.5 | DepthFlow: `zoom` / `dolly`, intensity | ✓ | ✓ |
| A2.6 | API: передать новые поля в `/api/upscale`, `/api/animate` | ✓ | ✓ |

**Критерий:** пресет «Качество» — `anime_6B` (×4) + depthflow без правки YAML.

---

### Этап A3 — Синхронизация и тесты (1 день)

| # | Задача |
|---|--------|
| A3.1 | Gradio и :8000 читают одни и те же пресеты (`presets.yaml`) |
| A3.2 | Smoke: standard → quality → standard (сравнить config на диске или ответ API) |
| A3.3 | Обновить [ComicSplit_Documentation.md](ComicSplit_Documentation.md), [MODELS_SPECIFICATION.md](MODELS_SPECIFICATION.md) §8 |
| A3.4 | Параграф в [CHANGELOG.md](../CHANGELOG.md) |

---

### Итог блока A

```text
[x] A0 Пресеты в коде + API
[x] A1 Split UI (оба фронта)
[x] A2 Anim UI (оба фронта)
[x] A3 Синхронизация и доки
[x] A4 Апскейл: UI ×4 для x4plus-anime, guard в upscale.py, benchmark_upscale
[ ] A0.4 localStorage — опционально позже
```

**Оценка:** ~6–9 рабочих дней — **выполнено**.

---

## Блок B — новые модели и интеграция

**Результат блока:** альтернативные детекторы и motion transfer выбираются в UI; скрипты загрузки; verify.

### Этап P1 — Боевая готовность моделей (в работе)

| # | Задача | Статус |
|---|--------|--------|
| P1.1 | Скрипт `scripts/download_upscale_backends.ps1` (Real-CUGAN + SPAN) | ✅ |
| P1.2 | `config/models_registry.yaml` + `utils/models_registry.py` | ✅ |
| P1.3 | `scripts/verify_upscale_backends.py` (registry + smoke upscale) | ✅ |
| P1.4 | Доки: MODELS_SETUP_GUIDE, models/README, MODELS_SPEC §2.2–2.3 | ✅ |
| P1.5 | Таблица «параметры качества» CUGAN/SPAN для UI (этап 2) | ✅ [UPSCALE_UI_PARAMS.md](UPSCALE_UI_PARAMS.md) |

**Следующий шаг:** B4.4 benchmark; B1/B2 по приоритету.

---

### Этап B0 — Реестр моделей в приложении (1 день)

| # | Задача |
|---|--------|
| B0.1 | `config/models_registry.yaml`: id, путь, тип, железо, ссылка HF/GitHub | ✅ (базовая версия) |
| B0.2 | `utils/models_registry.py`: проверка «модель установлена» перед запуском | ✅ |
| B0.3 | UI: статус моделей + команды скачивания (`GET /api/models/setup`, Gradio/:8000) | ✅ |

---

### Этап B1 — Manga / альтернативный YOLO (3–5 дней)

| # | Задача | Статус |
|---|--------|--------|
| B1.1 | Скрипт: export `leoxs22/manga-panel-detector-yolo26n` → ONNX INT8 | ✅ `scripts/export_manga_yolo.ps1` |
| B1.2 | `pipeline.py`: выбор детектора `comic` \| `manga` | ✅ |
| B1.3 | UI: Dropdown + API; пресет не меняет детектор | ✅ |
| B1.4 | Benchmark на `exam_imgs` + 1 manga page | 📋 (после установки manga ONNX) |
| B1.5 | Док: когда какой детектор | ✅ [SPLIT_DETECTORS.md](SPLIT_DETECTORS.md) |

**Не в scope v1:** два детектора на одной странице.

---

### Этап B2 — TPSMM motion transfer (5–8 дней)

| # | Задача | Статус |
|---|--------|--------|
| B2.1 | `anim/animate_tpsmm.py` — ONNX CPU, driving video | ✅ |
| B2.2 | `anim_pipeline.py` + режим `tpsmm` | ✅ |
| B2.3 | UI: mode `tpsmm`, путь к driving video | ✅ (сегментация — B3) |
| B2.4 | Gradio + :8000 + API поля | ✅ |
| B2.5 | Предупреждение в UI: «медленно, N мин/панель» | ✅ |

**Зависимость:** модели уже в `models/anim/tpsmm/` — verify `quantize_animate_models.py --verify`.

---

### Этап B3 — Опционально: сегментация + SAM2-tiny (позже)

| # | Задача | Приоритет |
|---|--------|-----------|
| B3.1 | `anim/segment.py` — MobileSAM по bbox для TPSMM | средний |
| B3.2 | SAM2-tiny ONNX для split (вместо MobileSAM) | низкий (тест CPU) |
| B3.3 | Split FP16 ONNX (без INT8) — флаг «Точность детекции» | низкий |

---

### Этап B4 — Дополнительные NCNN-апскейлеры (Real-CUGAN, SPAN)

| # | Задача |
|---|--------|
| B4.0 | P1: скачать + verify (без квантования) | ✅ |
| B4.1 | `anim/upscale.py`: router `backend` → realesrgan / realcugan / span | ✅ |
| B4.2 | UI: dropdown backend + вариант; условные поля (CUGAN: noise, syncgap) | ✅ |
| B4.3 | API `GET /api/upscale/options` + POST поля; пресеты без смены дефолта | ✅ |
| B4.4 | Расширить `benchmark_upscale` на CUGAN/SPAN; док с рекомендациями | ✅ |
| B4.5 | MangaJaNai — только B&W, вместе с B1 (не в цветной dropdown) |

Waifu2x — низкий приоритет, если B4 не даст выигрыша.

---

### Итог блока B

```text
[x] B0 Реестр + UI статуса установки
[~] B1 Manga YOLO (код готов; `yolo_manga_int8.onnx` — локально через export)
[~] B2 TPSMM (код + UI; модели `models/anim/tpsmm/` — download + verify)
[ ] B3 Segment / SAM2 / FP16 (по необходимости)
[x] B4 CUGAN + SPAN (пайплайн, UI, benchmark)
```

**Оценка:** B0+B1+B2 ≈ 2–3 недели; B3–B4 по запросу.

---

## Матрица паритета UI (целевое состояние)

| Настройка | config | Gradio | Web | Пресет |
|-----------|--------|--------|-----|--------|
| Пресет Стандарт/Качество | presets.yaml | ✓ | ✓ | — |
| Split SAM / quality_mode | config.yaml | ✓ | ✓ | ✓ |
| YOLO пороги | config.yaml | ✓ | ✓ | ✓ |
| Детектор comic/manga | models_registry | B1 | B1 | — |
| Upscale model 6B/v3 | anim yaml | ✓ | ✓ | ✓ |
| Upscale scale, gpu_id | anim yaml | ✓ | ✓ | ✓ |
| Harmonize mode | anim yaml | ✓ | ✓ | ✓ |
| Anim mode + depthflow | anim yaml | ✓ | ✓ | ✓ |
| Подсказки ко всем полям | ui_tooltips | ✓ | ✓ | — |
| Выбор путей (Обзор…) | path_dialog | ✓ | ✓ | — |
| TPSMM + driving | — | B2 | B2 | — |

Легенда: ✓ реализовано; B1/B2 — блок B roadmap.

---

## Что вы не указали, но стоит заложить

| Тема | Зачем |
|------|--------|
| **Проверка моделей перед run** | Не падать в середине batch с «файл не найден» |
| **Оценка времени** | «~5 мин, 10 панелей, depthflow» в UI |
| **Лог последнего прогона** | Уже есть batch-log на :8000 — расширить на Gradio |
| **Экспорт/импорт пресета** | JSON для шаринга настроек между ПК |
| **Не трогать** | CUDA, SD, Wails — вне roadmap |

---

## Рекомендуемый порядок работ

```mermaid
gantt
  title Roadmap качества (ориентир)
  dateFormat YYYY-MM-DD
  section Блок A
  A0 Пресеты           :a0, 2026-06-01, 2d
  A1 Split UI          :a1, after a0, 3d
  A2 Anim UI           :a2, after a0, 3d
  A3 Синхронизация     :a3, after a2, 1d
  section Блок B
  B0 Реестр            :b0, after a3, 1d
  B1 Manga YOLO        :b1, after b0, 5d
  B2 TPSMM             :b2, after b1, 8d
```

**Практично:** сначала **весь блок A** (быстрый выигрыш без новых весов), затем **B1 → B2**.

---

## Связанные документы

| Документ | Роль |
|----------|------|
| [MODELS_SPECIFICATION.md](MODELS_SPECIFICATION.md) | Какие модели и зачем |
| [ComicSplit_Documentation.md](ComicSplit_Documentation.md) | Как пользоваться после внедрения |
| [scripts/MODELS_SETUP_GUIDE.md](../scripts/MODELS_SETUP_GUIDE.md) | Скачивание весов |
| [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) | Отмечать ✓ по мере закрытия этапов |

---

## Журнал

| Дата | Изменение |
|------|-----------|
| 2026-05-31 | Первая версия roadmap (блоки A и B, пресеты, паритет UI) |
| 2026-06-02 | Блок A закрыт: финал доков, апскейл ×4/x4plus-anime, tile_size, benchmark; A0.4 отложен |
| 2026-06-02 | P1: Real-CUGAN + SPAN скачаны, models_registry, verify_upscale_backends; B4 переформулирован |

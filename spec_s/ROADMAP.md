# ComicSplit — Roadmap качества

**Версия:** 2.0 (июнь 2026)  
**Целевое железо:** Ryzen 5 5600H, AMD Radeon iGPU, 16 GB RAM, Windows, без CUDA

---

## Статус блоков

| Блок | Содержание | Статус |
|------|-----------|--------|
| **A** | Пресеты, UI-настройки, паритет интерфейсов | ✅ **Закрыт** |
| **B0** | Реестр моделей в приложении | ✅ **Закрыт** |
| **B1** | Манга-детектор YOLO | ✅ **Закрыт** |
| **B4** | CUGAN + SPAN backend апскейла | ✅ **Закрыт** |
| **B2** | TPSMM motion transfer | 🟡 **Интегрировано** — нужны тесты на реальных панелях + B3 segment |
| **B3** | Сегментация + SAM2-tiny | 📋 В планах (зависит от B2) |

---

## Блок A — пресеты и UI ✅

**Закрыт 2 июня 2026.** Все значимые параметры доступны в Gradio и :8000; пресеты Стандарт/Качество работают; документация актуальна.

### Пресеты (эталон: `config/presets.yaml`)

| Параметр | Стандарт | Качество |
|----------|----------|---------|
| `quality_mode` | `fast` | `accurate` |
| `confidence_threshold` | `0.35` | `0.30` |
| SAM | выкл | вкл |
| `upscale.model` | `animevideov3` | `anime_6B` (x4plus-anime ×4) |
| `harmonize.mode` | `auto` | `blurred_pillarbox` |
| `animation.mode` | `opencv_zoom` | `depthflow` |
| `animation.depthflow_animation` | `zoom` | `dolly` |
| `animation.duration` | `3.0` | `3.0` |
| `animation.intensity` | `0.3` | `0.4` |

### Механика пресетов

- Gradio: кнопки «Стандарт» / «Качество» + бейдж `MODE: STANDARD / QUALITY`
- Веб `:8000`: те же кнопки + бейдж
- API: `GET /api/presets`, `POST /api/presets/apply?name=quality|standard`
- Локальные правки: `config/presets.user.yaml` (в `.gitignore`)

---

## Блок B0 — реестр моделей ✅

`config/models_registry.yaml` + `utils/models_registry.py`: проверка «модель установлена» перед запуском.  
`GET /api/models/setup` — статус в UI (блок «Скачать / проверить модели»).

---

## Блок B1 — манга-детектор ✅

- `utils/panel_detector.py`, поле `panel_detector: comic | manga` в `config.yaml` и `POST /api/process`
- Экспорт: `scripts/export_manga_yolo.ps1` → `yolo_manga_int8.onnx`
- UI: dropdown «Детектор панелей» в Gradio и :8000
- Пресеты детектор **не перезаписывают**

Подробнее: §1.2 в [MODELS_SPECIFICATION.md](MODELS_SPECIFICATION.md).

---

## Блок B4 — CUGAN и SPAN ✅

- `anim/upscale.py`: backend `realesrgan | realcugan | span`
- UI: dropdown **Backend** в режиме «Качество»; подсказка если модель не установлена
- API v1.3: `GET /api/upscale/options`, расширенные поля `POST /api/upscale`
- Скачивание: `scripts/download_upscale_backends.ps1`

Параметры UI и CLI: §2.2–2.3 в [MODELS_SPECIFICATION.md](MODELS_SPECIFICATION.md).

---

## Блок B2 — TPSMM motion transfer 🟡

**Текущее состояние:** `anim/animate_tpsmm.py` вызывается из `anim_pipeline.py` при `mode: tpsmm`; модели в `models/anim/tpsmm/`; поля driving MP4 в Gradio, :8000 и API v1.3. Глобально в `config_animate.yaml` по умолчанию остаётся `opencv_zoom` — TPSMM только при явном выборе режима и указании driving video.

### Что осталось

| # | Задача |
|---|--------|
| B2.1 | ✅ Режим `tpsmm` в `anim_pipeline.process_panel()` |
| B2.2 | Проверить качество на панелях комикса, подобрать дефолтный driving video |
| B2.3 | Предупреждение в UI о времени на CPU (уточнить по замерам) |
| B2.4 | Тесты: `tests/test_tpsmm.py` (smoke с коротким driving clip) |
| B2.5 | `anim/segment.py` — перенесено в блок B3 |

**Зависимость:** модели уже в репо; проверить: `python scripts/quantize_animate_models.py --verify`

---

## Блок B3 — сегментация (в планах) 📋

| # | Задача | Приоритет |
|---|--------|-----------|
| B3.1 | `anim/segment.py` — MobileSAM по bbox для TPSMM | После B2 |
| B3.2 | SAM2-tiny ONNX (тест как замена MobileSAM в split) | Низкий |
| B3.3 | YOLO split без INT8 — флаг «точность детекции» | Низкий |

---

## Матрица паритета UI (целевое состояние)

| Настройка | Gradio | Web :8000 | Пресет |
|-----------|--------|-----------|--------|
| Пресет Стандарт/Качество | ✅ | ✅ | — |
| Split SAM / quality_mode | ✅ | ✅ | ✅ |
| YOLO пороги | ✅ | ✅ | ✅ |
| Детектор comic/manga | ✅ | ✅ | — |
| Upscale model + backend | ✅ | ✅ | ✅ |
| Upscale scale, gpu_id, tile_size | ✅ | ✅ | ✅ |
| Harmonize mode + params | ✅ | ✅ | ✅ |
| Anim mode + depthflow preset | ✅ | ✅ | ✅ |
| CUGAN noise/syncgap | ✅ | ✅ | — |
| Подсказки ко всем полям | ✅ | ✅ | — |
| Выбор путей (Обзор…) | ✅ | ✅ | — |
| Статус моделей (B0) | ✅ | ✅ | — |
| TPSMM + driving video | ✅ | ✅ | — |
| Сегментация объектов | B3 📋 | B3 📋 | — |

---

## Что сознательно не включается

| Технология | Причина |
|---|---|
| CUDA / SD / AnimateDiff / SVD | Нет NVIDIA GPU |
| ControlNet inpainting для 16:9 | CPU непрактично |
| Wails UI / gRPC | Отдельная веха спеки v2.0 |
| localStorage на :8000 | Опционально — добавить при необходимости |

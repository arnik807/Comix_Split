# Детекторы панелей (Split)

**Версия:** 1.0 (июнь 2026)

## Когда какой детектор

| Детектор | ID | Контент | Модель |
|----------|-----|---------|--------|
| Западный комикс | `comic` | Franco-Belgian, American, цветные комиксы | mosesb/best-comic-panel-detection → `yolo_comic_int8.onnx` |
| Манга | `manga` | Японская манга, Manga109 | leoxs22/manga-panel-detector-yolo26n → `yolo_manga_int8.onnx` |

Манга-модель обучена на **двух классах**: `0 = panel`, `1 = text bubble`. В пайплайне используется **только класс panel** (баблы не режутся как панели).

## Установка

```powershell
# Западный комикс (уже в базовом гайде)
powershell -File scripts\split_models_craft_scripts\download_models.ps1
python scripts\split_models_craft_scripts\quantize_models.py

# Манга
powershell -File scripts\export_manga_yolo.ps1
```

## Конфиг

`config.yaml`:

```yaml
panel_detector: comic   # comic | manga
```

Пресеты **Стандарт / Качество** детектор **не меняют** — выбор сохраняется в сессии.

## UI

- Gradio / :8000 — dropdown «Детектор панелей»
- `GET /api/split/options` — статус установки

## Рекомендации

- Манга: включайте **RTL** и при необходимости снижайте `confidence_threshold` (0.25–0.30).
- Для манги на цветных страницах western-комикса попробуйте оба детектора и сравните `_visualization.jpg`.

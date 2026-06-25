# diagnose_stage_2a.py

Диагностика Stage 2a: bbox YOLO + кропы + OCR (по умолчанию **SiliconFlow VLM** из `config/story_stage_2a.yaml`).

Подробнее: [../spec_s/STORY_ANALYZER_STAGE_2A.md](../spec_s/STORY_ANALYZER_STAGE_2A.md)

## Запуск

Из корня проекта, venv активирован. Нужен `.env` с `SILICONFLOW_API_KEY` при `ocr_engine: siliconflow`.

```powershell
cd D:\DEVELOP\COMICS\SPLIT_PANELS_DEV

# Американский комикс (5 панелей)
.\venv_311\Scripts\python.exe scripts\diagnose_stage_2a.py `
  --panels "exam_img\americ_comix_1\americ_comix__upscaled" `
  --label americ `
  --limit 5

# Манга (5 панелей)
.\venv_311\Scripts\python.exe scripts\diagnose_stage_2a.py `
  --panels "exam_img\manga_test_1\manga_test_1_upscaled" `
  --label manga `
  --limit 5

# Отдельная папка вывода для сравнения прогонов
.\venv_311\Scripts\python.exe scripts\diagnose_stage_2a.py `
  --panels "exam_img\americ_comix_1\americ_comix__upscaled" `
  --label americ_vlm --limit 5 --out debug/stage_2a_vlm
```

## Результат

```
debug/stage_2a/<label>/
  report.json
  <имя_панели>/
    overlay.png            # bbox + score
    panel.png
    crop_00_raw.jpg        # кроп бабла (то, что уходит в VLM)
    crop_00_prep.jpg       # preprocess (для локального OCR; при siliconflow может не использоваться)
    crop_00_result.txt     # текст + ocr_engine + время
    summary.json
```

## Что смотреть

1. **overlay.png** — мало рамок → проблема **детекции** (tiled YOLO, этап 2 roadmap).
2. **crop_*_raw.jpg** — текст виден, **result.txt** пустой → проблема **OCR** (проверить API, ключ, модель).
3. **result.txt** → поле `ocr_engine: siliconflow` (или фактический при `auto`).
4. **report.json** → `bubbles`, `empty_ocr`.

## Smoke-test API (без полного diagnose)

```powershell
python scripts\test_siliconflow_api.py
python scripts\test_siliconflow_api.py --vision debug\stage_2a\americ\003_p003_panel\crop_00_raw.jpg
```

## После прогона

См. [../problems_fix/bubbles_detect_problems/ROADMAP_STAGE_2A.md](../problems_fix/bubbles_detect_problems/ROADMAP_STAGE_2A.md) — что писать в чат по текущему этапу.

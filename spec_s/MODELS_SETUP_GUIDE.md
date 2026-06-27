# ComicSplit — установка и подготовка моделей

**Версия:** 2.0 (июнь 2026)  
**Связанные документы:** [MODELS_SPECIFICATION.md](MODELS_SPECIFICATION.md) (параметры и железо), [models/README.md](../models/README.md) (краткий список файлов)

Пошаговая инструкция: откуда скачать артефакты, куда положить, как проверить.  
Спецификация «что за модель и зачем» — в [MODELS_SPECIFICATION.md](MODELS_SPECIFICATION.md).

---

## 1. Обзор

| Блок | Модели | Формат | Квантование | Где в проекте |
|------|--------|--------|-------------|---------------|
| **Split** | YOLO comic / manga | ONNX INT8 | dynamic INT8 | `models/*.onnx` |
| **Split** | MobileSAM | ONNX INT8 | dynamic INT8 | `models/mobilesam_*_int8.onnx` |
| **Anim upscale** | Real-ESRGAN | NCNN Vulkan exe | не нужно | `models/anim/upscale/` |
| **Anim upscale** | Real-CUGAN, SPAN | NCNN Vulkan exe | не нужно | `models/anim/upscale/realcugan/`, `span/` |
| **Anim depth** | MiDaS small | ONNX → INT8 | да | `models/anim/depth/` |
| **Anim video** | TPSMM | ONNX → INT8 | да | `models/anim/tpsmm/` |
| **Anim video** | DepthFlow | pip-пакет | — | venv; DA-V2 качается при первом запуске |
| **Anim render** | ffmpeg | exe | — | PATH или `models/anim/ffmpeg/` |
| **ExText (Stage 2a)** | SiliconFlow VLM | **облако API** | — | `.env` → `SILICONFLOW_API_KEY` |
| **ExText fallback** | PaddleOCR | whl-кэш | — | `models/paddleocr/` |

**Ориентир по месту на диске:** ~400–500 MB до INT8-квантования anim → ~250 MB после; split INT8 ~150 MB; PaddleOCR ~200 MB (опционально).

---

## 2. Структура `models/`

```
SPLIT_PANELS_DEV/
└── models/                              ← не в git (.gitignore)
    ├── README.md
    ├── yolo_comic_int8.onnx             ← split, comic
    ├── yolo_manga_int8.onnx             ← split + ExText bbox (class 1)
    ├── mobilesam_encoder_int8.onnx      ← split Accurate
    ├── mobilesam_decoder_int8.onnx
    ├── paddleocr/                       ← ExText offline OCR (опционально)
    │   └── whl/...
    └── anim/
        ├── upscale/
        │   ├── realesrgan-ncnn-vulkan.exe
        │   ├── models/                  ← .bin + .param Real-ESRGAN
        │   ├── realcugan/
        │   │   ├── realcugan-ncnn-vulkan.exe
        │   │   └── models-se/ ...
        │   └── span/
        │       ├── span-ncnn-vulkan.exe
        │       └── models/ ...
        ├── depth/
        │   ├── midas_v21_small_256.onnx
        │   └── midas_v21_small_256_int8.onnx
        ├── tpsmm/
        │   ├── kp_detector.onnx / kp_detector_int8.onnx
        │   └── tpsmm_rel.onnx / tpsmm_rel_int8.onnx
        └── ffmpeg/bin/ffmpeg.exe        ← опционально (скрипт может положить)
```

Реестр путей для проверок UI/API: `config/models_registry.yaml` → `utils/models_registry.py`.

---

## 3. Быстрый старт (полная установка)

Из **корня репозитория**, venv активирован (`venv_311`):

```powershell
pip install -r requirements.txt

# ── Split ──
powershell -ExecutionPolicy Bypass -File scripts\split_models_craft_scripts\download_models.ps1
# Экспорт comic .pt → ONNX (если yolo_comic.onnx ещё нет) — см. §4.2
python scripts\split_models_craft_scripts\quantize_models.py

# Манга (опционально, нужна для manga split и ExText bbox)
powershell -ExecutionPolicy Bypass -File scripts\export_manga_yolo.ps1

# ── Anim ──
powershell -ExecutionPolicy Bypass -File scripts\download_animate_models.ps1
powershell -ExecutionPolicy Bypass -File scripts\download_upscale_backends.ps1
python scripts\quantize_animate_models.py

# ── ExText OCR offline (только если ocr_engine: paddle | easyocr | auto) ──
powershell -ExecutionPolicy Bypass -File scripts\install_paddle_ocr.ps1

# ── Проверка ──
python scripts\quantize_animate_models.py --verify
python scripts\verify_upscale_backends.py
python scripts\test_siliconflow_api.py          # ExText VLM (нужен .env)
```

Статус в UI: **Gradio** и **:8000** → блок «Скачать / проверить модели» (`GET /api/models/setup`).

---

## 4. Split — детекция панелей и SAM

### 4.1. Загрузка

```powershell
powershell -ExecutionPolicy Bypass -File scripts\split_models_craft_scripts\download_models.ps1
```

Скрипт кладёт файлы в `scripts/split_models_craft_scripts/models/`:

| Файл | Источник |
|------|----------|
| `yolo_comic.pt` | [mosesb/best-comic-panel-detection](https://huggingface.co/mosesb/best-comic-panel-detection) |
| `mobilesam_encoder.onnx` | [Acly/MobileSAM](https://huggingface.co/Acly/MobileSAM) |
| `mobilesam_decoder.onnx` | Acly/MobileSAM (sam_mask_decoder_single.onnx) |

При ошибке HuggingFace задайте токен: `$env:HF_HUB_TOKEN = 'hf_...'`.

### 4.2. Comic YOLO: PT → ONNX

Пайплайн ожидает `models/yolo_comic.onnx` в **корне репозитория**. После download:

```powershell
# из корня, venv с ultralytics
python -c "
from pathlib import Path
import shutil
from ultralytics import YOLO
src = Path('scripts/split_models_craft_scripts/models/yolo_comic.pt')
dst_dir = Path('models')
dst_dir.mkdir(exist_ok=True)
shutil.copy2(src, dst_dir / 'yolo_comic.pt')
m = YOLO(str(dst_dir / 'yolo_comic.pt'))
m.export(format='onnx', imgsz=640, simplify=True, opset=12)
# ultralytics пишет yolo_comic.onnx рядом с .pt
"

# SAM — готовые ONNX, только копируем
Copy-Item scripts\split_models_craft_scripts\models\mobilesam_*.onnx models\
```

### 4.3. INT8-квантование split

```powershell
python scripts\split_models_craft_scripts\quantize_models.py
```

Результат в `models/`:

- `yolo_comic_int8.onnx`
- `mobilesam_encoder_int8.onnx`
- `mobilesam_decoder_int8.onnx`

> **Кириллица в пути проекта:** квантование использует временные папки `C:/tmp_quant` — репозиторий лучше держать в ASCII-пути (`D:\DEVELOP\COMICS\...`).

### 4.4. Manga YOLO (split + ExText)

Один файл `models/yolo_manga_int8.onnx` — классы **0 = panel**, **1 = text bubble**.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\export_manga_yolo.ps1
```

Зависимости: `pip install ultralytics onnxruntime`. Экспорт через ASCII workdir `C:/tmp_comicsplit_manga`.

Проверка: `GET /api/split/options` — статус `manga_yolo`.

---

## 5. Anim — апскейл (NCNN Vulkan)

### 5.1. Real-ESRGAN (основной backend)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\download_animate_models.ps1
```

Или вручную:

```
https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip
```

→ распаковать в `models/anim/upscale/` (`realesrgan-ncnn-vulkan.exe` + `models/*.bin`).

| NCNN `-n` | ID в конфиге / UI | Масштаб |
|-----------|-------------------|---------|
| `realesr-animevideov3` | `animevideov3` | ×2, ×3, ×4 |
| `realesrgan-x4plus-anime` | `anime_6B` | **только ×4** |

Пресеты: «Стандарт» — videov3 ×2; «Качество» — x4plus-anime ×4.

Smoke-тест (AMD iGPU):

```powershell
cd models\anim\upscale
.\realesrgan-ncnn-vulkan.exe -i ..\..\..\test_page.jpg -o out.png -n realesr-animevideov3 -s 2 -g 0
# -g 0 = первый GPU; -g -1 = CPU fallback
```

Бенчмарк: `scripts\benchmark_upscale.ps1 -Quick`.

### 5.2. Real-CUGAN и SPAN (интегрированы в UI/API, блок B4 ✅)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\download_upscale_backends.ps1
```

| Backend | Exe | Релиз |
|---------|-----|--------|
| Real-CUGAN | `models/anim/upscale/realcugan/realcugan-ncnn-vulkan.exe` | [20220728](https://github.com/nihui/realcugan-ncnn-vulkan/releases/tag/20220728) |
| SPAN | `models/anim/upscale/span/span-ncnn-vulkan.exe` | [20240831-055257](https://github.com/TNTwise/SPAN-ncnn-vulkan/releases/tag/20240831-055257) |

Проверка всех backend:

```powershell
python scripts\verify_upscale_backends.py
python scripts\verify_upscale_backends.py --backend realcugan
```

В приложении: dropdown backend на вкладках Upscale / Video, `GET /api/upscale/options`, поля CUGAN (`noise`, `syncgap`) и SPAN (`model_name`, `scale`) в `POST /api/upscale` и `/api/animate`.

**CUGAN (качество line-art):** `-n` denoise −1…3, `-m` models-se / models-pro, `-c` syncgap 0–3, `-t` tile.  
**SPAN:** `-n` spanx2_ch48 / spanx4_ch48, `-s` должен совпадать с моделью.

---

## 6. Anim — глубина, motion, рендер

### 6.1. MiDaS small (задел / TPSMM)

Скачивается скриптом `download_animate_models.ps1`:

```
https://huggingface.co/julienkay/sentis-MiDaS/resolve/main/onnx/midas_v21_small_256.onnx
```

→ `models/anim/depth/midas_v21_small_256.onnx`  
INT8: `python scripts\quantize_animate_models.py` → `midas_v21_small_256_int8.onnx`.

### 6.2. TPSMM (режим `tpsmm` в anim)

Скрипт тянет latest release [Thin-plate-spline-motion-model-ONNX](https://github.com/instant-high/Thin-plate-spline-motion-model-ONNX):

- `kp_detector.onnx`
- `tpsmm_rel.onnx`

→ `models/anim/tpsmm/` + INT8-версии после квантования.

Нужен **driving MP4** (`tpsmm_driving_video` в конфиге / UI). На CPU медленно — см. [MODELS_SPECIFICATION.md](MODELS_SPECIFICATION.md) §2.5.

### 6.3. DepthFlow (parallax)

```powershell
pip install depthflow
```

(`download_animate_models.ps1` ставит пакет в `venv_311` автоматически.)

- Первый запуск качает **Depth Anything V2 Small** внутри пакета.
- Рендер: OpenGL (AMD iGPU через драйвер); headless: `$env:WINDOW_BACKEND = "headless"`.
- Код: `anim/animate_depthflow.py` — цепочка `input → preset → main --render`.

Portable exe (альтернатива pip): [DepthFlow releases](https://github.com/BrokenSource/DepthFlow/releases).

### 6.4. ffmpeg

Для `anim/render.py` → MP4 / storyboard. Системный `ffmpeg` в PATH или bundled в `models/anim/ffmpeg/bin/`.

---

## 7. ExText (Stage 2a) — OCR и детекция баблов

### 7.1. Основной OCR — SiliconFlow VLM (без файлов в `models/`)

1. Ключ в `.env` в корне репозитория:

```env
SILICONFLOW_API_KEY=sk-...
# опционально:
# SILICONFLOW_BASE_URL=https://api.siliconflow.com/v1
# SILICONFLOW_VLM_MODEL=Qwen/Qwen3-VL-8B-Instruct
```

2. Конфиг: `config/story_stage_2a.yaml` → `ocr_engine: siliconflow` (default).

3. Smoke-test:

```powershell
python scripts\test_siliconflow_api.py
python scripts\test_siliconflow_api.py --vision path\to\crop.jpg
```

Документация: [STORY_ANALYZER_STAGE_2A.md](STORY_ANALYZER_STAGE_2A.md).

### 7.2. Детекция bbox баблов

Используется **`yolo_manga_int8.onnx`**, class **1**, tiled inference — см. §4.4.  
Отдельной «bubble-only» модели не скачивается.

### 7.3. Offline OCR — PaddleOCR (fallback)

Только если в конфиге `ocr_engine: paddle | easyocr | auto`.

```powershell
# Закройте uvicorn / Gradio (блокировка cv2.pyd на Windows)
powershell -ExecutionPolicy Bypass -File scripts\install_paddle_ocr.ps1
```

Кэш: `models/paddleocr/` (`PADDLE_OCR_BASE_DIR`).  
**Важно:** путь к проекту и `models/paddleocr` — **ASCII** (ограничение Paddle C++ на Windows).

Локальный OCR как primary **не рекомендуется** — см. [LEGACY_LOCAL_OCR.md](../problems_fix/bubbles_detect_problems/LEGACY_LOCAL_OCR.md).

Диагностика bbox + OCR:

```powershell
python scripts\diagnose_stage_2a.py --panels exam_img\...\upscaled --limit 5
```

---

## 8. Квантование ONNX (anim)

Dynamic INT8 — без калибровочного датасета.

```powershell
pip install onnxruntime onnx
python scripts\quantize_animate_models.py          # квантование + проверка
python scripts\quantize_animate_models.py --verify # только проверка
```

| Модель | До | После INT8 | Ускорение CPU |
|--------|-----|------------|---------------|
| MiDaS small | ~66 MB | ~33 MB | ~1.5–2× |
| kp_detector | ~15 MB | ~8 MB | ~1.5× |
| tpsmm_rel | ~100 MB | ~50 MB | ~1.5–2× |

Временные пути: `C:/tmp_quant_anim` (обход кириллицы).

---

## 9. Проверка готовности

### 9.1. Скрипты

```powershell
python scripts\quantize_animate_models.py --verify
python scripts\verify_upscale_backends.py
```

Ожидаемо: `[OK]` для exe Real-ESRGAN, загрузки INT8 ONNX, импорта `depthflow`.

### 9.2. API / UI

```powershell
uvicorn api.server:app --port 8000
```

- `GET /api/models/setup` — сводка split / upscale / story_2a / depthflow  
- `GET /api/split/options` — comic + manga YOLO  
- `GET /api/upscale/options` — realesrgan | realcugan | span  
- `GET /api/story/stage_2a/options` — OCR-движки ExText  

### 9.3. pytest (опционально)

```powershell
python -m pytest tests/test_models_registry.py tests/test_upscale_options.py tests/test_stage_2a_sync.py -q
```

---

## 10. Итоговый порядок (шпаргалка)

```
requirements.txt
    ↓
Split: download_models.ps1 → export comic ONNX → quantize_models.py
    ↓
Manga (опц.): export_manga_yolo.ps1
    ↓
Anim: download_animate_models.ps1 + download_upscale_backends.ps1
    ↓
Anim INT8: quantize_animate_models.py
    ↓
ExText: .env SILICONFLOW_API_KEY (+ install_paddle_ocr.ps1 если offline)
    ↓
verify: quantize_animate_models.py --verify + verify_upscale_backends.py
    ↓
GET /api/models/setup → всё ready
```

---

## 11. Частые проблемы

| Симптом | Решение |
|---------|---------|
| Vulkan / NCNN не видит GPU | `-g -1` CPU; обновить AMD Adrenalin |
| `anime_6B` ×2 даёт артефакты | Только ×4; UI принудительно поднимает scale |
| HuggingFace HTML вместо модели | `$env:HF_HUB_TOKEN`, перекачать |
| PaddleOCR crash / mojibake | ASCII-путь проекта; `models/paddleocr` |
| SiliconFlow 401 | Base URL `.com/v1`, не `.cn` |
| DepthFlow минуты на кадр | CPU/iGPU норма; OpenCV zoom быстрее |
| Модель «есть», UI пишет missing | Сверить путь с `config/models_registry.yaml` |

---

## 12. Источники

| Компонент | Репозиторий / URL |
|-----------|-------------------|
| YOLO comic | https://huggingface.co/mosesb/best-comic-panel-detection |
| YOLO manga | https://huggingface.co/leoxs22/manga-panel-detector-yolo26n |
| MobileSAM ONNX | https://huggingface.co/Acly/MobileSAM |
| Real-ESRGAN NCNN | https://github.com/xinntao/Real-ESRGAN/releases |
| Real-CUGAN NCNN | https://github.com/nihui/realcugan-ncnn-vulkan |
| SPAN NCNN | https://github.com/TNTwise/SPAN-ncnn-vulkan |
| MiDaS ONNX | https://huggingface.co/julienkay/sentis-MiDaS |
| TPSMM ONNX | https://github.com/instant-high/Thin-plate-spline-motion-model-ONNX |
| DepthFlow | https://github.com/BrokenSource/DepthFlow |
| SiliconFlow VLM | https://siliconflow.com — модель `Qwen/Qwen3-VL-8B-Instruct` |
| PaddleOCR | https://github.com/PaddlePaddle/PaddleOCR |

---

## 13. Скрипты в `scripts/`

| Скрипт | Назначение |
|--------|------------|
| `split_models_craft_scripts/download_models.ps1` | Comic PT + MobileSAM ONNX |
| `split_models_craft_scripts/quantize_models.py` | Split INT8 |
| `export_manga_yolo.ps1` / `.py` | Manga YOLO INT8 |
| `download_animate_models.ps1` | Real-ESRGAN, MiDaS, TPSMM, depthflow |
| `download_upscale_backends.ps1` | CUGAN + SPAN |
| `quantize_animate_models.py` | Anim INT8 + verify |
| `verify_upscale_backends.py` | Smoke NCNN backend |
| `install_paddle_ocr.ps1` | PaddleOCR для ExText fallback |
| `test_siliconflow_api.py` | Smoke VLM API |
| `diagnose_stage_2a.py` | Bbox + OCR диагностика |
| `benchmark_upscale.ps1` | Бенчмарк апскейла |

Краткое описание папки `scripts/`: [scripts/readme.md](../scripts/readme.md).

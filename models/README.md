# Модели

Файлы моделей в git не хранятся (см. `.gitignore`).

**Полная спецификация** (описание, ссылки, железо, апгрейды): [spec_s/MODELS_SPECIFICATION.md](../spec_s/MODELS_SPECIFICATION.md).

## Split (раскройка панелей)

Папка `models/`:

| Файл | Назначение |
|------|------------|
| `yolo_comic_int8.onnx` | Детекция панелей — западный комикс (`panel_detector: comic`) |
| `yolo_manga_int8.onnx` | Детекция панелей — манга (`panel_detector: manga`) |
| `mobilesam_encoder_int8.onnx` | MobileSAM encoder |
| `mobilesam_decoder_int8.onnx` | MobileSAM decoder |

```powershell
.\scripts\split_models_craft_scripts\download_models.ps1
python scripts\split_models_craft_scripts\quantize_models.py

# Манга (отдельно)
powershell -ExecutionPolicy Bypass -File scripts\export_manga_yolo.ps1
```

Когда какой детектор: [spec_s/MODELS_SPECIFICATION.md](../spec_s/MODELS_SPECIFICATION.md) §1.2

## Story 2a (OCR баблов)

**Основной OCR (июнь 2026):** SiliconFlow VLM `Qwen/Qwen3-VL-8B-Instruct` — ключ в `.env`, без файлов в `models/`.  
Документация: [spec_s/STORY_ANALYZER_STAGE_2A.md](../spec_s/STORY_ANALYZER_STAGE_2A.md)

**Офлайн fallback** — папка `models/paddleocr/` (структура кэша PaddleOCR, не в git):

| Путь | Назначение |
|------|------------|
| `whl/rec/cyrillic/cyrillic_PP-OCRv3_rec_infer/` | Распознавание кириллицы (ru) |
| `whl/det/ml/Multilingual_PP-OCRv3_det_infer/` | Детектор (при init PaddleOCR) |
| `whl/cls/ch_ppocr_mobile_v2.0_cls_infer/` | Классификатор угла (опционально) |

```powershell
# Только если нужен ocr_engine: paddle | easyocr | auto
powershell -ExecutionPolicy Bypass -File scripts\install_paddle_ocr.ps1
```

Конфиг: `config/story_stage_2a.yaml` → `ocr_engine: siliconflow` (default), `paddle_ocr_base_dir: models/paddleocr`

Smoke-test облака: `python scripts/test_siliconflow_api.py`

## Anim (апскейл + видео)

Папка `models/anim/`:

| Путь | Назначение |
|------|------------|
| `upscale/realesrgan-ncnn-vulkan.exe` | Апскейл NCNN/Vulkan (AMD iGPU) — **в пайплайне** |
| `upscale/models/*.bin`, `*.param` | Real-ESRGAN: videov3, x4plus-anime (`anime_6B`, только ×4) |
| `upscale/realcugan/realcugan-ncnn-vulkan.exe` | Real-CUGAN — **скачано, verify OK; UI — в разработке** |
| `upscale/span/span-ncnn-vulkan.exe` | SPAN — **скачано, verify OK; UI — в разработке** |
| `depth/midas_v21_small_256.onnx` | MiDaS исходная |
| `depth/midas_v21_small_256_int8.onnx` | MiDaS INT8 (для CPU inference) |
| `tpsmm/kp_detector.onnx` | TPSMM keypoints |
| `tpsmm/tpsmm_rel.onnx` | TPSMM animation |
| `tpsmm/*_int8.onnx` | TPSMM INT8 |

DepthFlow — Python-пакет (`pip install depthflow`), не файл в `models/`.

### Загрузка и подготовка

```powershell
powershell -ExecutionPolicy Bypass -File scripts\download_animate_models.ps1
powershell -ExecutionPolicy Bypass -File scripts\download_upscale_backends.ps1
python scripts\quantize_animate_models.py
python scripts\quantize_animate_models.py --verify
python scripts\verify_upscale_backends.py
```

Подробнее: `scripts/MODELS_SETUP_GUIDE.md`

### Проверка апскейла

```powershell
.\models\anim\upscale\realesrgan-ncnn-vulkan.exe -i test_page.jpg -o test_up.png -n realesr-animevideov3-x4 -s 2 -g 0
```

### ffmpeg

Для сборки MP4. Рекомендуется bundled:

`models/anim/ffmpeg/bin/ffmpeg.exe` (скрипт `download_animate_models.ps1`).

Или системный `ffmpeg` в PATH — подхватывается `utils/anim_config.py`.

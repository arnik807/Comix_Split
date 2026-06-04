# ComicSplit — спецификация моделей

**Версия:** 1.2 (июнь 2026)  
**Связанные документы:** [ARCHITECTURE.md](ARCHITECTURE.md), [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)

Документ описывает все ML-модели и inference-инструменты проекта: ссылки на источники, оценку под целевое железо, параметры запуска и рекомендации по качеству.

---

## Целевое железо

| Параметр | Значение |
|----------|----------|
| CPU | AMD Ryzen 5 5600H (6C/12T, 3.3 GHz) |
| GPU | AMD Radeon iGPU (~1 GB shared VRAM, Vulkan 1.3) |
| RAM | 16 GB DDR4 |
| ОС | Windows 10/11 |
| Ограничения | **Нет CUDA**; SD/диффузия — вне проекта |

**Легенда:**

| Символ | Значение |
|--------|----------|
| ⭐⭐⭐ | Оптимально: разумная скорость и качество |
| ⭐⭐ | Допустимо: работает, заметно медленнее |
| ⭐ | Тяжело: только для единичных кадров |
| ❌ | Не подходит: требует CUDA или >8 GB VRAM |

---

## Обзор: что и где используется

```
Страница комикса
  → YOLO INT8 (comic | manga)
  → [Accurate] MobileSAM INT8
  → PNG панели

PNG панели
  → Real-ESRGAN / Real-CUGAN / SPAN (NCNN Vulkan)
  → harmonize OpenCV (16:9)
  → DepthFlow + Depth Anything V2 Small  ← parallax
    или OpenCV эффекты                   ← быстрая анимация
  → ffmpeg → MP4
```

---

## 1. Split — детекция и маски

### 1.1 YOLO — детектор западного комикса

| | |
|---|---|
| **Файл** | `models/yolo_comic_int8.onnx` |
| **Источник** | Fine-tune [mosesb/best-comic-panel-detection](https://huggingface.co/mosesb/best-comic-panel-detection) → ONNX → dynamic INT8 |
| **Скрипты** | `scripts/split_models_craft_scripts/download_models.ps1`, `quantize_models.py` |
| **Вход** | 640×640, BGR, CPUExecutionProvider |
| **Класс** | `panel` |

**Под железо: ⭐⭐⭐** — лёгкая INT8. На больших страницах > 600 ms — норма в Accurate+SAM.

---

### 1.2 YOLO — детектор манги

| | |
|---|---|
| **Файл** | `models/yolo_manga_int8.onnx` |
| **Источник** | [leoxs22/manga-panel-detector-yolo26n](https://huggingface.co/leoxs22/manga-panel-detector-yolo26n) → ONNX → INT8 |
| **Скрипты** | `scripts/export_manga_yolo.ps1`, `scripts/export_manga_yolo.py` |
| **Классы** | `0 = panel`, `1 = text bubble` (пайплайн берёт только panel) |
| **API поле** | `panel_detector: manga` в `POST /api/process` |

**Под железо: ⭐⭐⭐** — ~2.7 MB TFLite / лёгкий ONNX.

**Когда использовать манга-детектор:**
- Чёрно-белый контент, японский стиль (Manga109)
- Рекомендуется: RTL + `confidence_threshold: 0.25–0.30`
- Пресеты детектор **не меняют** — выбор сохраняется в сессии

**Ссылки:**
- `GET /api/split/options` — статус установки
- Gradio + `:8000`: dropdown «Детектор панелей»

---

### 1.3 MobileSAM — уточнение контура (режим Accurate)

| | |
|---|---|
| **Файлы** | `mobilesam_encoder_int8.onnx`, `mobilesam_decoder_int8.onnx` |
| **Источник** | [Acly/MobileSAM](https://huggingface.co/Acly/MobileSAM) — готовые ONNX |
| **Оригинал** | [ChaoningZhang/MobileSAM](https://github.com/ChaoningZhang/MobileSAM) (~9.7M параметров, Tiny-ViT) |
| **Включение** | `quality_mode: accurate`, пресет «Качество», Gradio «MobileSAM» |

**Под железо: ⭐⭐** — encoder раз на страницу + decoder на каждую панель. На 6–12 панелях — секунды. Для пакетной раскройки предпочтителен **fast** (только YOLO).

**Ссылки:** https://huggingface.co/Acly/MobileSAM · https://huggingface.co/spaces/dhkim2810/MobileSAM

---

## 2. Anim — апскейл

Все три апскейлера работают через NCNN + Vulkan на AMD iGPU. Выбор в UI — dropdown **Backend**; пресеты по умолчанию используют Real-ESRGAN.

### 2.1 Real-ESRGAN (основной, в пресетах)

| | |
|---|---|
| **Файлы** | `models/anim/upscale/realesrgan-ncnn-vulkan.exe` + `models/*.bin` |
| **Скачивание** | `scripts/download_animate_models.ps1` → [GitHub release v0.2.5.0](https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip) |

| NCNN-модель | ID в конфиге | Флаг `-n` | Масштаб |
|---|---|---|---|
| realesr-animevideov3 | `animevideov3` | `realesr-animevideov3` | ×2 или ×4 |
| realesrgan-x4plus-anime | `anime_6B` | `realesrgan-x4plus-anime` | **только ×4** |

> **Важно:** `anime_6B` в коде — не отдельные веса, это NCNN-имя `realesrgan-x4plus-anime`. При `scale: 2` с этим backend появляются артефакты — UI принудительно ставит ×4.

**Под железо: ⭐⭐⭐ (Vulkan)** / ⭐ (CPU fallback `-g -1`)

**Ссылки:** https://github.com/xinntao/Real-ESRGAN · https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan

---

### 2.2 Real-CUGAN (Tencent/Bilibili)

| | |
|---|---|
| **Файлы** | `models/anim/upscale/realcugan/realcugan-ncnn-vulkan.exe` + `models-se/` |
| **Скачивание** | `scripts/download_upscale_backends.ps1` |
| **Verify** | `python scripts/verify_upscale_backends.py --backend realcugan` |

**Когда использовать:** чистые края, line art, плоские цветовые зоны аниме-стиля.

**Ключевые параметры:**

| Параметр UI | CLI флаг | Рекомендация |
|---|---|---|
| `model` | `-m models-se` | `cugan_se` → папка `models-se` |
| `scale` | `-s 1–4` | **×2** для баланса скорость/качество |
| `cugan_noise` | `-n -1..3` | **−1** без денойза (цветные); 1–2 для шумных сканов |
| `cugan_syncgap` | `-c 0–3` | **3** (very rough) — быстрее |
| `gpu_id` | `-g 0` | AMD iGPU |
| `tile_size` | `-t` | 0=auto; 128/256 при швах |

**Под железо: ⭐⭐⭐ (Vulkan)** — smoke ~3–4 с/панель ×2.

**Ссылки:** https://github.com/nihui/realcugan-ncnn-vulkan

---

### 2.3 SPAN (NTIRE 2024 Champion)

| | |
|---|---|
| **Файлы** | `models/anim/upscale/span/span-ncnn-vulkan.exe` + `models/` |
| **Скачивание** | `scripts/download_upscale_backends.ps1` |
| **Verify** | `python scripts/verify_upscale_backends.py --backend span` |

**Когда использовать:** когда нужно максимальное качество при разумной скорости. Победитель NTIRE 2024 Efficient SR Challenge (1-е место по качеству + скорости).

| Параметр UI | CLI флаг | Значения |
|---|---|---|
| `span_model_name` | `-n` | `spanx2_ch48` (scale 2) / `spanx4_ch48` (scale 4) |
| `scale` | — | фиксируется по выбранной модели |
| `gpu_id` | `-g` | 0 = AMD iGPU; −1 = CPU |
| `tile_size` | `-t` | аналогично Real-ESRGAN |

> Масштаб нельзя задать отдельно от модели: `spanx2_ch48` — только ×2, `spanx4_ch48` — только ×4.

**Под железо: ⭐⭐⭐ (Vulkan)**

**Ссылки:** https://github.com/TNTwise/SPAN-ncnn-vulkan

---

### Сравнение апскейлеров для выбора

| Backend | Сильные стороны | Слабые стороны | Рекомендация |
|---|---|---|---|
| Real-ESRGAN animevideov3 | Быстро, хорошо для пакетов | Средние линии | **Стандарт**, пакетная обработка |
| Real-ESRGAN x4plus-anime | Чёткие линии на статике | Только ×4 | **Качество**, финальный рендер |
| Real-CUGAN se | Лучшие края / line art | Настройка шума | Аниме-стиль, чёткие контуры |
| SPAN | Лучшее качество PSNR | Фиксированный масштаб | Максимальное качество |

---

## 3. Anim — гармонизация 16:9

| | |
|---|---|
| **Модуль** | `anim/harmonize.py` |
| **Backend** | OpenCV (без ML) |

| Режим | Когда автовыбирается | Описание |
|---|---|---|
| `blurred_pillarbox` | AR панели > 1.0 (горизонтальные) | Размытая растянутая версия + оригинал по центру |
| `dominant_color` | AR < 1.0 (вертикальные/квадратные) | Доминантный цвет через k-means + виньетка |
| `smart_crop` | AR близко к 16:9 (±20%) | Crop по центру |
| `auto` | — | Автовыбор по AR |

**Параметры:** `blur_sigma` (60 по умолчанию), `vignette_strength` (0.6), `dominant_k` (3).

**Под железо: ⭐⭐⭐** — только CPU, < 0.1 с/панель.

---

## 4. Anim — оживление

### 4.1 OpenCV эффекты (без ML)

| | |
|---|---|
| **Модуль** | `anim/animate_opencv.py` |
| **Режимы** | `opencv_zoom`, `opencv_shake`, `opencv_chromatic`, `opencv_combined`, `static` |

**Под железо: ⭐⭐⭐** — мгновенно, без зависимостей.

---

### 4.2 DepthFlow + Depth Anything V2 Small (основной parallax)

| | |
|---|---|
| **Модуль** | `anim/animate_depthflow.py` |
| **Установка** | `pip install depthflow` |
| **Depth-модель** | Depth Anything V2 Small — качается автоматически при первом запуске |
| **HF страница** | https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf |

**Режимы анимации:** `zoom`, `dolly`, `orbital`, `horizontal`, `vertical`, `circle`  
**Пресет «Качество»:** `dolly`

**Под железо: ⭐⭐ (качество) / ⭐ (скорость)**

- ✅ Лучший parallax, использует AMD iGPU через OpenGL для рендера
- ⚠️ Оценка глубины — PyTorch на CPU (медленно)
- ⚠️ На 1920×1080, 3 s @ 24 fps — **минуты** на панель
- RAM: 16 GB достаточно для Small; Base/Large — не рекомендуется

**Ссылки:** https://github.com/BrokenSource/DepthFlow · https://github.com/DepthAnything/Depth-Anything-V2

---

### 4.3 MiDaS v2.1 small (задел, не основной путь)

| | |
|---|---|
| **Файлы** | `models/anim/depth/midas_v21_small_256.onnx`, `*_int8.onnx` |
| **Источник** | https://huggingface.co/julienkay/sentis-MiDaS/tree/main/onnx |
| **Статус** | Скачан и квантован для совместимости; DepthFlow использует DA-V2, не этот файл |

**Под железо: ⭐⭐⭐** — если подключать напрямую через ONNX; легче DA-V2, грубее детали.

---

### 4.4 TPSMM — motion transfer

| | |
|---|---|
| **Модуль** | `anim/animate_tpsmm.py` |
| **Файлы** | `kp_detector_int8.onnx`, `tpsmm_rel_int8.onnx` в `models/anim/tpsmm/` |
| **Источник** | https://github.com/instant-high/Thin-plate-spline-motion-model-ONNX |
| **Режим** | `mode: tpsmm` в `anim_pipeline.py`, Gradio, :8000, `POST /api/animate` |
| **Вход** | Панель PNG + **driving video** (MP4): `tpsmm_driving_video` в `config_animate.yaml` или UI |

**Под железо: ⭐⭐** — ~50–120 MB INT8, CPU inference медленный (минуты на панель). Сегментация персонажа (блок B3) улучшит качество, но не обязательна для запуска.

---

## 5. Вспомогательное

| Компонент | Назначение | Путь | Оценка |
|-----------|-----------|------|--------|
| **ffmpeg** | H.264 MP4, concat storyboard | `models/anim/ffmpeg/bin/ffmpeg.exe` | ⭐⭐⭐ |
| **OpenCV** | Harmonize, эффекты, crop | pip | ⭐⭐⭐ |
| **Konva 9** | Canvas-редактор масок (:8000) | CDN | ⭐⭐⭐ |

---

## 6. Сводная таблица: модель → железо → качество

| Модель | Backend | RAM | Скорость | Качество |
|--------|---------|-----|----------|---------|
| YOLO INT8 (comic) | ONNX CPU | < 500 MB | Быстро | Хорошо (western) |
| YOLO INT8 (manga) | ONNX CPU | < 500 MB | Быстро | Хорошо (манга) |
| MobileSAM INT8 | ONNX CPU | +1–2 GB | Медленно | Отличные края |
| Real-ESRGAN animevideov3 | NCNN Vulkan | низкая | Быстро | Хорошо |
| Real-ESRGAN x4plus-anime | NCNN Vulkan | средняя | ×4 только | Линии на статике |
| Real-CUGAN se | NCNN Vulkan | средняя | Быстро | Аниме-edges |
| SPAN x2/x4 | NCNN Vulkan | средняя | Быстро | **Лучшее PSNR** |
| DepthFlow + DA-V2 Small | OpenGL + CPU | 4–8 GB пик | Медленно | **Лучший parallax** |
| OpenCV анимация | CPU | минимум | Мгновенно | Базовое движение |
| TPSMM INT8 | ONNX CPU | средняя | Медленно | Driving MP4 обязателен |

---

## 7. Рекомендации по улучшению качества (без CUDA)

### Быстрый профиль (черновик)

```yaml
# config.yaml
quality_mode: fast

# config_animate.yaml
upscale:
  model: animevideov3
  scale: 2
  gpu_id: 0
animation:
  mode: opencv_zoom
  duration: 2.0
```

### Максимум качества (без CUDA)

```yaml
# config.yaml
quality_mode: accurate

# config_animate.yaml
upscale:
  model: anime_6B        # NCNN: realesrgan-x4plus-anime, только ×4
  scale: 4
  gpu_id: 0
  tile_size: 128         # при швах плиток на iGPU
animation:
  mode: depthflow
  depthflow_animation: dolly
  duration: 3.0
```

### Что не рекомендуется

| Технология | Причина |
|---|---|
| Stable Diffusion / AnimateDiff / SVD | CUDA, VRAM, минуты на кадр |
| ControlNet inpainting для 16:9 | Тяжёлый CPU |
| Полный Meta SAM2 Large | CPU непрактичен |
| TensorRT / CUDA EP | Нет NVIDIA GPU |
| DA-V2 Base/Large в DepthFlow | ×3–10 медленнее Small |

---

## 8. Диск и скрипты загрузки

| Группа | ~Размер |
|--------|---------|
| Split INT8 (YOLO comic + manga + MobileSAM) | ~100 MB |
| Real-ESRGAN NCNN | ~90 MB |
| Real-CUGAN NCNN | ~60 MB |
| SPAN NCNN | ~80 MB |
| MiDaS ONNX INT8 | ~35 MB |
| TPSMM INT8 | ~60 MB |
| ffmpeg exe | ~100 MB |
| DepthFlow + DA-V2 Small (HF кэш) | +100–500 MB при первом запуске |
| **Итого (без кэша)** | ~500–600 MB |

**Скрипты:**

```powershell
# Split
.\scripts\split_models_craft_scripts\download_models.ps1
python scripts\split_models_craft_scripts\quantize_models.py

# Anim (основные)
.\scripts\download_animate_models.ps1
python scripts\quantize_animate_models.py

# CUGAN + SPAN
.\scripts\download_upscale_backends.ps1
python scripts\verify_upscale_backends.py
```

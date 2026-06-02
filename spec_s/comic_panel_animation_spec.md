# СПЕЦИФИКАЦИЯ ПРОЕКТА: Система оживления панелей комикса
### Универсальный промпт-документ для разработки с LLM-ассистентом

---

## 🎯 ЦЕЛЬ ПРОЕКТА

Разработать локальный Python-пайплайн для автоматической обработки раскроенных панелей комикса:
1. **Апскейл** — повышение качества и разрешения панелей
2. **Гармонизация к 16:9** — приведение панелей к формату видеомонтажа без AI-inpainting
3. **Оживление** — создание эффектов движения (parallax, shake, motion transfer) на статичных изображениях
4. **Сборка** — объединение обработанных панелей в видео-раскадровку

**Конечный результат:** из набора статичных панелей комикса получить короткие MP4-клипы на каждую панель, пригодные для нелинейного монтажа, с последующей сборкой в единую раскадровку.

---

## ✅ СТАТУС РЕАЛИЗАЦИИ (июнь 2026)

См. также [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md), [ComicSplit_Documentation.md](ComicSplit_Documentation.md), [ROADMAP_QUALITY_BOOST.md](ROADMAP_QUALITY_BOOST.md).

| Модуль / функция | Файл | Статус |
|------------------|------|--------|
| Апскейл NCNN (Real-ESRGAN Vulkan) | `anim/upscale.py` | ✅ videov3 ×2/×4; x4plus-anime ×4; `tile_size`, benchmark |
| Гармонизация 16:9 | `anim/harmonize.py` | ✅ blurred_pillarbox, dominant_color, smart_crop, auto |
| OpenCV zoom / shake / static | `anim/animate_opencv.py` | ✅ |
| DepthFlow parallax | `anim/animate_depthflow.py` | ✅ CLI 0.9.x (`input … preset … main --render`) |
| ffmpeg → MP4, concat | `anim/render.py` | ✅ |
| Оркестратор CLI | `anim_pipeline.py` | ✅ |
| Конфиг | `config_animate.yaml`, `utils/anim_config.py` | ✅ |
| Пресеты Стандарт / Качество | `config/presets.yaml`, `utils/presets.py` | ✅ API + Gradio + :8000 |
| Gradio вкладки Upscale / Video | `main.py` | ✅ модель, GPU, harmonize, intensity, tooltips |
| REST API v1.2 | `api/server.py` → upscale, animate, presets, tooltips | ✅ |
| Веб UI Upscale / Video | `frontend/index.html` | ✅ паритет с Gradio |
| Сегментация (`segment.py`) | — | ❌ не реализовано |
| TPSMM motion transfer | модели в `models/anim/tpsmm/` | 🟡 ONNX есть, **не в пайплайне** |
| LivePortrait | — | ❌ |
| MiDaS в anim-пайплайне | ONNX в `models/anim/depth/` | 🟡 для TPSMM/будущего; DepthFlow оценивает глубину сам |

**Точки входа:**

```powershell
python anim_pipeline.py <panels_dir> <output_dir> --mode opencv_zoom --scale 2
uvicorn api.server:app --port 8000   # вкладки Upscale / Video
python main.py                       # Gradio Upscale / Video
```

**Модели:** `scripts/download_animate_models.ps1`, `scripts/quantize_animate_models.py --verify`

---

## 💻 ЦЕЛЕВОЕ ЖЕЛЕЗО (HARD CONSTRAINT)

```
CPU:  AMD Ryzen 5 5600H (6 ядер / 12 потоков, 3.30 GHz)
GPU:  AMD Radeon Graphics (iGPU, интегрированный, ~1009 MB VRAM)
RAM:  16.0 GB DDR4 @ 3200 МГц
HDD:  477 GB (занято ~339 GB)
OS:   Windows 10/11
```

**Критические ограничения:**
- ❌ CUDA недоступен (нет NVIDIA GPU)
- ❌ Диффузионные модели (SD, SDXL, SVD, AnimateDiff) — неприемлемо медленны на CPU
- ✅ ONNX Runtime с CPUExecutionProvider — основной путь инференса
- ✅ NCNN + Vulkan — возможен через AMD iGPU (требует проверки Vulkan 1.3)
- ✅ OpenCV — для всех операций без ML
- ✅ 16 GB RAM — позволяет загружать несколько небольших моделей одновременно

---

## 🔬 ХОД ИССЛЕДОВАНИЯ

### Этап 1 — Анализ существующего инструментария
Отправная точка: уже используется `yolo_comic.onnx` (~100 MB) для раскройки панелей комикса. Принцип "лёгкие специализированные ONNX/NCNN модели" принят как стандарт для всего последующего стека.

### Этап 2 — Исследование инструментов оживления
Изучены следующие подходы:
- Диффузионные видео-модели (SVD, AnimateDiff) — **отклонены** из-за требований к VRAM и CUDA
- TPSMM (Thin Plate Spline Motion Model) — **принят**, есть ONNX-версия с флагом CPU
- LivePortrait — **условно принят** (только для реалистичных лиц, медленно на CPU)
- DepthFlow — **принят** как лучший инструмент для parallax из коробки
- MiDaS small — **принят** как лёгкая модель карты глубины

### Этап 3 — Исследование сегментации
Нужна для: "оживить только персонажа отдельно от фона"
- SAM (оригинальный) — **отклонён**, слишком тяжёлый
- MobileSAM — **принят**, ~40 MB, CPU inference за ~3 сек
- SAM2-tiny ONNX — **принят** как альтернатива с лучшим качеством

### Этап 4 — Исследование апскейла
- Upscayl (GUI, NCNN/Vulkan) — **принят как основной**, поддерживает AMD Vulkan
- Real-ESRGAN ONNX — **принят как fallback** (100% CPU, медленнее)
- Модель `RealESRGAN_x4plus_anime_6B` — **выбрана** как специализированная под иллюстрации

### Этап 5 — Исследование гармонизации к 16:9
AI-inpainting **отклонён** (слишком тяжёл для целевого железа).
Выбраны три техники на чистом OpenCV:
- **Blurred Pillarbox** — главная техника (стандарт ТВ-производства)
- **Dominant Color + Vignette** — для стилизованных панелей
- **Smart Crop** — для панелей близких к 16:9

---

## 🏗️ ФИНАЛЬНЫЙ СТЕК ТЕХНОЛОГИЙ

### Порядок обработки одной панели:

```
[Входная панель из yolo_comic.onnx]
          │
          ▼
┌─────────────────────┐
│   1. АПСКЕЙЛ        │  Real-ESRGAN anime_6B (x2-x4)
│   NCNN/Vulkan       │  Инструмент: Upscayl CLI / realesrgan-ncnn-vulkan
│   или ONNX/CPU      │  Fallback: RealESRGAN_ONNX (CPUExecutionProvider)
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  2. ГАРМОНИЗАЦИЯ    │  Blurred Pillarbox / Dominant Color + Vignette
│     к 16:9          │  Инструмент: OpenCV (нет ML)
│  1920 × 1080 px     │  
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  3. СЕГМЕНТАЦИЯ     │  MobileSAM ONNX (по необходимости)
│  (если нужна        │  SAM2-tiny ONNX (лучше качество)
│   маска объекта)    │  
└────────┬────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│           4. ОЖИВЛЕНИЕ (выбрать режим)       │
│                                             │
│  A) Parallax/Глубина:                       │
│     MiDaS small → DepthFlow                 │
│     Эффект: 3D parallax, Ken Burns, zoom    │
│                                             │
│  B) Motion Transfer (персонаж):             │
│     TPSMM-ONNX (source=панель,              │
│     driving=короткое видео движения)        │
│     Эффект: перенос анимации на объект      │
│                                             │
│  C) Face Animation (реалистичные лица):     │
│     LivePortrait ONNX                       │
│     Эффект: мимика, моргание               │
│                                             │
│  D) Простые эффекты (без ML):               │
│     OpenCV: shake, zoom pulse,              │
│     chromatic aberration, text bubble pop   │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────┐
│   5. РЕНДЕР         │  OpenCV → покадровый PNG
│                     │  ffmpeg → .mp4 панель (2-5 сек, 24fps)
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  6. СБОРКА          │  ffmpeg concat → финальная раскадровка
│  РАСКАДРОВКИ        │  Формат: 1920×1080, H.264, AAC
└─────────────────────┘
```

---

## 📦 ПОЛНЫЙ СПИСОК РЕСУРСОВ

### Существующий инструмент (точка входа)
| Инструмент | Описание | Ссылка |
|---|---|---|
| yolo_comic.onnx | Раскройка панелей комикса, ~100 MB | уже используется |

### Апскейл
| Инструмент | Описание | Ссылка |
|---|---|---|
| Real-ESRGAN (основной репо) | Базовый проект, Python + PyTorch | https://github.com/xinntao/Real-ESRGAN |
| Real-ESRGAN NCNN Vulkan | CLI-бинарник для AMD/Intel/NVIDIA без CUDA | https://github.com/xinntao/Real-ESRGAN/releases |
| RealESRGAN_ONNX | ONNX-версия для CPU inference | https://github.com/muhammad-ahmed-ghani/RealESRGAN_ONNX |
| Upscayl (GUI + CLI) | Десктопный GUI на NCNN/Vulkan, модель Digital Art для комиксов | https://github.com/upscayl/upscayl |
| Upscayl NCNN backend | CLI-ядро Upscayl для скриптовой интеграции | https://github.com/upscayl/upscayl-ncnn |
| Модель anime_6B | Веса для комикс/аниме стиля, ~18 MB | https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth |
| Модель animevideov3 | Быстрая лёгкая модель, хороша для пакетной обработки | https://github.com/xinntao/Real-ESRGAN/releases |

### Глубина и Parallax
| Инструмент | Описание | Ссылка |
|---|---|---|
| DepthFlow | Главный инструмент parallax-анимации из статичного изображения, Windows portable | https://github.com/BrokenSource/DepthFlow |
| DepthFlow документация | Параметры движения камеры, примеры команд | https://depth.brokensrc.dev/docs/ |
| MiDaS | Оценка глубины, модель small ~50 MB | https://github.com/isl-org/MiDaS |
| MiDaS ONNX модели | Готовые .onnx веса | https://github.com/isl-org/MiDaS/releases |
| Depth Anything v2 | Более точная карта глубины (тяжелее MiDaS) | https://github.com/LiheYoung/Depth-Anything |
| ComfyUI DepthFlow Nodes | Ноды для интеграции DepthFlow в ComfyUI | https://github.com/akatz-ai/ComfyUI-Depthflow-Nodes |

### Анимация движения объектов
| Инструмент | Описание | Ссылка |
|---|---|---|
| TPSMM-ONNX | Thin Plate Spline Motion Model, ONNX + флаг --cpu, анимация любых объектов | https://github.com/instant-high/Thin-plate-spline-motion-model-ONNX |
| TPSMM оригинал (CVPR 2022) | Академическая база, архитектура модели | https://github.com/yoyo-nb/Thin-Plate-Spline-Motion-Model |

### Анимация лиц
| Инструмент | Описание | Ссылка |
|---|---|---|
| LivePortrait (KwaiVGI) | Официальный репо, CPU поддержка через onnxruntime | https://github.com/KwaiVGI/LivePortrait |
| LivePortrait веса HuggingFace | .pth файлы моделей | https://huggingface.co/KwaiVGI/LivePortrait |
| ComfyUI-LivePortraitKJ | Ноды LivePortrait для ComfyUI | https://github.com/kijai/ComfyUI-LivePortraitKJ |

### Сегментация объектов
| Инструмент | Описание | Ссылка |
|---|---|---|
| MobileSAM | Лёгкий SAM, ~40 MB, CPU ~3 сек/изображение, ONNX экспорт | https://github.com/ChaoningZhang/MobileSAM |
| SAM2-tiny ONNX | Точнее MobileSAM, ~155 MB, pip install samexporter | https://huggingface.co/vietanhdev/segment-anything-2-onnx-models |
| samexporter | Конвертер SAM2 → ONNX | https://github.com/vietanhdev/samexporter |

### GUI / Оркестрация
| Инструмент | Описание | Ссылка |
|---|---|---|
| ComfyUI | Визуальный node-based интерфейс для пайплайнов, флаг --cpu | https://github.com/comfyanonymous/ComfyUI |

### Базовые инструменты (обязательны)
| Инструмент | Описание | Установка |
|---|---|---|
| Python 3.10+ | Основной язык | https://www.python.org |
| OpenCV | Все операции с изображениями без ML | `pip install opencv-python` |
| ONNX Runtime | CPU инференс для всех .onnx моделей | `pip install onnxruntime` |
| ffmpeg | Сборка видео из кадров, конкатенация | https://ffmpeg.org/download.html |
| NumPy | Матричные операции | `pip install numpy` |
| Pillow | Работа с изображениями | `pip install Pillow` |
| scikit-learn | k-means для dominant color | `pip install scikit-learn` |

---

## 📐 ТЕХНИЧЕСКИЕ ТРЕБОВАНИЯ К ВЫХОДНЫМ ДАННЫМ

```
Формат кадра:     1920 × 1080 px (16:9)
Частота кадров:   24 fps
Длина клипа:      2–5 секунд на панель (настраивается)
Видеокодек:       H.264 (libx264)
Аудио:            нет (или AAC заглушка для монтажа)
Контейнер:        .mp4
Цветовое пр-во:   sRGB
```

---

## 🧩 ДЕТАЛЬНОЕ ОПИСАНИЕ МОДУЛЕЙ

### Модуль 1: Апскейл (`upscale.py`)

**Входные данные:** PNG/JPG панель комикса (любой размер)
**Выходные данные:** PNG апскейленная панель (x2 или x4)

**Логика выбора модели:**
- Если доступен Vulkan 1.3 на AMD iGPU → `realesrgan-ncnn-vulkan` с моделью `RealESRGAN_x4plus_anime_6B`
- Если Vulkan недоступен → `RealESRGAN_ONNX` через `onnxruntime.InferenceSession` с `CPUExecutionProvider`

**Параметры:**
- `scale`: 2 или 4 (рекомендуется 2 для скорости, 4 для качества)
- `tile_size`: 256 (для экономии RAM при больших изображениях)
- `model`: `anime_6B` или `animevideov3`

**Проверка Vulkan перед запуском:**
```python
import subprocess
result = subprocess.run(['realesrgan-ncnn-vulkan.exe', '-h'], capture_output=True)
vulkan_available = result.returncode == 0
```

---

### Модуль 2: Гармонизация к 16:9 (`harmonize.py`)

**Входные данные:** PNG панели (любые пропорции)
**Выходные данные:** PNG 1920×1080

**Три режима (выбираются автоматически или вручную):**

#### Режим A: Blurred Pillarbox (рекомендуемый по умолчанию)
```
Алгоритм:
1. Взять оригинальную панель
2. Растянуть до 1920×1080 (с нарушением пропорций) → background_layer
3. Применить cv2.GaussianBlur(sigma=60) или cv2.blur(kernel=(120,120))
4. Поместить оригинальную панель по центру (сохранив пропорции, вписав в 1920×1080)
5. Опционально: добавить лёгкую виньетку по краям панели через alpha-маску
```

#### Режим B: Dominant Color + Vignette
```
Алгоритм:
1. Найти доминантный цвет панели через cv2.kmeans (k=3, выбрать наиболее представленный)
2. Залить 1920×1080 canvas этим цветом
3. Поместить оригинальную панель по центру
4. Создать elliptical gradient mask для плавного перехода краёв панели в фон
5. Применить маску: panel_rgba → blend с background
```

#### Режим C: Smart Crop (для широких панелей, AR > 1.5)
```
Алгоритм:
1. Если соотношение сторон панели уже близко к 16:9 (±20%) → просто crop по центру
2. Если используется SAM-маска объектов → crop так, чтобы объект остался в кадре
```

**Автовыбор режима:**
```python
panel_ar = width / height
if abs(panel_ar - 16/9) < 0.2:
    mode = 'smart_crop'
elif panel_ar < 1.0:  # вертикальные/квадратные
    mode = 'dominant_color'  # или 'blurred_pillarbox'
else:
    mode = 'blurred_pillarbox'
```

---

### Модуль 3: Сегментация (`segment.py`)

**Входные данные:** PNG панель + опционально point prompt (x, y)
**Выходные данные:** бинарная маска PNG (белый=объект, чёрный=фон)

**Использование MobileSAM:**
```python
from mobile_sam import sam_model_registry, SamPredictor
model = sam_model_registry["vit_t"](checkpoint="./mobile_sam.pt")
model.eval()
predictor = SamPredictor(model)
predictor.set_image(image_rgb)
masks, _, _ = predictor.predict(point_coords=[[x, y]], point_labels=[1])
```

**Использование SAM2-tiny ONNX:**
```bash
pip install samexporter
python -m samexporter.export_sam2 --checkpoint sam2_hiera_tiny.pt --output sam2_tiny.onnx
```

---

### Модуль 4: Оживление (`animate.py`)

#### Режим A: DepthFlow Parallax
```bash
# Установка (portable Windows)
# Скачать с https://github.com/BrokenSource/DepthFlow/releases

# Запуск (DepthFlow 0.9.x — цепочка команд, не `run`)
python -m depthflow input --image panel.png zoom --intensity 0.75 \
    main --render --output panel_animated.mp4 --time 3 --fps 24

python -m depthflow input --image panel.png dolly \
    main --render --output panel_animated.mp4 --time 3 --fps 24
```

#### Режим B: TPSMM Motion Transfer
```python
import onnxruntime as ort
import numpy as np

# Загрузка сессий
kp_session = ort.InferenceSession('kp_detector.onnx', 
    providers=['CPUExecutionProvider'])
tpsmm_session = ort.InferenceSession('tpsmm_rel.onnx',
    providers=['CPUExecutionProvider'])

# source_image: панель комикса (256x256, нормализованная)
# driving_video: массив кадров движения (numpy)
# Результат: кадры анимированной панели
```

**Важно:** TPSMM требует driving video — короткую запись движения.
Можно создать synthetic driving video из геометрических трансформаций (качание, поворот).

#### Режим C: OpenCV эффекты (без ML)
```python
def shake_effect(frame, intensity=5, n_frames=24):
    """Случайная тряска кадра"""
    frames = []
    for _ in range(n_frames):
        dx = np.random.randint(-intensity, intensity)
        dy = np.random.randint(-intensity, intensity)
        M = np.float32([[1,0,dx],[0,1,dy]])
        frames.append(cv2.warpAffine(frame, M, (frame.shape[1], frame.shape[0])))
    return frames

def zoom_pulse(frame, n_frames=24, max_zoom=1.05):
    """Плавный zoom in/out"""
    frames = []
    for i in range(n_frames):
        scale = 1 + (max_zoom-1) * np.sin(np.pi * i / n_frames)
        M = cv2.getRotationMatrix2D((frame.shape[1]//2, frame.shape[0]//2), 0, scale)
        frames.append(cv2.warpAffine(frame, M, (frame.shape[1], frame.shape[0])))
    return frames

def chromatic_aberration(frame, shift=3):
    """Расщепление RGB каналов"""
    b, g, r = cv2.split(frame)
    r = np.roll(r, shift, axis=1)
    b = np.roll(b, -shift, axis=1)
    return cv2.merge([b, g, r])
```

---

### Модуль 5: Рендер и сборка (`render.py`)

**Покадровый рендер → MP4:**
```python
import subprocess

def frames_to_video(frames, output_path, fps=24):
    h, w = frames[0].shape[:2]
    cmd = [
        'ffmpeg', '-y',
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo', 
        '-s', f'{w}x{h}',
        '-pix_fmt', 'bgr24',
        '-r', str(fps),
        '-i', 'pipe:',
        '-vcodec', 'libx264',
        '-pix_fmt', 'yuv420p',
        output_path
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for frame in frames:
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    proc.wait()
```

**Конкатенация панелей в раскадровку:**
```bash
# Создать файл list.txt:
# file 'panel_001.mp4'
# file 'panel_002.mp4'
# ...

ffmpeg -f concat -safe 0 -i list.txt -c copy storyboard.mp4
```

---

## ⚡ ОЖИДАЕМАЯ ПРОИЗВОДИТЕЛЬНОСТЬ

| Операция | Инструмент | Время / панель |
|---|---|---|
| Апскейл x2 (NCNN/Vulkan) | realesrgan-ncnn-vulkan + anime_6B | ~10–30 сек |
| Апскейл x2 (ONNX/CPU) | RealESRGAN_ONNX | ~1–3 мин |
| Гармонизация 16:9 | OpenCV | < 0.1 сек |
| Карта глубины | MiDaS small ONNX | ~0.5–1 сек |
| DepthFlow анимация | DepthFlow (CPU) | ~30–90 сек |
| Сегментация | MobileSAM | ~3–5 сек |
| Motion Transfer | TPSMM-ONNX (CPU) | ~30–60 сек (30 кадров) |
| Shake/Zoom эффекты | OpenCV | < 0.1 сек |
| Рендер в MP4 | ffmpeg | ~2–5 сек |

**Суммарно на одну панель (базовый режим: апскейл + 16:9 + parallax):** ~2–4 минуты

---

## 📁 РЕКОМЕНДУЕМАЯ СТРУКТУРА ПРОЕКТА

```
comic_animator/
├── models/
│   ├── mobile_sam.pt                    # MobileSAM веса
│   ├── midas_v21_small_256.onnx         # MiDaS depth
│   ├── kp_detector.onnx                 # TPSMM keypoints
│   ├── tpsmm_rel.onnx                   # TPSMM animation
│   └── realesrgan-ncnn-vulkan.exe       # Апскейл бинарник
├── input/
│   └── panels/                          # Раскроенные панели от yolo_comic.onnx
├── output/
│   ├── upscaled/                        # После апскейла
│   ├── harmonized/                      # После 16:9 гармонизации
│   ├── animated/                        # MP4 клипы панелей
│   └── storyboard.mp4                   # Финальная раскадровка
├── anim/
│   ├── upscale.py
│   ├── harmonize.py
│   ├── animate_opencv.py
│   ├── animate_depthflow.py
│   ├── render.py
│   └── io_utils.py
├── anim_pipeline.py                     # CLI оркестратор
├── config_animate.yaml                  # Настройки anim
├── main.py                              # Gradio (вкладки Upscale / Video)
├── api/server.py                        # REST upscale / animate
└── requirements.txt                     # + depthflow (pip)
```

---

## 📋 REQUIREMENTS.TXT

```txt
opencv-python>=4.8.0
onnxruntime>=1.16.0
numpy>=1.24.0
Pillow>=10.0.0
scikit-learn>=1.3.0
tqdm>=4.65.0
PyYAML>=6.0
# MobileSAM (установка отдельно):
# pip install git+https://github.com/ChaoningZhang/MobileSAM.git
# SAM2 ONNX (установка отдельно):
# pip install samexporter
```

---

## ⚙️ CONFIG.YAML (пример)

```yaml
# Апскейл
upscale:
  enabled: true
  scale: 2                    # 2 или 4
  model: anime_6B             # anime_6B | animevideov3 | x4plus
  backend: auto               # auto | ncnn_vulkan | onnx_cpu
  tile_size: 256

# Гармонизация
harmonize:
  enabled: true
  target_width: 1920
  target_height: 1080
  mode: auto                  # auto | blurred_pillarbox | dominant_color | smart_crop
  blur_sigma: 60              # для blurred_pillarbox
  vignette_strength: 0.7      # 0.0 - 1.0

# Сегментация
segmentation:
  enabled: false              # включать только при motion transfer
  model: mobile_sam           # mobile_sam | sam2_tiny
  
# Анимация
animation:
  mode: depthflow             # depthflow | tpsmm | opencv_shake | opencv_zoom
  duration: 3                 # секунды
  fps: 24
  intensity: 0.3              # общая интенсивность эффекта 0.0-1.0

# Сборка
render:
  concat_panels: true         # собирать раскадровку
  output_format: mp4
  codec: libx264
```

---

## 🚀 СЛЕДУЮЩИЕ ШАГИ (после MVP)

1. **TPSMM** — подключить `models/anim/tpsmm/*_int8.onnx` в `anim_pipeline` (режим `tpsmm`)
2. **`segment.py`** — MobileSAM для отделения персонажа (опционально к TPSMM)
3. **Нагрузочный тест** — 10+ панелей, замер RAM/времени на Ryzen 5600H
4. **PyInstaller** — единый EXE с anim-моделями (модели вне git)
5. **LivePortrait** — только если появится лёгкий CPU-путь (низкий приоритет)

**Уже сделано (не повторять):** harmonize, upscale NCNN, OpenCV/DepthFlow, `anim_pipeline.py`, Gradio/API/UI, скрипты загрузки моделей.

---

## 📌 ВАЖНЫЕ ЗАМЕТКИ ДЛЯ LLM-АССИСТЕНТА

- Весь код должен работать **без CUDA**. Всегда использовать `providers=['CPUExecutionProvider']` в `onnxruntime.InferenceSession`
- При работе с NCNN-бинарниками — вызывать через `subprocess`, не Python-биндинги
- Для батч-обработки — обрабатывать панели **последовательно** (не параллельно), RAM ограничена
- **Не предлагать** Stable Diffusion, ControlNet, AnimateDiff, SVD и другие диффузионные модели
- **Не предлагать** PyTorch inference напрямую — только через ONNX Runtime или предкомпилированные бинарники
- Для тайлинга в апскейле использовать `tile_size=256` чтобы не выходить за пределы 16GB RAM
- DepthFlow — первый приоритет для тестирования, так как имеет готовый portable exe

---

*Документ: исследование v1.0 + статус реализации v1.2 (июнь 2026)*  
*MVP проверен на AMD Ryzen 5 5600H + Radeon iGPU + 16GB RAM, Windows, Python 3.11*

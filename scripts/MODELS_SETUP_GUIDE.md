# Инструкция: загрузка и подготовка моделей для модуля `anim/`

## Карта моделей

| Модуль | Модель | Формат | Размер | Квантование |
|--------|--------|--------|--------|-------------|
| `upscale.py` | realesrgan-ncnn-vulkan | NCNN бинарник | ~7 MB exe + ~64 MB модели | не нужно |
| `upscale.py` (fallback) | midas_v21_small_256 | ONNX → INT8 | 66 MB → ~33 MB | да, dynamic INT8 |
| `animate_depthflow.py` | DepthFlow | Python пакет / exe | ~pip зависимости | не применимо |
| `animate_depthflow.py` | midas_v21_small_256 | ONNX → INT8 | 66 MB → ~33 MB | да, dynamic INT8 |
| `animate_tpsmm.py` | kp_detector + tpsmm_rel | ONNX → INT8 | ~120 MB → ~60 MB | да, dynamic INT8 |

**Итого место на диске:** ~300 MB до квантования → ~150 MB после

---

## Структура директорий (куда кладём файлы)

```
SPLIT_PANELS_DEV/
└── models/
    ├── README.md                        ← уже есть (split-модели)
    ├── anim/                            ← создаём новую папку
    │   ├── upscale/
    │   │   ├── realesrgan-ncnn-vulkan.exe
    │   │   └── models/                  ← .bin + .param файлы
    │   │       ├── realesr-animevideov3-x4.bin
    │   │       ├── realesr-animevideov3-x4.param
    │   │       ├── RealESRGAN_x4plus_anime_6B.bin
    │   │       └── RealESRGAN_x4plus_anime_6B.param
    │   ├── depth/
    │   │   ├── midas_v21_small_256.onnx      ← исходная
    │   │   └── midas_v21_small_256_int8.onnx ← после квантования
    │   └── tpsmm/
    │       ├── kp_detector.onnx              ← исходная
    │       ├── kp_detector_int8.onnx         ← после квантования
    │       ├── tpsmm_rel.onnx                ← исходная
    │       └── tpsmm_rel_int8.onnx           ← после квантования
```

---

## Шаг 1 — Real-ESRGAN (апскейл) 

### Что скачиваем

Готовый Windows бинарник с NCNN моделями внутри.  
Никакой конвертации не нужно — архив уже содержит всё.

### Ссылка для скачивания

```
https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip
```

### Что внутри архива

```
realesrgan-ncnn-vulkan-20220424-windows.zip
├── realesrgan-ncnn-vulkan.exe      ← исполняемый файл (Vulkan/NCNN)
└── models/
    ├── realesr-animevideov3-x4.bin     ← быстрая модель для аниме/видео
    ├── realesr-animevideov3-x4.param
    ├── RealESRGAN_x4plus_anime_6B.bin  ← качественная модель для иллюстраций
    ├── RealESRGAN_x4plus_anime_6B.param
    ├── RealESRGAN_x4plus.bin
    └── RealESRGAN_x4plus.param
```

### Распаковка

Содержимое архива → `models/anim/upscale/`

### Проверка работы

```powershell
# Из папки models/anim/upscale/
.\realesrgan-ncnn-vulkan.exe -i test.png -o test_upscaled.png -n realesr-animevideov3-x4 -s 2
```

### Режимы и выбор модели

| Модель | Назначение | Скорость |
|--------|-----------|---------|
| `realesr-animevideov3-x4` | Аниме/комиксы, пакетная обработка | Быстрее |
| `RealESRGAN_x4plus_anime_6B` | Иллюстрации, высокое качество | Медленнее |

**Рекомендация:** использовать `realesr-animevideov3-x4` с `-s 2` (x2 апскейл вместо x4 — в 2 раза быстрее).

### Важно: флаг GPU для AMD iGPU

```powershell
# Список GPU в системе (проверить что Vulkan видит AMD Radeon)
.\realesrgan-ncnn-vulkan.exe -i test.png -o out.png -g -1
# -g -1 = CPU fallback если Vulkan не работает
# -g 0  = первый GPU (AMD iGPU)
```

---

## Шаг 2 — MiDaS small (карта глубины для DepthFlow)

### Что скачиваем

Файл ONNX с HuggingFace (уже конвертирован, не требует PyTorch):

```
https://huggingface.co/julienkay/sentis-MiDaS/resolve/main/onnx/midas_v21_small_256.onnx
```

Или оригинальный `.pt` с GitHub (потребуется конвертация, см. ниже):

```
https://github.com/isl-org/MiDaS/releases/download/v2_1/midas_v21_small_256.pt
```

**Рекомендуем ONNX с HuggingFace** — не нужен PyTorch для конвертации.

### Куда кладём

```
models/anim/depth/midas_v21_small_256.onnx
```

### Конвертация .pt → .onnx (только если скачали .pt)

```python
# Требуется: pip install torch timm
import torch
import torch.onnx

# Клонировать репо MiDaS
# git clone https://github.com/isl-org/MiDaS.git
# cd MiDaS

from midas.model_loader import load_model
model, transform, net_w, net_h = load_model(
    device=torch.device("cpu"),
    model_path="midas_v21_small_256.pt",
    model_type="MiDaS_small",
    optimize=False
)
model.eval()
dummy = torch.randn(1, 3, 256, 256)
torch.onnx.export(
    model, dummy,
    "midas_v21_small_256.onnx",
    opset_version=12,
    input_names=["input"],
    output_names=["output"],
    dynamic_axes={"input": {0: "batch"}, "output": {0: "batch"}}
)
```

---

## Шаг 3 — TPSMM (анимация движения объектов)

### Что скачиваем

Готовые ONNX файлы из releases:

```
https://github.com/instant-high/Thin-plate-spline-motion-model-ONNX/releases/latest
```

Нужны два файла из архива `tpsmm-onnx.zip`:
- `kp_detector.onnx` (~15 MB)
- `tpsmm_rel.onnx` (~100 MB)

### Куда кладём

```
models/anim/tpsmm/kp_detector.onnx
models/anim/tpsmm/tpsmm_rel.onnx
```

---

## Шаг 4 — DepthFlow (parallax анимация)

DepthFlow — это инструмент, не просто модель. Два варианта установки:

### Вариант A: pip (рекомендуется — интеграция с Python-пайплайном)

```powershell
pip install depthflow
```

DepthFlow автоматически скачает модели глубины при первом запуске.  
Если хочешь использовать наш MiDaS ONNX вместо встроенного — конфигурируется через API.

### Вариант B: CPU portable exe (если pip не подходит)

Скачать CPU-версию для Windows:
```
https://github.com/BrokenSource/DepthFlow/releases
# Файл: depthflow-cpu-windows-amd64-latest.exe
```

Запуск через subprocess из Python:
```python
subprocess.run([
    "depthflow-cpu-windows-amd64-latest.exe",
    "input", "--image", "panel.png",
    "main", "--output", "panel_animated.mp4",
    "--duration", "3", "--fps", "24"
])
```

### Важно: DepthFlow требует OpenGL

DepthFlow использует GLSL шейдеры для рендеринга параллакса.  
На AMD Ryzen 5 5600H + Radeon iGPU это работает через AMD драйверы (OpenGL 4.6 поддерживается).  
Убедись что AMD драйверы установлены и актуальны.

---

## Шаг 5 — Квантование ONNX моделей в INT8

### Что и зачем

| Модель | До квантования | После INT8 | Ускорение на CPU |
|--------|---------------|------------|-----------------|
| midas_v21_small_256.onnx | 66 MB | ~33 MB | 1.5–2× |
| kp_detector.onnx | ~15 MB | ~8 MB | 1.5× |
| tpsmm_rel.onnx | ~100 MB | ~50 MB | 1.5–2× |

Используем **dynamic quantization** — не требует калибровочных данных.

### Установка зависимостей

```powershell
pip install onnxruntime onnx
```

### Скрипт квантования (запускать после скачивания моделей)

Готовый скрипт: `scripts/quantize_animate_models.py`

```powershell
python scripts/quantize_animate_models.py
```

---

## Шаг 6 — Проверка готовности

Скрипт `scripts/quantize_animate_models.py --verify` проверяет:
- все файлы на месте
- ONNX модели загружаются без ошибок
- realesrgan-ncnn-vulkan.exe работает
- DepthFlow импортируется

```powershell
python scripts\quantize_animate_models.py --verify
```

Ожидаемый вывод:
```
[OK] realesrgan-ncnn-vulkan.exe найден
[OK] realesr-animevideov3-x4 модели найдены
[OK] midas_v21_small_256_int8.onnx загружается (вход: [1,3,256,256])
[OK] kp_detector_int8.onnx загружается
[OK] tpsmm_rel_int8.onnx загружается
[OK] depthflow импортируется
[OK] Все модели готовы к работе
```

---

## Итоговый порядок действий

```
1. Запустить scripts/download_animate_models.ps1
       ↓
2. Проверить Vulkan: realesrgan-ncnn-vulkan.exe -i test.png -o out.png
       ↓
3. Запустить scripts/quantize_animate_models.py
       ↓
4. Запустить scripts/verify_animate_models.py
       ↓
5. Если всё [OK] → можно интегрировать в anim/ модули
```

---

## Источники / репозитории

| Инструмент | Репозиторий | Документация |
|-----------|-------------|-------------|
| Real-ESRGAN | https://github.com/xinntao/Real-ESRGAN | https://github.com/xinntao/Real-ESRGAN/blob/master/docs/anime_video_model.md |
| Real-ESRGAN NCNN | https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan | README |
| MiDaS | https://github.com/isl-org/MiDaS | README |
| MiDaS ONNX (HF) | https://huggingface.co/julienkay/sentis-MiDaS | — |
| TPSMM ONNX | https://github.com/instant-high/Thin-plate-spline-motion-model-ONNX | README |
| DepthFlow | https://github.com/BrokenSource/DepthFlow | https://depth.brokensrc.dev/docs/ |
| DepthFlow installers | https://depth.brokensrc.dev/get/installers/ | — |

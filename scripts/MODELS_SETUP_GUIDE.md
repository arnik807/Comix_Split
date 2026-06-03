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
    │   │       ├── realesr-animevideov3-x2/x3/x4.bin + .param
    │   │       ├── realesrgan-x4plus-anime.bin + .param
    │   │       └── realesrgan-x4plus.bin + .param
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
    ├── realesr-animevideov3-x2.bin / -x3 / -x4 (+ .param)
    ├── realesrgan-x4plus-anime.bin     ← в UI: «x4plus-anime», конфиг id anime_6B
    ├── realesrgan-x4plus-anime.param
    ├── realesrgan-x4plus.bin
    └── realesrgan-x4plus.param
```

### Распаковка

Содержимое архива → `models/anim/upscale/`

### Проверка работы

```powershell
# Из папки models/anim/upscale/
.\realesrgan-ncnn-vulkan.exe -i test.png -o test_upscaled.png -n realesr-animevideov3-x4 -s 2
```

### Режимы и выбор модели

| NCNN `-n` | Конфиг id | Масштаб в приложении |
|-----------|-----------|----------------------|
| `realesr-animevideov3` | `animevideov3` | ×2 или ×4 |
| `realesrgan-x4plus-anime` | `anime_6B` | **только ×4** |

**Рекомендация:** пресет «Стандарт» — videov3 ×2; «Качество» — x4plus-anime ×4. Бенчмарк: `scripts\benchmark_upscale.ps1 -Quick`.

### Важно: флаг GPU для AMD iGPU

```powershell
# Список GPU в системе (проверить что Vulkan видит AMD Radeon)
.\realesrgan-ncnn-vulkan.exe -i test.png -o out.png -g -1
# -g -1 = CPU fallback если Vulkan не работает
# -g 0  = первый GPU (AMD iGPU)
```

---

## Шаг 1b — Real-CUGAN и SPAN (дополнительные апскейлеры, без квантования)

Готовые NCNN Vulkan сборки — **отдельные exe** и папки моделей. Квантование ONNX не применяется.

### Загрузка

```powershell
powershell -ExecutionPolicy Bypass -File scripts\download_upscale_backends.ps1
```

| Backend | Папка | Exe | Релиз |
|---------|-------|-----|--------|
| Real-CUGAN | `models/anim/upscale/realcugan/` | `realcugan-ncnn-vulkan.exe` | [20220728](https://github.com/nihui/realcugan-ncnn-vulkan/releases/tag/20220728) |
| SPAN | `models/anim/upscale/span/` | `span-ncnn-vulkan.exe` | [20240831-055257](https://github.com/TNTwise/SPAN-ncnn-vulkan/releases/tag/20240831-055257) |

Реестр путей и вариантов: `config/models_registry.yaml`, проверка: `utils/models_registry.py`.

### Проверка (все три backend)

```powershell
python scripts\verify_upscale_backends.py
```

### Ручной smoke (из корня репозитория)

```powershell
# Real-CUGAN — line art / аниме-зоны, noise -1 = без денойза
cd models\anim\upscale\realcugan
.\realcugan-ncnn-vulkan.exe -i ..\..\..\exam_img\standart_split\test_page\001_p001_panel.png -o out_cugan.png -s 2 -n -1 -m models-se -g 0

# SPAN — general efficient SR
cd ..\span
.\span-ncnn-vulkan.exe -m models -n spanx4_ch48 -s 4 -i ..\..\..\exam_img\standart_split\test_page\001_p001_panel.png -o out_span.png -g 0
```

**Параметры CUGAN, важные для качества (этап 2 UI):** `-n` (denoise -1..3), `-s` (1–4), `-m` (models-se / models-pro), `-c` (syncgap 0–3), `-t` (tile).

**Параметры SPAN:** `-n` (имя модели), `-s` (2/3/4, должен совпадать с моделью), `-m` (папка models).

Интеграция в ComicSplit UI/API — **следующий этап** (блок B4 roadmap); сейчас модели только скачаны и верифицированы CLI.

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

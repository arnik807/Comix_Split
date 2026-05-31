## Что за файлы в этой папке:

**`MODELS_SETUP_GUIDE.md`** — полный справочник: откуда что берётся, куда кладётся, зачем, с таблицами и пояснениями.

**`download_animate_models.ps1`** — кладёшь в `scripts/`, запускаешь один раз:
```powershell
powershell -ExecutionPolicy Bypass -File scripts\download_animate_models.ps1
```
Он сам создаст `models/anim/`, скачает Real-ESRGAN zip и распакует, скачает MiDaS ONNX с HuggingFace, получит TPSMM через GitHub API, установит depthflow через pip, проверит ffmpeg.

**`quantize_animate_models.py`** — кладёшь в `scripts/`, запускаешь после загрузки:
```powershell
python scripts\quantize_animate_models.py          # квантование + верификация
python scripts\quantize_animate_models.py --verify # только проверка
```
Квантует MiDaS и TPSMM в INT8 (~вдвое меньше размер, быстрее на CPU), затем проверяет весь стек и печатает итог с цветными статусами.

## Один важный момент про DepthFlow

DepthFlow использует GLSL шейдеры для рендеринга параллакса — это значит что AMD Radeon iGPU нужен не для ML, а именно для OpenGL рендера. На Ryzen 5 5600H с AMD Radeon это работает через стандартные AMD драйверы. Если при запуске возникнут проблемы — добавь флаг `--noturbo` в CLI команду.
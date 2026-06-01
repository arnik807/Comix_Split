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

## DepthFlow (parallax)

- Пакет: `pip install depthflow` (ставит `download_animate_models.ps1`)
- В коде: `anim/animate_depthflow.py` — цепочка `input -i … zoom|dolly main --render -o …`
- Нужен OpenGL (AMD iGPU через драйверы); headless: `WINDOW_BACKEND=headless`
- Первый запуск качает depth-модель (HuggingFace)

Split-модели — отдельно в `scripts/split_models_craft_scripts/`.
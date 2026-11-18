# Новая машина: чеклист установки и handoff для Cursor

**Версия:** 1.0 (ноябрь 2026)  
**Связано:** [MODELS_SETUP_GUIDE.md](MODELS_SETUP_GUIDE.md), [WEB_LLM_GIT_WORKFLOW.md](WEB_LLM_GIT_WORKFLOW.md), [LLM_HANDOFF_CONTEXT.md](LLM_HANDOFF_CONTEXT.md), [COMICSPLIT_SPEC.md](COMICSPLIT_SPEC.md)

Документ для переноса разработки на другой ПК: код, модели, Python, запуск `:8000` / Gradio, контекст для LLM в Cursor.

---

## Краткий handoff (вставить в первый чат Cursor на новой машине)

Скопируйте блок ниже в новый чат вместе с `@spec_s/LLM_HANDOFF_CONTEXT.md` и `@spec_s/COMICSPLIT_SPEC.md`.

```
Проект: ComicSplit (SPLIT_PANELS_DEV), Windows, Python 3.11, без CUDA.
Стек: split YOLO/SAM ONNX, веб :8000 FastAPI+Konva, ExText Stage 2a, NCNN upscale, anim CLI.
Статус (нояб 2026): main на GitHub/Sourcecraft; snap S1–S3, workspace project mode; R1 ExText HITL — formal ACCEPTANCE ⏳.
Продукт: COMICSPLIT_SPEC — beachhead recap/motion, v1 = софт для монтажёра, не автопилот.
Инфра: .env → SILICONFLOW_* (BYOK OCR); models/ не в git — копия или scripts; venv всегда пересоздавать.
Недавнее: починен main.py (Gradio); siliconflow test — баланс аккаунта критичен (402).
Железо-референс: Ryzen 5600H, AMD iGPU Vulkan, 16 GB RAM.
```

**Важно:** история чатов Cursor **не** переносится с папкой проекта — только файлы в `spec_s/`.

---

## Два способа получить проект на новой машине

| Способ | Когда | Модели | Git |
|--------|--------|--------|-----|
| **A. `git clone`** | Есть сеть, код уже на remote | Скачать скриптами (см. §4) | Сразу готов |
| **B. Копия всей папки** | USB / общий диск | Копировать `models/` целиком | Нужна папка `.git` в копии + `git pull` |

Рекомендуемый путь на диске: `D:\DEVELOP\COMICS\SPLIT_PANELS_DEV` (ASCII, удобно для PaddleOCR).

---

## Чеклист (отмечайте по шагам)

### 0. Перед уходом со старой машины

- [ ] `git status` — закоммитить или сознательно оставить WIP
- [ ] `git push github main; git push origin main` (см. [WEB_LLM_GIT_WORKFLOW.md](WEB_LLM_GIT_WORKFLOW.md))
- [ ] Перенести **`.env`** безопасно (не в git)
- [ ] При копии папки: включить **`models/`**, **`.git`**, опционально `config/presets.user.yaml`, `config/ui_state.user.json`
- [ ] **Не** копировать старый `venv_311` как рабочий (см. §3)

### 1. Система (новая машина)

- [ ] Windows 10/11 x64
- [ ] **Python 3.11** установлен, `python --version` → 3.11.x
- [ ] Драйвер GPU (Vulkan для NCNN upscale)
- [ ] Git установлен

### 2. Код репозитория

**Вариант A — clone:**

```powershell
cd D:\DEVELOP\COMICS
git clone https://github.com/arnik807/Comix_Split.git SPLIT_PANELS_DEV
cd SPLIT_PANELS_DEV
git remote add origin https://git.sourcecraft.dev/sparky/comixsplitter.git  # если ещё нет
git fetch github; git fetch origin
```

**Вариант B — копия папки:**

- [ ] Скопировать каталог целиком в `D:\DEVELOP\COMICS\SPLIT_PANELS_DEV`
- [ ] `git status` и `git pull origin main` (если есть `.git`)

### 3. Python-окружение (обязательно пересоздать)

Старый `venv_311` с другой машины **не использовать**.

```powershell
cd D:\DEVELOP\COMICS\SPLIT_PANELS_DEV
# переименовать или удалить старый venv при копии папки
python -m venv venv_311
.\venv_311\Scripts\activate
pip install -U pip
pip install -r requirements.txt
```

- [ ] `python -c "import fastapi, gradio, onnxruntime; print('ok')"`

### 4. Модели (`models/` — не в git)

**Если скопировали `models/` с рабочей машины** — переходите к §5.

**Если `models/` пустой** — из [MODELS_SETUP_GUIDE.md](MODELS_SETUP_GUIDE.md) / [../models/README.md](../models/README.md):

```powershell
.\venv_311\Scripts\activate
cd D:\DEVELOP\COMICS\SPLIT_PANELS_DEV

# Split
powershell -ExecutionPolicy Bypass -File scripts\split_models_craft_scripts\download_models.ps1
python scripts\split_models_craft_scripts\quantize_models.py
powershell -ExecutionPolicy Bypass -File scripts\export_manga_yolo.ps1

# Anim + upscale backends
powershell -ExecutionPolicy Bypass -File scripts\download_animate_models.ps1
powershell -ExecutionPolicy Bypass -File scripts\download_upscale_backends.ps1
python scripts\quantize_animate_models.py

# PaddleOCR — только если нужен offline OCR (не обязательно при siliconflow)
# powershell -ExecutionPolicy Bypass -File scripts\install_paddle_ocr.ps1
```

- [ ] Есть `models/yolo_comic_int8.onnx`, `models/yolo_manga_int8.onnx`
- [ ] Есть `models/anim/upscale/realesrgan-ncnn-vulkan.exe` (и при необходимости realcugan/span)

### 5. Секреты и локальный конфиг

- [ ] Создать `.env` из [../.env.example](../.env.example):

```env
SILICONFLOW_API_KEY=sk-...
SILICONFLOW_BASE_URL=https://api.siliconflow.com/v1
SILICONFLOW_VLM_MODEL=Qwen/Qwen3-VL-8B-Instruct
```

- [ ] По желанию скопировать `config/presets.user.yaml`, `config/ui_state.user.json`

### 6. Проверки (smoke)

```powershell
.\venv_311\Scripts\activate
cd D:\DEVELOP\COMICS\SPLIT_PANELS_DEV

python scripts\quantize_animate_models.py --verify
python scripts\verify_upscale_backends.py
python scripts\test_siliconflow_api.py
# опционально vision: python scripts\test_siliconflow_api.py --vision debug\...\crop.jpg
```

- [ ] Verify anim/upscale — OK
- [ ] SiliconFlow — OK (не 402 insufficient balance)

### 7. Запуск приложений

```powershell
$env:NO_PROXY = "127.0.0.1,localhost"

# Веб-редактор (основной UI разработки)
uvicorn api.server:app --reload --port 8000
# → http://127.0.0.1:8000

# Gradio (паритет batch UI)
python main.py
# → http://127.0.0.1:7860
```

- [ ] `:8000` открывается, Split / ExText грузятся
- [ ] `:7860` стартует без IndentationError в `main.py`

### 8. Cursor / LLM на новой машине

- [ ] Открыть папку `SPLIT_PANELS_DEV` как workspace
- [ ] Новый чат + handoff (блок в начале этого файла)
- [ ] Прикрепить: `LLM_HANDOFF_CONTEXT.md`, `COMICSPLIT_SPEC.md`, при правках кода — `REPO_MAP.md`
- [ ] Правила проекта: при необходимости добавить `.cursor/rules` (в git опционально)

### 9. После первой успешной сессии на новой машине

- [ ] При изменениях в дереве файлов: `python scripts/generate_repo_map.py` → commit `REPO_MAP.md` (второй push-проход, см. WEB_LLM_GIT_WORKFLOW)
- [ ] Обновить дату в этом чеклисте, если менялся процесс установки

---

## Что сознательно не переносить

| Путь | Почему |
|------|--------|
| `venv_311/` | Пересоздать (привязка к Python на ПК) |
| `output/`, `story_out/`, `debug/` | Локальные артефакты (в `.gitignore`) |
| История чатов Cursor | Вне репозитория |
| `exam_imgs/` тяжёлые наборы | Часто локальные; при необходимости копировать отдельно |

---

## Быстрый troubleshooting

| Симптом | Действие |
|---------|----------|
| ImportError после копии папки | Пересоздать `venv_311`, `pip install -r requirements.txt` |
| Split/ExText «нет модели» | Проверить файлы в `models/`, `GET /api/models/setup` на `:8000` |
| ExText OCR 402 | Пополнить баланс SiliconFlow, `test_siliconflow_api.py` |
| Paddle / пути с кириллицей | Держать репозиторий и `models/paddleocr` на ASCII-путях |
| Gradio не стартует | `python -m py_compile main.py` |

---

## См. также

| Документ | Содержание |
|----------|------------|
| [MODELS_SETUP_GUIDE.md](MODELS_SETUP_GUIDE.md) | Подробно про все модели |
| [ComicSplit_Documentation.md](ComicSplit_Documentation.md) | Пользовательский запуск |
| [README.md](../README.md) | Быстрый старт в корне |
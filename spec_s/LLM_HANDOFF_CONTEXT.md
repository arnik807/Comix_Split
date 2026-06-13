# ComicSplit — экспорт контекста для LLM (handoff)

**Дата:** июнь 2026  
**Репозиторий:** `SPLIT_PANELS_DEV` (Windows, Python 3.11)  
**Назначение файла:** дать другой модели исчерпывающее представление о проекте без доступа к истории чата.

---

## 1. Что это за проект

**ComicSplit** — десктопная утилита для Windows: автоматическая **нарезка страниц комикса на панели** (YOLO + MobileSAM, ONNX CPU) и опциональное **оживление** панелей (апскейл NCNN Vulkan → гармонизация 16:9 → MP4).

Типичный пайплайн:

```
CBZ / PNG страницы → PNG панели (split) → апскейл → 16:9 → анимация → MP4 / storyboard.mp4
```

**Не цель проекта:** CUDA, Stable Diffusion, AnimateDiff, Wails desktop (пока), gRPC-оркестратор — это было в спеке v2.0, но не реализовано.

---

## 2. Целевое железо (жёсткое ограничение)

Все решения под машину разработчика:

| Параметр | Значение |
|----------|----------|
| CPU | AMD Ryzen 5 5600H |
| GPU | AMD Radeon iGPU (Vulkan для NCNN) |
| RAM | 16 GB |
| ОС | Windows 10/11 |
| CUDA | **Нет** |

Следствия: split и TPSMM на **ONNX Runtime CPU**; апскейл через **NCNN + Vulkan**; DepthFlow — CPU inference + OpenGL render (медленно на полном 1080p).

---

## 3. Интерфейсы (как пользователь работает)

| # | Интерфейс | Порт / команда | Возможности |
|---|-----------|----------------|-------------|
| 1 | **Gradio** | `:7860`, `python main.py` | Split / Upscale / Video, пресеты, tooltips, диалоги путей |
| 2 | **Веб-редактор** | `:8000`, `uvicorn api.server:app --port 8000` | Split + **ручная правка** масок (Konva), Upscale, Video |
| 3 | **CLI split** | `python pipeline.py` | Пакетная нарезка |
| 4 | **CLI anim** | `python anim_pipeline.py` | Апскейл + видео без UI |
| 5 | **Go CLI** | `comicsplit.exe` | Batch split через `ml_worker` (CBR только в Python) |

**Паритет UI:** Gradio и :8000 согласованы по пресетам, полям anim/upscale, tooltips. Расширенные блоки (SAM, пороги YOLO, backend апскейла, DepthFlow, TPSMM) видны в режиме **«Качество»**.

---

## 4. Пресеты и важные правила продукта

Два пресета в `config/presets.yaml`:

| Пресет | ID | Split | Anim (кратко) |
|--------|-----|-------|----------------|
| **Стандарт** | `standard` | YOLO без SAM, conf 0.35 | animevideov3 ×2, OpenCV zoom |
| **Качество** | `quality` | YOLO + SAM, conf 0.30 | x4plus-anime ×4, DepthFlow dolly |

**Критичные правила (согласованы с пользователем):**

1. **Пресеты НЕ меняют** `panel_detector` (comic/manga) и **НЕ меняют** backend апскейла (realesrgan/cugan/span) — выбор пользователя сохраняется в сессии.
2. **TPSMM не включать глобально** в `config_animate.yaml` — по умолчанию `mode: opencv_zoom`; TPSMM только при явном выборе режима + driving MP4.
3. **`anime_6B` (x4plus-anime)** — только масштаб **×4**; ×2 даёт артефакты (UI принудительно ставит ×4).
4. **«Сохранить в YAML»** (пресет) — осознанная запись на диск (`config.yaml`, `config_animate.yaml`, опционально `presets.user.yaml`). Отдельно от «памяти UI».
5. Коммиты в git — **только по явной просьбе** пользователя. Не коммитить `exam_img/`, `models/**`, локальные `ui_state.user.json`, `presets.user.yaml`.

---

## 5. Статус разработки (roadmap)

| Блок | Содержание | Статус |
|------|-----------|--------|
| **A** | Пресеты, UI, tooltips, path pickers, паритет Gradio/:8000 | ✅ Закрыт |
| **B0** | Реестр моделей `models_registry.yaml`, `GET /api/models/setup` | ✅ Закрыт |
| **B1** | Манга-детектор `yolo_manga_int8.onnx`, `panel_detector: comic\|manga` | ✅ Закрыт |
| **B4** | Backend апскейла Real-CUGAN + SPAN (NCNN Vulkan) | ✅ Закрыт |
| **B2** | TPSMM motion transfer | 🟡 Код + UI + `anim_pipeline` — нужны тесты на реальных панелях |
| **B3** | Сегментация персонажа для TPSMM, SAM2-tiny | 📋 В планах |

**Не сделано / отложено:** OpenCV fast-path split, Wails, gRPC, benchmark <600 ms/стр., PyInstaller сборка «из коробки», `tests/test_tpsmm.py`, B1.4 benchmark детекторов (опционально).

**API:** FastAPI **v1.3.0** (`api/server.py`).  
**Тесты:** ~**41** pytest в 10 файлах.

---

## 6. Архитектура (фактическая MVP)

```
Интерфейсы:  Gradio :7860 | Web :8000 | CLI | Go comicsplit.exe
                    ↓
Ядро Python:  pipeline.py (split)  |  anim_pipeline.py (upscale→16:9→animate→MP4)
                    ↓
Split ML:     ONNX CPU — yolo_comic_int8 | yolo_manga_int8 + mobilesam_*_int8
Anim:         NCNN Vulkan (Real-ESRGAN / CUGAN / SPAN)
              OpenCV эффекты | DepthFlow | TPSMM ONNX | ffmpeg
```

Ключевые конфиги:

- `config.yaml` — split
- `config_animate.yaml` — anim
- `config/presets.yaml` — эталон пресетов
- `config/models_registry.yaml` — реестр моделей
- `config/presets.user.yaml` — локальные правки пресетов (gitignore)
- `config/ui_state.user.json` — **память UI** (gitignore)

---

## 7. Память настроек UI (недавняя работа, может быть не закоммичена)

Реализовано в сессии после консолидации документации:

| Компонент | Назначение |
|-----------|------------|
| `utils/ui_state.py` | Схема v1, save/load/reset секций split/upscale/video/global |
| `utils/gradio_ui_state.py` | Восстановление полей Gradio, сохранение вкладки |
| `frontend/ui_state.js` | localStorage + sync `PUT /api/ui/state` для :8000 |
| `api/server.py` | `GET/PUT /api/ui/state`, `POST /api/ui/state/reset` |

**Поведение:**

- **:8000:** localStorage `comicsplit.ui.v1` + файл на диске; автосохранение с debounce; кнопки **↺ Сброс Split/Upscale/Video** (заводские значения из config, не пресет).
- **Gradio:** чтение/запись `config/ui_state.user.json`; `demo.load` восстанавливает поля; **активная вкладка** (split/upscale/video) сохраняется через `main_tabs.select` и `gr.Tabs(selected=…)`.
- Общий файл `ui_state.user.json` связывает оба UI на одной машине (разные порты → разный localStorage, но один файл через API/Gradio).

**Статус в git (на момент экспорта):** изменения UI state могут быть **незакоммичены** — см. `git status`: `utils/ui_state.py`, `utils/gradio_ui_state.py`, `frontend/ui_state.js`, `tests/test_ui_state.py`, правки `main.py`, `api/server.py`, `frontend/index.html`, `.gitignore`.

---

## 8. Документация (после консолидации)

Активные файлы в `spec_s/`:

| Файл | Роль |
|------|------|
| `ComicSplit_Documentation.md` | Руководство пользователя (v1.5+) |
| `ARCHITECTURE.md` | Стек, API, структура |
| `IMPLEMENTATION_STATUS.md` | Статус модулей |
| `MODELS_SPECIFICATION.md` | Все модели, параметры, железо |
| `ROADMAP.md` | План блоков A/B |
| `README.md` | Индекс |
| `archive/` | Устаревшие спеки (v2.0, SPLIT_DETECTORS, ROADMAP_QUALITY_BOOST и др.) |

Корень: `README.md`, `CHANGELOG.md`.  
Вне spec_s: `scripts/MODELS_SETUP_GUIDE.md`, `models/README.md`.

Папка `spec_s/Claude_track_anliz/` — черновики слияния доков; канон — файлы в корне `spec_s/`.

---

## 9. Модели (не в git)

**Split** (`models/`):

- `yolo_comic_int8.onnx`
- `yolo_manga_int8.onnx`
- `mobilesam_encoder_int8.onnx`, `mobilesam_decoder_int8.onnx`

**Anim** (`models/anim/`):

- `upscale/` — realesrgan-ncnn-vulkan, realcugan, span
- `tpsmm/` — `kp_detector_int8.onnx`, `tpsmm_rel_int8.onnx`
- `ffmpeg/bin/ffmpeg.exe`
- DepthFlow качает DA-V2 Small при первом запуске

Скрипты: `scripts/split_models_craft_scripts/`, `download_animate_models.ps1`, `download_upscale_backends.ps1`, `quantize_animate_models.py --verify`.

---

## 10. API v1.3 (краткий список)

| Метод | Путь | Назначение |
|-------|------|------------|
| POST | `/api/process` | Детекция (`panel_detector`, пороги) |
| POST | `/api/export` | PNG панелей |
| POST | `/api/upscale` | Апскейл (backend, CUGAN/SPAN поля) |
| POST | `/api/animate` | Видео (`mode`, `tpsmm_driving_video`, …) |
| GET | `/api/presets`, `/api/presets/{name}` | Пресеты |
| POST | `/api/presets/apply` | Применить пресет |
| GET | `/api/split/options` | Детекторы comic/manga |
| GET | `/api/upscale/options` | Backend апскейла |
| GET | `/api/models/setup` | Статус моделей |
| GET/PUT | `/api/ui/state` | Память UI |
| POST | `/api/ui/state/reset` | Сброс секции UI |
| POST | `/api/path/pick` | Нативный диалог (`kind`: file/folder/video) |
| GET | `/api/tooltips` | Подсказки |

---

## 11. История работ в чате (хронология смысла)

1. **Блок A** — пресеты Стандарт/Качество, паритет Gradio и :8000, tooltips, path dialogs, NCNN апскейл ×4/x4plus-anime.
2. **B4/P1** — Real-CUGAN + SPAN, `models_registry`, verify-скрипты, API v1.3 upscale options.
3. **B1** — manga YOLO, `panel_detector`, export script, UI dropdown, пресеты не трогают детектор.
4. **B2** — `animate_tpsmm.py`, режим `tpsmm` в `anim_pipeline`, driving MP4 в UI/API; не глобальный default.
5. **Документация** — консолидация 14+ файлов → 7 активных + `archive/`; исправлены ошибки (TPSMM в пайплайне, API 1.3, 41 тест).
6. **Память UI** — localStorage + файл, сброс по вкладкам, Gradio tab persistence.
7. **`.gitignore`** — `exam_img/`, `models/**`, benchmark CSV, `ui_state.user.json`, и т.д.

---

## 12. Известные ограничения и подводные камни

| Тема | Деталь |
|------|--------|
| Кириллица в путях | `path_resolve`, относительные пути на :8000; export manga YOLO через ASCII workdir `C:/tmp_comicsplit_manga` |
| Gradio | Нет галереи превью; результат split — текстовый список путей |
| DepthFlow | Минуты на панель 1920×1080 на CPU |
| TPSMM | Медленно на CPU; нужен driving MP4; качество ↑ с B3 segment |
| :8000 «Обзор…» | Диалог на машине, где запущен uvicorn |
| `localhost` vs `127.0.0.1` | Разный localStorage на :8000 |
| Пресет vs UI state | Пресет — эталонные значения anim/split flags; UI state — последние пути и ручные правки |

---

## 13. Что делать дальше (приоритеты для следующей LLM)

1. **Закоммитить** память UI (если пользователь попросит) — отдельный commit от docs.
2. **B2:** `tests/test_tpsmm.py`, прогон с реальным driving MP4, замеры времени на CPU.
3. **B3:** `anim/segment.py` для отделения персонажа (улучшение TPSMM).
4. **B1.4:** `scripts/benchmark_split_detectors.py` (опционально).
5. **ROADMAP:** OpenCV fast-path, Wails — только если пользователь сменит приоритет.

---

## 14. Быстрые команды

```powershell
.\venv_311\Scripts\activate
$env:NO_PROXY = "127.0.0.1,localhost"

# Gradio
python main.py                    # → :7860

# Веб-редактор
uvicorn api.server:app --reload --port 8000

# Split CLI
python pipeline.py exam_imgs output --order

# Anim CLI
python anim_pipeline.py output\exam_imgs story_out --mode opencv_zoom --scale 2
python anim_pipeline.py output\exam_imgs story_out --mode tpsmm --tpsmm-driving-video path\to\drive.mp4

# Тесты
pytest -q
```

---

## 15. Карта ключевых файлов кода

```
main.py                 # Gradio UI
api/server.py           # FastAPI v1.3
frontend/index.html     # Konva + вкладки
frontend/ui_state.js    # Память :8000
pipeline.py             # Split ML
anim_pipeline.py        # Anim orchestration
anim/upscale.py         # NCNN backends
anim/animate_*.py       # opencv, depthflow, tpsmm
utils/presets.py        # Пресеты
utils/panel_detector.py # comic | manga
utils/models_registry.py
utils/ui_state.py       # Память UI (файл)
utils/gradio_ui_state.py
config/presets.yaml
config/models_registry.yaml
tests/                  # ~41 тест
spec_s/                 # Документация
```

---

## 16. Стиль работы с пользователем

- Общение на **русском**.
- Минимальный scope в коде; не over-engineer.
- Следовать существующим конвенциям в репозитории.
- Не создавать markdown без запроса (исключение — этот handoff по запросу).
- Реальная среда Windows + shell; проверять команды, не сдаваться после одной ошибки.

---

## 17. Ссылки внутри репозитория

Начать чтение с: `README.md` → `spec_s/IMPLEMENTATION_STATUS.md` → `spec_s/ROADMAP.md` → `spec_s/ComicSplit_Documentation.md`.

История чата Cursor (если нужны детали диалога): транскрипт сессии `6dcf8b71-029b-4b1b-82b2-f0937e978a01` в agent-transcripts (не в git).

---

*Документ сгенерирован для handoff другой LLM. Обновляйте при крупных изменениях roadmap или архитектуры.*

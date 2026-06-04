# MVP Implementation Plan for ComicSplit (Desktop + Web Tails)

> **Статус (июнь 2026):** план исходный (англ.); фактическая реализация описана в [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) и [ComicSplit_Documentation.md](ComicSplit_Documentation.md).

## План vs факт (кратко)

| Пункт плана | Статус |
|-------------|--------|
| Python 3.11 + ONNX Runtime CPU | ✅ |
| YOLO + MobileSAM (fast/accurate) | ✅ |
| CBZ/CBR/ZIP/папка (`io_helpers`) | ✅ |
| OpenCV fast-path каскад | ❌ |
| `process_source` + параллельный analyze | ✅ |
| Gradio UI | ✅ (5.x, без Gallery; пресеты, tooltips) |
| FastAPI + Konva + anim API | ✅ (`api/` v1.2, :8000, 3 вкладки UI) |
| Anim pipeline (upscale/video) | ✅ (`anim/`, `anim_pipeline.py`, Gradio) |
| Пресеты Стандарт / Качество (блок A) | ✅ |
| Tooltips, path pickers, API v1.2 | ✅ |
| Апскейл: x4plus-anime только ×4, benchmark | ✅ |
| TPSMM / segment в anim | ❌ |
| `config.yaml` + Pydantic/YAML | ✅ |
| pytest | ✅ (`tests/`) |
| PyInstaller spec | ✅ (сборка вручную) |
| Go orchestrator | 🟡 `cmd/comicsplit` |
| Wails desktop | ❌ |
| Benchmark &lt;600 ms/page | ❌ не достигнут на exam_imgs |

---

## 1. Goals
- Deliver a **desktop‑only** MVP that can split comic pages into panels.
- Keep **integration hooks** for a future full‑stack web UI.
- Use the **simplest, most debuggable stack** (Python only, no Go).
- Provide **two quality modes**: "Fast" (YOLO only) and "Accurate" (YOLO + MobileSAM).
- UI language: Russian default, English optional.
- Simple installation & manual (PyInstaller bundle).

## 2. Chosen Technology Stack (MVP)
| Layer | Tech | Reason |
|-------|------|--------|
| Core pipeline | **Python 3.11** (virtualenv) | Single language, easy to script, wide ML ecosystem |
| Model inference | **ONNX Runtime 1.18 (CPU)** | Works on CPU‑only hardware, fast loading |
| Detection model | **YOLOv11n‑seg** (pre‑trained comic model from HuggingFace) | Small (~3 MB), good speed on Ryzen 5600H |
| Mask refinement | **MobileSAM** (ONNX) | Optional, adds quality, still CPU‑friendly (~40 MB) |
| Image preprocessing / fallback | **OpenCV‑Python 4.10** | Handles simple pages without ML |
| UI (desktop) | **Gradio 5.x** (runs locally, opens browser) | Zero‑config UI, works on Windows; pin starlette &lt; 0.47 |
| Optional web API | **FastAPI** (runs alongside Gradio) | Provides REST endpoints for future web front‑end |
| Packaging | **PyInstaller** (creates single .exe) | End‑user gets a double‑file bundle (exe + models) |
| Config | **Pydantic** based config file (`config.yaml`) | Easy validation, allows quality toggle |

## 3. File Structure
```
ComicSplit_MVP/
│   README.md               # Overview, install & run guide
│   requirements.txt        # Python dependencies
│   config.yaml              # Default configuration (language, quality)
│   main.py                 # Entry point (CLI + Gradio UI)
│   pipeline.py             # Core processing: CBZ/CBR extraction, OpenCV fallback, YOLO, MobileSAM
│   models/                  # Folder for .onnx models (YOLO, MobileSAM)
│   utils/                  
│       └─ io_helpers.py    # Zip/rar handling, image I/O helpers
│   api/                    # FastAPI stub (future web integration)
│       └─ server.py
│   scripts/                # Helper scripts (e.g., download_models.sh)
│   packaging/              # PyInstaller spec file
``` 

## 4. Core Pipeline (`pipeline.py`)
1. **Input handling** – Accept a path to a CBZ/CBR archive or a folder.
   - Use `zipfile` for CBZ, `rarfile` (via `python‑rarfile` + `unrar` installed) for CBR.
   - Extract images to an in‑memory list of `numpy` arrays.
2. **Pre‑processing** – Resize longest side to ≤1024 px, convert to grayscale, apply Canny + morphological ops (OpenCV). This step also serves as a fast‑path fallback.
3. **Fast mode** – Run YOLOv11n‑seg only, obtain polygon masks.
4. **Accurate mode** – For each YOLO bbox, run MobileSAM to refine mask.
5. **Reading order** – Sort polygons top‑to‑bottom, left‑to‑right using centroid coordinates.
6. **Cropping & export** – Use `cv2.fillPoly` to create alpha mask, then `cv2.imwrite` for each panel as `{{order}}_page_{N}_panel_{M}.png`.
7. **Parallelism** – Simple `concurrent.futures.ThreadPoolExecutor` with `max_workers = os.cpu_count()` to process pages concurrently.

## 5. UI (`main.py` with Gradio)
- **Sidebar**: file selector (drag‑&‑drop), quality toggle (Fast / Accurate), language dropdown (RU / EN), start button.
- **Main panel**: progress bar, live preview of first page with overlayed masks, and a gallery of resulting PNG thumbnails.
- **Export**: Choose output folder; after processing show “Open folder” button.
- Gradio runs on `localhost:7860`; PyInstaller will bundle the embedded browser window.

## 6. Integration Tails for Web
- Expose a **FastAPI** endpoint (`/process`) that accepts multipart/form‑data (archive or folder path) and returns a JSON list of panel file paths.
- The desktop Gradio UI can call the same underlying functions from `pipeline.py`; future web front‑end can reuse the API.
- The FastAPI server will be optional – started with a flag `--api`.

## 7. Configuration (`config.yaml`)
```yaml
language: ru            # ru or en
quality_mode: fast      # fast | accurate
max_workers: 4          # default, can be overridden via CLI
output_pattern: "{order}_page_{page}_panel_{panel}.png"
``` 
The UI will load this file on start and allow the user to override values.

## 8. Model Acquisition (`scripts/download_models.sh`)
- Download YOLOv11n‑seg ONNX from HuggingFace repo.
- Download MobileSAM ONNX.
- Verify SHA256 checksums.
- Place into `models/`.

## 9. Packaging (`packaging/comicsplit.spec`)
- Use `pyinstaller --onefile --add-data "models;models" main.py`.
- After build, distribute `ComicSplit.exe` plus a short README.

## 10. Timeline (MVP) – ~2 weeks
| Day | Deliverable |
|-----|-------------|
| 1   | Repo scaffolding, requirements, config, download script |
| 2‑3 | IO helpers for CBZ/CBR, image loading, basic CLI entry point |
| 4‑5 | YOYO inference wrapper (ONNX Runtime) + fallback OpenCV pipeline |
| 6   | MobileSAM integration (optional mode) |
| 7   | Parallel page processing, reading‑order logic |
| 8   | Gradio UI prototype, progress bar, preview |
| 9   | FastAPI skeleton (stub) for web tails |
|10   | PyInstaller spec, test build on Windows 11 |
|11‑12| QA: run on sample comic archives, verify speed (< 600 ms/page in accurate mode) and quality, write README & manual |

## 11. Documentation (README excerpt)
- **Installation**: `python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt && scripts\download_models.sh`
- **Run Desktop MVP**: `python main.py` (opens Gradio UI).
- **Run as API**: `python main.py --api` (starts FastAPI on 8000).
- **Build EXE**: `pyinstaller packaging/comicsplit.spec`.
- **Usage notes**: toggle quality for speed vs accuracy, language selection persists in `config.yaml`.

---
**Next steps after MVP**
- Replace Gradio UI with native Wails UI (Go+React) for tighter desktop feel.
- Migrate orchestrator to Go for better performance and packaging.
- Add GPU support flag.
- Implement detailed logging & telemetry.

*Please review the plan and let me know if any modifications are needed before we start coding.*

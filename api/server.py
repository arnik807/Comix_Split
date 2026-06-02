"""
ComicSplit API Server
FastAPI backend + static frontend на одном порту.

Запуск из корня проекта SPLIT_PANELS_DEV/:
    pip install fastapi uvicorn python-multipart
    uvicorn api.server:app --reload --port 8000

Затем открыть: http://localhost:8000
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

from dataclasses import asdict
from typing import List, Optional

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import analyze_page, _json_convert, Panel  # noqa: E402
from utils.config import apply_config_to_pipeline, get_config, load_config  # noqa: E402
from utils.path_resolve import resolve_dir_path, resolve_file_path  # noqa: E402
from utils.presets import (  # noqa: E402
    apply_preset,
    list_presets,
    preset_ui_payload,
    snapshot_from_configs,
)
from utils.ui_tooltips import FIELD_TIPS  # noqa: E402

load_config()


# ══════════════════════════════════════════════════════════════════════════════
# Pydantic schemas
# ══════════════════════════════════════════════════════════════════════════════


class ProcessRequest(BaseModel):
    image_path: str
    use_sam: bool = False
    reading_order: bool = True
    rtl: bool = False
    confidence_threshold: Optional[float] = None
    iou_threshold: Optional[float] = None


class PanelExport(BaseModel):
    panel_id: str
    bbox: List[int]  # [x1, y1, x2, y2]
    polygon: Optional[List[List[int]]] = None  # [[x,y], ...] если полигон задан


class ExportRequest(BaseModel):
    image_path: str
    panels: List[PanelExport]
    output_dir: str


class UpscaleRequest(BaseModel):
    panels_dir: str
    output_dir: str = "output_upscaled"
    scale: int = 2
    upscale_model: Optional[str] = None  # animevideov3 | anime_6B
    gpu_id: Optional[int] = None


class AnimateRequest(BaseModel):
    panels_dir: str
    output_dir: str = "story_out"
    mode: str = "opencv_zoom"
    do_upscale: bool = True
    scale: int = 2
    duration: float = 3.0
    fps: int = 24
    do_concat: bool = True
    upscale_model: Optional[str] = None
    gpu_id: Optional[int] = None
    harmonize_mode: Optional[str] = None
    harmonize_blur_sigma: Optional[int] = None
    harmonize_vignette: Optional[float] = None
    intensity: Optional[float] = None
    depthflow_animation: Optional[str] = None


class PresetApplyRequest(BaseModel):
    name: str
    persist: bool = False


# ══════════════════════════════════════════════════════════════════════════════
# App
# ══════════════════════════════════════════════════════════════════════════════

app = FastAPI(title="ComicSplit API", version="1.2.0")


def _cfg_from_animate_request(req: AnimateRequest):
    from utils.anim_config import load_anim_config

    cfg = load_anim_config()
    cfg.upscale.enabled = bool(req.do_upscale)
    cfg.upscale.scale = int(req.scale)
    cfg.harmonize.enabled = True
    cfg.animation.mode = str(req.mode)
    cfg.animation.duration = float(req.duration)
    cfg.animation.fps = int(req.fps)
    cfg.render.concat_panels = bool(req.do_concat)
    if req.upscale_model is not None:
        cfg.upscale.model = str(req.upscale_model)
    if req.gpu_id is not None:
        cfg.upscale.gpu_id = int(req.gpu_id)
    if req.harmonize_mode is not None:
        cfg.harmonize.mode = str(req.harmonize_mode)
    if req.harmonize_blur_sigma is not None:
        cfg.harmonize.blur_sigma = int(req.harmonize_blur_sigma)
    if req.harmonize_vignette is not None:
        cfg.harmonize.vignette_strength = float(req.harmonize_vignette)
    if req.intensity is not None:
        cfg.animation.intensity = float(req.intensity)
    if req.depthflow_animation is not None:
        cfg.animation.depthflow_animation = str(req.depthflow_animation)
    return cfg


# ══════════════════════════════════════════════════════════════════════════════
# Image helpers (кириллица в путях через np.fromfile/imencode+tofile)
# ══════════════════════════════════════════════════════════════════════════════


def _imread(path: str) -> Optional[np.ndarray]:
    """Читает изображение с поддержкой кириллицы в пути."""
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)


def _imwrite(path: str, img: np.ndarray) -> bool:
    """Сохраняет изображение с поддержкой кириллицы в пути."""
    ext = pathlib.Path(path).suffix.lower()
    ret, buf = cv2.imencode(ext if ext else ".png", img)
    if ret:
        buf.tofile(path)
    return ret


def _crop_rect(img: np.ndarray, bbox: List[int]) -> np.ndarray:
    """Прямоугольный crop по [x1,y1,x2,y2]."""
    oh, ow = img.shape[:2]
    x1, y1, x2, y2 = bbox
    x1 = max(0, min(x1, ow))
    x2 = max(0, min(x2, ow))
    y1 = max(0, min(y1, oh))
    y2 = max(0, min(y2, oh))
    return img[y1:y2, x1:x2]


def _crop_polygon(img: np.ndarray, polygon: List[List[int]]) -> np.ndarray:
    """
    Вырезает панель по произвольному полигону.
    Возвращает BGRA: пиксели вне полигона прозрачны.
    Crop ограничен bounding box полигона.
    """
    oh, ow = img.shape[:2]
    pts = np.array(polygon, dtype=np.int32)

    x1 = max(0, int(pts[:, 0].min()))
    y1 = max(0, int(pts[:, 1].min()))
    x2 = min(ow, int(pts[:, 0].max()))
    y2 = min(oh, int(pts[:, 1].max()))

    if x2 <= x1 or y2 <= y1:
        return np.zeros((1, 1, 4), dtype=np.uint8)

    mask = np.zeros((oh, ow), dtype=np.uint8)
    cv2.fillPoly(mask, [pts], 255)

    rgba = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    rgba[:, :, 3] = mask

    return rgba[y1:y2, x1:x2]


# ══════════════════════════════════════════════════════════════════════════════
# API Routes
# ══════════════════════════════════════════════════════════════════════════════


@app.get("/api/tooltips")
def api_tooltips():
    """Тексты подсказок для веб-UI (ключ → описание)."""
    return JSONResponse(FIELD_TIPS)


@app.get("/api/presets")
def api_presets_list():
    """Список пресетов и текущие значения (для UI)."""
    return JSONResponse(
        {
            "presets": list_presets(),
            "current": snapshot_from_configs(),
            "standard": preset_ui_payload("standard"),
            "quality": preset_ui_payload("quality"),
        }
    )


@app.get("/api/presets/{name}")
def api_presets_get(name: str):
    try:
        return JSONResponse(preset_ui_payload(name))
    except KeyError as exc:
        raise HTTPException(404, detail=str(exc)) from exc


@app.post("/api/presets/apply")
def api_presets_apply(req: PresetApplyRequest):
    """Применить пресет standard | quality; persist=true пишет YAML на диск."""
    try:
        payload = apply_preset(req.name, persist=req.persist)
    except KeyError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    return JSONResponse({"ok": True, "applied": req.name, "persist": req.persist, **payload})


@app.post("/api/process")
def api_process(req: ProcessRequest):
    """Детекция панелей. Возвращает bbox + polygon для каждой панели."""
    try:
        img_path = resolve_file_path(req.image_path, ROOT)
    except OSError:
        img_path = pathlib.Path(req.image_path)
    img = _imread(str(img_path))
    if img is None:
        raise HTTPException(
            404,
            detail=(
                f"Файл не найден: {req.image_path}\n"
                f"Подсказка: укажите относительный путь, например "
                f"exam_imgs\\01_Asterix_the_Gaul_page-0004.jpg"
            ),
        )

    cfg = get_config()
    if req.use_sam:
        cfg.quality_mode = "accurate"
    else:
        cfg.quality_mode = "fast"
    cfg.reading_order = req.reading_order
    cfg.reading_direction = "rtl" if req.rtl else "ltr"
    if req.confidence_threshold is not None:
        cfg.confidence_threshold = float(req.confidence_threshold)
    if req.iou_threshold is not None:
        cfg.iou_threshold = float(req.iou_threshold)
    apply_config_to_pipeline()

    try:
        page_result = analyze_page(
            img,
            use_sam=req.use_sam,
            reading_order=req.reading_order,
            rtl=req.rtl,
        )
    except Exception as exc:
        raise HTTPException(500, detail=str(exc))

    panels: List[Panel] = page_result.panels
    result = json.loads(json.dumps([asdict(p) for p in panels], default=_json_convert))
    return JSONResponse(
        {
            "panels": result,
            "page": img_path.name,
            "resolved_path": str(img_path),
            "timings_ms": page_result.timings_ms,
        }
    )


@app.get("/api/image")
def api_image(path: str):
    """Отдаёт оригинальное изображение по локальному пути."""
    try:
        p = resolve_file_path(path, ROOT)
    except OSError:
        raise HTTPException(404, detail=f"Файл не найден: {path}")
    if _imread(str(p)) is None:
        raise HTTPException(404, detail=f"Файл не найден: {path}")
    suffix = p.suffix.lower()
    media_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".bmp": "image/bmp",
    }
    return FileResponse(
        str(p), media_type=media_map.get(suffix, "application/octet-stream")
    )


@app.post("/api/export")
def api_export(req: ExportRequest):
    """
    Нарезает и сохраняет панели.
    - polygon задан (≥3 точек) → вырезает по маске, BGRA (прозрачный фон)
    - polygon is None          → прямоугольный crop по bbox, BGR

    Веб-редактор передаёт polygon только в режиме «Полигон» или после ручной правки;
    контуры SAM при обычной раскройке не отправляются (только bbox).
    """
    try:
        img_path = resolve_file_path(req.image_path, ROOT)
    except OSError:
        img_path = pathlib.Path(req.image_path)

    img = _imread(str(img_path))
    if img is None:
        raise HTTPException(
            404,
            detail=f"Файл не найден или не читается: {req.image_path}",
        )

    out_base = resolve_dir_path(req.output_dir, ROOT)
    out_dir = out_base / img_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    saved: List[str] = []

    for i, panel in enumerate(req.panels, start=1):
        filename = f"{i:03d}_{panel.panel_id}_panel.png"
        out_path = out_dir / filename

        if panel.polygon and len(panel.polygon) >= 3:
            crop = _crop_polygon(img, panel.polygon)
        else:
            crop = _crop_rect(img, panel.bbox)

        if crop.size == 0:
            continue

        if _imwrite(str(out_path), crop):
            saved.append(str(out_path))

    return JSONResponse({"saved": saved, "count": len(saved)})


@app.post("/api/upscale")
def api_upscale(req: UpscaleRequest):
    """Апскейл всех PNG/JPG в папке через Real-ESRGAN NCNN."""
    try:
        panels_dir = resolve_dir_path(req.panels_dir, ROOT)
    except OSError as exc:
        raise HTTPException(404, detail=str(exc)) from exc

    from anim.io_utils import list_images
    from anim.upscale import upscale_folder
    from utils.anim_config import load_anim_config

    images = list_images(panels_dir)
    if not images:
        raise HTTPException(404, detail=f"Нет изображений в: {req.panels_dir}")

    try:
        out_base = resolve_dir_path(req.output_dir, ROOT)
    except OSError:
        out_base = pathlib.Path(req.output_dir)

    cfg = load_anim_config()
    cfg.upscale.enabled = True
    cfg.upscale.scale = int(req.scale)
    if req.upscale_model is not None:
        cfg.upscale.model = str(req.upscale_model)
    if req.gpu_id is not None:
        cfg.upscale.gpu_id = int(req.gpu_id)

    try:
        results = upscale_folder(panels_dir, out_base, cfg)
    except Exception as exc:
        raise HTTPException(500, detail=str(exc)) from exc

    files = [str(p.resolve()) for p in results]
    return JSONResponse(
        {
            "ok": True,
            "count": len(files),
            "output_dir": str(out_base.resolve()),
            "files": files[:100],
        }
    )


@app.post("/api/animate")
def api_animate(req: AnimateRequest):
    """Панели → harmonize + анимация → MP4 (+ storyboard)."""
    try:
        panels_dir = resolve_dir_path(req.panels_dir, ROOT)
    except OSError as exc:
        raise HTTPException(404, detail=str(exc)) from exc

    from anim.io_utils import list_images
    from anim_pipeline import process_folder
    from utils.anim_config import load_anim_config

    if not list_images(panels_dir):
        raise HTTPException(404, detail=f"Нет изображений в: {req.panels_dir}")

    try:
        out_base = resolve_dir_path(req.output_dir, ROOT)
    except OSError:
        out_base = pathlib.Path(req.output_dir)

    cfg = _cfg_from_animate_request(req)

    try:
        result = process_folder(panels_dir, out_base, cfg)
    except Exception as exc:
        raise HTTPException(500, detail=str(exc)) from exc

    return JSONResponse(
        {
            "ok": True,
            "panels_processed": result.panels_processed,
            "output_dir": str(out_base.resolve()),
            "panel_videos": result.panel_videos,
            "storyboard_path": result.storyboard_path,
        }
    )


@app.get("/api/video")
def api_video(path: str):
    """Отдаёт MP4 для предпросмотра в браузере."""
    try:
        p = resolve_file_path(path, ROOT)
    except OSError:
        raise HTTPException(404, detail=f"Файл не найден: {path}")
    if not p.is_file() or p.suffix.lower() != ".mp4":
        raise HTTPException(404, detail="Ожидается .mp4")
    return FileResponse(str(p), media_type="video/mp4")


# ══════════════════════════════════════════════════════════════════════════════
# Static files (монтируем ПОСЛЕ API-роутов)
# ══════════════════════════════════════════════════════════════════════════════

FRONTEND_DIR = ROOT / "frontend"
FRONTEND_DIR.mkdir(exist_ok=True)

app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

"""FastAPI routes for Story Analyzer Stage 2a."""

from __future__ import annotations

import pathlib
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError, field_validator

from story_analyzer.ocr_engine_ids import OCR_ENGINES
from story_analyzer.config import load_stage_2a_config
from story_analyzer.paths import stage_2a_json_path
from story_analyzer.schemas import BUBBLE_TYPES, Stage2aDocument
from story_analyzer.stages.stage_2a_processor import (
    load_stage_2a,
    process_panels_dir,
    reocr_bubble,
    resolve_panel_abs_path,
    save_stage_2a,
)
from utils.path_resolve import ROOT, resolve_dir_path

router = APIRouter(prefix="/api/story/stage_2a", tags=["story-stage-2a"])


class Stage2aProcessRequest(BaseModel):
    project: str
    panels_dir: str


class Stage2aSaveRequest(BaseModel):
    document: Dict[str, Any]


class Stage2aReocrRequest(BaseModel):
    panel_id: str
    bubble_id: str
    bbox: List[int]
    image_path: Optional[str] = None
    panel_abs_path: Optional[str] = None

    @field_validator("bbox")
    @classmethod
    def coerce_bbox(cls, v: List[int]) -> List[int]:
        if len(v) != 4:
            raise ValueError("bbox должен содержать 4 числа [x1,y1,x2,y2]")
        return [int(round(x)) for x in v]


@router.get("/options")
def stage_2a_options():
    cfg = load_stage_2a_config()
    pp = cfg.ocr_preprocess
    return {
        "bubble_types": BUBBLE_TYPES,
        "ocr_languages": list(cfg.ocr_languages),
        "ocr_engine": cfg.ocr_engine,
        "ocr_engines": list(OCR_ENGINES),
        "siliconflow_model": cfg.siliconflow.vlm_model,
        "ocr_preprocess": {
            "enabled": pp.enabled,
            "upscale_factor": pp.upscale_factor,
            "contrast": pp.contrast,
            "invert": pp.invert,
        },
        "confidence_threshold": cfg.confidence_threshold,
        "min_bubble_area_px": cfg.min_bubble_area_px,
        "bubble_detect": {
            "tiled": cfg.bubble_detect.tiled,
            "tile_size": cfg.bubble_detect.tile_size,
            "tile_overlap": cfg.bubble_detect.tile_overlap,
            "filter_contained": cfg.bubble_detect.filter_contained,
        },
        "projects_root": str((ROOT / "story_out" / "projects").resolve()),
    }


@router.post("/process")
def stage_2a_process(req: Stage2aProcessRequest):
    try:
        panels_path = resolve_dir_path(req.panels_dir, ROOT)
    except OSError as exc:
        raise HTTPException(404, detail=str(exc)) from exc

    if not panels_path.is_dir():
        raise HTTPException(404, detail=f"Папка не найдена: {req.panels_dir}")

    try:
        doc, stats = process_panels_dir(panels_path, req.project)
        out_path = save_stage_2a(doc)
    except FileNotFoundError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, detail=str(exc)) from exc

    return JSONResponse(
        {
            "ok": True,
            "path": str(out_path.resolve()),
            "document": doc.model_dump(mode="json"),
            "stats": {
                "panels": stats.panels,
                "bubbles": stats.bubbles,
                "yolo_ms": round(stats.yolo_ms, 1),
                "ocr_ms": round(stats.ocr_ms, 1),
                "total_ms": round(stats.total_ms, 1),
                "ocr_engine": load_stage_2a_config().ocr_engine,
                "errors": stats.errors,
            },
        }
    )


@router.get("/{project}")
def stage_2a_get(project: str):
    try:
        doc = load_stage_2a(project)
    except FileNotFoundError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(422, detail=exc.errors()) from exc

    panel_paths: List[Dict[str, str]] = []
    for panel in doc.panels:
        try:
            abs_path = resolve_panel_abs_path(doc.project, panel.image_path)
            panel_paths.append(
                {
                    "panel_id": panel.panel_id,
                    "image_path": panel.image_path,
                    "abs_path": str(abs_path),
                }
            )
        except FileNotFoundError:
            panel_paths.append(
                {
                    "panel_id": panel.panel_id,
                    "image_path": panel.image_path,
                    "abs_path": "",
                }
            )

    return {
        "ok": True,
        "path": str(stage_2a_json_path(project).resolve()),
        "document": doc.model_dump(mode="json"),
        "panel_paths": panel_paths,
    }


@router.put("/{project}")
def stage_2a_put(project: str, req: Stage2aSaveRequest):
    try:
        doc = Stage2aDocument.model_validate(req.document)
    except ValidationError as exc:
        return JSONResponse(
            status_code=422,
            content={"ok": False, "errors": exc.errors()},
        )

    if doc.project != project:
        doc = doc.model_copy(update={"project": project})

    for panel in doc.panels:
        try:
            resolve_panel_abs_path(doc.project, panel.image_path)
        except FileNotFoundError as exc:
            raise HTTPException(
                422,
                detail=f"Панель не найдена: {panel.image_path} ({exc})",
            ) from exc

    path = save_stage_2a(doc, project)
    return {"ok": True, "path": str(path.resolve()), "document": doc.model_dump(mode="json")}


@router.post("/{project}/reocr")
def stage_2a_reocr(project: str, req: Stage2aReocrRequest):
    if len(req.bbox) != 4:
        raise HTTPException(422, detail="bbox должен содержать 4 числа [x1,y1,x2,y2]")
    try:
        raw_text, ocr_ms, engine_used = reocr_bubble(
            project,
            req.panel_id,
            req.bubble_id,
            req.bbox,
            image_path=req.image_path,
            panel_abs_path=req.panel_abs_path,
        )
    except ValueError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, detail=str(exc)) from exc

    return {
        "ok": True,
        "raw_text": raw_text,
        "corrected_text": raw_text,
        "ocr_ms": round(ocr_ms, 1),
        "ocr_engine": engine_used,
    }

"""Stage 2a: detect bubbles + OCR → stage_2a.json."""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from anim.io_utils import IMAGE_EXTS, list_images
from story_analyzer.config import Stage2aConfig, load_stage_2a_config
from story_analyzer.paths import panels_dir, project_dir, sanitize_project_name, stage_2a_json_path
from story_analyzer.schemas import Bubble, BubbleType, Panel2a, Stage2aDocument
from story_analyzer.stages.bubble_detector import detect_text_bubbles
from story_analyzer.stages.ocr_reader import crop_with_padding, ocr_bubble_crop
from utils.path_resolve import ROOT, resolve_file_path

try:
    from pipeline import _sort_reading_order
except ImportError:  # pragma: no cover
    _sort_reading_order = None


@dataclass
class ProcessStats:
    panels: int = 0
    bubbles: int = 0
    yolo_ms: float = 0.0
    ocr_ms: float = 0.0
    total_ms: float = 0.0
    errors: List[str] = field(default_factory=list)


def _imread_panel(path: Path, composite_alpha: bool) -> Optional[np.ndarray]:
    arr = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.shape[2] == 4:
        if not composite_alpha:
            return img[:, :, :3]
        bgr = img[:, :, :3].astype(np.float32)
        alpha = img[:, :, 3:4].astype(np.float32) / 255.0
        white = np.full_like(bgr, 255.0)
        return (bgr * alpha + white * (1.0 - alpha)).astype(np.uint8)
    return img[:, :, :3]


def panel_id_from_filename(name: str) -> str:
    stem = Path(name).stem
    return stem or "panel"


def assign_bubble_reading_orders(
    bubbles: List[Bubble],
    *,
    rtl: bool = False,
) -> List[Bubble]:
    """Assign or normalize reading_order for bubbles on one panel."""
    if not bubbles:
        return bubbles
    if all(b.reading_order is not None for b in bubbles):
        return sorted(bubbles, key=lambda b: b.reading_order or 0)
    if _sort_reading_order is None or len(bubbles) == 1:
        out: List[Bubble] = []
        for rank, b in enumerate(bubbles, start=1):
            out.append(b.model_copy(update={"reading_order": rank}))
        return out
    bboxes = np.array([b.bbox for b in bubbles], dtype=np.float64)
    order = _sort_reading_order(bboxes, rtl=rtl)
    out = []
    for rank, idx in enumerate(order, start=1):
        out.append(bubbles[idx].model_copy(update={"reading_order": rank}))
    return out


def sync_panels_to_project(
    source_dir: Path,
    project: str,
    *,
    copy: bool = True,
    replace: bool = False,
) -> Path:
    """Copy panel PNGs into story_out/projects/<project>/panels/."""
    dest = panels_dir(project)
    dest.mkdir(parents=True, exist_ok=True)
    if replace:
        for existing in dest.iterdir():
            if existing.is_file():
                try:
                    existing.unlink()
                except OSError:
                    pass
    for src in list_images(source_dir):
        target = dest / src.name
        if copy:
            if not target.exists() or src.resolve() != target.resolve():
                shutil.copy2(src, target)
        elif not target.exists():
            shutil.copy2(src, target)
    return dest


def _unique_panel_id(stem: str, used: set[str]) -> str:
    pid = stem or "panel"
    if pid not in used:
        used.add(pid)
        return pid
    n = 2
    while f"{stem}_{n}" in used:
        n += 1
    pid = f"{stem}_{n}"
    used.add(pid)
    return pid


def resolve_panel_display_path(
    project: str,
    panel: Panel2a,
    *,
    source_dir: Optional[Path] = None,
    source_only: bool = False,
) -> Optional[Path]:
    """Путь к PNG для UI: сначала текущая папка панелей, затем копия в проекте."""
    name = Path(panel.image_path).name
    if source_dir is not None and source_dir.is_dir():
        direct = (source_dir / name).resolve()
        if direct.is_file():
            return direct
        for candidate in list_images(source_dir):
            if panel_id_from_filename(candidate.name) == panel.panel_id:
                return candidate.resolve()
        if source_only:
            return None
    try:
        return resolve_panel_abs_path(project, panel.image_path)
    except FileNotFoundError:
        return None


def panel_paths_for_document(
    doc: Stage2aDocument,
    *,
    source_dir: Optional[Path] = None,
    source_only: bool = False,
) -> List[dict[str, str]]:
    rows: List[dict[str, str]] = []
    for panel in doc.panels:
        abs_path = resolve_panel_display_path(
            doc.project,
            panel,
            source_dir=source_dir,
            source_only=source_only,
        )
        rows.append(
            {
                "panel_id": panel.panel_id,
                "image_path": panel.image_path,
                "abs_path": str(abs_path) if abs_path else "",
            }
        )
    return rows


def process_panels_dir(
    panels_folder: Path,
    project: str,
    *,
    cfg: Optional[Stage2aConfig] = None,
    sync_panels: bool = True,
) -> tuple[Stage2aDocument, ProcessStats]:
    t0 = time.perf_counter()
    cfg = cfg or load_stage_2a_config()
    project_name = sanitize_project_name(project)
    project_dir(project_name).mkdir(parents=True, exist_ok=True)

    if sync_panels:
        work_dir = sync_panels_to_project(panels_folder, project_name, replace=True)
    else:
        work_dir = Path(panels_folder)

    images = list_images(panels_folder if sync_panels else work_dir)
    stats = ProcessStats()
    doc_panels: List[Panel2a] = []
    used_ids: set[str] = set()

    for img_path in images:
        bgr = _imread_panel(img_path, cfg.composite_alpha_on_white)
        if bgr is None:
            stats.errors.append(f"Не удалось прочитать: {img_path.name}")
            continue

        bboxes, _scores, yolo_ms = detect_text_bubbles(
            bgr,
            bubble_class_id=cfg.bubble_class_id,
            confidence_threshold=cfg.confidence_threshold,
            iou_threshold=cfg.iou_threshold,
            min_area_px=cfg.min_bubble_area_px,
            bubble_detect=cfg.bubble_detect,
        )
        stats.yolo_ms += yolo_ms

        pid = _unique_panel_id(panel_id_from_filename(img_path.name), used_ids)
        rel_image = f"panels/{img_path.name}"
        bubbles: List[Bubble] = []
        bubble_rows: List[tuple[List[int], str, float, str]] = []

        for bbox in bboxes:
            crop = crop_with_padding(bgr, bbox, cfg.crop_padding_px)
            raw_text, ocr_ms, _engine = ocr_bubble_crop(crop, cfg)
            stats.ocr_ms += ocr_ms
            bubble_rows.append((bbox, raw_text, ocr_ms, _engine))

        ordered_rows = bubble_rows
        if len(bubble_rows) > 1 and _sort_reading_order is not None:
            arr = np.array([row[0] for row in bubble_rows], dtype=np.float64)
            order = _sort_reading_order(arr, rtl=False)
            ordered_rows = [bubble_rows[i] for i in order]

        for idx, (bbox, raw_text, _ocr_ms, _engine) in enumerate(ordered_rows, start=1):
            bubbles.append(
                Bubble(
                    bubble_id=f"{pid}_b{idx}",
                    bbox=bbox,
                    raw_text=raw_text,
                    corrected_text=raw_text,
                    type=BubbleType.speech,
                    reading_order=idx,
                )
            )
        bubbles = assign_bubble_reading_orders(bubbles)

        doc_panels.append(
            Panel2a(
                panel_id=pid,
                image_path=rel_image,
                bubbles=bubbles,
            )
        )
        stats.panels += 1
        stats.bubbles += len(bubbles)

    doc = Stage2aDocument(project=project_name, panels=doc_panels)
    stats.total_ms = (time.perf_counter() - t0) * 1000.0
    return doc, stats


def save_stage_2a(
    doc: Stage2aDocument,
    project: Optional[str] = None,
    *,
    output_path: Optional[str | Path] = None,
) -> Path:
    name = sanitize_project_name(project or doc.project)
    if output_path is not None and str(output_path).strip():
        raw = str(output_path).strip()
        candidate = Path(raw)
        path = (ROOT / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    else:
        path = stage_2a_json_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc.model_dump_json_pretty(), encoding="utf-8")
    return path


def load_stage_2a(project: str) -> Stage2aDocument:
    path = stage_2a_json_path(project)
    if not path.is_file():
        raise FileNotFoundError(f"stage_2a.json не найден: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return Stage2aDocument.model_validate(data)


def resolve_panel_abs_path(project: str, image_path: str) -> Path:
    base = project_dir(sanitize_project_name(project))
    candidate = (base / image_path).resolve()
    if candidate.is_file():
        return candidate
    alt = (base / "panels" / Path(image_path).name).resolve()
    if alt.is_file():
        return alt
    raise FileNotFoundError(f"Панель не найдена: {image_path}")


def reocr_bubble(
    project: str,
    panel_id: str,
    bubble_id: str,
    bbox: List[int],
    *,
    image_path: Optional[str] = None,
    panel_abs_path: Optional[str] = None,
    cfg: Optional[Stage2aConfig] = None,
) -> Tuple[str, float, str]:
    """Re-run OCR on one bubble bbox; returns (raw_text, ocr_ms, engine_used)."""
    _ = bubble_id
    cfg = cfg or load_stage_2a_config()
    bbox_int = [int(round(x)) for x in bbox]
    if len(bbox_int) != 4:
        raise ValueError("bbox должен содержать 4 числа [x1,y1,x2,y2]")

    img_path: Optional[Path] = None
    abs_raw = (panel_abs_path or "").strip()
    if abs_raw:
        img_path = resolve_file_path(abs_raw, ROOT)

    if img_path is None:
        rel = (image_path or "").strip()
        if not rel:
            doc = load_stage_2a(project)
            panel = next((p for p in doc.panels if p.panel_id == panel_id), None)
            if panel is None:
                raise ValueError(f"Панель не найдена: {panel_id}")
            rel = panel.image_path
        img_path = resolve_panel_abs_path(project, rel)

    bgr = _imread_panel(img_path, cfg.composite_alpha_on_white)
    if bgr is None:
        raise FileNotFoundError(f"Не удалось прочитать: {img_path}")

    crop = crop_with_padding(bgr, bbox_int, cfg.crop_padding_px)
    return ocr_bubble_crop(crop, cfg)


def _bbox_iou(a: List[int], b: List[int]) -> float:
    ix1 = max(a[0], b[0])
    iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2])
    iy2 = min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    area_a = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
    area_b = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _next_bubble_id(panel: Panel2a) -> str:
    n = len(panel.bubbles) + 1
    bid = f"{panel.panel_id}_b{n}"
    existing = {b.bubble_id for b in panel.bubbles}
    while bid in existing:
        n += 1
        bid = f"{panel.panel_id}_b{n}"
    return bid


def init_project_from_panels_dir(
    panels_folder: Path,
    project: str,
    *,
    cfg: Optional[Stage2aConfig] = None,
    sync_panels: bool = True,
) -> Stage2aDocument:
    """Create stage_2a.json with empty bubbles (manual-first workflow)."""
    _ = cfg or load_stage_2a_config()
    project_name = sanitize_project_name(project)
    project_dir(project_name).mkdir(parents=True, exist_ok=True)

    if sync_panels:
        sync_panels_to_project(panels_folder, project_name, replace=True)
    images = list_images(panels_folder)
    doc_panels: List[Panel2a] = []
    used_ids: set[str] = set()
    for img_path in images:
        pid = _unique_panel_id(panel_id_from_filename(img_path.name), used_ids)
        doc_panels.append(
            Panel2a(
                panel_id=pid,
                image_path=f"panels/{img_path.name}",
                bubbles=[],
            )
        )
    doc = Stage2aDocument(project=project_name, panels=doc_panels)
    save_stage_2a(doc)
    return doc


def _read_panel_bgr(
    project: str,
    panel: Panel2a,
    *,
    panel_abs_path: Optional[str] = None,
    cfg: Optional[Stage2aConfig] = None,
) -> tuple[np.ndarray, Path]:
    cfg = cfg or load_stage_2a_config()
    img_path: Optional[Path] = None
    abs_raw = (panel_abs_path or "").strip()
    if abs_raw:
        img_path = resolve_file_path(abs_raw, ROOT)
    if img_path is None:
        img_path = resolve_panel_abs_path(project, panel.image_path)
    bgr = _imread_panel(img_path, cfg.composite_alpha_on_white)
    if bgr is None:
        raise FileNotFoundError(f"Не удалось прочитать: {img_path}")
    return bgr, img_path


def ocr_panel_bubbles(
    project: str,
    panel_id: str,
    *,
    panel_abs_path: Optional[str] = None,
    bubbles: Optional[List[Bubble]] = None,
    cfg: Optional[Stage2aConfig] = None,
) -> tuple[Panel2a, int, float, str]:
    """OCR all bubbles on one panel; returns (panel, count, ocr_ms, last_engine)."""
    cfg = cfg or load_stage_2a_config()
    doc = load_stage_2a(project)
    panel = next((p for p in doc.panels if p.panel_id == panel_id), None)
    if panel is None:
        raise ValueError(f"Панель не найдена: {panel_id}")

    work_bubbles = bubbles if bubbles is not None else panel.bubbles
    if not work_bubbles:
        return panel, 0, 0.0, cfg.ocr_engine

    bgr, _ = _read_panel_bgr(project, panel, panel_abs_path=panel_abs_path, cfg=cfg)
    updated: List[Bubble] = []
    ocr_ms = 0.0
    engine_used = cfg.ocr_engine
    for b in work_bubbles:
        bbox = [int(round(x)) for x in b.bbox]
        crop = crop_with_padding(bgr, bbox, cfg.crop_padding_px)
        raw_text, ms, eng = ocr_bubble_crop(crop, cfg)
        ocr_ms += ms
        engine_used = eng
        updated.append(
            b.model_copy(
                update={
                    "bbox": bbox,
                    "raw_text": raw_text,
                    "corrected_text": raw_text,
                }
            )
        )
    out_panel = panel.model_copy(update={"bubbles": updated})
    return out_panel, len(updated), ocr_ms, engine_used


def detect_panel_bubbles(
    project: str,
    panel_id: str,
    *,
    panel_abs_path: Optional[str] = None,
    merge_mode: str = "append",
    cfg: Optional[Stage2aConfig] = None,
    iou_dedupe: float = 0.45,
) -> tuple[Panel2a, int]:
    """Run YOLO on one panel; merge_mode: append | replace."""
    cfg = cfg or load_stage_2a_config()
    doc = load_stage_2a(project)
    panel = next((p for p in doc.panels if p.panel_id == panel_id), None)
    if panel is None:
        raise ValueError(f"Панель не найдена: {panel_id}")

    bgr, _ = _read_panel_bgr(project, panel, panel_abs_path=panel_abs_path, cfg=cfg)
    bboxes, _scores, _yolo_ms = detect_text_bubbles(
        bgr,
        bubble_class_id=cfg.bubble_class_id,
        confidence_threshold=cfg.confidence_threshold,
        iou_threshold=cfg.iou_threshold,
        min_area_px=cfg.min_bubble_area_px,
        bubble_detect=cfg.bubble_detect,
    )

    if merge_mode == "replace":
        bubbles: List[Bubble] = []
        for idx, bbox in enumerate(bboxes, start=1):
            bubbles.append(
                Bubble(
                    bubble_id=f"{panel_id}_b{idx}",
                    bbox=[int(v) for v in bbox],
                    raw_text="",
                    corrected_text="",
                    type=BubbleType.speech,
                    reading_order=idx,
                )
            )
        bubbles = assign_bubble_reading_orders(bubbles)
        return panel.model_copy(update={"bubbles": bubbles}), len(bboxes)

    existing = list(panel.bubbles)
    added = 0
    for bbox in bboxes:
        bb = [int(v) for v in bbox]
        if any(_bbox_iou(bb, ex.bbox) >= iou_dedupe for ex in existing):
            continue
        bid = _next_bubble_id(panel.model_copy(update={"bubbles": existing}))
        order = len(existing) + 1
        existing.append(
            Bubble(
                bubble_id=bid,
                bbox=bb,
                raw_text="",
                corrected_text="",
                type=BubbleType.speech,
                reading_order=order,
            )
        )
        added += 1
    existing = assign_bubble_reading_orders(existing)
    return panel.model_copy(update={"bubbles": existing}), added

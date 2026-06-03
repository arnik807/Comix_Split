# pipeline.py
"""
ComicSplit MVP pipeline.

YOLO output:  (1, 5, 8400)  → [cx, cy, w, h, conf] в координатах 640×640
SAM encoder:  HWC float32, масштабируется до 1024px по длинной стороне
SAM decoder:  box prompt в пространстве SAM + orig_im_size для обратного resize
"""

from __future__ import annotations

import json
import pathlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import onnxruntime as ort

from utils.config import AppConfig, get_config

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")


# ── Кеш ONNX сессий ───────────────────────────────────────────────────
_SESSION_CACHE: dict[str, ort.InferenceSession] = {}

ROOT_DIR = pathlib.Path(__file__).resolve().parent
MODEL_DIR = ROOT_DIR / "models"
SAM_ENCODER_MODEL = MODEL_DIR / "mobilesam_encoder_int8.onnx"
SAM_DECODER_MODEL = MODEL_DIR / "mobilesam_decoder_int8.onnx"

CONF_THRESHOLD = 0.35
IOU_THRESHOLD = 0.45
_OVERLAP_FILTER_THRESH = 0.7
SAM_SIZE = 1024


def _sync_config() -> AppConfig:
    cfg = get_config()
    global CONF_THRESHOLD, IOU_THRESHOLD, _OVERLAP_FILTER_THRESH
    CONF_THRESHOLD = cfg.confidence_threshold
    IOU_THRESHOLD = cfg.iou_threshold
    _OVERLAP_FILTER_THRESH = cfg.overlap_filter_threshold
    return cfg


@dataclass
class Panel:
    panel_id: str
    bbox: List[int]
    polygon: List[Tuple[int, int]]
    confidence: float
    reading_order: Optional[int] = None
    source: str = "yolo"
    output_path: Optional[str] = None


@dataclass
class PageResult:
    panels: List[Panel]
    timings_ms: Dict[str, float] = field(default_factory=dict)
    page_name: str = ""


@dataclass
class SourceResult:
    pages_processed: int
    panels_total: int
    output_dir: str
    page_results: List[PageResult] = field(default_factory=list)


def _load_session(model_path: pathlib.Path) -> ort.InferenceSession:
    key = str(model_path)
    if key not in _SESSION_CACHE:
        if not model_path.is_file():
            raise FileNotFoundError(f"Модель не найдена: {model_path}")
        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        opts.intra_op_num_threads = 0
        _SESSION_CACHE[key] = ort.InferenceSession(
            str(model_path), opts, providers=["CPUExecutionProvider"]
        )
    return _SESSION_CACHE[key]


def _log(msg: str, quiet: bool) -> None:
    if not quiet:
        print(msg)


def _parse_yolo_output(
    raw: np.ndarray,
    num_classes: int = 1,
    panel_class_id: int = 0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return cx, cy, w, h, scores in 640-space from ONNX output."""
    if raw.ndim == 3:
        pred = raw[0]
    else:
        pred = raw

    # YOLO26 end2end export: (N, 6) = x1, y1, x2, y2, conf, class_id
    if pred.ndim == 2 and pred.shape[1] == 6:
        cls = pred[:, 5].astype(int)
        keep = cls == int(panel_class_id)
        pred = pred[keep]
        if pred.size == 0:
            empty = np.array([], dtype=np.float32)
            return empty, empty, empty, empty, empty
        x1, y1, x2, y2 = pred[:, 0], pred[:, 1], pred[:, 2], pred[:, 3]
        scores = pred[:, 4].astype(np.float32)
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        w = x2 - x1
        h = y2 - y1
        return cx, cy, w, h, scores

    if pred.shape[0] == 5 and num_classes <= 1:
        cx, cy, w, h, scores = pred[0], pred[1], pred[2], pred[3], pred[4]
        return cx, cy, w, h, scores

    if pred.shape[0] >= 4 + num_classes:
        cx, cy, w, h = pred[0], pred[1], pred[2], pred[3]
        class_scores = pred[4 : 4 + num_classes]
        scores = class_scores[int(panel_class_id)]
        return cx, cy, w, h, scores

    raise ValueError(
        f"Unexpected YOLO ONNX shape {tuple(raw.shape)} for num_classes={num_classes}"
    )


def _preprocess_yolo(img: np.ndarray) -> np.ndarray:
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, (640, 640), interpolation=cv2.INTER_LINEAR)
    norm = resized.astype(np.float32) / 255.0
    return np.expand_dims(norm.transpose(2, 0, 1), axis=0)


def _run_yolo(
    session: ort.InferenceSession,
    img: np.ndarray,
    quiet: bool = False,
    num_classes: int = 1,
    panel_class_id: int = 0,
) -> Tuple[np.ndarray, np.ndarray, float]:
    t0 = time.perf_counter()
    raw = session.run(None, {"images": _preprocess_yolo(img)})[0]
    cx, cy, w, h, scores = _parse_yolo_output(
        raw, num_classes=num_classes, panel_class_id=panel_class_id
    )
    keep = scores > CONF_THRESHOLD
    if not np.any(keep):
        ms = (time.perf_counter() - t0) * 1000
        _log(f"  YOLO: нет детекций выше {CONF_THRESHOLD}", quiet)
        return np.zeros((0, 4), dtype=int), np.array([]), ms

    cx, cy, w, h, scores = cx[keep], cy[keep], w[keep], h[keep], scores[keep]
    x1 = cx - w / 2
    y1 = cy - h / 2
    boxes_nms = np.stack([x1, y1, w, h], axis=1).tolist()
    idxs = cv2.dnn.NMSBoxes(boxes_nms, scores.tolist(), CONF_THRESHOLD, IOU_THRESHOLD)

    if len(idxs) == 0:
        ms = (time.perf_counter() - t0) * 1000
        _log("  YOLO: все детекции отфильтрованы NMS", quiet)
        return np.zeros((0, 4), dtype=int), np.array([]), ms

    idxs = idxs.flatten()
    x1, y1, w, h, scores = x1[idxs], y1[idxs], w[idxs], h[idxs], scores[idxs]
    x2, y2 = x1 + w, y1 + h
    oh, ow = img.shape[:2]
    sx, sy = ow / 640, oh / 640
    bboxes = np.stack(
        [
            np.clip((x1 * sx).astype(int), 0, ow),
            np.clip((y1 * sy).astype(int), 0, oh),
            np.clip((x2 * sx).astype(int), 0, ow),
            np.clip((y2 * sy).astype(int), 0, oh),
        ],
        axis=1,
    )
    ms = (time.perf_counter() - t0) * 1000
    _log(
        f"  YOLO: {len(bboxes)} панелей, conf={scores.round(2).tolist()}, {ms:.0f}ms",
        quiet,
    )
    keep_mask = _filter_contained(bboxes, scores)
    bboxes, scores = bboxes[keep_mask], scores[keep_mask]
    return bboxes, scores, ms


def _filter_contained(
    bboxes: np.ndarray, scores: np.ndarray, overlap_thresh: Optional[float] = None
) -> np.ndarray:
    thresh = overlap_thresh if overlap_thresh is not None else _OVERLAP_FILTER_THRESH
    keep = np.ones(len(bboxes), dtype=bool)
    areas = (bboxes[:, 2] - bboxes[:, 0]) * (bboxes[:, 3] - bboxes[:, 1])
    order = np.argsort(scores)[::-1]

    for i, idx in enumerate(order):
        if not keep[idx]:
            continue
        for jdx in order[i + 1 :]:
            if not keep[jdx]:
                continue
            ix1 = max(bboxes[idx, 0], bboxes[jdx, 0])
            iy1 = max(bboxes[idx, 1], bboxes[jdx, 1])
            ix2 = min(bboxes[idx, 2], bboxes[jdx, 2])
            iy2 = min(bboxes[idx, 3], bboxes[jdx, 3])
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            if inter / min(areas[idx], areas[jdx]) > thresh:
                keep[jdx] = False
    return keep


def _run_sam_encoder(
    encoder_sess: ort.InferenceSession,
    img: np.ndarray,
    quiet: bool = False,
) -> Tuple[np.ndarray, float, float]:
    t0 = time.perf_counter()
    oh, ow = img.shape[:2]
    sam_scale = SAM_SIZE / max(oh, ow)
    new_h = int(oh * sam_scale)
    new_w = int(ow * sam_scale)
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32)
    resized = cv2.resize(rgb, (new_w, new_h))
    emb = encoder_sess.run(None, {"input_image": resized})[0]
    ms = (time.perf_counter() - t0) * 1000
    _log(
        f"  SAM encoder: {ms:.0f}ms  ({ow}×{oh} → {new_w}×{new_h}, scale={sam_scale:.3f})",
        quiet,
    )
    return emb, sam_scale, ms


def _run_sam_decoder(
    decoder_sess: ort.InferenceSession,
    embeddings: np.ndarray,
    bbox: Tuple[int, int, int, int],
    orig_shape: Tuple[int, int],
    sam_scale: float,
) -> np.ndarray:
    oh, ow = orig_shape
    x1, y1, x2, y2 = bbox
    sx1, sy1, sx2, sy2 = x1 * sam_scale, y1 * sam_scale, x2 * sam_scale, y2 * sam_scale
    point_coords = np.array([[[sx1, sy1], [sx2, sy2]]], dtype=np.float32)
    point_labels = np.array([[2, 3]], dtype=np.float32)
    mask_input = np.zeros((1, 1, 256, 256), dtype=np.float32)
    has_mask = np.array([0], dtype=np.float32)
    orig_im_size = np.array([oh, ow], dtype=np.float32)
    out = decoder_sess.run(
        None,
        {
            "image_embeddings": embeddings,
            "point_coords": point_coords,
            "point_labels": point_labels,
            "mask_input": mask_input,
            "has_mask_input": has_mask,
            "orig_im_size": orig_im_size,
        },
    )
    mask = out[0][0, 0]
    return (mask > 0.0).astype(np.uint8) * 255


def _sort_reading_order(bboxes: np.ndarray, rtl: bool = False) -> List[int]:
    if len(bboxes) == 0:
        return []
    centers_y = ((bboxes[:, 1] + bboxes[:, 3]) / 2).tolist()
    heights = (bboxes[:, 3] - bboxes[:, 1]).tolist()
    order = sorted(range(len(bboxes)), key=lambda i: centers_y[i])
    rows: List[List[int]] = []

    for idx in order:
        placed = False
        for row in rows:
            rep = row[0]
            overlap = min(bboxes[idx, 3], bboxes[rep, 3]) - max(
                bboxes[idx, 1], bboxes[rep, 1]
            )
            if overlap > 0.4 * min(heights[idx], heights[rep]):
                row.append(idx)
                placed = True
                break
        if not placed:
            rows.append([idx])

    sorted_indices: List[int] = []
    for row in rows:
        row.sort(key=lambda i: bboxes[i, 0], reverse=rtl)
        sorted_indices.extend(row)
    return sorted_indices


def format_panel_filename(
    global_order: int,
    page_num: int,
    panel_num: int,
    cfg: Optional[AppConfig] = None,
) -> str:
    cfg = cfg or get_config()
    return cfg.format_panel_name(global_order, page_num, panel_num)


def analyze_page(
    img: np.ndarray,
    use_sam: bool = False,
    reading_order: bool = False,
    rtl: bool = False,
    quiet: bool = False,
    panel_detector: Optional[str] = None,
) -> PageResult:
    """Run detection on an in-memory BGR image; return panels without saving files."""
    from utils.panel_detector import ensure_detector_installed, get_detector

    cfg = _sync_config()
    spec = ensure_detector_installed(get_detector(panel_detector))
    t_total = time.perf_counter()
    timings: Dict[str, float] = {}
    timings["detector"] = spec.id

    yolo_sess = _load_session(spec.onnx_path)
    bboxes, scores, timings["yolo_ms"] = _run_yolo(
        yolo_sess,
        img,
        quiet=quiet,
        num_classes=spec.num_classes,
        panel_class_id=spec.panel_class_id,
    )

    if len(bboxes) == 0:
        timings["total_ms"] = (time.perf_counter() - t_total) * 1000
        return PageResult(panels=[], timings_ms=timings)

    embeddings: Optional[np.ndarray] = None
    sam_scale = 1.0
    dec_sess = None
    timings["sam_encoder_ms"] = 0.0
    timings["sam_decoder_ms"] = 0.0

    if use_sam:
        enc_sess = _load_session(SAM_ENCODER_MODEL)
        dec_sess = _load_session(SAM_DECODER_MODEL)
        embeddings, sam_scale, timings["sam_encoder_ms"] = _run_sam_encoder(
            enc_sess, img, quiet=quiet
        )

    oh, ow = img.shape[:2]
    indices = (
        _sort_reading_order(bboxes, rtl=rtl)
        if reading_order
        else list(range(len(bboxes)))
    )

    panels: List[Panel] = []
    for read_order, orig_idx in enumerate(indices, start=1):
        bbox = tuple(int(v) for v in bboxes[orig_idx])
        score = float(scores[orig_idx])
        x1, y1, x2, y2 = bbox

        if use_sam and embeddings is not None and dec_sess is not None:
            t_dec = time.perf_counter()
            mask = _run_sam_decoder(dec_sess, embeddings, bbox, (oh, ow), sam_scale)
            timings["sam_decoder_ms"] += (time.perf_counter() - t_dec) * 1000
            source_tag = "yolo+sam"
        else:
            mask = np.zeros((oh, ow), dtype=np.uint8)
            cv2.rectangle(mask, (x1, y1), (x2, y2), 255, -1)
            source_tag = "yolo"

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        best = max(contours, key=cv2.contourArea)
        epsilon = 0.02 * cv2.arcLength(best, True)
        approx = cv2.approxPolyDP(best, epsilon, True)
        polygon = [(int(p[0][0]), int(p[0][1])) for p in approx]

        panels.append(
            Panel(
                panel_id=f"p{read_order:03d}",
                bbox=list(bbox),
                polygon=polygon,
                confidence=score,
                reading_order=read_order if reading_order else None,
                source=source_tag,
            )
        )

    timings["total_ms"] = (time.perf_counter() - t_total) * 1000
    return PageResult(panels=panels, timings_ms=timings)


def _save_panel_crop(
    img: np.ndarray,
    panel: Panel,
    out_path: pathlib.Path,
) -> None:
    x1, y1, x2, y2 = panel.bbox
    oh, ow = img.shape[:2]
    mask = np.zeros((oh, ow), dtype=np.uint8)
    pts = np.array(panel.polygon, dtype=np.int32)
    cv2.fillPoly(mask, [pts], 255)
    panel_rgba = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    panel_rgba[:, :, 3] = mask
    cropped = panel_rgba[y1:y2, x1:x2]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", cropped)
    if ok:
        buf.tofile(str(out_path))
    panel.output_path = str(out_path)


def _save_visualization(
    img: np.ndarray, panels: List[Panel], vis_path: pathlib.Path
) -> None:
    vis = img.copy()
    colors = [
        (52, 152, 219),
        (46, 204, 113),
        (231, 76, 60),
        (155, 89, 182),
        (241, 196, 15),
        (26, 188, 156),
    ]
    for i, panel in enumerate(panels):
        color = colors[i % len(colors)]
        pts = np.array(panel.polygon, dtype=np.int32)
        overlay = vis.copy()
        cv2.fillPoly(overlay, [pts], color)
        vis = cv2.addWeighted(overlay, 0.3, vis, 0.7, 0)
        cv2.polylines(vis, [pts], True, color, 2)
    cv2.imwrite(str(vis_path), vis)


def export_page_panels(
    img: np.ndarray,
    panels: List[Panel],
    out_root: pathlib.Path,
    page_num: int,
    global_order_start: int,
    cfg: Optional[AppConfig] = None,
) -> int:
    """Save panel PNGs; return next global order index."""
    cfg = cfg or get_config()
    order = global_order_start
    for panel in panels:
        order += 1
        panel_num = panel.reading_order or order
        fname = format_panel_filename(order, page_num, panel_num, cfg)
        out_path = out_root / fname
        _save_panel_crop(img, panel, out_path)
    return order


def process_page(
    source_path: str,
    output_dir: str,
    use_sam: bool = False,
    reading_order: bool = False,
    rtl: bool = False,
    page_num: int = 1,
    global_order_start: int = 0,
    quiet: bool = False,
    cfg: Optional[AppConfig] = None,
    panel_detector: Optional[str] = None,
) -> List[Panel]:
    cfg = cfg or get_config()
    t_total = time.perf_counter()

    img = cv2.imdecode(np.fromfile(source_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Не удалось открыть: {source_path}")

    _log(f"\n[page] {source_path}  ({img.shape[1]}x{img.shape[0]} px)", quiet)

    result = analyze_page(
        img,
        use_sam=use_sam,
        reading_order=reading_order,
        rtl=rtl,
        quiet=quiet,
        panel_detector=panel_detector,
    )
    if not result.panels:
        _log("  [!] Панели не найдены.", quiet)
        return []

    stem = pathlib.Path(source_path).stem
    out_root = pathlib.Path(output_dir) / stem
    out_root.mkdir(parents=True, exist_ok=True)
    export_page_panels(img, result.panels, out_root, page_num, global_order_start, cfg)
    _save_visualization(img, result.panels, out_root / "_visualization.jpg")
    _log(f"  [vis] Визуализация: {out_root / '_visualization.jpg'}", quiet)

    ms_total = (time.perf_counter() - t_total) * 1000
    _log(
        f"  [ok] {len(result.panels)} панелей -> {out_root}  (total {ms_total:.0f}ms)",
        quiet,
    )
    return result.panels


def process_page_array(
    page_name: str,
    img: np.ndarray,
    out_root: pathlib.Path,
    page_num: int,
    global_order_start: int,
    use_sam: bool = False,
    reading_order: bool = False,
    rtl: bool = False,
    quiet: bool = False,
    cfg: Optional[AppConfig] = None,
    panel_detector: Optional[str] = None,
) -> PageResult:
    cfg = cfg or get_config()
    out_root.mkdir(parents=True, exist_ok=True)

    _log(f"\n[page] {page_name}  ({img.shape[1]}x{img.shape[0]} px)", quiet)
    result = analyze_page(
        img,
        use_sam=use_sam,
        reading_order=reading_order,
        rtl=rtl,
        quiet=quiet,
        panel_detector=panel_detector,
    )
    result.page_name = page_name

    if result.panels:
        export_page_panels(
            img, result.panels, out_root, page_num, global_order_start, cfg
        )
        page_sub = out_root / f"page_{page_num:03d}"
        page_sub.mkdir(parents=True, exist_ok=True)
        _save_visualization(img, result.panels, page_sub / "_visualization.jpg")
        _log(f"  [ok] {len(result.panels)} панелей (page {page_num})", quiet)
    else:
        _log("  [!] Панели не найдены.", quiet)

    return result


def process_source(
    source_path: str,
    output_dir: str,
    use_sam: Optional[bool] = None,
    reading_order: Optional[bool] = None,
    rtl: Optional[bool] = None,
    max_workers: Optional[int] = None,
    quiet: bool = False,
    cfg: Optional[AppConfig] = None,
    panel_detector: Optional[str] = None,
) -> SourceResult:
    """Process CBZ/CBR/ZIP/folder or single image; export all panels."""
    from utils.io_helpers import load_source

    cfg = cfg or get_config()
    if panel_detector is None:
        panel_detector = cfg.panel_detector
    use_sam = cfg.use_sam if use_sam is None else use_sam
    reading_order = cfg.reading_order if reading_order is None else reading_order
    rtl = cfg.rtl if rtl is None else rtl
    workers = max_workers if max_workers is not None else cfg.max_workers

    src = pathlib.Path(source_path)
    comic_name = src.stem if src.is_file() else src.name
    out_root = pathlib.Path(output_dir) / comic_name
    out_root.mkdir(parents=True, exist_ok=True)

    pages = load_source(source_path)
    if not pages:
        return SourceResult(pages_processed=0, panels_total=0, output_dir=str(out_root))

    indexed: List[Tuple[int, str, np.ndarray]] = [
        (i, name, img) for i, (name, img) in enumerate(pages, start=1)
    ]

    def _analyze_one(
        page_num: int, name: str, img: np.ndarray
    ) -> Tuple[int, str, PageResult]:
        pr = analyze_page(
            img,
            use_sam=use_sam,
            reading_order=reading_order,
            rtl=rtl,
            quiet=True,
            panel_detector=panel_detector,
        )
        pr.page_name = name
        return page_num, name, pr

    analyzed: List[Tuple[int, str, PageResult, np.ndarray]] = []

    if workers <= 1 or len(indexed) == 1:
        for page_num, name, img in indexed:
            _, _, pr = _analyze_one(page_num, name, img)
            analyzed.append((page_num, name, pr, img))
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_analyze_one, pn, nm, im) for pn, nm, im in indexed]
            for fut in as_completed(futures):
                page_num, name, pr = fut.result()
                img = next(
                    im for pn, nm, im in indexed if pn == page_num and nm == name
                )
                analyzed.append((page_num, name, pr, img))
        analyzed.sort(key=lambda x: x[0])

    global_order = 0
    page_results: List[PageResult] = []
    for page_num, name, pr, img in analyzed:
        _log(f"\n[page] {name}  (export)", quiet)
        if pr.panels:
            global_order = export_page_panels(
                img, pr.panels, out_root, page_num, global_order, cfg
            )
            page_sub = out_root / f"page_{page_num:03d}"
            page_sub.mkdir(parents=True, exist_ok=True)
            _save_visualization(img, pr.panels, page_sub / "_visualization.jpg")
        page_results.append(pr)

    panels_total = sum(len(p.panels) for p in page_results)
    return SourceResult(
        pages_processed=len(page_results),
        panels_total=panels_total,
        output_dir=str(out_root),
        page_results=page_results,
    )


def _json_convert(obj: Any) -> Any:
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Not serializable: {type(obj)}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(
            "Usage: python pipeline.py <image|cbz|folder> <output_dir> [--sam] [--order] [--rtl]\n"
            "  --sam    MobileSAM refinement\n"
            "  --order  reading order sort\n"
            "  --rtl    right-to-left (manga)"
        )
        sys.exit(1)

    src = sys.argv[1]
    out = sys.argv[2]
    cfg = get_config()
    use_sam = "--sam" in sys.argv or cfg.use_sam
    order = "--order" in sys.argv or cfg.reading_order
    rtl = "--rtl" in sys.argv or cfg.rtl

    path = pathlib.Path(src)
    if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
        result = process_page(src, out, use_sam=use_sam, reading_order=order, rtl=rtl)
        payload = [asdict(p) for p in result]
    else:
        sr = process_source(src, out, use_sam=use_sam, reading_order=order, rtl=rtl)
        payload = {
            "pages_processed": sr.pages_processed,
            "panels_total": sr.panels_total,
            "output_dir": sr.output_dir,
        }

    print(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_convert))

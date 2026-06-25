"""YOLO text_bubble detection on panel crops (manga model, class 1)."""

from __future__ import annotations

import time
from typing import List, Sequence, Tuple

import cv2
import numpy as np

import pipeline as pl
from story_analyzer.bubble_detect_config import BubbleDetectConfig
from utils.panel_detector import ensure_detector_installed, get_detector


def _tile_origins(length: int, tile_size: int, stride: int) -> List[int]:
    if length <= tile_size:
        return [0]
    origins = list(range(0, length, stride))
    last = length - tile_size
    if origins[-1] != last:
        origins.append(max(0, last))
    return sorted(set(origins))


def merge_boxes_nms(
    boxes: Sequence[Sequence[int]],
    scores: Sequence[float],
    *,
    conf_threshold: float,
    iou_threshold: float,
) -> Tuple[List[List[int]], List[float]]:
    if not boxes:
        return [], []
    b = np.asarray(boxes, dtype=np.float32)
    s = np.asarray(scores, dtype=np.float32)
    keep = s >= float(conf_threshold)
    b, s = b[keep], s[keep]
    if len(b) == 0:
        return [], []

    x1, y1, x2, y2 = b[:, 0], b[:, 1], b[:, 2], b[:, 3]
    w = np.maximum(0.0, x2 - x1)
    h = np.maximum(0.0, y2 - y1)
    boxes_nms = np.stack([x1, y1, w, h], axis=1).tolist()
    idxs = cv2.dnn.NMSBoxes(
        boxes_nms,
        s.tolist(),
        float(conf_threshold),
        float(iou_threshold),
    )
    if len(idxs) == 0:
        return [], []
    idxs = np.asarray(idxs).flatten()
    out_boxes = [[int(v) for v in b[i]] for i in idxs]
    out_scores = [float(s[i]) for i in idxs]
    return out_boxes, out_scores


def _run_yolo_pass(
    session,
    img_bgr: np.ndarray,
    *,
    spec,
    bubble_class_id: int,
    confidence_threshold: float,
    iou_threshold: float,
    input_size: int,
    filter_contained: bool,
) -> Tuple[np.ndarray, np.ndarray, float]:
    old_conf, old_iou = pl.CONF_THRESHOLD, pl.IOU_THRESHOLD
    try:
        pl.CONF_THRESHOLD = float(confidence_threshold)
        pl.IOU_THRESHOLD = float(iou_threshold)
        return pl._run_yolo(
            session,
            img_bgr,
            quiet=True,
            num_classes=spec.num_classes,
            panel_class_id=int(bubble_class_id),
            input_size=int(input_size),
            filter_contained=filter_contained,
        )
    finally:
        pl.CONF_THRESHOLD, pl.IOU_THRESHOLD = old_conf, old_iou


def _detect_tiled(
    session,
    img_bgr: np.ndarray,
    *,
    spec,
    bubble_class_id: int,
    confidence_threshold: float,
    iou_threshold: float,
    tile_size: int,
    tile_overlap: float,
    filter_contained: bool,
) -> Tuple[List[List[int]], List[float], float]:
    t0 = time.perf_counter()
    h, w = img_bgr.shape[:2]
    stride = max(1, int(tile_size * (1.0 - tile_overlap)))
    all_boxes: List[List[int]] = []
    all_scores: List[float] = []
    tile_ms = 0.0

    for y0 in _tile_origins(h, tile_size, stride):
        for x0 in _tile_origins(w, tile_size, stride):
            x2 = min(x0 + tile_size, w)
            y2 = min(y0 + tile_size, h)
            tile = img_bgr[y0:y2, x0:x2]
            if tile.size == 0:
                continue
            boxes, scores, ms = _run_yolo_pass(
                session,
                tile,
                spec=spec,
                bubble_class_id=bubble_class_id,
                confidence_threshold=confidence_threshold,
                iou_threshold=iou_threshold,
                input_size=tile_size,
                filter_contained=filter_contained,
            )
            tile_ms += ms
            for i in range(len(boxes)):
                x1, y1, bx2, by2 = (int(v) for v in boxes[i])
                all_boxes.append([x1 + x0, y1 + y0, bx2 + x0, by2 + y0])
                all_scores.append(float(scores[i]) if i < len(scores) else 0.0)

    merged_boxes, merged_scores = merge_boxes_nms(
        all_boxes,
        all_scores,
        conf_threshold=confidence_threshold,
        iou_threshold=iou_threshold,
    )
    total_ms = (time.perf_counter() - t0) * 1000.0
    return merged_boxes, merged_scores, total_ms


def _filter_min_area(
    boxes: List[List[int]],
    scores: List[float],
    min_area_px: int,
) -> Tuple[List[List[int]], List[float]]:
    out_boxes: List[List[int]] = []
    out_scores: List[float] = []
    for box, score in zip(boxes, scores):
        x1, y1, x2, y2 = box
        if max(0, x2 - x1) * max(0, y2 - y1) < min_area_px:
            continue
        out_boxes.append(box)
        out_scores.append(score)
    return out_boxes, out_scores


def _sort_boxes(boxes: List[List[int]], scores: List[float]) -> Tuple[List[List[int]], List[float]]:
    order = sorted(range(len(boxes)), key=lambda idx: (boxes[idx][1], boxes[idx][0]))
    return [boxes[i] for i in order], [scores[i] for i in order]


def detect_text_bubbles(
    img_bgr: np.ndarray,
    *,
    bubble_class_id: int = 1,
    confidence_threshold: float = 0.25,
    iou_threshold: float = 0.45,
    min_area_px: int = 64,
    bubble_detect: BubbleDetectConfig | None = None,
) -> Tuple[List[List[int]], List[float], float]:
    """Return list of [x1,y1,x2,y2], scores, yolo_ms."""
    bd = bubble_detect or BubbleDetectConfig()
    spec = ensure_detector_installed(get_detector("manga"))
    session = pl._load_session(spec.onnx_path)

    if bd.tiled:
        boxes, scores, ms = _detect_tiled(
            session,
            img_bgr,
            spec=spec,
            bubble_class_id=bubble_class_id,
            confidence_threshold=confidence_threshold,
            iou_threshold=iou_threshold,
            tile_size=bd.tile_size,
            tile_overlap=bd.tile_overlap,
            filter_contained=bd.filter_contained,
        )
    else:
        bboxes, scores_arr, ms = _run_yolo_pass(
            session,
            img_bgr,
            spec=spec,
            bubble_class_id=bubble_class_id,
            confidence_threshold=confidence_threshold,
            iou_threshold=iou_threshold,
            input_size=640,
            filter_contained=bd.filter_contained,
        )
        boxes = [[int(v) for v in row] for row in bboxes]
        scores = [float(s) for s in scores_arr]

    boxes, scores = _filter_min_area(boxes, scores, min_area_px)
    return _sort_boxes(boxes, scores) + (ms,)


def sort_bubble_indices(bboxes: List[List[int]]) -> List[int]:
    return sorted(range(len(bboxes)), key=lambda i: (bboxes[i][1], bboxes[i][0]))

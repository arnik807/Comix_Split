"""
Stage 2a diagnostic: YOLO bbox overlay + bubble crops + OCR results.

Run from repo root:
  python scripts/diagnose_stage_2a.py --panels PATH [--out debug/stage_2a] [--limit 5]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from anim.io_utils import list_images  # noqa: E402
from story_analyzer.config import load_stage_2a_config  # noqa: E402
from story_analyzer.stages.bubble_detector import detect_text_bubbles  # noqa: E402
from story_analyzer.stages.ocr_preprocess import preprocess_bubble_crop  # noqa: E402
from story_analyzer.stages.ocr_reader import crop_with_padding, ocr_bubble_crop  # noqa: E402
from story_analyzer.stages.stage_2a_processor import _imread_panel  # noqa: E402


def _draw_overlay(
    bgr: np.ndarray,
    boxes: list[list[int]],
    scores: list[float],
) -> np.ndarray:
    out = bgr.copy()
    for i, (x1, y1, x2, y2) in enumerate(boxes):
        score = scores[i] if i < len(scores) else 0.0
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 200, 255), 2)
        label = f"#{i + 1} {score:.2f}"
        cv2.putText(
            out,
            label,
            (x1, max(14, y1 - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 200, 255),
            1,
            cv2.LINE_AA,
        )
    return out


def _write_image(path: Path, img: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(path.suffix or ".png", img)
    if not ok:
        raise RuntimeError(f"imencode failed: {path}")
    buf.tofile(str(path))


def diagnose_panel(
    img_path: Path,
    out_dir: Path,
    cfg,
) -> dict:
    bgr = _imread_panel(img_path, cfg.composite_alpha_on_white)
    if bgr is None:
        return {"panel": img_path.name, "error": "imread failed"}

    t0 = time.perf_counter()
    boxes, scores, yolo_ms = detect_text_bubbles(
        bgr,
        bubble_class_id=cfg.bubble_class_id,
        confidence_threshold=cfg.confidence_threshold,
        iou_threshold=cfg.iou_threshold,
        min_area_px=cfg.min_bubble_area_px,
        bubble_detect=cfg.bubble_detect,
    )

    panel_out = out_dir / img_path.stem
    panel_out.mkdir(parents=True, exist_ok=True)

    overlay = _draw_overlay(bgr, boxes, scores)
    _write_image(panel_out / "overlay.png", overlay)
    _write_image(panel_out / "panel.png", bgr)

    bubbles_report = []
    total_ocr_ms = 0.0

    for idx, bbox in enumerate(boxes):
        crop = crop_with_padding(bgr, bbox, cfg.crop_padding_px)
        prepared = (
            preprocess_bubble_crop(crop, cfg.ocr_preprocess)
            if cfg.ocr_preprocess.enabled
            else crop
        )
        text, ocr_ms, engine_used = ocr_bubble_crop(crop, cfg)
        total_ocr_ms += ocr_ms

        prefix = panel_out / f"crop_{idx:02d}"
        _write_image(prefix.with_name(f"{prefix.name}_raw.jpg"), crop)
        _write_image(prefix.with_name(f"{prefix.name}_prep.jpg"), prepared)
        result_path = prefix.with_name(f"{prefix.name}_result.txt")
        result_path.write_text(
            "\n".join(
                [
                    f"bbox: {bbox}",
                    f"score: {scores[idx] if idx < len(scores) else 0.0:.4f}",
                    f"ocr_ms: {ocr_ms:.1f}",
                    f"ocr_engine: {engine_used}",
                    f"text_len: {len(text.strip())}",
                    "---",
                    text or "(empty)",
                ]
            ),
            encoding="utf-8",
        )

        bubbles_report.append(
            {
                "index": idx,
                "bbox": bbox,
                "score": float(scores[idx]) if idx < len(scores) else 0.0,
                "text_len": len(text.strip()),
                "text_preview": (text.strip()[:80] if text else ""),
                "ocr_ms": round(ocr_ms, 1),
            }
        )

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    summary = {
        "panel": img_path.name,
        "size": [int(bgr.shape[1]), int(bgr.shape[0])],
        "bubbles": len(boxes),
        "empty_ocr": sum(1 for b in bubbles_report if b["text_len"] == 0),
        "yolo_ms": round(yolo_ms, 1),
        "ocr_ms": round(total_ocr_ms, 1),
        "total_ms": round(elapsed_ms, 1),
        "bubbles_detail": bubbles_report,
    }
    (panel_out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 2a bubble/OCR diagnostics")
    parser.add_argument(
        "--panels",
        required=True,
        help="Folder with panel PNG/JPG (upscaled recommended)",
    )
    parser.add_argument(
        "--out",
        default="debug/stage_2a",
        help="Output root (default: debug/stage_2a)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Max panels to process (default: 5)",
    )
    parser.add_argument(
        "--label",
        default="",
        help="Subfolder tag, e.g. americ or manga",
    )
    args = parser.parse_args()

    panels_dir = Path(args.panels).expanduser().resolve()
    if not panels_dir.is_dir():
        print(f"ERROR: folder not found: {panels_dir}", file=sys.stderr)
        return 1

    cfg = load_stage_2a_config()
    out_root = (ROOT / args.out).resolve()
    if args.label:
        out_root = out_root / args.label
    out_root.mkdir(parents=True, exist_ok=True)

    images = list_images(panels_dir)[: max(0, args.limit)]
    if not images:
        print(f"ERROR: no images in {panels_dir}", file=sys.stderr)
        return 1

    print(f"Panels: {panels_dir}")
    print(f"Output: {out_root}")
    print(f"Count:  {len(images)}")
    print(
        f"Config: conf={cfg.confidence_threshold}, "
        f"min_area={cfg.min_bubble_area_px}, tiled={cfg.bubble_detect.tiled}, "
        f"ocr={cfg.ocr_engine}"
    )
    print("-" * 50)

    all_summaries = []
    for img_path in images:
        print(f"Processing {img_path.name} ...", flush=True)
        try:
            summary = diagnose_panel(img_path, out_root, cfg)
        except Exception as exc:
            summary = {"panel": img_path.name, "error": str(exc)}
            print(f"  FAIL: {exc}", file=sys.stderr)
        all_summaries.append(summary)
        if "error" not in summary:
            print(
                f"  bubbles={summary['bubbles']}, "
                f"empty_ocr={summary['empty_ocr']}, "
                f"yolo={summary['yolo_ms']}ms"
            )

    report = {
        "panels_dir": str(panels_dir),
        "output": str(out_root),
        "config": {
            "confidence_threshold": cfg.confidence_threshold,
            "min_bubble_area_px": cfg.min_bubble_area_px,
            "bubble_detect": {
                "tiled": cfg.bubble_detect.tiled,
                "tile_size": cfg.bubble_detect.tile_size,
                "tile_overlap": cfg.bubble_detect.tile_overlap,
                "filter_contained": cfg.bubble_detect.filter_contained,
            },
            "ocr_engine": cfg.ocr_engine,
        },
        "panels": all_summaries,
        "totals": {
            "panels": len(all_summaries),
            "bubbles": sum(s.get("bubbles", 0) for s in all_summaries if "error" not in s),
            "empty_ocr": sum(s.get("empty_ocr", 0) for s in all_summaries if "error" not in s),
        },
    }
    report_path = out_root / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("-" * 50)
    print(f"Done. Report: {report_path}")
    print(
        f"Totals: panels={report['totals']['panels']}, "
        f"bubbles={report['totals']['bubbles']}, "
        f"empty_ocr={report['totals']['empty_ocr']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

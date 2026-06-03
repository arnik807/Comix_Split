#!/usr/bin/env python3
"""Isolated YOLO detection test on a single page."""

from __future__ import annotations

import argparse
import pathlib
import sys

import cv2

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import numpy as np

from pipeline import _load_session, _run_yolo, _sync_config  # noqa: E402
from utils.config import load_config  # noqa: E402
from utils.panel_detector import get_detector, normalize_detector  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=pathlib.Path, nargs="?", default=ROOT / "test_page.jpg")
    parser.add_argument("--out", type=pathlib.Path, default=None, help="Save annotated preview")
    parser.add_argument("--detector", default="comic", choices=("comic", "manga"))
    args = parser.parse_args()

    load_config()
    _sync_config()

    img = cv2.imdecode(np.fromfile(str(args.image), dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        sys.exit(f"Cannot read {args.image}")

    spec = get_detector(normalize_detector(args.detector))
    sess = _load_session(spec.onnx_path)
    bboxes, scores, ms = _run_yolo(
        sess,
        img,
        quiet=False,
        num_classes=spec.num_classes,
        panel_class_id=spec.panel_class_id,
    )
    print(f"Detections: {len(bboxes)}, time: {ms:.1f}ms")

    if args.out and len(bboxes):
        vis = img.copy()
        for box, sc in zip(bboxes, scores):
            x1, y1, x2, y2 = box
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                vis, f"{sc:.2f}", (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1
            )
        cv2.imwrite(str(args.out), vis)
        print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()

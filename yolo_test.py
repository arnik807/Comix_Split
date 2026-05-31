#!/usr/bin/env python3
"""Isolated YOLO detection test on a single page."""

from __future__ import annotations

import argparse
import pathlib
import sys

import cv2

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from pipeline import YOLO_MODEL, _load_session, _run_yolo  # noqa: E402
from utils.config import load_config  # noqa: E402
from pipeline import _sync_config  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=pathlib.Path, nargs="?", default=ROOT / "test_page.jpg")
    parser.add_argument("--out", type=pathlib.Path, default=None, help="Save annotated preview")
    args = parser.parse_args()

    load_config()
    _sync_config()

    img = cv2.imdecode(np.fromfile(str(args.image), dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        sys.exit(f"Cannot read {args.image}")

    sess = _load_session(YOLO_MODEL)
    bboxes, scores, ms = _run_yolo(sess, img, quiet=False)
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

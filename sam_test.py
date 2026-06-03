#!/usr/bin/env python3
"""YOLO bbox → MobileSAM mask test on a single page."""

from __future__ import annotations

import argparse
import pathlib
import sys

import cv2
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from pipeline import (  # noqa: E402
    SAM_DECODER_MODEL,
    SAM_ENCODER_MODEL,
    _load_session,
    _run_sam_decoder,
    _run_sam_encoder,
    _run_yolo,
    _sync_config,
)
from utils.config import load_config  # noqa: E402
from utils.panel_detector import get_detector, normalize_detector  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=pathlib.Path, nargs="?", default=ROOT / "test_page.jpg")
    parser.add_argument("--out", type=pathlib.Path, default=ROOT / "output" / "sam_test_vis.jpg")
    parser.add_argument("--detector", default="comic", choices=("comic", "manga"))
    args = parser.parse_args()

    load_config()
    _sync_config()

    img = cv2.imdecode(np.fromfile(str(args.image), dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        sys.exit(f"Cannot read {args.image}")

    spec = get_detector(normalize_detector(args.detector))
    yolo_sess = _load_session(spec.onnx_path)
    bboxes, scores, yolo_ms = _run_yolo(
        yolo_sess,
        img,
        quiet=False,
        num_classes=spec.num_classes,
        panel_class_id=spec.panel_class_id,
    )
    if len(bboxes) == 0:
        sys.exit("No panels from YOLO")

    enc = _load_session(SAM_ENCODER_MODEL)
    dec = _load_session(SAM_DECODER_MODEL)
    emb, scale, enc_ms = _run_sam_encoder(enc, img, quiet=False)
    oh, ow = img.shape[:2]

    vis = img.copy()
    for i, box in enumerate(bboxes):
        mask = _run_sam_decoder(dec, emb, tuple(int(v) for v in box), (oh, ow), scale)
        color = (0, 255, 255) if i % 2 == 0 else (255, 0, 255)
        vis[mask > 0] = (vis[mask > 0] * 0.5 + np.array(color) * 0.5).astype(np.uint8)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.out), vis)
    print(f"YOLO: {yolo_ms:.0f}ms, SAM encoder: {enc_ms:.0f}ms, panels: {len(bboxes)}")
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    main()

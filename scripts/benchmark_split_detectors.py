#!/usr/bin/env python3
"""
Compare comic vs manga YOLO detectors on one or more pages (fast mode, YOLO only).

Usage:
    python scripts/benchmark_split_detectors.py
    python scripts/benchmark_split_detectors.py --image exam_imgs/test_page.jpg
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import sys

import cv2
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import _load_session, _run_yolo  # noqa: E402
from utils.panel_detector import DETECTORS, get_detector  # noqa: E402

SUPPORTED = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}


def bench_detector(detector_id: str, img: np.ndarray) -> dict:
    spec = get_detector(detector_id)
    if not spec.onnx_path.is_file():
        return {
            "detector": detector_id,
            "installed": False,
            "panels": 0,
            "yolo_ms": 0.0,
            "error": f"missing {spec.onnx_path.name}",
        }
    sess = _load_session(spec.onnx_path)
    bboxes, scores, ms = _run_yolo(
        sess,
        img,
        quiet=True,
        num_classes=spec.num_classes,
        panel_class_id=spec.panel_class_id,
    )
    return {
        "detector": detector_id,
        "installed": True,
        "panels": len(bboxes),
        "yolo_ms": round(ms, 1),
        "error": "",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark split detectors (comic vs manga)")
    parser.add_argument("--image", type=pathlib.Path, default=None)
    parser.add_argument("--dataset", type=pathlib.Path, default=ROOT / "exam_imgs")
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=ROOT / "benchmark_split_detectors.csv",
    )
    args = parser.parse_args()

    if args.image:
        images = [args.image]
    else:
        images = sorted(
            p
            for p in args.dataset.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED
        ) if args.dataset.is_dir() else []

    if not images:
        fallback = ROOT / "test_page.jpg"
        if fallback.is_file():
            images = [fallback]
        else:
            print("No images. Pass --image or add files to exam_imgs/")
            sys.exit(1)

    rows: list[dict] = []
    for img_path in images:
        img = cv2.imdecode(np.fromfile(str(img_path), dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            print(f"Skip unreadable: {img_path}")
            continue
        print(f"{img_path.name}:")
        for did in DETECTORS:
            row = bench_detector(did, img)
            row["file"] = img_path.name
            rows.append(row)
            if row["installed"]:
                print(f"  {did}: {row['panels']} panels, {row['yolo_ms']:.0f} ms")
            else:
                print(f"  {did}: SKIP — {row['error']}")

    if rows and args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=["file", "detector", "installed", "panels", "yolo_ms", "error"],
            )
            w.writeheader()
            w.writerows(rows)
        print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()

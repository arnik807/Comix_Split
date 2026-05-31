#!/usr/bin/env python3
"""
Benchmark ComicSplit pipeline on exam_imgs/ or custom paths.
Writes CSV with per-page timings and Phase 1 criteria check (<600ms fast mode).

Usage:
    python benchmark.py
    python benchmark.py --dataset exam_imgs --modes fast,accurate
    python benchmark.py --image test_page.jpg
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import sys
import time
from typing import List

import cv2
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from pipeline import analyze_page, YOLO_MODEL, _load_session  # noqa: E402
from utils.config import get_config, load_config  # noqa: E402

DEFAULT_DATASET = ROOT / "exam_imgs"
PHASE1_MS_LIMIT = 600.0
SUPPORTED = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}


def collect_images(paths: List[str], dataset: pathlib.Path) -> List[pathlib.Path]:
    if paths:
        out: List[pathlib.Path] = []
        for p in paths:
            pp = pathlib.Path(p)
            if pp.is_file():
                out.append(pp)
            elif pp.is_dir():
                out.extend(sorted(pp.iterdir()))
        return [x for x in out if x.suffix.lower() in SUPPORTED]

    if not dataset.is_dir():
        return []
    return sorted(
        p for p in dataset.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED
    )


def warmup() -> None:
    """Load YOLO session once."""
    _load_session(YOLO_MODEL)


def bench_image(path: pathlib.Path, use_sam: bool, repeats: int) -> dict:
    img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(path)

    # warmup inference (model + page)
    analyze_page(img, use_sam=use_sam, reading_order=True, quiet=True)

    rows = []
    for _ in range(repeats):
        pr = analyze_page(img, use_sam=use_sam, reading_order=True, quiet=True)
        rows.append(pr.timings_ms)

    avg = {k: sum(r.get(k, 0) for r in rows) / len(rows) for k in rows[0]}
    last = analyze_page(img, use_sam=use_sam, reading_order=True, quiet=True)
    return {
        "file": path.name,
        "panels": len(last.panels),
        "yolo_ms": round(avg.get("yolo_ms", 0), 1),
        "sam_encoder_ms": round(avg.get("sam_encoder_ms", 0), 1),
        "sam_decoder_ms": round(avg.get("sam_decoder_ms", 0), 1),
        "total_ms": round(avg.get("total_ms", 0), 1),
        "passes_600ms": avg.get("total_ms", 9999) < PHASE1_MS_LIMIT,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="ComicSplit benchmark")
    parser.add_argument("--dataset", type=pathlib.Path, default=DEFAULT_DATASET)
    parser.add_argument("--image", type=pathlib.Path, default=None)
    parser.add_argument("--modes", default="fast,accurate", help="fast and/or accurate")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=ROOT / "benchmark_results.csv",
    )
    args = parser.parse_args()

    load_config()
    images = (
        [args.image]
        if args.image
        else collect_images([], args.dataset)
    )
    if not images:
        # fallback to test_page.jpg
        tp = ROOT / "test_page.jpg"
        if tp.is_file():
            images = [tp]
        else:
            print("No images found. Add files to exam_imgs/ or pass --image.")
            sys.exit(1)

    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    print(f"Benchmark: {len(images)} image(s), modes={modes}, repeats={args.repeats}")
    warmup()

    results: List[dict] = []
    for mode in modes:
        use_sam = mode == "accurate"
        for img_path in images:
            img_path = pathlib.Path(img_path)
            print(f"  {mode}: {img_path.name}...", end=" ", flush=True)
            try:
                row = bench_image(img_path, use_sam=use_sam, repeats=args.repeats)
                row["mode"] = mode
                results.append(row)
                status = "OK" if row["passes_600ms"] or mode == "accurate" else "SLOW"
                print(f"{row['total_ms']:.0f}ms, {row['panels']} panels [{status}]")
            except Exception as e:
                print(f"FAIL: {e}")
                results.append(
                    {
                        "file": img_path.name,
                        "mode": mode,
                        "error": str(e),
                    }
                )

    fieldnames = [
        "file",
        "mode",
        "panels",
        "yolo_ms",
        "sam_encoder_ms",
        "sam_decoder_ms",
        "total_ms",
        "passes_600ms",
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)

    fast_rows = [r for r in results if r.get("mode") == "fast" and "total_ms" in r]
    if fast_rows:
        avg_total = sum(r["total_ms"] for r in fast_rows) / len(fast_rows)
        passed = sum(1 for r in fast_rows if r.get("passes_600ms"))
        print(f"\nPhase 1 (fast): avg {avg_total:.0f}ms/page, "
              f"{passed}/{len(fast_rows)} under {PHASE1_MS_LIMIT:.0f}ms")
    print(f"CSV: {args.out}")


if __name__ == "__main__":
    main()

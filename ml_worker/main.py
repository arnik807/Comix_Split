#!/usr/bin/env python3
"""
ML worker for Go orchestrator (stdin/stdout JSON lines).

Request per line:
{
  "image_b64": "<base64 png/jpeg>",
  "page_num": 1,
  "global_order_start": 0,
  "output_dir": "/path/to/out",
  "use_sam": false,
  "reading_order": true,
  "rtl": false
}

Response:
{
  "panels": [{"panel_id", "bbox", "polygon", "confidence", "reading_order", "source"}],
  "files": ["001_page_001_panel_01.png"],
  "time_ms": 342.1,
  "error": null
}
"""

from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import analyze_page, export_page_panels  # noqa: E402
from utils.config import load_config  # noqa: E402

load_config()


def _decode_image(b64: str) -> np.ndarray:
    raw = base64.b64decode(b64)
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image")
    return img


def handle(req: dict) -> dict:
    t0 = time.perf_counter()
    try:
        img = _decode_image(req["image_b64"])
        page_num = int(req.get("page_num", 1))
        start = int(req.get("global_order_start", 0))
        out_dir = Path(req["output_dir"])
        use_sam = bool(req.get("use_sam", False))
        reading_order = bool(req.get("reading_order", True))
        rtl = bool(req.get("rtl", False))

        result = analyze_page(
            img,
            use_sam=use_sam,
            reading_order=reading_order,
            rtl=rtl,
            quiet=True,
        )
        files: list[str] = []
        if result.panels:
            end_order = export_page_panels(
                img, result.panels, out_dir, page_num, start
            )
            files = [p.output_path for p in result.panels if p.output_path]
            _ = end_order

        panels_out = []
        for p in result.panels:
            panels_out.append(
                {
                    "panel_id": p.panel_id,
                    "bbox": p.bbox,
                    "polygon": p.polygon,
                    "confidence": p.confidence,
                    "reading_order": p.reading_order,
                    "source": p.source,
                }
            )

        return {
            "panels": panels_out,
            "files": [Path(f).name for f in files],
            "time_ms": (time.perf_counter() - t0) * 1000,
            "error": None,
        }
    except Exception as e:
        return {
            "panels": [],
            "files": [],
            "time_ms": (time.perf_counter() - t0) * 1000,
            "error": str(e),
        }


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        resp = handle(req)
        print(json.dumps(resp, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()

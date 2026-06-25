"""CLI: Stage 2a bubble detection + OCR."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from story_analyzer.stages.stage_2a_processor import (  # noqa: E402
    process_panels_dir,
    save_stage_2a,
)
from utils.path_resolve import resolve_dir_path  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 2a: YOLO bubbles + EasyOCR")
    parser.add_argument("--panels", required=True, help="Папка с PNG панелей")
    parser.add_argument("--project", required=True, help="Имя проекта Story Analyzer")
    args = parser.parse_args()

    panels_dir = resolve_dir_path(args.panels, ROOT)
    if not panels_dir.is_dir():
        print(f"Папка не найдена: {panels_dir}", file=sys.stderr)
        return 1

    doc, stats = process_panels_dir(panels_dir, args.project)
    out = save_stage_2a(doc)
    print(f"OK: {out}")
    print(
        f"panels={stats.panels} bubbles={stats.bubbles} "
        f"yolo={stats.yolo_ms:.0f}ms ocr={stats.ocr_ms:.0f}ms total={stats.total_ms:.0f}ms"
    )
    if stats.errors:
        for err in stats.errors:
            print(f"WARN: {err}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

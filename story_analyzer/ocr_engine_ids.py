"""OCR engine id constants (no heavy imports)."""

from __future__ import annotations

OCR_ENGINES = ("easyocr", "paddle", "siliconflow", "auto")


def normalize_ocr_engine(raw: str | None) -> str:
    name = str(raw or "siliconflow").strip().lower()
    return name if name in OCR_ENGINES else "siliconflow"

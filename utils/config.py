"""Load and access ComicSplit config.yaml."""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Any, Optional

import yaml

ROOT_DIR = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT_DIR / "config.yaml"


@dataclass
class AppConfig:
    language: str = "ru"
    quality_mode: str = "fast"  # fast | accurate
    reading_order: bool = True
    reading_direction: str = "ltr"  # ltr | rtl
    max_workers: int = 4
    confidence_threshold: float = 0.35
    iou_threshold: float = 0.45
    overlap_filter_threshold: float = 0.7
    output_pattern: str = "{order:03d}_page_{page:03d}_panel_{panel:02d}.png"

    @property
    def use_sam(self) -> bool:
        return self.quality_mode == "accurate"

    @property
    def rtl(self) -> bool:
        return self.reading_direction == "rtl"

    def format_panel_name(self, order: int, page: int, panel: int) -> str:
        return self.output_pattern.format(order=order, page=page, panel=panel)


_config: Optional[AppConfig] = None


def load_config(path: Optional[pathlib.Path] = None) -> AppConfig:
    global _config
    cfg_path = path or DEFAULT_CONFIG_PATH
    if not cfg_path.is_file():
        _config = AppConfig()
        return _config

    with open(cfg_path, encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    _config = AppConfig(
        language=str(raw.get("language", "ru")),
        quality_mode=str(raw.get("quality_mode", "fast")),
        reading_order=bool(raw.get("reading_order", True)),
        reading_direction=str(raw.get("reading_direction", "ltr")),
        max_workers=int(raw.get("max_workers", 4)),
        confidence_threshold=float(raw.get("confidence_threshold", 0.35)),
        iou_threshold=float(raw.get("iou_threshold", 0.45)),
        overlap_filter_threshold=float(raw.get("overlap_filter_threshold", 0.7)),
        output_pattern=str(
            raw.get(
                "output_pattern",
                "{order:03d}_page_{page:03d}_panel_{panel:02d}.png",
            )
        ),
    )
    return _config


def get_config() -> AppConfig:
    if _config is None:
        return load_config()
    return _config


def apply_config_to_pipeline() -> AppConfig:
    """Push config thresholds into pipeline module globals."""
    import pipeline as pl

    return pl._sync_config()

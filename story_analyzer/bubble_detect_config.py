"""Bubble detection settings for Stage 2a."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BubbleDetectConfig:
    tiled: bool = True
    tile_size: int = 640
    tile_overlap: float = 0.2
    filter_contained: bool = False

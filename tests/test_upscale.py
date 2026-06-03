"""Upscale scale guard and config."""

from __future__ import annotations

import pytest

from utils.anim_config import (
    UpscaleConfig,
    X4_ONLY_UPSCALE_MODEL,
    load_anim_config,
    resolve_upscale_scale,
)


@pytest.fixture(autouse=True)
def _reload_anim_config():
    load_anim_config()
    yield


def test_resolve_scale_videov3_keeps_2():
    assert resolve_upscale_scale("realesrgan", "animevideov3", 2) == 2
    assert resolve_upscale_scale("realesrgan", "animevideov3", 4) == 4


def test_resolve_scale_anime_6b_forces_4():
    assert resolve_upscale_scale("realesrgan", X4_ONLY_UPSCALE_MODEL, 2) == 4
    assert resolve_upscale_scale("realesrgan", X4_ONLY_UPSCALE_MODEL, 3) == 4
    assert resolve_upscale_scale("realesrgan", X4_ONLY_UPSCALE_MODEL, 4) == 4


def test_resolve_scale_span_from_model():
    assert resolve_upscale_scale("span", "span_x2_ch48", 4) == 2
    assert resolve_upscale_scale("span", "span_x4_ch48", 2) == 4


def test_upscale_config_effective_scale():
    up = UpscaleConfig(model=X4_ONLY_UPSCALE_MODEL, scale=2)
    assert up.effective_scale == 4


def test_anim_yaml_has_tile_size():
    cfg = load_anim_config()
    assert hasattr(cfg.upscale, "tile_size")
    assert cfg.upscale.tile_size >= 0

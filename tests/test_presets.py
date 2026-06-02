"""Presets: load, apply, round-trip standard ↔ quality."""

from __future__ import annotations

import pytest

from utils.config import get_config, load_config
from utils.anim_config import get_anim_config, load_anim_config
from utils.presets import (
    apply_preset,
    get_preset,
    list_presets,
    preset_ui_payload,
    snapshot_from_configs,
)


@pytest.fixture(autouse=True)
def _reload_configs():
    load_config()
    load_anim_config()
    yield


def test_list_presets_has_standard_and_quality():
    ids = {p["id"] for p in list_presets()}
    assert ids >= {"standard", "quality"}


def test_preset_ui_payload_quality_sam_and_depthflow():
    p = preset_ui_payload("quality")
    assert p["split"]["use_sam"] is True
    assert p["split"]["confidence_threshold"] == pytest.approx(0.30)
    assert p["anim"]["upscale_model"] == "anime_6B"
    assert p["anim"]["mode"] == "depthflow"
    assert p["anim"]["depthflow_animation"] == "dolly"
    assert p["anim"]["harmonize_mode"] == "blurred_pillarbox"


def test_apply_preset_standard_then_quality_roundtrip():
    apply_preset("standard", persist=False)
    s0 = snapshot_from_configs()
    assert s0["split"]["use_sam"] is False
    assert s0["anim"]["upscale_model"] == "animevideov3"
    assert s0["anim"]["mode"] == "opencv_zoom"

    apply_preset("quality", persist=False)
    s1 = snapshot_from_configs()
    assert s1["split"]["use_sam"] is True
    assert s1["anim"]["upscale_model"] == "anime_6B"
    assert s1["anim"]["mode"] == "depthflow"

    apply_preset("standard", persist=False)
    s2 = snapshot_from_configs()
    assert s2["split"]["use_sam"] is False
    assert s2["anim"]["mode"] == "opencv_zoom"


def test_get_preset_unknown_raises():
    with pytest.raises(KeyError):
        get_preset("nonexistent")

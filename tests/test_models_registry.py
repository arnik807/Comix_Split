"""Tests for utils/models_registry.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.models_registry import (
    check_all_backends,
    check_backend,
    get_variant,
    list_setup_scripts,
    load_registry,
    models_setup_payload,
    resolve_path,
)


def test_load_registry():
    reg = load_registry()
    assert "backends" in reg
    assert "realesrgan" in reg["backends"]
    assert "realcugan" in reg["backends"]
    assert "span" in reg["backends"]


def test_resolve_path_relative():
    p = resolve_path("config/presets.yaml")
    assert p.is_file()


def test_check_backend_structure():
    st = check_backend("realesrgan")
    assert st.backend_id == "realesrgan"
    assert st.exe.name == "realesrgan-ncnn-vulkan.exe"
    assert isinstance(st.installed, bool)


def test_get_variant_realesrgan():
    v = get_variant("realesrgan", "animevideov3")
    assert v["ncnn_name"] == "realesr-animevideov3"


def test_models_setup_payload_shape():
    p = models_setup_payload()
    assert "backends" in p and "scripts" in p
    assert "split_detectors" in p
    assert len(p["split_detectors"]) == 2
    assert len(list_setup_scripts()) >= 2


def test_get_variant_unknown():
    with pytest.raises(KeyError):
        get_variant("realesrgan", "no_such_model")


@pytest.mark.skipif(
    not Path(__file__).resolve().parent.parent.joinpath(
        "models/anim/upscale/realesrgan-ncnn-vulkan.exe"
    ).is_file(),
    reason="realesrgan exe not installed",
)
def test_all_backends_install_check_runs():
    statuses = check_all_backends()
    assert len(statuses) >= 3

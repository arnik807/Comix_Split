"""Tests for utils/ui_state.py."""

from utils import ui_state as us


def test_default_state_has_sections():
    st = us.default_state()
    assert st["version"] == us.UI_STATE_VERSION
    assert "split" in st and "upscale" in st and "video" in st


def test_patch_and_reset_split(tmp_path, monkeypatch):
    path = tmp_path / "ui_state.user.json"
    monkeypatch.setattr(us, "UI_STATE_PATH", path)
    us.patch_ui_state(split={"output_dir": "custom_out"})
    assert us.load_ui_state()["split"]["output_dir"] == "custom_out"
    us.reset_ui_section("split")
    assert us.load_ui_state()["split"]["output_dir"] == us.default_split()["output_dir"]

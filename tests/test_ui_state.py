"""Tests for utils/ui_state.py."""

from utils import ui_state as us


def test_default_state_has_sections():
    st = us.default_state()
    assert st["version"] == us.UI_STATE_VERSION
    assert "split" in st and "upscale" in st and "video" in st and "story2a" in st


def test_patch_and_reset_story2a(tmp_path, monkeypatch):
    path = tmp_path / "ui_state.user.json"
    monkeypatch.setattr(us, "UI_STATE_PATH", path)
    us.patch_ui_state(story2a={"project": "my_proj", "panels_dir": "exam_img\\x"})
    loaded = us.load_ui_state()["story2a"]
    assert loaded["project"] == "my_proj"
    assert loaded["panels_dir"] == "exam_img\\x"
    us.patch_ui_state(story2a={"project": "", "panels_dir": ""})
    loaded2 = us.load_ui_state()["story2a"]
    assert loaded2["project"] == "my_proj"
    assert loaded2["panels_dir"] == "exam_img\\x"
    us.reset_ui_section("story2a")
    assert us.load_ui_state()["story2a"] == us.default_story2a()


def test_patch_and_reset_split(tmp_path, monkeypatch):
    path = tmp_path / "ui_state.user.json"
    monkeypatch.setattr(us, "UI_STATE_PATH", path)
    us.patch_ui_state(split={"output_dir": "custom_out"})
    assert us.load_ui_state()["split"]["output_dir"] == "custom_out"
    us.reset_ui_section("split")
    assert us.load_ui_state()["split"]["output_dir"] == us.default_split()["output_dir"]

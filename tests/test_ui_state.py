"""Tests for utils/ui_state.py."""

from utils import ui_state as us


def test_default_state_has_sections():
    st = us.default_state()
    assert st["version"] == us.UI_STATE_VERSION
    assert "split" in st and "upscale" in st and "video" in st and "story2a" in st


def test_default_story2a_manual_mode():
    assert us.default_story2a()["workflow_mode"] == "manual"


def test_patch_workflow_mode(tmp_path, monkeypatch):
    path = tmp_path / "ui_state.user.json"
    monkeypatch.setattr(us, "UI_STATE_PATH", path)
    us.patch_ui_state(story2a={"workflow_mode": "auto"})
    assert us.load_ui_state()["story2a"]["workflow_mode"] == "auto"
    us.patch_ui_state(story2a={"workflow_mode": "invalid"})
    assert us.load_ui_state()["story2a"]["workflow_mode"] == "auto"


def test_patch_and_reset_story2a(tmp_path, monkeypatch):
    path = tmp_path / "ui_state.user.json"
    monkeypatch.setattr(us, "UI_STATE_PATH", path)
    us.patch_ui_state(story2a={"project": "my_proj", "panels_dir": "exam_img\\x"})
    loaded = us.load_ui_state()["story2a"]
    assert loaded["project"] == "my_proj"
    assert loaded["panels_dir"] == "exam_img\\x"
    us.patch_ui_state(story2a={"project": "", "panels_dir": ""})
    loaded2 = us.load_ui_state()["story2a"]
    assert loaded2["project"] == ""
    assert loaded2["panels_dir"] == ""
    us.reset_ui_section("story2a")
    assert us.load_ui_state()["story2a"] == us.default_story2a()


def test_default_split_snap_defaults():
    s = us.default_split()
    assert s["snap_mode"] == "off"
    assert s["snap_grid_step"] == 8


def test_patch_snap_mode(tmp_path, monkeypatch):
    path = tmp_path / "ui_state.user.json"
    monkeypatch.setattr(us, "UI_STATE_PATH", path)
    us.patch_ui_state(split={"snap_mode": "grid", "snap_grid_step": 3})
    loaded = us.load_ui_state()["split"]
    assert loaded["snap_mode"] == "grid"
    assert loaded["snap_grid_step"] == 3
    us.patch_ui_state(split={"snap_mode": "invalid"})
    assert us.load_ui_state()["split"]["snap_mode"] == "grid"
    us.reset_ui_section("split")
    assert us.load_ui_state()["split"]["snap_mode"] == "off"


def test_patch_and_reset_split(tmp_path, monkeypatch):
    path = tmp_path / "ui_state.user.json"
    monkeypatch.setattr(us, "UI_STATE_PATH", path)
    us.patch_ui_state(split={"output_dir": "custom_out", "source_path": "pages\\a.jpg"})
    loaded = us.load_ui_state()["split"]
    assert loaded["output_dir"] == "custom_out"
    assert loaded["source_path"] == "pages\\a.jpg"
    us.patch_ui_state(split={"source_path": "", "output_dir": ""})
    cleared = us.load_ui_state()["split"]
    assert cleared["source_path"] == ""
    assert cleared["output_dir"] == ""
    us.reset_ui_section("split")
    assert us.load_ui_state()["split"]["output_dir"] == us.default_split()["output_dir"]


def test_patch_and_reset_upscale_panels_dir(tmp_path, monkeypatch):
    path = tmp_path / "ui_state.user.json"
    monkeypatch.setattr(us, "UI_STATE_PATH", path)
    us.patch_ui_state(upscale={"panels_dir": "output\\page1", "output_dir": "out_x"})
    assert us.load_ui_state()["upscale"]["panels_dir"] == "output\\page1"
    us.patch_ui_state(upscale={"panels_dir": "", "output_dir": ""})
    cleared = us.load_ui_state()["upscale"]
    assert cleared["panels_dir"] == ""
    assert cleared["output_dir"] == ""
    us.reset_ui_section("upscale")
    assert us.load_ui_state()["upscale"] == us.default_upscale()


def test_patch_and_reset_video_panels_dir(tmp_path, monkeypatch):
    path = tmp_path / "ui_state.user.json"
    monkeypatch.setattr(us, "UI_STATE_PATH", path)
    us.patch_ui_state(video={"panels_dir": "output\\page1"})
    assert us.load_ui_state()["video"]["panels_dir"] == "output\\page1"
    us.patch_ui_state(video={"panels_dir": ""})
    assert us.load_ui_state()["video"]["panels_dir"] == ""
    us.reset_ui_section("video")
    assert us.load_ui_state()["video"]["panels_dir"] == ""

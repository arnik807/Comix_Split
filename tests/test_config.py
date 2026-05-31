"""Tests for config loading."""

from pathlib import Path

import pytest

from utils.config import AppConfig, load_config


def test_default_config():
    cfg = AppConfig()
    assert cfg.quality_mode == "fast"
    assert not cfg.use_sam


def test_format_panel_name():
    cfg = AppConfig()
    name = cfg.format_panel_name(1, 2, 3)
    assert name == "001_page_002_panel_03.png"


def test_load_project_config():
    root = Path(__file__).resolve().parent.parent
    cfg = load_config(root / "config.yaml")
    assert cfg.language in ("ru", "en")
    assert cfg.max_workers >= 1

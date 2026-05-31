"""Tests for archive/folder loaders."""

from pathlib import Path

import cv2
import numpy as np
import pytest

from utils.io_helpers import load_single_image, read_folder


def _write_png(path, img):
    ok, buf = cv2.imencode(".png", img)
    assert ok
    buf.tofile(str(path))


def test_load_single_image(tmp_path):
    img = np.zeros((100, 80, 3), dtype=np.uint8)
    p = tmp_path / "page.png"
    _write_png(p, img)
    pages = load_single_image(str(p))
    assert len(pages) == 1
    assert pages[0][0] == "page.png"
    assert pages[0][1].shape == (100, 80, 3)


def test_read_folder(tmp_path):
    for i in range(2):
        img = np.zeros((50, 50, 3), dtype=np.uint8)
        _write_png(tmp_path / f"{i:02d}.png", img)
    pages = read_folder(str(tmp_path))
    assert len(pages) == 2


def test_load_source_unknown(tmp_path):
    from utils.io_helpers import load_source

    with pytest.raises(ValueError):
        load_source(str(tmp_path / "file.txt"))

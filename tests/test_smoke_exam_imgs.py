"""Smoke: presets + detection on exam_imgs (Asterix page-0004)."""

from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
EXAM = ROOT / "exam_imgs" / "01_Asterix_the_Gaul_page-0004.jpg"
MODELS_OK = (ROOT / "models" / "yolo_comic_int8.onnx").is_file()

pytestmark = pytest.mark.skipif(
    not MODELS_OK or not EXAM.is_file(),
    reason="models or exam_imgs sample missing",
)


def _load_exam() -> np.ndarray:
    buf = np.fromfile(str(EXAM), dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    assert img is not None
    return img


def _detect(use_sam: bool, conf: float) -> tuple[int, float]:
    from pipeline import analyze_page
    from utils.config import apply_config_to_pipeline, get_config, load_config

    load_config()
    cfg = get_config()
    cfg.quality_mode = "accurate" if use_sam else "fast"
    cfg.confidence_threshold = conf
    apply_config_to_pipeline()

    t0 = time.perf_counter()
    result = analyze_page(
        _load_exam(),
        use_sam=use_sam,
        reading_order=True,
        quiet=True,
    )
    ms = (time.perf_counter() - t0) * 1000
    return len(result.panels), ms


def test_exam_standard_preset_fast():
    from utils.presets import apply_preset

    apply_preset("standard", persist=False)
    n, ms = _detect(use_sam=False, conf=0.35)
    assert n >= 4, f"expected several panels, got {n}"
    assert ms < 120_000, f"standard too slow: {ms:.0f} ms"


def test_exam_quality_preset_sam():
    from utils.presets import apply_preset

    apply_preset("quality", persist=False)
    n, ms = _detect(use_sam=True, conf=0.30)
    assert n >= 4, f"expected several panels, got {n}"
    # SAM on large page — allow minutes on CPU
    assert ms < 600_000, f"quality exceeded 10 min: {ms:.0f} ms"


def test_tooltips_api():
    from fastapi.testclient import TestClient

    from api.server import app
    from utils.ui_tooltips import FIELD_TIPS

    client = TestClient(app)
    r = client.get("/api/tooltips")
    assert r.status_code == 200
    body = r.json()
    assert body["use_sam"] == FIELD_TIPS["use_sam"]
    assert "vid_mode" in body


def test_presets_api_shape():
    from fastapi.testclient import TestClient

    from api.server import app

    client = TestClient(app)
    r = client.get("/api/presets")
    assert r.status_code == 200
    body = r.json()
    assert "presets" in body
    ids = {p["id"] for p in body["presets"]}
    assert "standard" in ids and "quality" in ids

    r2 = client.post(
        "/api/presets/apply",
        json={"name": "quality", "persist": False},
    )
    assert r2.status_code == 200
    assert r2.json()["split"]["use_sam"] is True

    img_rel = "exam_imgs\\01_Asterix_the_Gaul_page-0004.jpg"
    r3 = client.post(
        "/api/process",
        json={
            "image_path": img_rel,
            "use_sam": False,
            "reading_order": True,
            "rtl": False,
            "confidence_threshold": 0.35,
        },
    )
    assert r3.status_code == 200
    panels = r3.json().get("panels") or []
    assert len(panels) >= 4

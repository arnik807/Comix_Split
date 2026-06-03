"""Upscale options API payload."""

from utils.upscale_options import allowed_scales, models_for_backend, upscale_options_payload


def test_upscale_options_has_three_backends():
    data = upscale_options_payload()
    ids = [b["id"] for b in data["backends"]]
    assert ids == ["realesrgan", "realcugan", "span"]


def test_span_model_scales():
    assert allowed_scales("span", "span_x4_ch48") == [4]
    assert allowed_scales("realcugan", "cugan_se") == [1, 2, 3, 4]


def test_models_for_realesrgan():
    models = models_for_backend("realesrgan")
    assert any(m["id"] == "animevideov3" for m in models)

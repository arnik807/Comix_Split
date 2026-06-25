"""Upscale GPU policy (Real-ESRGAN = Vulkan only)."""

from utils.upscale_options import (
    cpu_gpu_allowed,
    normalize_upscale_gpu,
)


def test_realesrgan_forces_gpu_zero():
    assert normalize_upscale_gpu("realesrgan", -1) == 0
    assert normalize_upscale_gpu("realesrgan", 0) == 0


def test_cugan_allows_cpu():
    assert cpu_gpu_allowed("realcugan") is True
    assert normalize_upscale_gpu("realcugan", -1) == -1

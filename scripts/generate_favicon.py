#!/usr/bin/env python3
"""Generate PNG/ICO favicons for frontend/ from the puzzle design."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "frontend"

BG = (24, 24, 27, 255)
PIECE = (240, 192, 64, 255)
PIECE_EDGE = (224, 90, 43, 255)
ACCENT = (74, 222, 128, 255)


def _pt(ox: float, oy: float, s: float, x: float, y: float) -> tuple[float, float]:
    return (ox + x * s, oy + y * s)


def puzzle_polygon(size: int) -> list[tuple[float, float]]:
    """40×40 logical grid → jigsaw with top tab and right socket."""
    margin = size * 0.14
    s = (size - 2 * margin) / 40.0
    ox, oy = margin, margin * 1.05
    p = _pt
    return [
        p(ox, oy, s, 6, 14),
        p(ox, oy, s, 22, 14),
        p(ox, oy, s, 22, 8),
        p(ox, oy, s, 20, 4),
        p(ox, oy, s, 24, 4),
        p(ox, oy, s, 26, 8),
        p(ox, oy, s, 26, 14),
        p(ox, oy, s, 36, 14),
        p(ox, oy, s, 36, 24),
        p(ox, oy, s, 40, 24),
        p(ox, oy, s, 40, 28),
        p(ox, oy, s, 36, 32),
        p(ox, oy, s, 36, 36),
        p(ox, oy, s, 6, 36),
        p(ox, oy, s, 6, 32),
        p(ox, oy, s, 2, 28),
        p(ox, oy, s, 2, 24),
        p(ox, oy, s, 6, 24),
    ]


def accent_polygon(size: int) -> list[tuple[float, float]]:
    margin = size * 0.14
    s = (size - 2 * margin) / 40.0
    ox, oy = margin, margin * 1.05
    p = _pt
    return [
        p(ox, oy, s, 12, 20),
        p(ox, oy, s, 24, 20),
        p(ox, oy, s, 18, 28),
    ]


def render(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    r = max(2, int(size * 0.21))
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=BG)

    poly = puzzle_polygon(size)
    outline = max(1, size // 48) if size >= 32 else 0
    if outline:
        draw.polygon(poly, fill=PIECE, outline=PIECE_EDGE, width=outline)
    else:
        draw.polygon(poly, fill=PIECE)

    draw.polygon(accent_polygon(size), fill=ACCENT)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    master = render(512)

    sizes = {
        "favicon-16x16.png": 16,
        "favicon-32x32.png": 32,
        "apple-touch-icon.png": 180,
        "icon-192.png": 192,
        "icon-512.png": 512,
    }
    for name, px in sizes.items():
        im = master.resize((px, px), Image.Resampling.LANCZOS) if px != 512 else master
        im.save(OUT / name, format="PNG", optimize=True)

    icon16 = master.resize((16, 16), Image.Resampling.LANCZOS)
    icon32 = master.resize((32, 32), Image.Resampling.LANCZOS)
    icon48 = master.resize((48, 48), Image.Resampling.LANCZOS)
    icon16.save(
        OUT / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)],
        append_images=[icon32, icon48],
    )
    print(f"Wrote favicons to {OUT}")


if __name__ == "__main__":
    main()

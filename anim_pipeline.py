"""
anim_pipeline.py — CLI: панели PNG → MP4 + storyboard.

Пример:
    python anim_pipeline.py output/mycomic story_out --mode opencv_zoom
    python anim_pipeline.py panels story_out --no-upscale --mode static
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from anim.animate_depthflow import render_depthflow  # noqa: E402
from anim.animate_opencv import animate_opencv  # noqa: E402
from anim.animate_tpsmm import render_tpsmm  # noqa: E402
from anim.harmonize import harmonize  # noqa: E402
from anim.io_utils import imread, imwrite, list_images  # noqa: E402
from anim.render import concat_videos, frames_to_video  # noqa: E402
from anim.upscale import upscale_image  # noqa: E402
from utils.anim_config import AnimConfig, get_anim_config, load_anim_config  # noqa: E402


@dataclass
class PanelAnimResult:
    source: str
    video_path: str
    timings_ms: dict[str, float] = field(default_factory=dict)


@dataclass
class AnimPipelineResult:
    panels_processed: int
    output_dir: str
    panel_videos: list[str] = field(default_factory=list)
    storyboard_path: str | None = None


def process_panel(
    src: Path,
    work_upscaled: Path,
    work_harmonized: Path,
    work_animated: Path,
    cfg: AnimConfig,
) -> PanelAnimResult:
    timings: dict[str, float] = {}
    t0 = time.perf_counter()

    current = src
    if cfg.upscale.enabled:
        t_up = time.perf_counter()
        up_out = work_upscaled / src.name
        upscale_image(src, up_out, cfg)
        current = up_out
        timings["upscale"] = (time.perf_counter() - t_up) * 1000

    img = imread(current)
    if img is None:
        raise RuntimeError(f"Cannot read image: {current}")

    t_h = time.perf_counter()
    if cfg.harmonize.enabled:
        hm = cfg.harmonize
        img = harmonize(
            img,
            target_width=hm.target_width,
            target_height=hm.target_height,
            mode=hm.mode,
            blur_sigma=hm.blur_sigma,
            vignette_strength=hm.vignette_strength,
        )
    harm_path = work_harmonized / src.name
    imwrite(harm_path, img)
    timings["harmonize"] = (time.perf_counter() - t_h) * 1000

    t_a = time.perf_counter()
    mode = cfg.animation.mode
    video_path = work_animated / f"{src.stem}.mp4"

    if mode == "depthflow":
        render_depthflow(harm_path, video_path, cfg)
    elif mode == "tpsmm":
        render_tpsmm(harm_path, video_path, cfg)
    else:
        frames = animate_opencv(
            img,
            mode=mode,
            duration=cfg.animation.duration,
            fps=cfg.animation.fps,
            intensity=cfg.animation.intensity,
        )
        frames_to_video(frames, video_path, fps=cfg.animation.fps, cfg=cfg)
    timings["animate"] = (time.perf_counter() - t_a) * 1000
    timings["total"] = (time.perf_counter() - t0) * 1000

    return PanelAnimResult(
        source=str(src),
        video_path=str(video_path),
        timings_ms=timings,
    )


def process_folder(input_dir: str | Path, output_dir: str | Path, cfg: AnimConfig | None = None) -> AnimPipelineResult:
    cfg = cfg or get_anim_config()
    inp = Path(input_dir)
    out = Path(output_dir)
    images = list_images(inp)
    if not images:
        raise FileNotFoundError(f"No images in {inp}")

    work_up = out / "upscaled"
    work_hm = out / "harmonized"
    work_an = out / "animated"
    for d in (work_up, work_hm, work_an):
        d.mkdir(parents=True, exist_ok=True)

    panel_videos: list[str] = []
    for i, src in enumerate(images, 1):
        print(f"[anim] {i}/{len(images)} {src.name}", file=sys.stderr)
        result = process_panel(src, work_up, work_hm, work_an, cfg)
        panel_videos.append(result.video_path)
        ms = result.timings_ms
        print(
            f"  upscale={ms.get('upscale', 0):.0f}ms "
            f"harmonize={ms.get('harmonize', 0):.0f}ms "
            f"animate={ms.get('animate', 0):.0f}ms",
            file=sys.stderr,
        )

    storyboard: str | None = None
    if cfg.render.concat_panels and len(panel_videos) > 1:
        storyboard = str(out / cfg.render.storyboard_name)
        concat_videos(panel_videos, storyboard, cfg)
        print(f"[ok] storyboard -> {storyboard}", file=sys.stderr)

    return AnimPipelineResult(
        panels_processed=len(images),
        output_dir=str(out),
        panel_videos=panel_videos,
        storyboard_path=storyboard,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="ComicSplit anim pipeline")
    parser.add_argument("input", help="Folder with panel PNG/JPG")
    parser.add_argument("output", help="Output folder")
    parser.add_argument(
        "--mode",
        choices=["opencv_zoom", "opencv_shake", "depthflow", "static", "tpsmm"],
        help="Animation mode (overrides config)",
    )
    parser.add_argument("--scale", type=int, choices=[2, 4], help="Upscale factor")
    parser.add_argument("--no-upscale", action="store_true")
    parser.add_argument("--no-harmonize", action="store_true")
    parser.add_argument("--no-concat", action="store_true")
    parser.add_argument("--duration", type=float, help="Clip duration (sec)")
    parser.add_argument("--fps", type=int, help="Frames per second")
    parser.add_argument("--config", type=Path, help="Path to config_animate.yaml")
    args = parser.parse_args()

    cfg = load_anim_config(args.config)
    if args.mode:
        cfg.animation.mode = args.mode
    if args.scale:
        cfg.upscale.scale = args.scale
    if args.no_upscale:
        cfg.upscale.enabled = False
    if args.no_harmonize:
        cfg.harmonize.enabled = False
    if args.no_concat:
        cfg.render.concat_panels = False
    if args.duration is not None:
        cfg.animation.duration = args.duration
    if args.fps is not None:
        cfg.animation.fps = args.fps

    result = process_folder(args.input, args.output, cfg)
    print(f"Done: {result.panels_processed} panels -> {result.output_dir}")
    for v in result.panel_videos:
        print(f"  {v}")
    if result.storyboard_path:
        print(f"  storyboard: {result.storyboard_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# main.py — Gradio UI: Split / Upscale / Video
from __future__ import annotations

import os
from pathlib import Path
import sys

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")


def _patch_gradio_client_schema() -> None:
    import gradio_client.utils as gc_utils

    _orig_get_type = gc_utils.get_type

    def get_type(schema):  # type: ignore[no-untyped-def]
        if not isinstance(schema, dict):
            return "Any"
        return _orig_get_type(schema)

    gc_utils.get_type = get_type  # type: ignore[method-assign]

    _orig_json = gc_utils._json_schema_to_python_type

    def _json_schema_to_python_type(schema, defs=None):  # type: ignore[no-untyped-def]
        if isinstance(schema, bool) or not isinstance(schema, dict):
            return "Any"
        return _orig_json(schema, defs)

    gc_utils._json_schema_to_python_type = _json_schema_to_python_type  # type: ignore[method-assign]


_patch_gradio_client_schema()

import gradio as gr

from pipeline import process_page, process_source
from utils.config import get_config, load_config
from utils.anim_config import load_anim_config


def _resolve_path(file_path, folder: str | None) -> str | None:
    if file_path:
        return str(file_path)
    if folder and Path(folder).exists():
        return folder
    return None


def run_comicsplit(
    source_path: str | None,
    output_dir: str,
    use_sam: bool,
    reading_order: bool,
    rtl: bool,
) -> str:
    if not source_path:
        return "Укажите файл или папку (файл, CBZ или путь к папке)."

    load_config()
    out_path = Path(output_dir) if output_dir else Path("output")
    out_path.mkdir(parents=True, exist_ok=True)
    src = Path(source_path)

    is_archive_or_folder = src.is_dir() or src.suffix.lower() in {
        ".cbz",
        ".cbr",
        ".zip",
    }

    if is_archive_or_folder:
        sr = process_source(
            str(src),
            str(out_path),
            use_sam=use_sam,
            reading_order=reading_order,
            rtl=rtl,
        )
        out_root = Path(sr.output_dir)
        images = sorted(out_root.glob("*.png"))
        msg = (
            f"Готово: {sr.pages_processed} стр., {sr.panels_total} панелей → {out_root}"
        )
        files = "\n".join(str(p) for p in images[:50])
        if len(images) > 50:
            files += f"\n... и ещё {len(images) - 50} файлов"
        return f"{msg}\n\nФайлы:\n{files}"

    process_page(
        source_path=str(src),
        output_dir=str(out_path),
        use_sam=use_sam,
        reading_order=reading_order,
        rtl=rtl,
    )
    comic_name = src.stem
    panel_dir = out_path / comic_name
    images = sorted(panel_dir.glob("*.png"))
    files = "\n".join(str(p) for p in images)
    return f"Готово: {len(images)} панелей → {panel_dir}\n\nФайлы:\n{files}"


def run_upscale_only(
    panels_dir: str,
    output_dir: str,
    scale: int,
) -> str:
    if not panels_dir or not Path(panels_dir).is_dir():
        return "Укажите существующую папку с PNG/JPG панелями."

    from anim.io_utils import list_images
    from anim.upscale import upscale_folder

    cfg = load_anim_config()
    cfg.upscale.enabled = True
    cfg.upscale.scale = int(scale)

    out = Path(output_dir or "output_upscaled")
    out.mkdir(parents=True, exist_ok=True)

    try:
        results = upscale_folder(panels_dir, out, cfg)
    except Exception as exc:
        return f"Ошибка апскейла: {exc}"

    if not results:
        return f"В папке нет изображений: {panels_dir}"

    lines = "\n".join(str(p) for p in results[:50])
    extra = ""
    if len(results) > 50:
        extra = f"\n... и ещё {len(results) - 50} файлов"
    return f"Готово: {len(results)} панелей → {out.resolve()}\n\n{lines}{extra}"


def run_video_pipeline(
    panels_dir: str,
    output_dir: str,
    mode: str,
    do_upscale: bool,
    scale: int,
    duration: float,
    fps: int,
    do_concat: bool,
) -> str:
    if not panels_dir or not Path(panels_dir).is_dir():
        return "Укажите существующую папку с PNG/JPG панелями."

    from anim.io_utils import list_images
    from anim_pipeline import process_folder

    images = list_images(panels_dir)
    if not images:
        return f"В папке нет изображений: {panels_dir}"

    cfg = load_anim_config()
    cfg.upscale.enabled = bool(do_upscale)
    cfg.upscale.scale = int(scale)
    cfg.harmonize.enabled = True
    cfg.animation.mode = mode
    cfg.animation.duration = float(duration)
    cfg.animation.fps = int(fps)
    cfg.render.concat_panels = bool(do_concat)

    out = Path(output_dir or "story_out")
    out.mkdir(parents=True, exist_ok=True)

    try:
        result = process_folder(panels_dir, out, cfg)
    except Exception as exc:
        return f"Ошибка видео-пайплайна: {exc}"

    lines = "\n".join(result.panel_videos[:30])
    extra = ""
    if len(result.panel_videos) > 30:
        extra = f"\n... и ещё {len(result.panel_videos) - 30} клипов"
    msg = (
        f"Готово: {result.panels_processed} панелей → {out.resolve()}\n"
        f"Режим: {mode}, апскейл: {'да' if do_upscale else 'нет'} (x{scale})\n\n"
        f"Клипы:\n{lines}{extra}"
    )
    if result.storyboard_path:
        msg += f"\n\nРаскадровка:\n{result.storyboard_path}"
    return msg


def _split_defaults():
    cfg = get_config()
    return cfg.use_sam, cfg.reading_order, cfg.rtl


def _anim_defaults():
    ac = load_anim_config()
    return (
        ac.upscale.scale,
        ac.animation.mode,
        ac.animation.duration,
        ac.animation.fps,
        ac.upscale.enabled,
        ac.render.concat_panels,
    )


use_sam_def, order_def, rtl_def = _split_defaults()
scale_def, mode_def, dur_def, fps_def, upscale_def, concat_def = _anim_defaults()
load_config()

ANIM_MODES = [
    ("Zoom (OpenCV)", "opencv_zoom"),
    ("Shake (OpenCV)", "opencv_shake"),
    ("Статичный кадр", "static"),
    ("Parallax (DepthFlow)", "depthflow"),
]

with gr.Blocks(title="ComicSplit") as demo:
    gr.Markdown(
        "# ComicSplit\n"
        "Раскройка панелей, апскейл и сборка видео-раскадровки."
    )

    with gr.Tabs():
        # ── Split ─────────────────────────────────────────────────────
        with gr.Tab("Split — раскройка"):
            gr.Markdown(
                "Страница (JPG/PNG), CBZ/ZIP или папка со страницами → PNG-панели."
            )
            with gr.Row():
                with gr.Column(scale=1):
                    source = gr.File(
                        label="Источник (JPG/PNG, CBZ, ZIP)",
                        type="filepath",
                    )
                    folder_path = gr.Textbox(
                        label="Или путь к папке со страницами",
                        placeholder="D:\\comics\\pages",
                    )
                    split_output = gr.Textbox(label="Папка вывода", value="output")
                    use_sam = gr.Checkbox(
                        label="MobileSAM (режим Accurate)",
                        value=use_sam_def,
                    )
                    reading_order = gr.Checkbox(
                        label="Сортировать по порядку чтения",
                        value=order_def,
                    )
                    rtl = gr.Checkbox(
                        label="Порядок справа-налево (манга)",
                        value=rtl_def,
                    )
                    split_btn = gr.Button("Запустить раскройку", variant="primary")

                with gr.Column(scale=2):
                    split_status = gr.Textbox(
                        label="Результат",
                        interactive=False,
                        lines=18,
                    )

            split_btn.click(
                fn=lambda f, folder, o, s, ro, rt: run_comicsplit(
                    _resolve_path(f, folder), o, s, ro, rt
                ),
                inputs=[
                    source,
                    folder_path,
                    split_output,
                    use_sam,
                    reading_order,
                    rtl,
                ],
                outputs=split_status,
            )

        # ── Upscale ───────────────────────────────────────────────────
        with gr.Tab("Upscale — апскейл"):
            gr.Markdown(
                "Папка с PNG-панелями (например `output\\имя_комикса`) → апскейл Real-ESRGAN NCNN."
            )
            with gr.Row():
                with gr.Column(scale=1):
                    up_input = gr.Textbox(
                        label="Папка с панелями",
                        placeholder="output\\mycomic",
                    )
                    up_output = gr.Textbox(
                        label="Папка вывода",
                        value="output_upscaled",
                    )
                    up_scale = gr.Radio(
                        label="Масштаб",
                        choices=[2, 4],
                        value=scale_def,
                    )
                    up_btn = gr.Button("Запустить апскейл", variant="primary")

                with gr.Column(scale=2):
                    up_status = gr.Textbox(
                        label="Результат",
                        interactive=False,
                        lines=18,
                    )

            up_btn.click(
                fn=run_upscale_only,
                inputs=[up_input, up_output, up_scale],
                outputs=up_status,
            )

        # ── Video ───────────────────────────────────────────────────
        with gr.Tab("Video — оживление"):
            gr.Markdown(
                "Папка с панелями → 16:9, анимация, MP4 на каждую панель + `storyboard.mp4`."
            )
            with gr.Row():
                with gr.Column(scale=1):
                    vid_input = gr.Textbox(
                        label="Папка с панелями",
                        placeholder="output\\mycomic",
                    )
                    vid_output = gr.Textbox(
                        label="Папка вывода",
                        value="story_out",
                    )
                    vid_mode = gr.Dropdown(
                        label="Режим анимации",
                        choices=ANIM_MODES,
                        value=mode_def,
                    )
                    vid_upscale = gr.Checkbox(
                        label="Апскейл перед видео",
                        value=upscale_def,
                    )
                    vid_scale = gr.Radio(
                        label="Масштаб апскейла",
                        choices=[2, 4],
                        value=scale_def,
                    )
                    vid_duration = gr.Slider(
                        label="Длина клипа (сек)",
                        minimum=1,
                        maximum=10,
                        step=0.5,
                        value=dur_def,
                    )
                    vid_fps = gr.Slider(
                        label="FPS",
                        minimum=12,
                        maximum=30,
                        step=1,
                        value=fps_def,
                    )
                    vid_concat = gr.Checkbox(
                        label="Собрать storyboard.mp4",
                        value=concat_def,
                    )
                    vid_btn = gr.Button("Создать видео", variant="primary")

                with gr.Column(scale=2):
                    vid_status = gr.Textbox(
                        label="Результат",
                        interactive=False,
                        lines=18,
                    )

            vid_btn.click(
                fn=run_video_pipeline,
                inputs=[
                    vid_input,
                    vid_output,
                    vid_mode,
                    vid_upscale,
                    vid_scale,
                    vid_duration,
                    vid_fps,
                    vid_concat,
                ],
                outputs=vid_status,
            )


if __name__ == "__main__":
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        show_error=True,
        show_api=False,
        share=False,
        inbrowser=True,
        quiet=True,
    )

# main.py — Gradio UI for ComicSplit MVP
from __future__ import annotations

import os
from pathlib import Path
import sys

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")


# Обход системного прокси на Windows (иначе Gradio не видит localhost)
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")


def _patch_gradio_client_schema() -> None:
    """gradio_client: JSON Schema с additionalProperties=true/false ломает парсер."""
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


def run_comicsplit(
    source_path: str,
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


def _defaults():
    cfg = get_config()
    return cfg.use_sam, cfg.reading_order, cfg.rtl


use_sam_def, order_def, rtl_def = _defaults()
load_config()

with gr.Blocks(title="ComicSplit") as demo:
    gr.Markdown(
        "# ComicSplit\n"
        "Детекция и вырезка панелей: страница (JPG/PNG), CBZ/ZIP или папка."
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
            output_dir = gr.Textbox(label="Папка вывода", value="output")
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
            run_btn = gr.Button("▶ Запустить", variant="primary")

        with gr.Column(scale=2):
            status = gr.Textbox(
                label="Результат (пути к PNG)",
                interactive=False,
                lines=20,
            )

    def _resolve_path(file_path, folder):
        if file_path:
            return file_path
        if folder and Path(folder).exists():
            return folder
        return None

    run_btn.click(
        fn=lambda f, folder, o, s, ro, rt: run_comicsplit(
            _resolve_path(f, folder), o, s, ro, rt
        ),
        inputs=[source, folder_path, output_dir, use_sam, reading_order, rtl],
        outputs=status,
    )


if __name__ == "__main__":
    # starlette>=1.0 ломает Jinja2; show_api=False обходит баг gradio_client schema
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        show_error=True,
        show_api=False,
        share=False,
        inbrowser=True,
        quiet=True,
    )

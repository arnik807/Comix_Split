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
from utils.anim_config import normalize_upscale_backend
from utils.gradio_upscale_ui import UPSCALE_BACKEND_CHOICES, upscale_controls_update
from utils.upscale_options import apply_upscale_fields
from utils.presets import apply_preset, preset_ui_payload
from utils.ui_tooltips import FIELD_TIPS as TIP
from utils.path_dialog import pick_file, pick_folder


def _resolve_path(file_path, explicit_path: str | None, folder: str | None) -> str | None:
    if file_path:
        return str(file_path)
    if explicit_path:
        return str(explicit_path)
    if folder and Path(folder).exists():
        return folder
    return None


def browse_file_or_archive(current: str | None = None) -> str:
    return pick_file(current) or (current or "")


def browse_driving_video(current: str | None = None) -> str:
    return (
        pick_file(
            current,
            title="Driving video (MP4)",
            filetypes=[
                ("Video", "*.mp4 *.mov *.webm *.avi"),
                ("All files", "*.*"),
            ],
        )
        or (current or "")
    )


def browse_folder(current: str | None = None) -> str:
    return pick_folder(current) or (current or "")


def run_comicsplit(
    source_path: str | None,
    output_dir: str,
    use_sam: bool,
    reading_order: bool,
    rtl: bool,
    panel_detector: str = "comic",
    confidence_threshold: float = 0.35,
    iou_threshold: float = 0.45,
) -> str:
    if not source_path:
        return "Укажите файл или папку (файл, CBZ или путь к папке)."

    from utils.config import apply_config_to_pipeline

    load_config()
    cfg = get_config()
    cfg.quality_mode = "accurate" if use_sam else "fast"
    cfg.reading_order = reading_order
    cfg.reading_direction = "rtl" if rtl else "ltr"
    from utils.panel_detector import normalize_detector

    cfg.confidence_threshold = float(confidence_threshold)
    cfg.iou_threshold = float(iou_threshold)
    cfg.panel_detector = normalize_detector(panel_detector)
    apply_config_to_pipeline()
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
            panel_detector=cfg.panel_detector,
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
        panel_detector=cfg.panel_detector,
    )
    comic_name = src.stem
    panel_dir = out_path / comic_name
    images = sorted(panel_dir.glob("*.png"))
    files = "\n".join(str(p) for p in images)
    return f"Готово: {len(images)} панелей → {panel_dir}\n\nФайлы:\n{files}"


def models_setup_help_md() -> str:
    from utils.models_registry import models_setup_payload

    p = models_setup_payload()
    lines = ["### Детекторы раскройки (YOLO)", ""]
    for d in p.get("split_detectors", []):
        mark = "установлен" if d["installed"] else "**не установлен**"
        lines.append(f"- **{d['label']}** (`{d['id']}`): {mark}")
    lines.extend(["", "### Статус моделей апскейла", ""])
    for b in p["backends"]:
        mark = "установлен" if b["installed"] else "**не установлен**"
        lines.append(f"- **{b['label']}** ({b['id']}): {mark}")
    lines.extend(["", "### Команды (из корня репозитория)", ""])
    for s in p["scripts"]:
        lines.append(f"**{s['label']}**  \n`{s['command']}`")
    lines.append(
        "\nПосле загрузки: `python scripts\\verify_upscale_backends.py`"
    )
    return "\n".join(lines)


def run_upscale_only(
    panels_dir: str,
    output_dir: str,
    scale: int,
    upscale_backend: str = "realesrgan",
    upscale_model: str = "animevideov3",
    gpu_id: int = 0,
    cugan_noise: int = -1,
    cugan_syncgap: int = 3,
) -> str:
    if not panels_dir or not Path(panels_dir).is_dir():
        return "Укажите существующую папку с PNG/JPG панелями."

    from anim.io_utils import list_images
    from anim.upscale import upscale_folder

    cfg = load_anim_config()
    cfg.upscale.enabled = True
    apply_upscale_fields(
        cfg.upscale,
        backend=upscale_backend,
        model=upscale_model,
        scale=int(scale),
        gpu_id=int(gpu_id),
        cugan_noise=int(cugan_noise),
        cugan_syncgap=int(cugan_syncgap),
    )

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
    upscale_backend: str = "realesrgan",
    upscale_model: str = "animevideov3",
    gpu_id: int = 0,
    cugan_noise: int = -1,
    cugan_syncgap: int = 3,
    harmonize_mode: str = "auto",
    harmonize_blur_sigma: int = 60,
    harmonize_vignette: float = 0.7,
    intensity: float = 0.3,
    depthflow_animation: str = "zoom",
    tpsmm_driving_video: str = "",
    tpsmm_mode: str = "relative",
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
    apply_upscale_fields(
        cfg.upscale,
        backend=upscale_backend,
        model=upscale_model,
        scale=int(scale),
        gpu_id=int(gpu_id),
        cugan_noise=int(cugan_noise),
        cugan_syncgap=int(cugan_syncgap),
    )
    cfg.harmonize.enabled = True
    cfg.harmonize.mode = str(harmonize_mode)
    cfg.harmonize.blur_sigma = int(harmonize_blur_sigma)
    cfg.harmonize.vignette_strength = float(harmonize_vignette)
    cfg.animation.mode = mode
    cfg.animation.duration = float(duration)
    cfg.animation.fps = int(fps)
    cfg.animation.intensity = float(intensity)
    cfg.animation.depthflow_animation = str(depthflow_animation)
    cfg.animation.tpsmm_driving_video = str(tpsmm_driving_video or "")
    cfg.animation.tpsmm_mode = str(tpsmm_mode or "relative")
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


load_config()


def _split_defaults():
    cfg = get_config()
    return (
        cfg.panel_detector,
        cfg.use_sam,
        cfg.reading_order,
        cfg.reading_direction == "rtl",
        cfg.confidence_threshold,
        cfg.iou_threshold,
    )


def _anim_defaults():
    ac = load_anim_config()
    return (
        ac.upscale.normalized_backend,
        ac.upscale.scale,
        ac.upscale.model,
        ac.upscale.cugan_noise,
        ac.upscale.cugan_syncgap,
        ac.upscale.gpu_id,
        ac.harmonize.mode,
        ac.harmonize.blur_sigma,
        ac.harmonize.vignette_strength,
        ac.animation.mode,
        ac.upscale.enabled,
        ac.animation.duration,
        ac.animation.fps,
        ac.animation.intensity,
        ac.animation.depthflow_animation,
        ac.animation.tpsmm_driving_video,
        ac.animation.tpsmm_mode,
        ac.render.concat_panels,
    )


(
    panel_detector_def,
    use_sam_def,
    order_def,
    rtl_def,
    conf_def,
    iou_def,
) = _split_defaults()

PANEL_DETECTORS = [
    ("Западный комикс", "comic"),
    ("Манга (Manga109)", "manga"),
]
(
    up_backend_def,
    scale_def,
    up_model_def,
    cugan_noise_def,
    cugan_syncgap_def,
    gpu_def,
    harm_mode_def,
    harm_blur_def,
    harm_vig_def,
    mode_def,
    upscale_def,
    dur_def,
    fps_def,
    intensity_def,
    df_anim_def,
    tpsmm_driving_def,
    tpsmm_mode_def,
    concat_def,
) = _anim_defaults()

ANIM_MODES = [
    ("Zoom (OpenCV)", "opencv_zoom"),
    ("Shake (OpenCV)", "opencv_shake"),
    ("Статичный кадр", "static"),
    ("Parallax (DepthFlow)", "depthflow"),
    ("TPSMM (медленно, driving MP4)", "tpsmm"),
]
UPSCALE_MODELS = [
    ("Быстрый (animevideov3)", "animevideov3"),
    ("Точный (x4plus-anime, только ×4)", "anime_6B"),
]
HARMONIZE_MODES = [
    "auto",
    "blurred_pillarbox",
    "dominant_color",
    "smart_crop",
]
DEPTHFLOW_PRESETS = [("Zoom", "zoom"), ("Dolly", "dolly")]


def _apply_preset_to_gradio(name: str, persist: bool):
    p = apply_preset(name, persist=persist)
    s, a = p["split"], p["anim"]
    is_quality = name == "quality"
    backend = normalize_upscale_backend(a.get("upscale_backend", "realesrgan"))
    up_ui = upscale_controls_update(
        backend,
        a["upscale_model"],
        a["upscale_scale"],
        a.get("cugan_noise", -1),
        a.get("cugan_syncgap", 3),
    )
    mode_choices = (
        ANIM_MODES
        if is_quality
        else [x for x in ANIM_MODES if x[1] not in ("depthflow", "tpsmm")]
    )
    mode_badge_md = (
        "**MODE: QUALITY** — точный режим, доступны расширенные настройки."
        if is_quality
        else "**MODE: STANDARD** — быстрый режим, минимум настроек."
    )
    return (
        gr.update(value=s["use_sam"], visible=is_quality),
        gr.update(value=s["reading_order"]),
        gr.update(value=s["rtl"]),
        gr.update(value=s["confidence_threshold"]),
        gr.update(value=s["iou_threshold"]),
        gr.update(value=backend, visible=is_quality),
        *up_ui,
        gr.update(visible=is_quality),
        gr.update(value=backend, visible=is_quality),
        *up_ui,
        gr.update(value=a["gpu_id"], visible=is_quality),
        gr.update(value=a["harmonize_mode"], visible=is_quality),
        gr.update(value=a["harmonize_blur_sigma"], visible=is_quality),
        gr.update(value=a["harmonize_vignette"], visible=is_quality),
        gr.update(value=a["mode"], choices=mode_choices),
        gr.update(value=a["upscale_enabled"]),
        gr.update(value=a["duration"]),
        gr.update(value=a["fps"]),
        gr.update(value=a["intensity"], visible=is_quality),
        gr.update(value=a["depthflow_animation"], visible=is_quality),
        gr.update(value=a["do_concat"]),
        gr.update(visible=is_quality),  # yolo thresholds accordion
        gr.update(value=mode_badge_md),
        f"Пресет «{p['label']}» применён" + (" и сохранён в YAML" if persist else ""),
    )


with gr.Blocks(title="ComicSplit") as demo:
    gr.Markdown(
        "# ComicSplit\n"
        "Раскройка панелей, апскейл и сборка видео-раскадровки."
    )

    with gr.Row():
        mode_badge = gr.Markdown("**MODE: STANDARD** — быстрый режим, минимум настроек.")
        preset_std_btn = gr.Button("Стандарт", size="sm")
        preset_q_btn = gr.Button("Качество", size="sm", variant="primary")
        preset_persist = gr.Checkbox(
            label="Сохранить в config.yaml",
            value=False,
            info=TIP["preset_persist"],
        )
        preset_status = gr.Markdown("")
    with gr.Accordion("Что делают пресеты «Стандарт» и «Качество»?", open=False):
        gr.Markdown(
            f"**Стандарт** — {TIP['preset_standard']}\n\n"
            f"**Качество** — {TIP['preset_quality']}"
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
                    gr.Markdown(f"<sub>ⓘ {TIP['split_source']}</sub>")
                    source_path_box = gr.Textbox(
                        label="Или путь к файлу/архиву",
                        placeholder="exam_imgs\\01_Asterix_the_Gaul_page-0004.jpg",
                    )
                    source_browse_btn = gr.Button("Обзор файла/архива", size="sm")
                    folder_path = gr.Textbox(
                        label="Или путь к папке со страницами",
                        placeholder="D:\\comics\\pages",
                        info=TIP["split_folder"],
                    )
                    folder_browse_btn = gr.Button("Обзор папки страниц", size="sm")
                    split_output = gr.Textbox(
                        label="Папка вывода",
                        value="output",
                        info=TIP["split_output"],
                    )
                    split_out_browse_btn = gr.Button("Обзор папки вывода", size="sm")
                    panel_detector = gr.Dropdown(
                        label="Детектор панелей",
                        choices=PANEL_DETECTORS,
                        value=panel_detector_def,
                        info=TIP["panel_detector"],
                    )
                    panel_detector_hint = gr.Markdown("")
                    use_sam = gr.Checkbox(
                        label="Точные контуры (SAM)",
                        value=use_sam_def,
                        info=TIP["use_sam"],
                        visible=False,
                    )
                    sam_note = gr.Markdown(
                        "<sub>На `exam_imgs` без SAM ~10–15 с; с SAM часто 1–3 мин. "
                        "Контуры на холсте — только в веб-редакторе (:8000), режим «Полигон».</sub>",
                        visible=False,
                    )
                    reading_order = gr.Checkbox(
                        label="Сортировать по порядку чтения",
                        value=order_def,
                        info=TIP["reading_order"],
                    )
                    rtl = gr.Checkbox(
                        label="Порядок справа-налево (манга)",
                        value=rtl_def,
                        info=TIP["rtl"],
                    )
                    with gr.Accordion("Пороги YOLO (расширенные)", open=False, visible=False) as yolo_adv:
                        conf_thr = gr.Slider(
                            label="Confidence",
                            minimum=0.1,
                            maximum=0.9,
                            step=0.05,
                            value=conf_def,
                            info=TIP["conf_thr"],
                        )
                        iou_thr = gr.Slider(
                            label="IoU NMS",
                            minimum=0.1,
                            maximum=0.9,
                            step=0.05,
                            value=iou_def,
                            info=TIP["iou_thr"],
                        )
                    split_btn = gr.Button("Запустить раскройку", variant="primary")

                with gr.Column(scale=2):
                    split_status = gr.Textbox(
                        label="Результат",
                        interactive=False,
                        lines=18,
                    )

            def _panel_detector_hint(det: str) -> str:
                from utils.panel_detector import DETECTORS, ensure_detector_installed

                spec = DETECTORS.get(det, DETECTORS["comic"])
                try:
                    ensure_detector_installed(spec)
                    return f"✓ {spec.label} — модель на диске."
                except FileNotFoundError as exc:
                    return str(exc).replace("\n", "  \n")

            panel_detector.change(
                fn=_panel_detector_hint,
                inputs=panel_detector,
                outputs=panel_detector_hint,
            )
            demo.load(
                fn=_panel_detector_hint,
                inputs=panel_detector,
                outputs=panel_detector_hint,
            )

            split_btn.click(
                fn=lambda f, srcp, folder, o, det, s, ro, rt, c, i: run_comicsplit(
                    _resolve_path(f, srcp, folder), o, s, ro, rt, det, c, i
                ),
                inputs=[
                    source,
                    source_path_box,
                    folder_path,
                    split_output,
                    panel_detector,
                    use_sam,
                    reading_order,
                    rtl,
                    conf_thr,
                    iou_thr,
                ],
                outputs=split_status,
            )
            source_browse_btn.click(fn=browse_file_or_archive, inputs=source_path_box, outputs=source_path_box)
            folder_browse_btn.click(fn=browse_folder, inputs=folder_path, outputs=folder_path)
            split_out_browse_btn.click(fn=browse_folder, inputs=split_output, outputs=split_output)

        # ── Upscale ───────────────────────────────────────────────────
        with gr.Tab("Upscale — апскейл"):
            gr.Markdown(
                "Папка с PNG-панелями → апскейл (Real-ESRGAN / Real-CUGAN / SPAN, Vulkan)."
            )
            with gr.Row():
                with gr.Column(scale=1):
                    up_input = gr.Textbox(
                        label="Папка с панелями",
                        placeholder="output\\mycomic",
                        info=TIP["up_panels"],
                    )
                    up_input_browse = gr.Button("Обзор папки панелей", size="sm")
                    up_output = gr.Textbox(
                        label="Папка вывода",
                        value="output_upscaled",
                        info=TIP["up_output"],
                    )
                    up_output_browse = gr.Button("Обзор папки вывода", size="sm")
                    up_scale = gr.Radio(
                        label="Масштаб",
                        choices=[2, 4],
                        value=scale_def,
                        info=TIP["up_scale"],
                    )
                    up_backend = gr.Dropdown(
                        label="Backend апскейла",
                        choices=UPSCALE_BACKEND_CHOICES,
                        value=up_backend_def,
                        info=TIP["up_backend"],
                        visible=False,
                    )
                    up_install_md = gr.Markdown("", visible=False)
                    with gr.Accordion("Скачать / проверить модели", open=False, visible=False) as up_models_acc:
                        up_models_setup_md = gr.Markdown(models_setup_help_md())
                        up_models_refresh_btn = gr.Button("Обновить статус", size="sm")
                    up_model = gr.Dropdown(
                        label="Модель",
                        choices=UPSCALE_MODELS,
                        value=up_model_def,
                        info=TIP["up_model"],
                        visible=False,
                    )
                    up_cugan_noise = gr.Slider(
                        label="CUGAN denoise",
                        minimum=-1,
                        maximum=3,
                        step=1,
                        value=cugan_noise_def,
                        info=TIP["up_cugan_noise"],
                        visible=False,
                    )
                    up_cugan_syncgap = gr.Radio(
                        label="CUGAN syncgap",
                        choices=[0, 1, 2, 3],
                        value=cugan_syncgap_def,
                        info=TIP["up_cugan_syncgap"],
                        visible=False,
                    )
                    up_gpu = gr.Radio(
                        label="GPU (Vulkan)",
                        choices=[("0 — видеокарта", 0), ("−1 — CPU", -1)],
                        value=gpu_def,
                        info=TIP["up_gpu"],
                        visible=False,
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
                inputs=[
                    up_input,
                    up_output,
                    up_scale,
                    up_backend,
                    up_model,
                    up_gpu,
                    up_cugan_noise,
                    up_cugan_syncgap,
                ],
                outputs=up_status,
            )
            up_input_browse.click(fn=browse_folder, inputs=up_input, outputs=up_input)
            up_output_browse.click(fn=browse_folder, inputs=up_output, outputs=up_output)
            _upscale_ui_inputs = [
                up_backend,
                up_model,
                up_scale,
                up_cugan_noise,
                up_cugan_syncgap,
            ]
            _upscale_ui_outputs = [
                up_model,
                up_scale,
                up_cugan_noise,
                up_cugan_syncgap,
                up_install_md,
            ]
            up_backend.change(
                fn=upscale_controls_update,
                inputs=_upscale_ui_inputs,
                outputs=_upscale_ui_outputs,
            )
            up_model.change(
                fn=upscale_controls_update,
                inputs=_upscale_ui_inputs,
                outputs=_upscale_ui_outputs,
            )
            up_models_refresh_btn.click(
                fn=models_setup_help_md,
                outputs=up_models_setup_md,
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
                        info=TIP["vid_panels"],
                    )
                    vid_input_browse = gr.Button("Обзор папки панелей", size="sm")
                    vid_output = gr.Textbox(
                        label="Папка вывода",
                        value="story_out",
                        info=TIP["vid_output"],
                    )
                    vid_output_browse = gr.Button("Обзор папки вывода", size="sm")
                    vid_mode = gr.Dropdown(
                        label="Режим анимации",
                        choices=ANIM_MODES,
                        value=mode_def,
                        info=TIP["vid_mode"],
                    )
                    vid_upscale = gr.Checkbox(
                        label="Апскейл перед видео",
                        value=upscale_def,
                        info=TIP["vid_upscale"],
                    )
                    vid_scale = gr.Radio(
                        label="Масштаб апскейла",
                        choices=[2, 4],
                        value=scale_def,
                        info=TIP["vid_scale"],
                    )
                    vid_backend = gr.Dropdown(
                        label="Backend апскейла",
                        choices=UPSCALE_BACKEND_CHOICES,
                        value=up_backend_def,
                        info=TIP["up_backend"],
                        visible=False,
                    )
                    vid_install_md = gr.Markdown("", visible=False)
                    vid_model = gr.Dropdown(
                        label="Модель апскейла",
                        choices=UPSCALE_MODELS,
                        value=up_model_def,
                        info=TIP["vid_model"],
                        visible=False,
                    )
                    vid_cugan_noise = gr.Slider(
                        label="CUGAN denoise",
                        minimum=-1,
                        maximum=3,
                        step=1,
                        value=cugan_noise_def,
                        info=TIP["up_cugan_noise"],
                        visible=False,
                    )
                    vid_cugan_syncgap = gr.Radio(
                        label="CUGAN syncgap",
                        choices=[0, 1, 2, 3],
                        value=cugan_syncgap_def,
                        info=TIP["up_cugan_syncgap"],
                        visible=False,
                    )
                    vid_gpu = gr.Radio(
                        label="GPU (Vulkan)",
                        choices=[("0 — видеокарта", 0), ("−1 — CPU", -1)],
                        value=gpu_def,
                        info=TIP["vid_gpu"],
                        visible=False,
                    )
                    vid_harm_mode = gr.Dropdown(
                        label="Фон 16:9 (harmonize)",
                        choices=[
                            ("auto", "auto"),
                            ("Размытые поля", "blurred_pillarbox"),
                            ("Доминантный цвет", "dominant_color"),
                            ("Умный кроп", "smart_crop"),
                        ],
                        value=harm_mode_def,
                        info=TIP["vid_harm_mode"],
                        visible=False,
                    )
                    vid_harm_blur = gr.Slider(
                        label="Blur sigma (pillarbox)",
                        minimum=10,
                        maximum=120,
                        step=5,
                        value=harm_blur_def,
                        info=TIP["vid_harm_blur"],
                        visible=False,
                    )
                    vid_harm_vig = gr.Slider(
                        label="Vignette",
                        minimum=0.0,
                        maximum=1.0,
                        step=0.05,
                        value=harm_vig_def,
                        info=TIP["vid_harm_vig"],
                        visible=False,
                    )
                    vid_intensity = gr.Slider(
                        label="Интенсивность анимации",
                        minimum=0.1,
                        maximum=1.0,
                        step=0.05,
                        value=intensity_def,
                        info=TIP["vid_intensity"],
                        visible=False,
                    )
                    vid_df_anim = gr.Dropdown(
                        label="DepthFlow preset",
                        choices=DEPTHFLOW_PRESETS,
                        value=df_anim_def,
                        info=TIP["vid_df_anim"],
                        visible=False,
                    )
                    vid_tpsmm_driving = gr.Textbox(
                        label="TPSMM driving video (MP4)",
                        value=tpsmm_driving_def,
                        info=TIP["vid_tpsmm_driving"],
                        visible=False,
                    )
                    vid_tpsmm_browse_btn = gr.Button(
                        "Обзор MP4…", size="sm", visible=False
                    )
                    vid_tpsmm_hint = gr.Markdown(
                        "⚠ TPSMM на CPU: ориентир **~1.5 с/кадр** (72 кадра ≈ 2 мин на панель).",
                        visible=False,
                    )
                    vid_duration = gr.Slider(
                        label="Длина клипа (сек)",
                        minimum=1,
                        maximum=10,
                        step=0.5,
                        value=dur_def,
                        info=TIP["vid_duration"],
                    )
                    vid_fps = gr.Slider(
                        label="FPS",
                        minimum=12,
                        maximum=30,
                        step=1,
                        value=fps_def,
                        info=TIP["vid_fps"],
                    )
                    vid_concat = gr.Checkbox(
                        label="Собрать storyboard.mp4",
                        value=concat_def,
                        info=TIP["vid_concat"],
                    )
                    vid_btn = gr.Button("Создать видео", variant="primary")

                with gr.Column(scale=2):
                    vid_status = gr.Textbox(
                        label="Результат",
                        interactive=False,
                        lines=18,
                    )

            def _vid_mode_ui(mode: str):
                is_tps = mode == "tpsmm"
                return (
                    gr.update(visible=mode == "depthflow"),
                    gr.update(visible=is_tps),
                    gr.update(visible=is_tps),
                    gr.update(visible=is_tps),
                )

            vid_mode.change(
                fn=_vid_mode_ui,
                inputs=vid_mode,
                outputs=[
                    vid_df_anim,
                    vid_tpsmm_driving,
                    vid_tpsmm_hint,
                    vid_tpsmm_browse_btn,
                ],
            )
            demo.load(
                fn=_vid_mode_ui,
                inputs=vid_mode,
                outputs=[
                    vid_df_anim,
                    vid_tpsmm_driving,
                    vid_tpsmm_hint,
                    vid_tpsmm_browse_btn,
                ],
            )
            vid_tpsmm_browse_btn.click(
                fn=browse_driving_video,
                inputs=vid_tpsmm_driving,
                outputs=vid_tpsmm_driving,
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
                    vid_backend,
                    vid_model,
                    vid_gpu,
                    vid_cugan_noise,
                    vid_cugan_syncgap,
                    vid_harm_mode,
                    vid_harm_blur,
                    vid_harm_vig,
                    vid_intensity,
                    vid_df_anim,
                    vid_tpsmm_driving,
                ],
                outputs=vid_status,
            )
            vid_input_browse.click(fn=browse_folder, inputs=vid_input, outputs=vid_input)
            vid_output_browse.click(fn=browse_folder, inputs=vid_output, outputs=vid_output)
            _vid_upscale_ui_inputs = [
                vid_backend,
                vid_model,
                vid_scale,
                vid_cugan_noise,
                vid_cugan_syncgap,
            ]
            _vid_upscale_ui_outputs = [
                vid_model,
                vid_scale,
                vid_cugan_noise,
                vid_cugan_syncgap,
                vid_install_md,
            ]
            vid_backend.change(
                fn=upscale_controls_update,
                inputs=_vid_upscale_ui_inputs,
                outputs=_vid_upscale_ui_outputs,
            )
            vid_model.change(
                fn=upscale_controls_update,
                inputs=_vid_upscale_ui_inputs,
                outputs=_vid_upscale_ui_outputs,
            )

    _preset_outputs = [
        use_sam,
        reading_order,
        rtl,
        conf_thr,
        iou_thr,
        up_backend,
        up_model,
        up_scale,
        up_cugan_noise,
        up_cugan_syncgap,
        up_install_md,
        up_models_acc,
        vid_backend,
        vid_model,
        vid_scale,
        vid_cugan_noise,
        vid_cugan_syncgap,
        vid_install_md,
        up_gpu,
        vid_harm_mode,
        vid_harm_blur,
        vid_harm_vig,
        vid_mode,
        vid_upscale,
        vid_duration,
        vid_fps,
        vid_intensity,
        vid_df_anim,
        vid_concat,
        yolo_adv,
        mode_badge,
        preset_status,
    ]

    preset_std_btn.click(
        fn=lambda p: _apply_preset_to_gradio("standard", p),
        inputs=preset_persist,
        outputs=_preset_outputs,
    )
    preset_q_btn.click(
        fn=lambda p: _apply_preset_to_gradio("quality", p),
        inputs=preset_persist,
        outputs=_preset_outputs,
    )


if __name__ == "__main__":
    _favicon = Path(__file__).resolve().parent / "frontend" / "favicon.ico"
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        show_error=True,
        show_api=False,
        share=False,
        inbrowser=True,
        quiet=True,
        favicon_path=str(_favicon) if _favicon.is_file() else None,
    )

"""Split panel detectors: comic vs manga YOLO ONNX paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT_DIR / "models"

VALID_DETECTORS = ("comic", "manga")


@dataclass(frozen=True)
class DetectorSpec:
    id: str
    label: str
    onnx_path: Path
    num_classes: int
    panel_class_id: int
    download_hint: str


DETECTORS: dict[str, DetectorSpec] = {
    "comic": DetectorSpec(
        id="comic",
        label="Западный комикс (mosesb)",
        onnx_path=MODELS_DIR / "yolo_comic_int8.onnx",
        num_classes=1,
        panel_class_id=0,
        download_hint="scripts\\split_models_craft_scripts\\download_models.ps1 + quantize_models.py",
    ),
    "manga": DetectorSpec(
        id="manga",
        label="Манга (YOLO26n, Manga109)",
        onnx_path=MODELS_DIR / "yolo_manga_int8.onnx",
        num_classes=2,
        panel_class_id=0,
        download_hint="scripts\\export_manga_yolo.ps1",
    ),
}


def normalize_detector(raw: str | None) -> str:
    d = str(raw or "comic").strip().lower()
    return d if d in DETECTORS else "comic"


def get_detector(detector_id: str | None = None) -> DetectorSpec:
    if detector_id is None:
        from utils.config import get_config

        detector_id = get_config().panel_detector
    return DETECTORS[normalize_detector(detector_id)]


def ensure_detector_installed(spec: DetectorSpec | None = None) -> DetectorSpec:
    spec = spec or get_detector()
    if not spec.onnx_path.is_file():
        raise FileNotFoundError(
            f"Модель детектора «{spec.label}» не найдена: {spec.onnx_path}\n"
            f"Установка: {spec.download_hint}"
        )
    return spec


def split_options_payload() -> dict:
    from utils.config import get_config

    cfg = get_config()
    items = []
    for did in VALID_DETECTORS:
        spec = DETECTORS[did]
        items.append(
            {
                "id": spec.id,
                "label": spec.label,
                "installed": spec.onnx_path.is_file(),
                "num_classes": spec.num_classes,
                "panel_class_id": spec.panel_class_id,
                "download_hint": spec.download_hint
                if not spec.onnx_path.is_file()
                else "",
            }
        )
    return {
        "panel_detector": normalize_detector(cfg.panel_detector),
        "detectors": items,
    }

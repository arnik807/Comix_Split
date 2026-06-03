"""Load config/models_registry.yaml and check model artifacts on disk."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY_PATH = ROOT_DIR / "config" / "models_registry.yaml"


@dataclass
class BackendStatus:
    backend_id: str
    label: str
    installed: bool
    exe: Path
    missing: list[str]
    download_script: str


def _registry_path(path: Path | None = None) -> Path:
    return path or DEFAULT_REGISTRY_PATH


def load_registry(path: Path | None = None) -> dict[str, Any]:
    p = _registry_path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Models registry not found: {p}")
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def resolve_path(rel: str) -> Path:
    return (ROOT_DIR / rel.replace("/", "\\")).resolve()


def backend_installed(backend: dict[str, Any]) -> tuple[bool, list[str]]:
    missing: list[str] = []
    exe = resolve_path(str(backend["exe"]))
    if not exe.is_file():
        missing.append(str(exe.relative_to(ROOT_DIR)))
    models_dir = backend.get("models_dir")
    if models_dir:
        mdir = resolve_path(str(models_dir))
        if not mdir.is_dir():
            missing.append(str(mdir.relative_to(ROOT_DIR)))
        elif not any(mdir.glob("*.bin")) and not any(mdir.glob("*.param")):
            missing.append(f"{mdir.relative_to(ROOT_DIR)} (no .bin/.param)")
    return len(missing) == 0, missing


def check_backend(backend_id: str, registry: dict[str, Any] | None = None) -> BackendStatus:
    reg = registry or load_registry()
    backends = reg.get("backends") or {}
    if backend_id not in backends:
        raise KeyError(f"Unknown backend: {backend_id}")
    b = backends[backend_id]
    ok, missing = backend_installed(b)
    return BackendStatus(
        backend_id=backend_id,
        label=str(b.get("label", backend_id)),
        installed=ok,
        exe=resolve_path(str(b["exe"])),
        missing=missing,
        download_script=str(b.get("download_script", "")),
    )


def check_all_backends(registry: dict[str, Any] | None = None) -> list[BackendStatus]:
    reg = registry or load_registry()
    return [check_backend(bid, reg) for bid in (reg.get("backends") or {})]


def check_pip_package(import_line: str) -> bool:
    try:
        subprocess.run(
            [sys.executable, "-c", import_line],
            capture_output=True,
            timeout=30,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def onnx_paths_ok(entry: dict[str, Any]) -> tuple[bool, list[str]]:
    missing: list[str] = []
    if "path" in entry:
        paths = [entry["path"]]
    else:
        paths = entry.get("paths") or []
    for rel in paths:
        p = resolve_path(str(rel))
        if not p.is_file():
            missing.append(str(p.relative_to(ROOT_DIR)))
    return len(missing) == 0, missing


def check_split_detectors() -> list[dict[str, Any]]:
    from utils.panel_detector import DETECTORS

    items = []
    for spec in DETECTORS.values():
        ok = spec.onnx_path.is_file()
        items.append(
            {
                "id": spec.id,
                "label": spec.label,
                "installed": ok,
                "path": str(spec.onnx_path.relative_to(ROOT_DIR)),
                "install_hint": ""
                if ok
                else f"Запустите: {spec.download_hint}",
            }
        )
    return items


def list_setup_scripts() -> list[dict[str, str]]:
    """Download/setup commands for UI (B0.3)."""
    return [
        {
            "id": "animate_core",
            "label": "Split + Real-ESRGAN + ONNX anim",
            "script": "scripts/download_animate_models.ps1",
            "command": "powershell -ExecutionPolicy Bypass -File scripts\\download_animate_models.ps1",
        },
        {
            "id": "upscale_extra",
            "label": "Real-CUGAN + SPAN (доп. апскейл)",
            "script": "scripts/download_upscale_backends.ps1",
            "command": "powershell -ExecutionPolicy Bypass -File scripts\\download_upscale_backends.ps1",
        },
        {
            "id": "verify_upscale",
            "label": "Проверка всех апскейлеров",
            "script": "scripts/verify_upscale_backends.py",
            "command": "python scripts\\verify_upscale_backends.py",
        },
        {
            "id": "manga_yolo",
            "label": "Manga YOLO26n",
            "script": "scripts/export_manga_yolo.ps1",
            "command": "powershell -ExecutionPolicy Bypass -File scripts\\export_manga_yolo.ps1",
        },
    ]


def models_setup_payload() -> dict[str, Any]:
    backends = [
        {
            "id": st.backend_id,
            "label": st.label,
            "installed": st.installed,
            "missing": st.missing,
            "download_script": st.download_script,
            "install_hint": format_install_hint(st) if not st.installed else "",
        }
        for st in check_all_backends()
    ]
    return {
        "backends": backends,
        "split_detectors": check_split_detectors(),
        "scripts": list_setup_scripts(),
    }


def format_install_hint(status: BackendStatus) -> str:
    if status.installed:
        return f"{status.label}: OK"
    script = status.download_script or "scripts/download_animate_models.ps1"
    lines = [f"{status.label}: NOT READY", f"  Run: powershell -File {script}"]
    for m in status.missing:
        lines.append(f"  Missing: {m}")
    return "\n".join(lines)


def get_variant(
    backend_id: str,
    variant_id: str,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reg = registry or load_registry()
    backends = reg.get("backends") or {}
    b = backends[backend_id]
    for v in b.get("variants") or []:
        if v.get("id") == variant_id:
            return dict(v)
    raise KeyError(f"Unknown variant {backend_id}/{variant_id}")

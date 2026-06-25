"""
Smoke-test SiliconFlow API key before Stage 2a cloud OCR integration.

Usage (from repo root):
  1. copy .env.example .env
  2. Open .env and paste key: SILICONFLOW_API_KEY=sk-...
  3. python scripts/test_siliconflow_api.py
  python scripts/test_siliconflow_api.py --vision debug/stage_2a/americ_v2/003_p003_panel/crop_00_raw.jpg
  python scripts/test_siliconflow_api.py --list-models
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_BASE_URL = "https://api.siliconflow.com/v1"
DEFAULT_VLM = "Qwen/Qwen3-VL-8B-Instruct"

# Candidates for comic bubble OCR (Visual models on SiliconFlow; verify with --list-models)
VLM_CANDIDATES = [
    "Qwen/Qwen3-VL-8B-Instruct",
    "Pro/Qwen/Qwen2.5-VL-7B-Instruct",
    "deepseek-ai/deepseek-vl2",
    "Qwen/Qwen2-VL-7B-Instruct",
]

BUBBLE_OCR_PROMPT = (
    "Extract ALL text visible in this comic speech bubble. "
    "Return only the text, nothing else. Preserve line breaks. "
    "Language may be Russian, English, or mixed."
)


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if not val:
            continue  # do not wipe $env: vars with empty .env.example placeholders
        if key not in os.environ or not str(os.environ.get(key, "")).strip():
            os.environ[key] = val


def _api_key() -> str:
    key = os.environ.get("SILICONFLOW_API_KEY", "").strip()
    if not key:
        env_path = ROOT / ".env"
        hint = (
            "Paste SILICONFLOW_API_KEY into .env (not empty .env.example copy), "
            "or set $env:SILICONFLOW_API_KEY in PowerShell before running."
        )
        if env_path.is_file() and "SILICONFLOW_API_KEY=" in env_path.read_text(encoding="utf-8"):
            hint = (
                ".env has empty SILICONFLOW_API_KEY= — open .env and paste your key after the = sign."
            )
        raise SystemExit(f"SILICONFLOW_API_KEY not set. {hint}")
    return key


def _base_url() -> str:
    return os.environ.get("SILICONFLOW_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _post_json(path: str, payload: dict, *, timeout: float = 120.0) -> dict:
    url = f"{_base_url()}{path}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} {url}\n{body}") from exc


def test_text_ping(model: str) -> str:
    data = _post_json(
        "/chat/completions",
        {
            "model": model,
            "messages": [{"role": "user", "content": "Reply with exactly: API_OK"}],
            "max_tokens": 16,
            "temperature": 0,
        },
        timeout=60,
    )
    return str(data["choices"][0]["message"]["content"]).strip()


def test_vision_ocr(image_path: Path, model: str) -> str:
    if not image_path.is_file():
        raise SystemExit(f"Image not found: {image_path}")
    mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"
    data = _post_json(
        "/chat/completions",
        {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": BUBBLE_OCR_PROMPT},
                    ],
                }
            ],
            "max_tokens": 512,
            "temperature": 0.1,
        },
        timeout=180,
    )
    return str(data["choices"][0]["message"]["content"]).strip()


def list_models() -> list[str]:
    url = f"{_base_url()}/models"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {_api_key()}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} {url}\n{body}") from exc
    items = data.get("data") or []
    ids = [str(m.get("id", "")) for m in items if m.get("id")]
    visual = [
        mid
        for mid in ids
        if any(
            token in mid.lower()
            for token in ("vl", "vision", "ocr", "deepseek-vl")
        )
    ]
    return sorted(set(visual))


def main() -> int:
    parser = argparse.ArgumentParser(description="SiliconFlow API smoke test")
    parser.add_argument(
        "--model",
        default=os.environ.get("SILICONFLOW_VLM_MODEL", DEFAULT_VLM),
        help=f"VLM model id (default: {DEFAULT_VLM})",
    )
    parser.add_argument(
        "--vision",
        metavar="IMAGE",
        help="Optional bubble crop path for vision OCR test",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List vision-related models available for your key",
    )
    args = parser.parse_args()

    _load_dotenv()
    print(f"Base URL: {_base_url()}")
    print(f"Key:      {'*' * 8}{_api_key()[-4:]}")

    if args.list_models:
        models = list_models()
        print(f"\nVision-related models ({len(models)}):")
        for mid in models:
            mark = " <-- default" if mid == args.model else ""
            print(f"  {mid}{mark}")
        return 0

    print(f"\n[1/2] Text ping -> {args.model}")
    reply = test_text_ping(args.model)
    print(f"      Reply: {reply!r}")
    if "API_OK" not in reply and "ok" not in reply.lower():
        print("      Warning: unexpected reply (key may still work for vision)")

    if args.vision:
        img = Path(args.vision)
        if not img.is_absolute():
            img = (ROOT / img).resolve()
        print(f"\n[2/2] Vision OCR -> {img.name}")
        text = test_vision_ocr(img, args.model)
        print("      --- OCR result ---")
        print(text)
        print("      ------------------")
    else:
        print("\n[2/2] Vision test skipped (pass --vision path/to/crop.jpg)")

    print("\nSiliconFlow API: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

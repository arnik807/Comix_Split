"""Load .env from project root (optional, for API keys)."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_LOADED = False


def load_dotenv(path: Path | None = None) -> None:
    global _LOADED
    env_path = path or (ROOT / ".env")
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
            continue
        if key not in os.environ or not str(os.environ.get(key, "")).strip():
            os.environ[key] = val
    _LOADED = True

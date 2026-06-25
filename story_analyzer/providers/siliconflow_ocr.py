"""SiliconFlow VLM OCR for comic bubble crops."""

from __future__ import annotations

import base64
import json
import os
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Sequence

import cv2
import numpy as np

from story_analyzer.env_loader import load_dotenv

BUBBLE_OCR_PROMPT = (
    "Extract ALL text visible in this comic speech bubble. "
    "Return only the text, nothing else. Preserve line breaks. "
    "Language may be Russian, English, or mixed."
)


@dataclass(frozen=True)
class SiliconFlowOcrSettings:
    base_url: str = "https://api.siliconflow.com/v1"
    vlm_model: str = "Qwen/Qwen3-VL-8B-Instruct"
    max_tokens: int = 512
    temperature: float = 0.1
    timeout_sec: float = 180.0


def load_siliconflow_settings(
    block: dict | None = None,
) -> SiliconFlowOcrSettings:
    load_dotenv()
    block = block or {}
    return SiliconFlowOcrSettings(
        base_url=str(
            block.get("base_url")
            or os.environ.get("SILICONFLOW_BASE_URL")
            or "https://api.siliconflow.com/v1"
        ).rstrip("/"),
        vlm_model=str(
            block.get("vlm_model")
            or os.environ.get("SILICONFLOW_VLM_MODEL")
            or "Qwen/Qwen3-VL-8B-Instruct"
        ),
        max_tokens=int(block.get("max_tokens", 512)),
        temperature=float(block.get("temperature", 0.1)),
        timeout_sec=float(block.get("timeout_sec", 180.0)),
    )


class SiliconFlowOcrClient:
    def __init__(self, settings: SiliconFlowOcrSettings | None = None) -> None:
        load_dotenv()
        self.settings = settings or load_siliconflow_settings()
        self._lock = threading.Lock()
        self._api_key = os.environ.get("SILICONFLOW_API_KEY", "").strip()
        if not self._api_key:
            raise RuntimeError(
                "SILICONFLOW_API_KEY not set. Add it to .env in the project root."
            )

    @staticmethod
    def _encode_bgr(crop_bgr: np.ndarray) -> str:
        if crop_bgr is None or crop_bgr.size == 0:
            raise ValueError("empty image")
        ok, buf = cv2.imencode(".jpg", crop_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
        if not ok:
            raise RuntimeError("failed to encode bubble crop as JPEG")
        return base64.b64encode(buf.tobytes()).decode("ascii")

    def recognize_bgr(
        self,
        crop_bgr: np.ndarray,
        languages: Sequence[str] | None = None,
    ) -> tuple[str, float]:
        _ = languages
        data_url = f"data:image/jpeg;base64,{self._encode_bgr(crop_bgr)}"
        payload = {
            "model": self.settings.vlm_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": BUBBLE_OCR_PROMPT},
                    ],
                }
            ],
            "max_tokens": self.settings.max_tokens,
            "temperature": self.settings.temperature,
        }
        url = f"{self.settings.base_url}/chat/completions"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        t0 = time.perf_counter()
        with self._lock:
            try:
                with urllib.request.urlopen(req, timeout=self.settings.timeout_sec) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"SiliconFlow HTTP {exc.code}: {body}") from exc
        ms = (time.perf_counter() - t0) * 1000.0
        text = str(data["choices"][0]["message"]["content"]).strip()
        return text, ms

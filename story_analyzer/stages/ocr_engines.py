"""OCR backends for Stage 2a bubble crops."""

from __future__ import annotations

import os
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Sequence, Tuple

import numpy as np

import sys

from story_analyzer.ocr_engine_ids import OCR_ENGINES, normalize_ocr_engine

# Paddle Inference (C++) on Windows cannot open model files under non-ASCII paths.
_DEFAULT_PADDLE_REL = "models/paddleocr"
_CONFIGURED_PADDLE_BASE_DIR: str | None = None


def _project_root() -> Path:
    from story_analyzer.config import ROOT

    return ROOT


def _path_is_ascii(path: str) -> bool:
    try:
        os.fsencode(path).decode("ascii")
        return True
    except (UnicodeDecodeError, UnicodeEncodeError):
        return False


def _resolve_configured_path(configured: str) -> str:
    p = Path(configured).expanduser()
    if not p.is_absolute():
        p = (_project_root() / p).resolve()
    return str(p)


def _default_paddle_base_dir() -> str:
    return str((_project_root() / _DEFAULT_PADDLE_REL).resolve())


def resolve_paddle_ocr_base_dir(configured: str | None = None) -> str:
    """Pick an ASCII-safe directory for PaddleOCR model cache."""
    if configured:
        candidate = _resolve_configured_path(configured)
        if _path_is_ascii(candidate):
            return candidate
        fallback = _default_paddle_base_dir()
        print(
            f"[stage_2a] paddle_ocr_base_dir содержит не-ASCII символы "
            f"({candidate!r}), используем {fallback}",
            file=sys.stderr,
        )
        if _path_is_ascii(fallback):
            return fallback
    default = _default_paddle_base_dir()
    if _path_is_ascii(default):
        return default
    home = os.path.expanduser("~")
    if _path_is_ascii(home):
        return os.path.join(home, ".paddleocr")
    return "D:/DEVELOP/paddleocr_cache"


def configure_paddle_ocr_base_dir(configured: str | None = None) -> str:
    """Set PADDLE_OCR_BASE_DIR before any paddleocr import (idempotent)."""
    global _CONFIGURED_PADDLE_BASE_DIR
    base_dir = resolve_paddle_ocr_base_dir(configured)
    os.makedirs(base_dir, exist_ok=True)
    os.environ["PADDLE_OCR_BASE_DIR"] = base_dir
    _CONFIGURED_PADDLE_BASE_DIR = base_dir
    return base_dir


class OcrEngine(ABC):
    @abstractmethod
    def recognize(self, crop_bgr: np.ndarray, languages: Sequence[str]) -> Tuple[str, float]:
        """Return (text, elapsed_ms)."""


class EasyOcrEngine(OcrEngine):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reader = None
        self._langs: Tuple[str, ...] | None = None

    def _get_reader(self, languages: Sequence[str]):
        langs = tuple(languages)
        with self._lock:
            if self._reader is None or self._langs != langs:
                import easyocr

                self._reader = easyocr.Reader(list(langs), gpu=False, verbose=False)
                self._langs = langs
            return self._reader

    def recognize(self, crop_bgr: np.ndarray, languages: Sequence[str]) -> Tuple[str, float]:
        if crop_bgr is None or crop_bgr.size == 0:
            return "", 0.0
        reader = self._get_reader(languages)
        t0 = time.perf_counter()
        results = reader.readtext(crop_bgr)
        ms = (time.perf_counter() - t0) * 1000.0
        parts: List[str] = []
        for item in results:
            if len(item) >= 2 and item[1]:
                parts.append(str(item[1]).strip())
        return " ".join(parts).strip(), ms


def _extract_paddle_text(result) -> str:
    """Merge Paddle det+rec lines top-to-bottom (bubble crops are multi-line)."""
    if not result:
        return ""
    lines: List[tuple[float, str]] = []
    for block in result:
        if not block:
            continue
        for item in block:
            if not item or len(item) < 2:
                continue
            text_part = item[1]
            text = ""
            if isinstance(text_part, (list, tuple)) and text_part:
                text = str(text_part[0]).strip()
            elif isinstance(text_part, str):
                text = text_part.strip()
            if not text:
                continue
            y = 0.0
            box = item[0]
            if isinstance(box, (list, tuple)) and box:
                try:
                    y = float(min(p[1] for p in box))
                except (TypeError, IndexError, ValueError):
                    y = 0.0
            lines.append((y, text))
    lines.sort(key=lambda row: row[0])
    return "\n".join(t for _, t in lines)


class PaddleOcrEngine(OcrEngine):
    def __init__(self, paddle_base_dir: str | None = None) -> None:
        self._lock = threading.Lock()
        self._ocr = None
        self._lang: str | None = None
        self._paddle_base_dir = configure_paddle_ocr_base_dir(paddle_base_dir)
        try:
            from paddleocr import PaddleOCR  # noqa: F401
        except Exception as exc:
            raise RuntimeError(
                "PaddleOCR не установлен или не совместим с окружением. "
                "Запустите scripts/install_paddle_ocr.ps1 (сервер/Gradio должны быть остановлены). "
                f"Причина: {exc}"
            ) from exc

    @staticmethod
    def _paddle_lang(languages: Sequence[str]) -> str:
        langs = [str(x).lower() for x in languages]
        if "ru" in langs:
            return "ru"
        if "en" in langs:
            return "en"
        return langs[0] if langs else "ru"

    def _get_ocr(self, languages: Sequence[str]):
        lang = self._paddle_lang(languages)
        with self._lock:
            if self._ocr is None or self._lang != lang:
                from paddleocr import PaddleOCR

                configure_paddle_ocr_base_dir(self._paddle_base_dir)
                self._ocr = PaddleOCR(
                    use_angle_cls=False,
                    lang=lang,
                    use_gpu=False,
                    show_log=False,
                )
                self._lang = lang
            return self._ocr

    def recognize(self, crop_bgr: np.ndarray, languages: Sequence[str]) -> Tuple[str, float]:
        if crop_bgr is None or crop_bgr.size == 0:
            return "", 0.0
        ocr = self._get_ocr(languages)
        t0 = time.perf_counter()
        result = ocr.ocr(crop_bgr, det=True, rec=True, cls=False)
        ms = (time.perf_counter() - t0) * 1000.0
        return _extract_paddle_text(result), ms


class SiliconFlowOcrEngine(OcrEngine):
    def __init__(self, siliconflow_block: dict | None = None) -> None:
        from story_analyzer.providers.siliconflow_ocr import (
            SiliconFlowOcrClient,
            load_siliconflow_settings,
        )

        self._client = SiliconFlowOcrClient(load_siliconflow_settings(siliconflow_block))

    def recognize(self, crop_bgr: np.ndarray, languages: Sequence[str]) -> Tuple[str, float]:
        if crop_bgr is None or crop_bgr.size == 0:
            return "", 0.0
        return self._client.recognize_bgr(crop_bgr, languages)


class AutoOcrEngine(OcrEngine):
    """Local Paddle/EasyOCR first; cloud VLM when text is empty or local fails."""

    last_engine_used: str = "paddle"

    def __init__(
        self,
        *,
        paddle_base_dir: str | None = None,
        siliconflow_block: dict | None = None,
    ) -> None:
        self._local: OcrEngine | None = None
        self._cloud: OcrEngine | None = None
        self._paddle_base_dir = paddle_base_dir
        self._siliconflow_block = siliconflow_block

    def _local_engine(self) -> OcrEngine:
        if self._local is None:
            try:
                self._local = PaddleOcrEngine(paddle_base_dir=self._paddle_base_dir)
            except Exception as exc:
                print(
                    f"[stage_2a] PaddleOCR недоступен, auto local → EasyOCR: {exc}",
                    file=sys.stderr,
                )
                self._local = EasyOcrEngine()
        return self._local

    def _cloud_engine(self) -> OcrEngine:
        if self._cloud is None:
            self._cloud = SiliconFlowOcrEngine(self._siliconflow_block)
        return self._cloud

    def recognize(self, crop_bgr: np.ndarray, languages: Sequence[str]) -> Tuple[str, float]:
        if crop_bgr is None or crop_bgr.size == 0:
            self.last_engine_used = "siliconflow"
            return "", 0.0
        try:
            text, ms = self._local_engine().recognize(crop_bgr, languages)
            if text.strip():
                self.last_engine_used = "paddle"
                return text, ms
        except Exception as exc:
            print(f"[stage_2a] auto local OCR failed, cloud fallback: {exc}", file=sys.stderr)
        text, ms = self._cloud_engine().recognize(crop_bgr, languages)
        self.last_engine_used = "siliconflow"
        return text, ms


_ENGINE_CACHE: dict[str, OcrEngine] = {}
_ENGINE_LOCK = threading.Lock()


def get_ocr_engine(
    engine_id: str | None = None,
    *,
    paddle_base_dir: str | None = None,
    siliconflow_block: dict | None = None,
) -> OcrEngine:
    name = normalize_ocr_engine(engine_id)
    with _ENGINE_LOCK:
        if name not in _ENGINE_CACHE:
            if name == "paddle":
                try:
                    _ENGINE_CACHE[name] = PaddleOcrEngine(paddle_base_dir=paddle_base_dir)
                except Exception as exc:
                    print(
                        f"[stage_2a] PaddleOCR недоступен, fallback → EasyOCR: {exc}",
                        file=sys.stderr,
                    )
                    _ENGINE_CACHE[name] = EasyOcrEngine()
            elif name == "siliconflow":
                _ENGINE_CACHE[name] = SiliconFlowOcrEngine(siliconflow_block)
            elif name == "auto":
                _ENGINE_CACHE[name] = AutoOcrEngine(
                    paddle_base_dir=paddle_base_dir,
                    siliconflow_block=siliconflow_block,
                )
            else:
                _ENGINE_CACHE[name] = EasyOcrEngine()
        return _ENGINE_CACHE[name]

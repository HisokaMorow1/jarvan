"""Captura de pantalla (mss) con caché temporal para evitar recapturas."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional, Tuple

import mss
import mss.tools
from PIL import Image

from config import settings
from core.logger import logger


class Screen:
    def __init__(self) -> None:
        self._sct = mss.mss()
        self._cache_img: Optional[Image.Image] = None
        self._cache_ts: float = 0.0
        self._ttl = settings.vision.cache_ttl_seconds
        self._scale = settings.vision.screenshot_scale
        self._out_dir: Path = settings.root / settings.app.screenshots_dir

    def size(self) -> Tuple[int, int]:
        mon = self._sct.monitors[1]
        return mon["width"], mon["height"]

    def grab(self, monitor: int = 1, fresh: bool = False) -> Image.Image:
        if not fresh and self._cache_img and (time.time() - self._cache_ts) < self._ttl:
            return self._cache_img
        mon = self._sct.monitors[monitor]
        raw = self._sct.grab(mon)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        if self._scale != 1.0:
            new = (int(img.width * self._scale), int(img.height * self._scale))
            img = img.resize(new, Image.LANCZOS)
        self._cache_img = img
        self._cache_ts = time.time()
        return img

    def save(self, img: Optional[Image.Image] = None, name: str = "screen.png") -> Path:
        img = img or self.grab()
        path = self._out_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path, "PNG")
        logger.debug(f"Screenshot guardado en {path}")
        return path

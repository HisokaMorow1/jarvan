"""OCR como fallback determinista al VLM.

Por defecto PaddleOCR (mejor precisión que tesseract en español).
Fallback a pytesseract si PaddleOCR no está disponible.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Tuple

from PIL import Image
from rapidfuzz import fuzz, process

from config import settings
from core.logger import logger


@dataclass
class OCRBox:
    text: str
    x: int
    y: int
    w: int
    h: int
    conf: float = 0.0

    @property
    def center(self) -> Tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2


class OCREngine:
    def __init__(self) -> None:
        self._paddle = None
        self._tess = None
        engine = settings.vision.ocr_engine
        if engine == "paddleocr":
            self._init_paddle()
        if not self._paddle:
            self._init_tesseract()

    def _init_paddle(self) -> None:
        try:
            from paddleocr import PaddleOCR

            self._paddle = PaddleOCR(use_angle_cls=True, lang=settings.vision.ocr_lang, show_log=False)
            logger.info("OCR: PaddleOCR cargado")
        except Exception as e:
            logger.warning(f"PaddleOCR no disponible: {e}")

    def _init_tesseract(self) -> None:
        try:
            import pytesseract

            tcmd = os.getenv("TESSERACT_CMD")
            if tcmd:
                pytesseract.pytesseract.tesseract_cmd = tcmd
            self._tess = pytesseract
            logger.info("OCR: pytesseract cargado (fallback)")
        except Exception as e:
            logger.error(f"Sin OCR disponible: {e}")

    def extract(self, image: Image.Image) -> List[OCRBox]:
        if self._paddle:
            return self._extract_paddle(image)
        if self._tess:
            return self._extract_tess(image)
        return []

    def _extract_paddle(self, image: Image.Image) -> List[OCRBox]:
        import numpy as np

        arr = np.array(image)
        result = self._paddle.ocr(arr, cls=True)
        boxes: List[OCRBox] = []
        if not result or not result[0]:
            return boxes
        for line in result[0]:
            poly, (text, conf) = line
            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            x, y = int(min(xs)), int(min(ys))
            w, h = int(max(xs) - x), int(max(ys) - y)
            boxes.append(OCRBox(text=text, x=x, y=y, w=w, h=h, conf=float(conf)))
        return boxes

    def _extract_tess(self, image: Image.Image) -> List[OCRBox]:
        data = self._tess.image_to_data(image, output_type=self._tess.Output.DICT, lang="spa")
        boxes: List[OCRBox] = []
        for i, txt in enumerate(data["text"]):
            t = txt.strip()
            if not t:
                continue
            try:
                conf = float(data["conf"][i]) / 100.0
            except Exception:
                conf = 0.0
            boxes.append(
                OCRBox(
                    text=t,
                    x=int(data["left"][i]),
                    y=int(data["top"][i]),
                    w=int(data["width"][i]),
                    h=int(data["height"][i]),
                    conf=conf,
                )
            )
        return boxes

    def find(self, image: Image.Image, query: str, min_score: int = 70) -> List[OCRBox]:
        boxes = self.extract(image)
        if not boxes:
            return []
        choices = {i: b.text for i, b in enumerate(boxes)}
        matches = process.extract(query, choices, scorer=fuzz.WRatio, limit=5)
        out = [boxes[idx] for _, score, idx in matches if score >= min_score]
        return out

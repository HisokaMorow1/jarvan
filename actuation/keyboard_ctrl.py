"""Control de teclado: escritura con cadencia humana y hotkeys."""
from __future__ import annotations

import random
import time
from typing import Iterable

import pyautogui

from core.logger import logger


class Keyboard:
    def type(self, text: str, interval: float = 0.02, humanize: bool = True) -> None:
        logger.info(f"Typing: {text!r}")
        if humanize:
            for ch in text:
                pyautogui.typewrite(ch, interval=0)
                time.sleep(interval + random.uniform(0, 0.04))
        else:
            pyautogui.typewrite(text, interval=interval)

    def press(self, key: str) -> None:
        logger.debug(f"Key press: {key}")
        pyautogui.press(key)

    def hotkey(self, *keys: Iterable[str]) -> None:
        logger.info(f"Hotkey: {'+'.join(keys)}")
        pyautogui.hotkey(*keys)

    def enter(self) -> None:
        self.press("enter")

    def esc(self) -> None:
        self.press("escape")

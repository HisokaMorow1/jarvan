"""Control de mouse con verificación. pyautogui + movimiento humanizado."""
from __future__ import annotations

import random
import time
from typing import Tuple

import pyautogui

from core.logger import logger

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


class Mouse:
    def position(self) -> Tuple[int, int]:
        return pyautogui.position()

    def move(self, x: int, y: int, duration: float = 0.25, humanize: bool = True) -> None:
        if humanize:
            x += random.randint(-2, 2)
            y += random.randint(-2, 2)
        logger.debug(f"Mouse move → ({x},{y})")
        pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeInOutQuad)

    def click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> None:
        self.move(x, y)
        time.sleep(0.05)
        pyautogui.click(x=x, y=y, button=button, clicks=clicks)
        logger.info(f"Click {button}x{clicks} @ ({x},{y})")

    def double_click(self, x: int, y: int) -> None:
        self.click(x, y, clicks=2)

    def right_click(self, x: int, y: int) -> None:
        self.click(x, y, button="right")

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.6) -> None:
        self.move(x1, y1)
        pyautogui.mouseDown()
        pyautogui.moveTo(x2, y2, duration=duration, tween=pyautogui.easeInOutQuad)
        pyautogui.mouseUp()
        logger.info(f"Drag ({x1},{y1}) → ({x2},{y2})")

    def scroll(self, amount: int) -> None:
        pyautogui.scroll(amount)

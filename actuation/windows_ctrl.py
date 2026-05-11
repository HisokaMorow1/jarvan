"""Control nativo Win32 vía pywinauto/uiautomation/pygetwindow.

Para clicks deterministas en controles (no por píxeles).
"""
from __future__ import annotations

from typing import List, Optional

import pygetwindow as gw

from core.logger import logger


class WindowsCtrl:
    def list_windows(self) -> List[str]:
        return [w.title for w in gw.getAllWindows() if w.title]

    def find(self, title_substr: str) -> Optional["gw.Window"]:
        for w in gw.getAllWindows():
            if title_substr.lower() in (w.title or "").lower():
                return w
        return None

    def focus(self, title_substr: str) -> bool:
        w = self.find(title_substr)
        if not w:
            logger.warning(f"Ventana no encontrada: {title_substr}")
            return False
        try:
            if w.isMinimized:
                w.restore()
            w.activate()
            logger.info(f"Focus → {w.title}")
            return True
        except Exception as e:
            logger.warning(f"No se pudo activar ventana: {e}")
            return False

    def close(self, title_substr: str) -> bool:
        w = self.find(title_substr)
        if not w:
            return False
        try:
            w.close()
            return True
        except Exception:
            return False

    def maximize(self, title_substr: str) -> bool:
        w = self.find(title_substr)
        if not w:
            return False
        w.maximize()
        return True

"""Lanzador de apps en Windows: vía start, ruta o atajo."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional

from core.logger import logger


COMMON_APPS: Dict[str, str] = {
    "chrome": "chrome",
    "edge": "msedge",
    "firefox": "firefox",
    "notepad": "notepad",
    "bloc de notas": "notepad",
    "calculadora": "calc",
    "calc": "calc",
    "explorador": "explorer",
    "explorer": "explorer",
    "vscode": "code",
    "code": "code",
    "spotify": "spotify",
    "discord": "discord",
    "cmd": "cmd",
    "powershell": "powershell",
    "terminal": "wt",
}


class AppLauncher:
    def open(self, name: str) -> bool:
        key = name.strip().lower()
        target = COMMON_APPS.get(key, key)
        logger.info(f"Abriendo app: {name} → {target}")

        if Path(target).exists():
            try:
                os.startfile(target)
                return True
            except Exception as e:
                logger.warning(f"startfile falló: {e}")

        if shutil.which(target):
            try:
                subprocess.Popen([target], shell=False)
                return True
            except Exception as e:
                logger.warning(f"Popen falló: {e}")

        try:
            subprocess.Popen(f'start "" "{target}"', shell=True)
            return True
        except Exception as e:
            logger.error(f"No se pudo abrir {name}: {e}")
            return False

    def open_url(self, url: str) -> bool:
        import webbrowser

        logger.info(f"Abriendo URL: {url}")
        return webbrowser.open(url)

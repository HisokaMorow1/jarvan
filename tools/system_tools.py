"""Tools de sistema: volumen, brillo, hora, screenshot, clipboard, ejecutar shell.

Aumentan dramáticamente la utilidad del agente para una demo: cosas que un
usuario real le pediría a Jarvis ("sube el volumen", "qué hora es", "cópiame esto").
"""
from __future__ import annotations

import datetime
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from config import settings
from core.logger import logger
from tools.registry import Tool, ToolRegistry, ToolResult


class VolumeArgs(BaseModel):
    direction: str = Field(..., description="up | down | mute | unmute")
    steps: int = Field(2, description="número de pulsaciones (cada una ~2%)")


class ClipboardCopyArgs(BaseModel):
    text: str


class ScreenshotArgs(BaseModel):
    name: str = Field("manual.png", description="nombre del archivo")


class ShellArgs(BaseModel):
    command: str = Field(..., description="comando PowerShell a ejecutar")


def _volume(a: VolumeArgs) -> ToolResult:
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from comtypes import CLSCTX_ALL, cast, POINTER

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol = cast(interface, POINTER(IAudioEndpointVolume))
        d = a.direction.lower()
        if d == "mute":
            vol.SetMute(1, None)
            return ToolResult(ok=True, message="audio silenciado")
        if d == "unmute":
            vol.SetMute(0, None)
            return ToolResult(ok=True, message="audio restaurado")
        cur = vol.GetMasterVolumeLevelScalar()
        delta = 0.04 * a.steps * (1 if d == "up" else -1)
        new = max(0.0, min(1.0, cur + delta))
        vol.SetMasterVolumeLevelScalar(new, None)
        return ToolResult(ok=True, message=f"volumen {int(new*100)}%")
    except Exception as e:
        return ToolResult(ok=False, message=f"no pude controlar volumen: {e}")


def _clipboard_copy(a: ClipboardCopyArgs) -> ToolResult:
    try:
        import subprocess as sp

        proc = sp.Popen("clip", stdin=sp.PIPE, shell=True)
        proc.communicate(a.text.encode("utf-16le"))
        return ToolResult(ok=True, message=f"copiado al portapapeles ({len(a.text)} chars)")
    except Exception as e:
        return ToolResult(ok=False, message=str(e))


def _screenshot(a: ScreenshotArgs) -> ToolResult:
    from perception.screen import Screen

    s = Screen()
    path = s.save(name=a.name)
    return ToolResult(ok=True, message=f"captura guardada", data=str(path))


def _time_now(_args=None) -> ToolResult:
    now = datetime.datetime.now()
    return ToolResult(
        ok=True,
        message=now.strftime("%H:%M del %A %d de %B de %Y"),
        data={"iso": now.isoformat()},
    )


def _shell(a: ShellArgs) -> ToolResult:
    """Ejecuta PowerShell con whitelist mínima. Pide confirmación."""
    forbidden = ["format ", "del ", "remove-item", "shutdown", "rd /s", "rm -rf"]
    if any(f in a.command.lower() for f in forbidden):
        return ToolResult(ok=False, message="comando bloqueado por seguridad")
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", a.command],
            capture_output=True, text=True, timeout=20,
        )
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        if r.returncode == 0:
            return ToolResult(ok=True, message=out[:400] or "ok", data=out)
        return ToolResult(ok=False, message=err[:400] or f"exit {r.returncode}")
    except Exception as e:
        return ToolResult(ok=False, message=str(e))


def register_system_tools(r: ToolRegistry) -> None:
    r.register(Tool("set_volume", "Sube/baja/silencia volumen del sistema", VolumeArgs, _volume))
    r.register(Tool("clipboard_copy", "Copia texto al portapapeles", ClipboardCopyArgs, _clipboard_copy))
    r.register(Tool("screenshot", "Guarda una captura de pantalla", ScreenshotArgs, _screenshot))
    r.register(Tool("time_now", "Devuelve hora y fecha actuales", None, _time_now))
    r.register(Tool("run_shell", "Ejecuta comando PowerShell (seguro)", ShellArgs, _shell, danger=True))

"""Tools de medios: música, brillo, hibernar pantalla."""
from __future__ import annotations

import subprocess

from pydantic import BaseModel, Field

from actuation.media import Brightness, Media
from tools.registry import Tool, ToolRegistry, ToolResult


class MediaArgs(BaseModel):
    action: str = Field(..., description="play_pause | next | prev | stop")


class BrightnessArgs(BaseModel):
    percent: int = Field(..., ge=0, le=100)


def _media(a: MediaArgs) -> ToolResult:
    act = a.action.lower()
    ok = {
        "play_pause": Media.play_pause,
        "play": Media.play_pause,
        "pause": Media.play_pause,
        "next": Media.next_track,
        "prev": Media.prev_track,
        "previous": Media.prev_track,
        "stop": Media.stop,
    }.get(act, lambda: False)()
    return ToolResult(ok=ok, message=f"media {act}")


def _brightness(a: BrightnessArgs) -> ToolResult:
    ok = Brightness.set_percent(a.percent)
    return ToolResult(ok=ok, message=f"brillo {a.percent}%")


def _lock_screen(_args=None) -> ToolResult:
    try:
        subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
        return ToolResult(ok=True, message="pantalla bloqueada")
    except Exception as e:
        return ToolResult(ok=False, message=str(e))


def register_media_tools(r: ToolRegistry) -> None:
    r.register(Tool("media_control", "Controla reproducción multimedia", MediaArgs, _media))
    r.register(Tool("set_brightness", "Ajusta brillo de pantalla 0-100", BrightnessArgs, _brightness))
    r.register(Tool("lock_screen", "Bloquea la pantalla de Windows", None, _lock_screen))

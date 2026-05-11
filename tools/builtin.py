"""Registra las herramientas integradas en el ToolRegistry."""
from __future__ import annotations

import shutil
import urllib.parse
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from actuation.apps import AppLauncher
from actuation.keyboard_ctrl import Keyboard
from actuation.mouse import Mouse
from actuation.windows_ctrl import WindowsCtrl
from core.llm_client import OllamaClient
from core.logger import logger
from perception.ocr import OCREngine
from perception.screen import Screen
from perception.vision import VisionEngine
from tools.registry import Tool, ToolRegistry, ToolResult


_apps = AppLauncher()
_mouse = Mouse()
_kbd = Keyboard()
_win = WindowsCtrl()
_screen = Screen()
_ocr = OCREngine()
_llm = OllamaClient()
_vision = VisionEngine(_llm, _screen)


class OpenAppArgs(BaseModel):
    name: str = Field(..., description="Nombre de la app (chrome, notepad, etc.)")


class OpenURLArgs(BaseModel):
    url: str


class SearchYouTubeArgs(BaseModel):
    query: str
    autoplay: bool = Field(True, description="Si True, abre el primer resultado y lo reproduce")


class CreateFolderArgs(BaseModel):
    path: str


class TypeTextArgs(BaseModel):
    text: str


class HotkeyArgs(BaseModel):
    keys: str = Field(..., description="Teclas separadas por +, ej: ctrl+s")


class ClickTextArgs(BaseModel):
    text: str = Field(..., description="Texto visible en pantalla a clicar")
    button: str = "left"


class FocusWindowArgs(BaseModel):
    title: str


class ObserveArgs(BaseModel):
    focus: Optional[str] = Field(None, description="Qué buscar específicamente, opcional")


def _open_app(a: OpenAppArgs) -> ToolResult:
    ok = _apps.open(a.name)
    return ToolResult(ok=ok, message=f"app '{a.name}' {'abierta' if ok else 'no abrió'}")


def _open_url(a: OpenURLArgs) -> ToolResult:
    ok = _apps.open_url(a.url)
    return ToolResult(ok=ok, message=f"url abierta: {a.url}")


def _search_youtube(a: SearchYouTubeArgs) -> ToolResult:
    if a.autoplay:
        video_url, title = _resolve_first_youtube_video(a.query)
        if video_url:
            ok = _apps.open_url(video_url)
            return ToolResult(
                ok=ok,
                message=f"reproduciendo '{title or a.query}'",
                data={"url": video_url, "title": title},
            )
        logger.warning("no pude resolver el primer video, abro búsqueda")
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(a.query)}"
    ok = _apps.open_url(url)
    return ToolResult(ok=ok, message=f"búsqueda abierta: '{a.query}'")


def _resolve_first_youtube_video(query: str):
    """Devuelve (url, titulo) del primer video de YouTube para una query.

    Intenta tres estrategias en orden de calidad:
      1) youtube-search-python (rápido, sin API key).
      2) yt-dlp en modo búsqueda (más robusto, descarga metadata).
      3) Scraping HTML mínimo de la página de resultados.
    """
    try:
        from youtubesearchpython import VideosSearch

        results = VideosSearch(query, limit=1).result().get("result", [])
        if results:
            v = results[0]
            return v["link"], v.get("title", "")
    except Exception as e:
        logger.debug(f"youtubesearchpython no disponible: {e}")

    try:
        import yt_dlp

        opts = {"quiet": True, "skip_download": True, "extract_flat": True, "default_search": "ytsearch1"}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            entries = info.get("entries") if info else None
            if entries:
                e = entries[0]
                vid = e.get("id") or ""
                title = e.get("title", "")
                if vid:
                    return f"https://www.youtube.com/watch?v={vid}", title
    except Exception as e:
        logger.debug(f"yt-dlp no disponible: {e}")

    try:
        import re
        import httpx

        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
        r = httpx.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        m = re.search(r'"videoId":"([A-Za-z0-9_-]{11})"', r.text)
        if m:
            return f"https://www.youtube.com/watch?v={m.group(1)}", ""
    except Exception as e:
        logger.debug(f"scrape falló: {e}")

    return None, None


def _create_folder(a: CreateFolderArgs) -> ToolResult:
    p = Path(a.path).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return ToolResult(ok=True, message=f"carpeta lista: {p}", data=str(p))


def _type_text(a: TypeTextArgs) -> ToolResult:
    _kbd.type(a.text)
    return ToolResult(ok=True, message=f"escrito ({len(a.text)} chars)")


def _hotkey(a: HotkeyArgs) -> ToolResult:
    keys = [k.strip() for k in a.keys.split("+") if k.strip()]
    _kbd.hotkey(*keys)
    return ToolResult(ok=True, message=f"hotkey {a.keys}")


def _click_text(a: ClickTextArgs) -> ToolResult:
    img = _screen.grab(fresh=True)
    matches = _ocr.find(img, a.text, min_score=70)
    if not matches:
        located = _vision.locate(a.text)
        return ToolResult(
            ok=False,
            message=f"no encontré '{a.text}' por OCR. VLM dice: {located}",
            data=located,
        )
    box = matches[0]
    x, y = box.center
    if a.button == "right":
        _mouse.right_click(x, y)
    elif a.button == "double":
        _mouse.double_click(x, y)
    else:
        _mouse.click(x, y)
    return ToolResult(ok=True, message=f"click sobre '{box.text}' @ ({x},{y})")


def _focus_window(a: FocusWindowArgs) -> ToolResult:
    ok = _win.focus(a.title)
    return ToolResult(ok=ok, message=f"focus '{a.title}'")


def _observe(a: ObserveArgs) -> ToolResult:
    if a.focus:
        loc = _vision.locate(a.focus)
        return ToolResult(ok=True, message="observación dirigida", data=loc)
    desc = _vision.describe_screen()
    return ToolResult(ok=True, message="pantalla descrita", data=desc.raw)


def register_builtins(r: ToolRegistry) -> None:
    r.register(Tool("open_app", "Abre una aplicación de Windows", OpenAppArgs, _open_app))
    r.register(Tool("open_url", "Abre una URL en el navegador", OpenURLArgs, _open_url))
    r.register(Tool("search_youtube", "Busca un término en YouTube", SearchYouTubeArgs, _search_youtube))
    r.register(Tool("create_folder", "Crea una carpeta", CreateFolderArgs, _create_folder))
    r.register(Tool("type_text", "Escribe texto en la ventana activa", TypeTextArgs, _type_text))
    r.register(Tool("hotkey", "Ejecuta combinación de teclas (ctrl+s, alt+f4)", HotkeyArgs, _hotkey))
    r.register(Tool("click_text", "Hace click sobre texto visible en pantalla", ClickTextArgs, _click_text))
    r.register(Tool("focus_window", "Pone foco en una ventana por título", FocusWindowArgs, _focus_window))
    r.register(Tool("observe", "Observa la pantalla y describe contenido", ObserveArgs, _observe))
    logger.info(f"Tools registradas: {r.names()}")

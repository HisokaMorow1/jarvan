"""Tools de archivos: leer, escribir, listar, abrir explorador, leer PDF."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from tools.registry import Tool, ToolRegistry, ToolResult


SAFE_ROOTS = [Path.home()]


def _is_safe(p: Path) -> bool:
    try:
        p = p.resolve()
        return any(str(p).startswith(str(root.resolve())) for root in SAFE_ROOTS)
    except Exception:
        return False


class PathArg(BaseModel):
    path: str


class WriteArgs(BaseModel):
    path: str
    content: str
    append: bool = False


class ListArgs(BaseModel):
    path: str = Field("~", description="ruta a listar")


class PDFArgs(BaseModel):
    path: str
    max_chars: int = 4000


def _read(a: PathArg) -> ToolResult:
    p = Path(a.path).expanduser()
    if not _is_safe(p):
        return ToolResult(ok=False, message="ruta fuera del sandbox del usuario")
    if not p.exists():
        return ToolResult(ok=False, message="archivo no existe")
    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
        return ToolResult(ok=True, message=f"{len(text)} chars leídos", data=text[:8000])
    except Exception as e:
        return ToolResult(ok=False, message=str(e))


def _write(a: WriteArgs) -> ToolResult:
    p = Path(a.path).expanduser()
    if not _is_safe(p):
        return ToolResult(ok=False, message="ruta fuera del sandbox del usuario")
    p.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if a.append else "w"
    try:
        with p.open(mode, encoding="utf-8") as f:
            f.write(a.content)
        return ToolResult(ok=True, message=f"escrito {len(a.content)} chars en {p}")
    except Exception as e:
        return ToolResult(ok=False, message=str(e))


def _list(a: ListArgs) -> ToolResult:
    p = Path(a.path).expanduser()
    if not p.exists() or not p.is_dir():
        return ToolResult(ok=False, message="carpeta no existe")
    items = []
    for entry in sorted(p.iterdir())[:80]:
        tag = "[D]" if entry.is_dir() else "[F]"
        items.append(f"{tag} {entry.name}")
    return ToolResult(ok=True, message=f"{len(items)} elementos", data="\n".join(items))


def _open_explorer(a: PathArg) -> ToolResult:
    import os

    p = Path(a.path).expanduser()
    if not p.exists():
        return ToolResult(ok=False, message="ruta no existe")
    try:
        os.startfile(str(p))
        return ToolResult(ok=True, message=f"abierto {p}")
    except Exception as e:
        return ToolResult(ok=False, message=str(e))


def _read_pdf(a: PDFArgs) -> ToolResult:
    p = Path(a.path).expanduser()
    if not p.exists():
        return ToolResult(ok=False, message="pdf no existe")
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(p))
        text = []
        for page in reader.pages:
            text.append(page.extract_text() or "")
        full = "\n".join(text)
        return ToolResult(
            ok=True,
            message=f"{len(reader.pages)} páginas, {len(full)} chars",
            data=full[: a.max_chars],
        )
    except Exception as e:
        return ToolResult(ok=False, message=str(e))


def register_file_tools(r: ToolRegistry) -> None:
    r.register(Tool("read_file", "Lee un archivo de texto del usuario", PathArg, _read))
    r.register(Tool("write_file", "Escribe texto en un archivo", WriteArgs, _write))
    r.register(Tool("list_dir", "Lista archivos de una carpeta", ListArgs, _list))
    r.register(Tool("open_path", "Abre carpeta o archivo en el explorador", PathArg, _open_explorer))
    r.register(Tool("read_pdf", "Lee texto de un PDF", PDFArgs, _read_pdf))

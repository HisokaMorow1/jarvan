"""Navegación web headless con Playwright (cuando esté instalado).

Si Playwright no está disponible, las tools devuelven mensaje claro pidiendo
'playwright install chromium'. No bloquea el resto del sistema.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from core.logger import logger
from tools.registry import Tool, ToolRegistry, ToolResult


_browser = None
_context = None


class FetchArgs(BaseModel):
    url: str
    selector: str = Field("body", description="CSS selector para extraer (default body)")
    timeout_ms: int = 15000


class SearchArgs(BaseModel):
    query: str
    max_results: int = 5


def _ensure_browser():
    global _browser, _context
    if _browser:
        return _browser, _context
    try:
        from playwright.sync_api import sync_playwright

        pw = sync_playwright().start()
        _browser = pw.chromium.launch(headless=True)
        _context = _browser.new_context()
        return _browser, _context
    except Exception as e:
        logger.warning(f"playwright no disponible: {e}")
        return None, None


def _fetch_url(a: FetchArgs) -> ToolResult:
    browser, ctx = _ensure_browser()
    if not browser:
        return ToolResult(ok=False, message="playwright no instalado. Ejecuta 'playwright install chromium'.")
    try:
        page = ctx.new_page()
        page.goto(a.url, timeout=a.timeout_ms)
        page.wait_for_load_state("domcontentloaded", timeout=a.timeout_ms)
        try:
            text = page.locator(a.selector).first.inner_text(timeout=5000)
        except Exception:
            text = page.content()[:6000]
        page.close()
        return ToolResult(ok=True, message=f"fetched {len(text)} chars", data=text[:6000])
    except Exception as e:
        return ToolResult(ok=False, message=str(e))


def _web_search(a: SearchArgs) -> ToolResult:
    browser, ctx = _ensure_browser()
    if not browser:
        return ToolResult(ok=False, message="playwright no instalado.")
    try:
        page = ctx.new_page()
        page.goto(f"https://duckduckgo.com/?q={a.query}&kl=es-cl", timeout=15000)
        page.wait_for_selector("[data-testid='result']", timeout=10000)
        items = page.locator("[data-testid='result']").all()[: a.max_results]
        results = []
        for it in items:
            try:
                title = it.locator("h2").inner_text(timeout=2000)
                snippet = it.locator("span").first.inner_text(timeout=2000)
                results.append(f"• {title.strip()} — {snippet.strip()[:160]}")
            except Exception:
                continue
        page.close()
        text = "\n".join(results) if results else "(sin resultados)"
        return ToolResult(ok=True, message=f"{len(results)} resultados", data=text)
    except Exception as e:
        return ToolResult(ok=False, message=str(e))


def register_web_tools(r: ToolRegistry) -> None:
    r.register(Tool("fetch_url", "Descarga contenido de una URL (texto)", FetchArgs, _fetch_url))
    r.register(Tool("web_search", "Busca en la web vía DuckDuckGo", SearchArgs, _web_search))

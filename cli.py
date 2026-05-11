"""CLI de texto para depurar/demostrar Jarvan sin micrófono ni audio.

Útil cuando:
- Estás probando en un equipo sin mic.
- Quieres iterar rápido sobre el agente, planner o tools.
- Vas a presentar y prefieres texto a voz.

Uso:
    python cli.py
    >>> abre el bloc de notas y escribe hola
"""
from __future__ import annotations

import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from core.agent import JarvanAgent
from core.health import check_health
from core.llm_client import OllamaClient
from core.logger import logger

console = Console()


def main() -> int:
    console.print(Panel.fit("[bold cyan]JARVAN CLI[/bold cyan] — modo texto", border_style="cyan"))
    llm = OllamaClient()
    health = check_health(llm)
    console.print(health.render(), style="dim")
    if not health.ollama_up:
        console.print("[red]Ollama no responde — abortando.[/red]")
        return 1

    agent = JarvanAgent(
        llm=llm,
        on_confirm=lambda step: True,
        on_token=lambda t: console.print(t, end="", style="white"),
        on_status=lambda s: logger.debug(f"status: {s}"),
    )

    while True:
        try:
            user = Prompt.ask("\n[bold green]tú[/bold green]")
        except (KeyboardInterrupt, EOFError):
            console.print("\nadiós.")
            return 0
        if not user.strip():
            continue
        if user.strip().lower() in {"salir", "exit", "quit", ":q"}:
            return 0
        reply = agent.handle(user)
        console.print()
        console.print(Panel(reply, title="jarvan", border_style="cyan"))


if __name__ == "__main__":
    sys.exit(main())

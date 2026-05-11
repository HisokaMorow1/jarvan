"""SystemContext: inyecta estado del SO en cada turno del agente.

Lo que Jarvis "sabe sin preguntar": hora, día, foreground window, baterías,
volumen, modelos disponibles, apps abiertas. Esto va al prompt del planner y
del responder para que no gaste pasos averiguándolo.
"""
from __future__ import annotations

import locale
import platform
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

try:
    import psutil
except Exception:
    psutil = None

try:
    import pygetwindow as gw
except Exception:
    gw = None


@dataclass
class SystemContext:
    now_iso: str = ""
    weekday_es: str = ""
    user: str = ""
    host: str = ""
    os: str = ""
    foreground_window: str = ""
    open_windows: List[str] = field(default_factory=list)
    battery_pct: Optional[float] = None
    battery_plugged: Optional[bool] = None
    cpu_pct: float = 0.0
    ram_pct: float = 0.0

    def render(self) -> str:
        lines = [
            f"Hora local: {self.now_iso} ({self.weekday_es})",
            f"Usuario: {self.user} en {self.host} ({self.os})",
        ]
        if self.foreground_window:
            lines.append(f"Ventana activa: {self.foreground_window}")
        if self.open_windows:
            short = self.open_windows[:6]
            lines.append("Ventanas abiertas: " + " | ".join(short))
        if self.battery_pct is not None:
            bat = f"{self.battery_pct:.0f}%"
            bat += " enchufado" if self.battery_plugged else " batería"
            lines.append(f"Energía: {bat}")
        lines.append(f"Carga: CPU {self.cpu_pct:.0f}% RAM {self.ram_pct:.0f}%")
        return "\n".join(lines)


_ES_WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def gather() -> SystemContext:
    import os as _os

    now = datetime.now()
    ctx = SystemContext(
        now_iso=now.strftime("%Y-%m-%d %H:%M"),
        weekday_es=_ES_WEEKDAYS[now.weekday()],
        user=_os.environ.get("USERNAME") or _os.environ.get("USER") or "usuario",
        host=platform.node(),
        os=f"{platform.system()} {platform.release()}",
    )

    if gw:
        try:
            active = gw.getActiveWindow()
            if active and active.title:
                ctx.foreground_window = active.title
            ctx.open_windows = [w.title for w in gw.getAllWindows() if w.title][:20]
        except Exception:
            pass

    if psutil:
        try:
            bat = psutil.sensors_battery()
            if bat:
                ctx.battery_pct = bat.percent
                ctx.battery_plugged = bat.power_plugged
        except Exception:
            pass
        try:
            ctx.cpu_pct = psutil.cpu_percent(interval=None)
            ctx.ram_pct = psutil.virtual_memory().percent
        except Exception:
            pass

    return ctx


def greeting() -> str:
    """Saludo contextual estilo Jarvis al iniciar."""
    h = datetime.now().hour
    if h < 6:
        return "Buenas noches. Sistemas operativos. ¿En qué puedo asistirte?"
    if h < 12:
        return "Buenos días. Núcleo Ollama en línea. A tu disposición."
    if h < 19:
        return "Buenas tardes. Todos los sistemas listos. ¿En qué te asisto?"
    return "Buenas noches. Jarvan operativo. A la orden."

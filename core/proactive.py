"""Proactividad: Jarvan habla solo cuando detecta algo que merece comentario.

Reglas:
- Batería bajando de umbral crítico.
- Inactividad larga + saludo amistoso ocasional.
- Hora redonda (al cambiar de hora, opcional).
- VRAM cerca del límite.

Diseño anti-molestia: cada regla tiene cooldown propio y máximo de avisos por sesión.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Dict, Optional

from core.logger import logger
from core.system_context import gather as gather_ctx


@dataclass
class Rule:
    name: str
    cooldown_s: float
    max_per_session: int
    last_fired: float = 0.0
    fires: int = 0

    def can_fire(self) -> bool:
        if self.fires >= self.max_per_session:
            return False
        return (time.time() - self.last_fired) >= self.cooldown_s

    def mark(self) -> None:
        self.last_fired = time.time()
        self.fires += 1


class Proactive:
    def __init__(self, on_announce: Callable[[str], None], interval_s: float = 60.0) -> None:
        self.on_announce = on_announce
        self.interval = interval_s
        self._running = False
        self._thread = None
        self.rules: Dict[str, Rule] = {
            "battery_low": Rule("battery_low", cooldown_s=600, max_per_session=3),
            "battery_critical": Rule("battery_critical", cooldown_s=300, max_per_session=5),
            "vram_high": Rule("vram_high", cooldown_s=900, max_per_session=2),
            "idle_chat": Rule("idle_chat", cooldown_s=1800, max_per_session=2),
        }
        self._last_user_activity = time.time()

    def mark_user_activity(self) -> None:
        self._last_user_activity = time.time()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        import threading

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _run(self) -> None:
        while self._running:
            time.sleep(self.interval)
            try:
                self._tick()
            except Exception as e:
                logger.debug(f"proactive tick: {e}")

    def _tick(self) -> None:
        ctx = gather_ctx()
        if ctx.battery_pct is not None and not ctx.battery_plugged:
            if ctx.battery_pct < 10 and self.rules["battery_critical"].can_fire():
                self.rules["battery_critical"].mark()
                self._fire(f"Señor, batería al {ctx.battery_pct:.0f}%. Recomiendo conectar el cargador.")
                return
            if ctx.battery_pct < 20 and self.rules["battery_low"].can_fire():
                self.rules["battery_low"].mark()
                self._fire(f"Aviso: batería al {ctx.battery_pct:.0f}%.")
                return

        if ctx.ram_pct > 90 and self.rules["vram_high"].can_fire():
            self.rules["vram_high"].mark()
            self._fire(f"Memoria del sistema al {ctx.ram_pct:.0f}%, señor.")
            return

        idle_s = time.time() - self._last_user_activity
        if idle_s > 1800 and self.rules["idle_chat"].can_fire():
            self.rules["idle_chat"].mark()
            self._fire("Sigo aquí, señor. A su disposición cuando me necesite.")

    def _fire(self, text: str) -> None:
        logger.info(f"proactive: {text}")
        try:
            self.on_announce(text)
        except Exception:
            pass

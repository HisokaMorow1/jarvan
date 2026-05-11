"""Filler talk: frases cortas que Jarvan dice mientras procesa.

Jarvis nunca está mudo: si tarda en pensar, dice "Analizando, señor..." o
"Un momento" para que el silencio no rompa la inmersión.

Reglas:
  - Solo se dispara si el estado THINKING dura > 1.5s.
  - Una sola vez por turno.
  - Cooldown de 8s para no repetirse.
  - Selección aleatoria con sesgo a frases cortas.
"""
from __future__ import annotations

import random
import threading
import time
from typing import Callable, Optional


FILLERS_THINKING = [
    "Procesando, señor.",
    "Un momento.",
    "Analizando.",
    "Consultando el sistema.",
    "Calibrando.",
    "Verificando.",
    "Casi listo.",
]

FILLERS_PLANNING = [
    "Trazando el plan, señor.",
    "Organizando los pasos.",
    "Diseñando ejecución.",
    "Un instante, planificando.",
]

FILLERS_EXECUTING = [
    "En ello, señor.",
    "Ejecutando.",
    "Procediendo.",
]


class Filler:
    """Dispara filler talk si la operación tarda más que `delay_s`."""

    def __init__(
        self,
        on_say: Callable[[str], None],
        delay_s: float = 1.5,
        cooldown_s: float = 8.0,
    ) -> None:
        self.on_say = on_say
        self.delay_s = delay_s
        self.cooldown_s = cooldown_s
        self._last_fire = 0.0
        self._timer: Optional[threading.Timer] = None

    def arm(self, category: str = "thinking") -> None:
        self.disarm()
        if (time.time() - self._last_fire) < self.cooldown_s:
            return

        def _fire():
            self._last_fire = time.time()
            pool = {
                "thinking": FILLERS_THINKING,
                "planning": FILLERS_PLANNING,
                "executing": FILLERS_EXECUTING,
            }.get(category, FILLERS_THINKING)
            try:
                self.on_say(random.choice(pool))
            except Exception:
                pass

        self._timer = threading.Timer(self.delay_s, _fire)
        self._timer.daemon = True
        self._timer.start()

    def disarm(self) -> None:
        if self._timer:
            try:
                self._timer.cancel()
            except Exception:
                pass
            self._timer = None

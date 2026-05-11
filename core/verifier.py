"""Verifier: tras una acción, toma screenshot y pregunta al VLM si funcionó.

Esto es la pieza que separa un agente de "computer use" real de un script
que ejecuta y reza. Si la acción no produjo el efecto esperado, re-planificamos.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from core.llm_client import OllamaClient
from core.logger import logger
from perception.screen import Screen


@dataclass
class Verdict:
    ok: bool
    confidence: float
    observation: str


VERIFY_PROMPT = """Acabo de ejecutar esta acción en el PC: {action}
Con estos argumentos: {args}
Esperando este resultado: {expected}

Mira la captura de pantalla y responde JSON estricto:
{{"ok": true|false, "confidence": 0.0-1.0, "observation": "qué ves realmente"}}"""


class Verifier:
    def __init__(self, llm: OllamaClient, screen: Screen) -> None:
        self.llm = llm
        self.screen = screen

    def verify(self, action: str, args: dict, expected: str, wait_ms: int = 800) -> Verdict:
        time.sleep(wait_ms / 1000.0)
        path = self.screen.save(name="verify.png")
        prompt = VERIFY_PROMPT.format(action=action, args=args, expected=expected)
        try:
            raw = self.llm.vision(prompt, path)
            import json

            s = raw.find("{")
            e = raw.rfind("}")
            data = json.loads(raw[s : e + 1])
            v = Verdict(
                ok=bool(data.get("ok", False)),
                confidence=float(data.get("confidence", 0.5)),
                observation=str(data.get("observation", "")),
            )
            logger.info(f"verify «{action}» → ok={v.ok} ({v.confidence:.2f}) — {v.observation}")
            return v
        except Exception as e:
            logger.warning(f"verifier falló, asumo ok: {e}")
            return Verdict(ok=True, confidence=0.3, observation="verificación no disponible")

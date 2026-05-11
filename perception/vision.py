"""VisionEngine: interpreta una pantalla con el VLM (qwen2.5-vl).

Saca semántica de la UI: qué app está abierta, qué elementos hay, dónde están.
Devuelve descripciones de alto nivel para que el agente decida.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from config import settings
from core.llm_client import OllamaClient
from core.logger import logger
from perception.screen import Screen


VLM_DESCRIBE = """Analiza esta captura de pantalla del escritorio del usuario.
Responde en español, breve y estructurado:
1. Aplicación o ventana activa.
2. Elementos UI relevantes visibles (botones, campos, menús).
3. Qué está haciendo el usuario aparentemente.
4. Acciones obvias disponibles."""


VLM_LOCATE = """En esta captura de pantalla, ubica el elemento descrito por el usuario.
Devuelve un JSON con: {{"found": bool, "description": "...", "approx_region": "centro|arriba|abajo|izq|der|esq_sup_der|..."}}.
Elemento a ubicar: {target}"""


@dataclass
class SceneDescription:
    app: str = ""
    elements: List[str] = None
    activity: str = ""
    raw: str = ""


class VisionEngine:
    def __init__(self, llm: OllamaClient, screen: Optional[Screen] = None) -> None:
        self.llm = llm
        self.screen = screen or Screen()

    def describe_screen(self, save_as: str = "vision.png") -> SceneDescription:
        img_path = self.screen.save(name=save_as)
        text = self.llm.vision(VLM_DESCRIBE, img_path)
        logger.debug(f"VLM dijo: {text[:200]}...")
        return SceneDescription(raw=text, elements=[])

    def locate(self, target: str, save_as: str = "locate.png") -> dict:
        img_path = self.screen.save(name=save_as)
        prompt = VLM_LOCATE.format(target=target)
        text = self.llm.vision(prompt, img_path)
        import json

        try:
            start = text.find("{")
            end = text.rfind("}")
            return json.loads(text[start : end + 1]) if start >= 0 else {"found": False}
        except Exception:
            return {"found": False, "description": text}

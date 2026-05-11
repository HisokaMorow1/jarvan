"""Aprendizaje automático de preferencias del usuario.

Después de cada turno, el LLM clasifica si lo que dijo el usuario revela una
preferencia estable (apps preferidas, formato de respuesta, idioma, horarios).
Si la confianza es alta, se guarda como `fact` en memoria de largo plazo.
"""
from __future__ import annotations

import json
from typing import Optional

from config import settings
from core.llm_client import OllamaClient
from core.logger import logger
from core.memory.long_term import LongTermMemory


EXTRACTOR_SYSTEM = """Eres un extractor de preferencias del usuario.
Analiza el mensaje del usuario y decide si revela una preferencia ESTABLE
(no algo de un solo uso). Ejemplos de preferencias estables:
- "siempre prefiero brave sobre chrome"
- "me llamo Claudio"
- "responde más corto"
- "me gusta el rock"
- "trabajo en horario nocturno"

NO son preferencias estables:
- "abre chrome ahora"
- "qué hora es"
- saludos, preguntas únicas

Devuelve SOLO JSON: {"is_preference": bool, "key": "string corto", "value": "string", "confidence": 0.0-1.0}"""


class PreferenceLearner:
    def __init__(self, llm: OllamaClient, memory: LongTermMemory) -> None:
        self.llm = llm
        self.memory = memory

    def observe(self, user_text: str) -> Optional[str]:
        try:
            msgs = [
                {"role": "system", "content": EXTRACTOR_SYSTEM},
                {"role": "user", "content": user_text},
            ]
            raw = self.llm.chat(
                msgs, model=settings.llm.router_model, format_json=True, temperature=0.0
            )
            s = raw.find("{")
            e = raw.rfind("}")
            data = json.loads(raw[s : e + 1])
            if not data.get("is_preference"):
                return None
            if float(data.get("confidence", 0)) < 0.7:
                return None
            key = data["key"].strip().lower().replace(" ", "_")[:48]
            value = data["value"].strip()[:200]
            self.memory.remember_fact(key, value)
            logger.info(f"preferencia aprendida: {key} = {value}")
            return key
        except Exception as e:
            logger.debug(f"learner: {e}")
            return None

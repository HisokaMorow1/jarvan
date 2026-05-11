"""Router: decide rápidamente si un input necesita planner o respuesta directa.

Evita invocar al planner de 30B para preguntas triviales ("hola", "qué hora es",
"cómo estás"). Usa el modelo rápido para clasificar.
"""
from __future__ import annotations

import re
from enum import Enum

from config import settings
from core.llm_client import OllamaClient
from core.logger import logger


class Intent(Enum):
    CHAT = "chat"
    TASK = "task"
    SYSTEM_QUERY = "system_query"


_ACTION_HINTS = re.compile(
    r"\b(abre|abrir|cierra|cerrar|busca|buscar|crea|crear|escribe|escribir|"
    r"haz|ejecuta|ejecutar|click|clic|copia|copiar|pega|pegar|guarda|guardar|"
    r"toma|captura|screenshot|reproduce|silencia|sube|baja|volumen|brillo|"
    r"apaga|reinicia|descarga|envia|enviar)\b",
    re.IGNORECASE,
)

_QUERY_HINTS = re.compile(
    r"\b(qué hora|que hora|qué día|que dia|qué ventana|que ventana|"
    r"cuál es|cual es|cuánto|cuanto|batería|bateria|cpu|ram|gpu|memoria)\b",
    re.IGNORECASE,
)


class Router:
    def __init__(self, llm: OllamaClient) -> None:
        self.llm = llm

    def classify(self, text: str) -> Intent:
        t = text.strip().lower()
        if len(t) < 3:
            return Intent.CHAT
        if _QUERY_HINTS.search(t):
            return Intent.SYSTEM_QUERY
        if _ACTION_HINTS.search(t):
            return Intent.TASK
        if "?" in t and len(t) < 80:
            return Intent.CHAT
        intent = self._classify_llm(text)
        logger.debug(f"router LLM → {intent}")
        return intent

    def _classify_llm(self, text: str) -> Intent:
        msgs = [
            {
                "role": "system",
                "content": (
                    "Clasifica el mensaje del usuario en una sola palabra: "
                    "chat, task, o system_query. "
                    "chat = saludo/conversación/pregunta general. "
                    "task = pide ejecutar acción en el PC. "
                    "system_query = pregunta sobre el estado del PC. "
                    "Responde SOLO la palabra."
                ),
            },
            {"role": "user", "content": text},
        ]
        try:
            out = self.llm.chat(msgs, model=settings.llm.router_model, temperature=0.0).strip().lower()
            if "task" in out:
                return Intent.TASK
            if "system" in out:
                return Intent.SYSTEM_QUERY
            return Intent.CHAT
        except Exception:
            return Intent.CHAT

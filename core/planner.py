"""Planner: descompone un objetivo del usuario en pasos accionables.

Patrón Plan-and-Execute con replanning. El planner NO ejecuta — solo planifica.
Recibe contexto del sistema y opcionalmente el error del intento anterior para
replanificar con conocimiento del fallo.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from config import settings
from core.llm_client import OllamaClient
from core.logger import logger


PLANNER_SYSTEM = """Eres el módulo planificador de Jarvan, un asistente local que controla Windows.
Tu rol: descomponer el objetivo del usuario en una secuencia mínima de pasos atómicos.

Principios:
- Cada paso es UNA acción concreta ejecutable por una herramienta del catálogo.
- Si necesitas ver la pantalla para decidir, incluye un paso "observe" antes.
- Si la tarea es destructiva (borrar archivos, apagar, shell), marca needs_confirmation=true.
- Si una acción podría no surtir efecto (click_text, type_text, hotkey), añade verify=true.
- Aprovecha el CONTEXTO DEL SISTEMA: ya conoces hora, ventana activa, apps abiertas.
- Si el objetivo es trivial o conversacional, devuelve steps vacíos.

Devuelve SOLO JSON válido con este esquema (sin texto extra):

{
  "goal": "string — reformulación breve del objetivo",
  "reasoning": "string — 1-2 frases del razonamiento",
  "steps": [
    {
      "id": 1,
      "action": "nombre_de_tool",
      "args": { "...": "..." },
      "rationale": "string corto",
      "expected": "string — qué espero observar tras esta acción",
      "needs_confirmation": false,
      "verify": false
    }
  ]
}

Catálogo de herramientas:
{tools}
"""


class PlanStep(BaseModel):
    id: int
    action: str
    args: dict = Field(default_factory=dict)
    rationale: str = ""
    expected: str = ""
    needs_confirmation: bool = False
    verify: bool = False


class Plan(BaseModel):
    goal: str
    reasoning: str = ""
    steps: List[PlanStep]


class Planner:
    def __init__(self, llm: OllamaClient, available_tools, registry=None) -> None:
        self.llm = llm
        self.tools = available_tools
        self.registry = registry

    def plan(
        self,
        user_goal: str,
        context: Optional[str] = None,
        prior_failure: Optional[str] = None,
    ) -> Plan:
        if self.registry is not None:
            tool_block = self.registry.describe()
        else:
            tool_block = ", ".join(self.tools)
        system = PLANNER_SYSTEM.replace("{tools}", tool_block)
        user_block = [f"Objetivo: {user_goal}"]
        if context:
            user_block.append(f"\nContexto:\n{context}")
        if prior_failure:
            user_block.append(
                f"\nINTENTO ANTERIOR FALLÓ:\n{prior_failure}\nReplanifica evitando ese error."
            )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": "\n".join(user_block)},
        ]
        raw = self.llm.chat_json(messages, model=settings.llm.planner_model)
        plan = Plan(**raw)
        logger.info(f"Plan: {len(plan.steps)} pasos — «{plan.goal}»")
        for s in plan.steps:
            logger.debug(f"  {s.id}. {s.action} {s.args} → esperado: {s.expected}")
        return plan

"""Orquestador principal de Jarvan.

Pipeline por turno:
  1. SystemContext.gather()   — hora, ventana activa, apps abiertas, batería.
  2. Router.classify(text)    — chat | task | system_query.
  3a. chat → respuesta directa streaming.
  3b. system_query → respuesta determinista con datos del SystemContext.
  3c. task → Planner → Executor (con Verifier) → Replanning si falla → narración.
  4. Memoria a corto y largo plazo, con embeddings.

Esto es lo que distingue al agente real del chatbot con tools:
- Replanning automático con conocimiento del error y screenshot.
- Verificación post-acción vía VLM.
- Contexto del sistema inyectado sin gastar pasos.
- Routing por intención para no quemar el modelo grande en saludos.
"""
from __future__ import annotations

from typing import Callable, Optional

from config import settings
from core.executor import Executor, ExecutionTrace
from core.llm_client import OllamaClient
from core.logger import logger
from core.memory.short_term import ShortTermMemory
from core.memory.long_term import LongTermMemory
from core.planner import Planner
from core.preferences import PreferenceLearner
from core.router import Intent, Router
from core.system_context import SystemContext, gather as gather_ctx
from core.verifier import Verifier
from perception.screen import Screen
from tools.registry import ToolRegistry


SYSTEM_PERSONA = """Eres Jarvan, un asistente local en español, modelado en Jarvis de Iron Man.
Voz: profesional, cercana, levemente formal, con calma incluso bajo presión.
Reglas:
- Respondes BREVE: 1-2 frases salvo que pidan explicación.
- Te diriges al usuario como "señor" o por su nombre si lo conoces.
- Confirmas acciones completadas en una frase: "Listo, señor. Chrome abierto."
- Si algo falla, lo dices con calma y propones alternativa.
- Conoces el estado del sistema (hora, ventanas, batería) sin que te pregunten.
- Nunca usas emojis. Nunca te disculpas en exceso. Nunca explicas tu razonamiento interno."""

MAX_REPLANS = 2


class JarvanAgent:
    def __init__(
        self,
        llm: Optional[OllamaClient] = None,
        registry: Optional[ToolRegistry] = None,
        on_confirm: Optional[Callable] = None,
        on_token: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.llm = llm or OllamaClient()
        self.registry = registry or ToolRegistry.default()
        self.screen = Screen()
        self.verifier = Verifier(self.llm, self.screen)
        self.planner = Planner(self.llm, available_tools=self.registry.names(), registry=self.registry)
        self.executor = Executor(self.registry, verifier=self.verifier)
        self.router = Router(self.llm)
        self.short = ShortTermMemory(window=settings.memory.short_term_window)
        self.long = LongTermMemory(self.llm)
        self.learner = PreferenceLearner(self.llm, self.long)
        self.on_confirm = on_confirm
        self.on_token = on_token
        self.on_status = on_status or (lambda s: None)

    def handle(self, user_text: str) -> str:
        logger.info(f"USUARIO: {user_text}")
        self.short.add("user", user_text)

        try:
            self.learner.observe(user_text)
        except Exception:
            pass

        self.on_status("analizando")
        sys_ctx = gather_ctx()
        intent = self.router.classify(user_text)
        logger.info(f"intent = {intent.value}")

        if intent == Intent.CHAT:
            return self._reply(self._chat(user_text, sys_ctx))
        if intent == Intent.SYSTEM_QUERY:
            return self._reply(self._system_answer(user_text, sys_ctx))
        return self._reply(self._task(user_text, sys_ctx))

    def _chat(self, user_text: str, sys_ctx: SystemContext) -> str:
        self.on_status("respondiendo")
        recall = self.long.recall(user_text, k=3)
        context = self._build_context(sys_ctx, recall)
        msgs = [
            {"role": "system", "content": SYSTEM_PERSONA},
            {"role": "system", "content": f"Contexto:\n{context}"},
            {"role": "user", "content": user_text},
        ]
        if self.on_token:
            return self.llm.chat_stream(msgs, model=settings.llm.router_model, on_token=self.on_token).strip()
        return self.llm.chat(msgs, model=settings.llm.router_model).strip()

    def _system_answer(self, user_text: str, sys_ctx: SystemContext) -> str:
        """Respuestas con datos del SO directamente, sin pasar por tools."""
        self.on_status("consultando sistema")
        msgs = [
            {"role": "system", "content": SYSTEM_PERSONA},
            {
                "role": "system",
                "content": f"Datos actuales del sistema:\n{sys_ctx.render()}",
            },
            {"role": "user", "content": user_text},
        ]
        if self.on_token:
            return self.llm.chat_stream(msgs, model=settings.llm.router_model, on_token=self.on_token).strip()
        return self.llm.chat(msgs, model=settings.llm.router_model).strip()

    def _task(self, user_text: str, sys_ctx: SystemContext) -> str:
        self.on_status("planificando")
        recall = self.long.recall(user_text, k=3)
        context = self._build_context(sys_ctx, recall)

        prior_failure: Optional[str] = None
        last_trace: Optional[ExecutionTrace] = None

        for attempt in range(1, MAX_REPLANS + 2):
            try:
                plan = self.planner.plan(user_text, context=context, prior_failure=prior_failure)
            except Exception as e:
                logger.exception("Error planificando")
                return f"No pude planificar la tarea: {e}"

            if not plan.steps:
                return self._chat(user_text, sys_ctx)

            self.on_status(f"ejecutando {len(plan.steps)} pasos (intento {attempt})")
            trace = self.executor.run(
                plan, on_confirm=self.on_confirm, on_step=self._on_step_progress
            )
            last_trace = trace

            if trace.success:
                self.long.remember_task(plan.goal, trace.summary(), success=True)
                return self._narrate_success(trace)

            prior_failure = trace.failure_reason or trace.summary()
            logger.warning(f"replanning ({attempt}/{MAX_REPLANS}): {prior_failure}")
            self.on_status(f"replanificando ({attempt})")

        if last_trace:
            self.long.remember_task(last_trace.goal, last_trace.summary(), success=False)
            return self._narrate_failure(last_trace)
        return "No pude completar la tarea tras varios intentos."

    def _on_step_progress(self, step, attempt: int) -> None:
        self.on_status(f"paso {step.id}: {step.action}")

    def _build_context(self, sys_ctx: SystemContext, recall) -> str:
        parts = ["[ESTADO DEL SISTEMA]", sys_ctx.render()]
        if recall:
            parts.append("\n[MEMORIA RELEVANTE]")
            parts.extend(f"- {r}" for r in recall)
        history = self.short.render()
        if history:
            parts.append("\n[CONVERSACIÓN RECIENTE]")
            parts.append(history)
        return "\n".join(parts)

    def _narrate_success(self, trace: ExecutionTrace) -> str:
        verbs = [o.step.action.replace("_", " ") for o in trace.outcomes]
        if len(verbs) == 1:
            return f"Listo, señor. {verbs[0].capitalize()} completado."
        return f"Listo, señor. Ejecuté: {', '.join(verbs)}."

    def _narrate_failure(self, trace: ExecutionTrace) -> str:
        failed = next((o for o in trace.outcomes if not o.result.ok), None)
        if failed:
            return (
                f"No conseguí completar la tarea. Falló «{failed.step.action}»: "
                f"{failed.result.message}. ¿Lo intentamos de otra forma, señor?"
            )
        return "La tarea no se completó por completo, señor."

    def _reply(self, text: str) -> str:
        self.short.add("assistant", text)
        logger.info(f"JARVAN: {text}")
        return text

    def remember_preference(self, key: str, value: str) -> None:
        self.long.remember_fact(key, value)

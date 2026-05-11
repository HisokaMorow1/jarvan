"""Executor con verificación post-acción y soporte para replanning.

Diferencia clave vs un script de tools: tras pasos marcados verify=true, pregunta
al VLM si la acción tuvo el efecto esperado. Si no, el agente puede replanificar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from config import settings
from core.logger import logger
from core.planner import Plan, PlanStep
from tools.registry import ToolRegistry, ToolResult


@dataclass
class StepOutcome:
    step: PlanStep
    result: ToolResult
    attempts: int = 1
    verified: Optional[bool] = None
    observation: str = ""


@dataclass
class ExecutionTrace:
    goal: str
    outcomes: List[StepOutcome] = field(default_factory=list)
    success: bool = False
    failure_reason: str = ""

    def summary(self) -> str:
        lines = [f"Objetivo: {self.goal}", f"Éxito: {self.success}"]
        for o in self.outcomes:
            tag = "OK" if o.result.ok else "FAIL"
            if o.verified is False:
                tag = "OK-pero-no-verificado"
            lines.append(
                f"  [{o.step.id}] {o.step.action}({o.step.args}) → {tag} "
                f"({o.attempts} intentos) {o.result.message}"
                + (f" | obs: {o.observation}" if o.observation else "")
            )
        if self.failure_reason:
            lines.append(f"Razón: {self.failure_reason}")
        return "\n".join(lines)


class Executor:
    def __init__(self, registry: ToolRegistry, verifier=None) -> None:
        self.registry = registry
        self.verifier = verifier
        self.max_retries = settings.agent.max_retries_per_step
        self.confirm_actions = set(settings.agent.require_confirmation_for)

    def run(
        self,
        plan: Plan,
        on_confirm: Optional[Callable] = None,
        on_step: Optional[Callable] = None,
    ) -> ExecutionTrace:
        trace = ExecutionTrace(goal=plan.goal)
        for step in plan.steps:
            if step.needs_confirmation or step.action in self.confirm_actions:
                if on_confirm and not on_confirm(step):
                    logger.warning(f"Paso {step.id} cancelado por usuario")
                    trace.outcomes.append(
                        StepOutcome(step, ToolResult(ok=False, message="cancelado"))
                    )
                    trace.failure_reason = "cancelado por usuario"
                    return trace

            outcome = self._run_step(step, on_step)
            trace.outcomes.append(outcome)
            if not outcome.result.ok:
                trace.failure_reason = (
                    f"paso «{step.action}» falló: {outcome.result.message}"
                )
                return trace

            if step.verify and self.verifier:
                verdict = self.verifier.verify(step.action, step.args, step.expected)
                outcome.verified = verdict.ok
                outcome.observation = verdict.observation
                if not verdict.ok and verdict.confidence > 0.6:
                    trace.failure_reason = (
                        f"verificación falló en paso «{step.action}»: {verdict.observation}"
                    )
                    return trace

        trace.success = True
        return trace

    def _run_step(self, step: PlanStep, on_step: Optional[Callable]) -> StepOutcome:
        attempts = 0
        last: ToolResult = ToolResult(ok=False, message="no ejecutado")
        while attempts < self.max_retries:
            attempts += 1
            if on_step:
                try:
                    on_step(step, attempts)
                except Exception:
                    pass
            logger.info(f"→ [{step.id}] {step.action}({step.args}) intento {attempts}")
            try:
                last = self.registry.invoke(step.action, **step.args)
                if last.ok:
                    return StepOutcome(step, last, attempts)
                logger.warning(f"   resultado: {last.message}")
            except Exception as e:
                logger.exception(f"   excepción: {e}")
                last = ToolResult(ok=False, message=str(e))
        return StepOutcome(step, last, attempts)

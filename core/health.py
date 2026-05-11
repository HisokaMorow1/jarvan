"""Comprueba el estado del 'servidor' de IA local (Ollama) y modelos requeridos."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from config import settings
from core.llm_client import OllamaClient
from core.logger import logger


@dataclass
class HealthReport:
    ollama_up: bool
    models_present: List[str]
    models_missing: List[str]

    @property
    def ready(self) -> bool:
        return self.ollama_up and not self.models_missing

    def render(self) -> str:
        lines = [f"Ollama: {'OK' if self.ollama_up else 'OFFLINE'} @ {settings.llm.base_url}"]
        if self.models_present:
            lines.append("Modelos disponibles: " + ", ".join(self.models_present))
        if self.models_missing:
            lines.append("FALTAN modelos: " + ", ".join(self.models_missing))
            lines.append("Ejecuta:")
            for m in self.models_missing:
                lines.append(f"  ollama pull {m}")
        return "\n".join(lines)


REQUIRED_MODELS = [
    settings.llm.planner_model,
    settings.llm.router_model,
    settings.llm.vision_model,
    settings.llm.embed_model,
]


def check_health(llm: OllamaClient | None = None) -> HealthReport:
    llm = llm or OllamaClient()
    up = llm.ping()
    if not up:
        return HealthReport(False, [], REQUIRED_MODELS)
    available = llm.list_models()
    norm_av = {m.split(":")[0]: m for m in available}
    norm_av_full = set(available)
    present, missing = [], []
    for req in REQUIRED_MODELS:
        if req in norm_av_full or req.split(":")[0] in norm_av:
            present.append(req)
        else:
            missing.append(req)
    report = HealthReport(True, present, missing)
    logger.info(report.render())
    return report

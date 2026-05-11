"""Tool Registry: registro central de herramientas con validación pydantic.

Cada Tool tiene: nombre, descripción, esquema de args, función handler.
El registry expone:
- register(tool)
- invoke(name, **kwargs) → ToolResult
- names() → lista para el planner
- spec() → esquema JSON para el LLM
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type

from pydantic import BaseModel, ValidationError

from core.logger import logger


@dataclass
class ToolResult:
    ok: bool
    message: str = ""
    data: Any = None


@dataclass
class Tool:
    name: str
    description: str
    args_model: Optional[Type[BaseModel]]
    handler: Callable[..., ToolResult]
    danger: bool = False


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            logger.warning(f"Tool sobrescrita: {tool.name}")
        self._tools[tool.name] = tool

    def names(self) -> List[str]:
        return sorted(self._tools.keys())

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def spec(self) -> List[Dict[str, Any]]:
        out = []
        for t in self._tools.values():
            schema = t.args_model.model_json_schema() if t.args_model else {}
            out.append({"name": t.name, "description": t.description, "args": schema, "danger": t.danger})
        return out

    def invoke(self, name: str, **kwargs) -> ToolResult:
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(ok=False, message=f"tool desconocida: {name}")
        try:
            if tool.args_model:
                args = tool.args_model(**kwargs)
                return tool.handler(args)
            return tool.handler(**kwargs)
        except ValidationError as e:
            return ToolResult(ok=False, message=f"args inválidos: {e}")
        except Exception as e:
            logger.exception(f"Error ejecutando {name}")
            return ToolResult(ok=False, message=str(e))

    def describe(self) -> str:
        """Catálogo amigable para inyectar en el prompt del planner."""
        lines = []
        for t in self._tools.values():
            schema = t.args_model.model_json_schema() if t.args_model else {"properties": {}}
            props = schema.get("properties", {})
            args = ", ".join(
                f"{k}: {v.get('type', 'any')}" for k, v in props.items()
            ) or "—"
            tag = " [DANGER]" if t.danger else ""
            lines.append(f"- {t.name}({args}){tag}  — {t.description}")
        return "\n".join(lines)

    @classmethod
    def default(cls) -> "ToolRegistry":
        from tools.builtin import register_builtins
        from tools.system_tools import register_system_tools
        from tools.file_tools import register_file_tools
        from tools.media_tools import register_media_tools
        from tools.web_tools import register_web_tools

        r = cls()
        register_builtins(r)
        register_system_tools(r)
        register_file_tools(r)
        register_media_tools(r)
        register_web_tools(r)
        logger.info(f"ToolRegistry listo: {len(r.names())} tools — {r.names()}")
        return r

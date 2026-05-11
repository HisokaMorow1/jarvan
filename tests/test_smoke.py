"""Tests de humo: cargar config, registrar tools, planner devuelve JSON."""
from __future__ import annotations

import pytest


def test_settings_load():
    from config import settings

    assert settings.app.name == "Jarvan"
    assert settings.llm.planner_model
    assert settings.memory.short_term_window > 0


def test_registry_default():
    from tools.registry import ToolRegistry

    r = ToolRegistry.default()
    names = r.names()
    for expected in ["open_app", "open_url", "click_text", "observe", "type_text"]:
        assert expected in names


def test_short_term_memory():
    from core.memory.short_term import ShortTermMemory

    m = ShortTermMemory(window=3)
    m.add("user", "hola")
    m.add("assistant", "buenas")
    m.add("user", "qué tal")
    m.add("assistant", "todo bien")
    assert len(m.turns()) == 3

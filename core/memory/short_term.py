"""Memoria de corto plazo: ring buffer de la conversación."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from time import time
from typing import Deque, List


@dataclass
class Turn:
    role: str
    content: str
    ts: float


class ShortTermMemory:
    def __init__(self, window: int = 20) -> None:
        self.window = window
        self._buf: Deque[Turn] = deque(maxlen=window)

    def add(self, role: str, content: str) -> None:
        self._buf.append(Turn(role=role, content=content, ts=time()))

    def turns(self) -> List[Turn]:
        return list(self._buf)

    def render(self) -> str:
        return "\n".join(f"{t.role}: {t.content}" for t in self._buf)

    def clear(self) -> None:
        self._buf.clear()

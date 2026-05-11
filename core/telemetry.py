"""Telemetría runtime: GPU, VRAM, CPU, RAM, latencias. Para el HUD de presentación."""
from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

try:
    import psutil
except Exception:
    psutil = None


@dataclass
class Snapshot:
    cpu: float = 0.0
    ram: float = 0.0
    gpu: float = 0.0
    vram_used_mb: float = 0.0
    vram_total_mb: float = 0.0
    gpu_temp: float = 0.0
    last_latency_ms: float = 0.0
    extras: Dict[str, str] = field(default_factory=dict)


class Telemetry:
    def __init__(self) -> None:
        self._nvidia = shutil.which("nvidia-smi")
        self._last = Snapshot()
        self._latencies: Dict[str, float] = {}

    def mark(self, key: str) -> None:
        self._latencies[key] = time.time()

    def measure(self, key: str) -> float:
        t0 = self._latencies.pop(key, None)
        if t0 is None:
            return 0.0
        ms = (time.time() - t0) * 1000.0
        self._last.last_latency_ms = ms
        return ms

    def sample(self) -> Snapshot:
        snap = Snapshot(last_latency_ms=self._last.last_latency_ms)
        if psutil:
            snap.cpu = psutil.cpu_percent(interval=None)
            snap.ram = psutil.virtual_memory().percent
        if self._nvidia:
            try:
                out = subprocess.check_output(
                    [
                        self._nvidia,
                        "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                        "--format=csv,noheader,nounits",
                    ],
                    timeout=2,
                    text=True,
                )
                line = out.strip().splitlines()[0]
                gpu, vu, vt, temp = [float(x.strip()) for x in line.split(",")]
                snap.gpu = gpu
                snap.vram_used_mb = vu
                snap.vram_total_mb = vt
                snap.gpu_temp = temp
            except Exception:
                pass
        self._last = snap
        return snap

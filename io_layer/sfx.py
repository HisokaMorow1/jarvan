"""SFX: efectos de sonido UI estilo Jarvis (boot, beep, confirm, alert).

Generamos los sonidos sintéticamente con numpy para no depender de assets
externos. Suenan limpios, "tech", al estilo del audio design de Marvel.
"""
from __future__ import annotations

import threading
from typing import Dict, Optional

import numpy as np

try:
    import sounddevice as sd
except Exception:
    sd = None

from core.logger import logger


SR = 44100


def _envelope(n: int, attack: float = 0.01, release: float = 0.15) -> np.ndarray:
    """ADSR simplificado: subida rápida, mantenimiento, caída suave."""
    env = np.ones(n)
    a = int(SR * attack)
    r = int(SR * release)
    if a > 0:
        env[:a] = np.linspace(0, 1, a)
    if r > 0 and r < n:
        env[-r:] = np.linspace(1, 0, r) ** 2
    return env


def _tone(freq: float, dur: float, vol: float = 0.25, harmonics: bool = True) -> np.ndarray:
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    wave = np.sin(2 * np.pi * freq * t)
    if harmonics:
        wave += 0.3 * np.sin(2 * np.pi * freq * 2 * t)
        wave += 0.15 * np.sin(2 * np.pi * freq * 3 * t)
        wave /= 1.45
    return (wave * _envelope(len(wave)) * vol).astype(np.float32)


def _chirp(f0: float, f1: float, dur: float, vol: float = 0.3) -> np.ndarray:
    """Barrido de frecuencia f0 → f1."""
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    freqs = np.linspace(f0, f1, len(t))
    phase = 2 * np.pi * np.cumsum(freqs) / SR
    wave = np.sin(phase) + 0.25 * np.sin(2 * phase)
    return (wave * _envelope(len(wave), attack=0.005, release=0.1) * vol).astype(np.float32)


def _noise_burst(dur: float, vol: float = 0.08, cutoff: int = 4000) -> np.ndarray:
    n = int(SR * dur)
    raw = np.random.randn(n).astype(np.float32)
    cumsum = np.cumsum(raw)
    smooth = (cumsum[cutoff:] - cumsum[:-cutoff]) / cutoff
    out = np.zeros(n, dtype=np.float32)
    out[: len(smooth)] = smooth
    return out * _envelope(n, attack=0.005, release=0.08) * vol


def _build_library() -> Dict[str, np.ndarray]:
    lib: Dict[str, np.ndarray] = {}

    boot = np.concatenate([
        _chirp(220, 880, 0.35, 0.28),
        np.zeros(int(SR * 0.05)),
        _tone(1320, 0.12, 0.22),
        np.zeros(int(SR * 0.04)),
        _tone(1760, 0.18, 0.18),
    ])
    lib["boot"] = boot

    lib["listen_start"] = np.concatenate([
        _tone(880, 0.08, 0.22),
        np.zeros(int(SR * 0.04)),
        _tone(1320, 0.10, 0.20),
    ])

    lib["listen_end"] = _tone(660, 0.08, 0.18)

    lib["confirm"] = np.concatenate([
        _tone(880, 0.06, 0.20),
        np.zeros(int(SR * 0.02)),
        _tone(1320, 0.08, 0.22),
    ])

    lib["error"] = np.concatenate([
        _tone(440, 0.10, 0.24),
        np.zeros(int(SR * 0.03)),
        _tone(330, 0.16, 0.22),
    ])

    lib["alert"] = np.concatenate([
        _tone(1500, 0.08, 0.22),
        np.zeros(int(SR * 0.04)),
        _tone(1500, 0.08, 0.22),
    ])

    lib["think"] = _noise_burst(0.18, vol=0.06, cutoff=2000) + _tone(120, 0.18, 0.04, harmonics=False)

    lib["pop"] = _tone(2200, 0.04, 0.14)

    return lib


class SFX:
    """Reproduce sonidos UI cortos en hilo aparte, no bloquea el pipeline."""

    def __init__(self, enabled: bool = True, volume: float = 0.7) -> None:
        self.enabled = enabled
        self.volume = volume
        self._lib: Optional[Dict[str, np.ndarray]] = None
        if sd is None:
            self.enabled = False
            logger.warning("SFX desactivado: sounddevice no disponible")

    def _ensure(self) -> None:
        if self._lib is None:
            self._lib = _build_library()

    def play(self, name: str, blocking: bool = False) -> None:
        if not self.enabled or sd is None:
            return
        self._ensure()
        wave = self._lib.get(name)
        if wave is None:
            return
        wave = wave * self.volume

        def _run():
            try:
                sd.play(wave, SR)
                if blocking:
                    sd.wait()
            except Exception as e:
                logger.debug(f"sfx {name}: {e}")

        if blocking:
            _run()
        else:
            threading.Thread(target=_run, daemon=True).start()

    def set_enabled(self, on: bool) -> None:
        self.enabled = on

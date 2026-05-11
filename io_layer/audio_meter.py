"""Medidores de audio: mic (entrada) y loopback de salida (TTS).

Si pycaw está instalado, intentamos leer el peak meter de la sesión de audio
del sistema → reactividad real del TTS. Si no, FakeMeter simula envoltura.
"""
from __future__ import annotations

import math
import random
import threading
import time
from typing import Callable, Optional

import numpy as np

try:
    import sounddevice as sd
except Exception:
    sd = None


class AudioMeter:
    """Lee RMS del micrófono en tiempo real."""

    def __init__(self, on_level: Callable[[float], None], samplerate: int = 16000) -> None:
        self._on_level = on_level
        self._sr = samplerate
        self._running = False
        self._stream = None
        self._thread = None

    def start(self) -> None:
        if self._running or sd is None:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def _run(self) -> None:
        def cb(indata, frames, t, status):
            try:
                rms = float(np.sqrt(np.mean(indata.astype(np.float32) ** 2)))
                level = min(1.0, rms * 8.0)
                self._on_level(level)
            except Exception:
                pass

        try:
            with sd.InputStream(
                channels=1,
                samplerate=self._sr,
                blocksize=int(self._sr * 0.05),
                dtype="float32",
                callback=cb,
            ) as stream:
                self._stream = stream
                while self._running:
                    time.sleep(0.05)
        except Exception:
            self._running = False


class SystemAudioMeter:
    """Lee el peak meter del sistema (Windows) usando pycaw.
    Cuando habla el TTS, el speaker reproduce → este meter sube.
    """

    def __init__(self, on_level: Callable[[float], None]) -> None:
        self._on_level = on_level
        self._running = False
        self._thread = None
        self._meter = None
        try:
            from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
            from comtypes import CLSCTX_ALL, cast, POINTER

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None)
            self._meter = cast(interface, POINTER(IAudioMeterInformation))
        except Exception:
            self._meter = None

    @property
    def available(self) -> bool:
        return self._meter is not None

    def start(self) -> None:
        if self._running or not self.available:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._on_level(0.0)

    def _run(self) -> None:
        while self._running:
            try:
                peak = float(self._meter.GetPeakValue())
                self._on_level(min(1.0, peak * 1.4))
            except Exception:
                pass
            time.sleep(0.04)


class FakeMeter:
    """Envoltura sintética para cuando no hay loopback disponible."""

    def __init__(self, on_level: Callable[[float], None]) -> None:
        self._on_level = on_level
        self._running = False
        self._thread = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._on_level(0.0)

    def _run(self) -> None:
        t = 0.0
        while self._running:
            t += 0.05
            base = 0.35 + 0.35 * abs(math.sin(t * 3.2))
            jitter = random.uniform(-0.1, 0.1)
            self._on_level(max(0.05, min(1.0, base + jitter)))
            time.sleep(0.04)


def make_output_meter(on_level: Callable[[float], None]):
    """Devuelve SystemAudioMeter si pycaw funciona, si no FakeMeter."""
    sm = SystemAudioMeter(on_level)
    if sm.available:
        return sm
    return FakeMeter(on_level)

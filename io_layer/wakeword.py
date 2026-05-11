"""Wake-word "Jarvan" con openWakeWord (offline, GPU/CPU).

Si openWakeWord no está disponible o el modelo no existe, hace fallback a
detección por volumen + STT corto (cada N segundos transcribe 1.5s y busca
"jarvan" en el texto). Menos preciso pero funciona sin descargar nada.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional

import numpy as np

try:
    import sounddevice as sd
except Exception:
    sd = None

from core.logger import logger


class WakeWord:
    """Llama on_detected() cuando escucha la palabra de activación."""

    def __init__(self, on_detected: Callable[[], None], phrase: str = "jarvan") -> None:
        self.on_detected = on_detected
        self.phrase = phrase.lower()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._mode = "off"
        self._oww = None
        self._stt = None

        self._try_oww()
        if not self._oww:
            self._try_fallback()

    def _try_oww(self) -> None:
        try:
            from openwakeword.model import Model

            self._oww = Model(wakeword_models=["alexa"], inference_framework="onnx")
            self._mode = "oww"
            logger.info("WakeWord: openWakeWord activo (modelo 'alexa' como placeholder)")
        except Exception as e:
            logger.info(f"openWakeWord no disponible: {e}")
            self._oww = None

    def _try_fallback(self) -> None:
        if sd is None:
            self._mode = "off"
            return
        try:
            from io_layer.stt import SpeechToText
            self._stt = SpeechToText()
            self._mode = "stt_poll"
            logger.info("WakeWord: fallback Whisper-poll activo")
        except Exception as e:
            logger.warning(f"fallback wake-word falló: {e}")
            self._mode = "off"

    @property
    def available(self) -> bool:
        return self._mode != "off"

    def start(self) -> None:
        if self._running or not self.available:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _run(self) -> None:
        if self._mode == "oww":
            self._run_oww()
        elif self._mode == "stt_poll":
            self._run_stt_poll()

    def _run_oww(self) -> None:
        sr = 16000
        chunk = 1280
        try:
            with sd.InputStream(channels=1, samplerate=sr, blocksize=chunk, dtype="int16") as stream:
                while self._running:
                    audio, _ = stream.read(chunk)
                    prediction = self._oww.predict(audio[:, 0])
                    for kw, score in prediction.items():
                        if score > 0.5:
                            logger.info(f"wakeword '{kw}' ({score:.2f}) → trigger")
                            try:
                                self.on_detected()
                            except Exception:
                                pass
                            time.sleep(1.5)
                            break
        except Exception as e:
            logger.error(f"oww loop falló: {e}")

    def _run_stt_poll(self) -> None:
        sr = 16000
        window_s = 1.6
        cooldown = 0.0
        while self._running:
            if cooldown > 0:
                time.sleep(0.5)
                cooldown -= 0.5
                continue
            try:
                rec = sd.rec(int(sr * window_s), samplerate=sr, channels=1, dtype="float32")
                sd.wait()
                audio = rec.flatten()
                if float(np.sqrt(np.mean(audio ** 2))) < 0.015:
                    continue
                segments, _ = self._stt.model.transcribe(
                    audio, language="es", beam_size=1, vad_filter=False
                )
                text = " ".join(s.text for s in segments).lower()
                if self.phrase in text:
                    logger.info(f"wakeword detectada en: «{text.strip()}»")
                    try:
                        self.on_detected()
                    except Exception:
                        pass
                    cooldown = 4.0
            except Exception as e:
                logger.debug(f"poll wake: {e}")
                time.sleep(0.5)

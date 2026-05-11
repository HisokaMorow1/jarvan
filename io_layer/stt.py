"""Speech-to-text con faster-whisper en GPU. Captura mic, transcribe en español."""
from __future__ import annotations

import queue
import threading
from typing import Optional

import numpy as np
import sounddevice as sd

from config import settings
from core.logger import logger


class SpeechToText:
    def __init__(self) -> None:
        from faster_whisper import WhisperModel

        cfg = settings.stt
        logger.info(f"Cargando Whisper {cfg.model_size} en {cfg.device}/{cfg.compute_type}")
        self.model = WhisperModel(cfg.model_size, device=cfg.device, compute_type=cfg.compute_type)
        self.sr = cfg.sample_rate
        self.lang = cfg.language
        self.beam = cfg.beam_size
        self.vad = cfg.vad_filter

    def listen_once(self, max_seconds: int = 15, silence_seconds: float = 1.2) -> str:
        logger.info("🎙️  Escuchando...")
        q: "queue.Queue[np.ndarray]" = queue.Queue()
        chunk = int(self.sr * 0.1)

        def cb(indata, frames, t, status):
            q.put(indata.copy())

        buf = []
        silence_chunks = 0
        max_chunks = int(max_seconds / 0.1)
        silence_thresh = 0.01
        silence_target = int(silence_seconds / 0.1)

        with sd.InputStream(channels=1, samplerate=self.sr, blocksize=chunk, callback=cb, dtype="float32"):
            for _ in range(max_chunks):
                data = q.get()
                buf.append(data)
                rms = float(np.sqrt(np.mean(data ** 2)))
                if rms < silence_thresh:
                    silence_chunks += 1
                else:
                    silence_chunks = 0
                if len(buf) > silence_target and silence_chunks >= silence_target:
                    break

        audio = np.concatenate(buf, axis=0).flatten()
        if audio.size == 0:
            return ""

        segments, _ = self.model.transcribe(
            audio,
            language=self.lang,
            beam_size=self.beam,
            vad_filter=self.vad,
        )
        text = " ".join(s.text.strip() for s in segments).strip()
        logger.info(f"📝 STT: {text}")
        return text

    def transcribe_file(self, path: str) -> str:
        segments, _ = self.model.transcribe(path, language=self.lang, beam_size=self.beam)
        return " ".join(s.text.strip() for s in segments).strip()

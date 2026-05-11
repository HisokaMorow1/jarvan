"""TTS con piper (preferido) y pyttsx3 fallback.

Para sensación Jarvis: voz grave, velocidad ligeramente reducida.
Si piper-tts no está instalado o el modelo de voz no existe, cae a pyttsx3
buscando la voz masculina más grave disponible en español.

Soporta:
  - speak(text)                → habla sincronicamente (bloquea hilo)
  - speak_async(text, on_word) → callback por palabra para subtítulos karaoke
  - stop()                     → corta el habla en curso
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from config import settings
from core.logger import logger


class TextToSpeech:
    def __init__(self) -> None:
        self._engine = settings.tts.engine
        self._piper_cmd = shutil.which("piper")
        self._pyttsx3 = None
        self._stop_flag = threading.Event()
        self._lock = threading.Lock()

        if self._engine == "piper" and not self._piper_cmd:
            logger.info("piper no en PATH, usando pyttsx3 (busca voz grave en español)")
            self._engine = "pyttsx3"
        if self._engine == "pyttsx3":
            self._init_pyttsx3()

    def _init_pyttsx3(self) -> None:
        try:
            import pyttsx3

            self._pyttsx3 = pyttsx3.init()
            self._pyttsx3.setProperty("rate", settings.tts.rate)
            self._pyttsx3.setProperty("volume", 1.0)
            voices = self._pyttsx3.getProperty("voices") or []
            picked = None
            for v in voices:
                name = (v.name or "").lower()
                langs = " ".join((l.decode() if isinstance(l, bytes) else str(l)) for l in (v.languages or []))
                if ("spanish" in name or "español" in name or "es-" in langs.lower() or "es_" in langs.lower()):
                    if any(m in name for m in ("male", "hombre", "raul", "carlos", "jorge", "diego", "pablo")):
                        picked = v.id
                        break
                    picked = picked or v.id
            if picked:
                self._pyttsx3.setProperty("voice", picked)
                logger.info(f"pyttsx3 voz: {picked}")
        except Exception as e:
            logger.error(f"pyttsx3 no inicializa: {e}")
            self._pyttsx3 = None

    def speak(self, text: str, blocking: bool = True) -> None:
        if not text or not text.strip():
            return
        self._stop_flag.clear()
        if blocking:
            self._speak_sync(text)
        else:
            threading.Thread(target=self._speak_sync, args=(text,), daemon=True).start()

    def speak_async(self, text: str, on_word: Optional[Callable[[str, int, int], None]] = None) -> None:
        """Habla en hilo y opcionalmente notifica progreso palabra-a-palabra.

        on_word(word, index, total) se invoca antes de cada palabra
        (timing aproximado, no por análisis del audio).
        """
        if not text or not text.strip():
            return
        self._stop_flag.clear()
        threading.Thread(target=self._speak_words, args=(text, on_word), daemon=True).start()

    def stop(self) -> None:
        self._stop_flag.set()
        try:
            if self._pyttsx3:
                self._pyttsx3.stop()
        except Exception:
            pass

    def _speak_sync(self, text: str) -> None:
        with self._lock:
            if self._engine == "piper" and self._piper_cmd:
                self._piper(text)
            elif self._pyttsx3:
                try:
                    self._pyttsx3.say(text)
                    self._pyttsx3.runAndWait()
                except Exception as e:
                    logger.warning(f"pyttsx3 falló: {e}")

    def _speak_words(self, text: str, on_word: Optional[Callable[[str, int, int], None]]) -> None:
        words = re.findall(r"\S+", text)
        if not words:
            return
        rate = max(80, settings.tts.rate)
        sec_per_word = max(0.18, 60.0 / rate * 1.6)
        thread = threading.Thread(target=self._speak_sync, args=(text,), daemon=True)
        thread.start()
        t0 = time.time()
        for i, w in enumerate(words):
            if self._stop_flag.is_set():
                break
            target = t0 + i * sec_per_word
            now = time.time()
            if target > now:
                time.sleep(target - now)
            if on_word:
                try:
                    on_word(w, i, len(words))
                except Exception:
                    pass
        thread.join(timeout=max(2.0, sec_per_word * len(words) + 2.0))
        if on_word:
            try:
                on_word("", len(words), len(words))
            except Exception:
                pass

    def _piper(self, text: str) -> None:
        try:
            tmp = Path(tempfile.gettempdir()) / "jarvan_tts.wav"
            proc = subprocess.Popen(
                [self._piper_cmd, "--model", settings.tts.voice, "--output_file", str(tmp)],
                stdin=subprocess.PIPE,
            )
            proc.communicate(text.encode("utf-8"))
            if tmp.exists() and not self._stop_flag.is_set():
                import sounddevice as sd
                import soundfile as sf

                data, sr = sf.read(str(tmp))
                sd.play(data, sr)
                while sd.get_stream().active:
                    if self._stop_flag.is_set():
                        sd.stop()
                        break
                    time.sleep(0.05)
        except Exception as e:
            logger.warning(f"piper falló, fallback pyttsx3: {e}")
            if not self._pyttsx3:
                self._init_pyttsx3()
            if self._pyttsx3:
                try:
                    self._pyttsx3.say(text)
                    self._pyttsx3.runAndWait()
                except Exception:
                    pass

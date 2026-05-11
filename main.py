"""Jarvan — entrada principal (versión Jarvis-grade).

Componentes simultáneos en la demo:
  - Splash UMAG inicial con fade-in/out.
  - Esfera flotante reactiva al audio del sistema (loopback real).
  - HUD lateral con respuesta en streaming + karaoke palabra a palabra
    sincronizado con la voz.
  - Panel telemetría GPU/VRAM/CPU/RAM/latencia (top-left).
  - Panel contextual: reloj, fecha, ventana activa, batería (top-right).
  - Tray icon con menú completo.
  - Wake-word "Jarvan" en background (F7).
  - Modo conversación continua (F8).
  - Filler talk: "Procesando, señor..." si el modelo tarda > 1.5s.
  - SFX UI: boot, listen, confirm, error, alert.
  - Reglas proactivas (batería, RAM, inactividad).

Controles:
  Espacio  → un turno manual.
  F7       → toggle wake-word.
  F8       → toggle conversación continua.
  F9       → mute/unmute voz.
  Esc      → salir.
"""
from __future__ import annotations

import sys
import threading
import time

from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QApplication, QShortcut

from config import settings
from core.agent import JarvanAgent
from core.filler import Filler
from core.health import check_health
from core.llm_client import OllamaClient
from core.logger import logger
from core.proactive import Proactive
from core.system_context import gather as gather_ctx, greeting
from core.telemetry import Telemetry
from io_layer.audio_meter import AudioMeter, make_output_meter
from io_layer.sfx import SFX
from io_layer.stt import SpeechToText
from io_layer.tts import TextToSpeech
from io_layer.wakeword import WakeWord
from ui.hud import ContextPanel, HUDPanel, TelemetryPanel
from ui.splash import SplashWindow
from ui.sphere import AgentState, SphereWindow
from ui.tray import TrayIcon


class Bridge(QObject):
    state_changed = pyqtSignal(object)
    audio_level = pyqtSignal(float)
    user_said = pyqtSignal(str)
    stream_begin = pyqtSignal()
    stream_token = pyqtSignal(str)
    assistant_said = pyqtSignal(str)
    karaoke_text = pyqtSignal(str)
    karaoke_word = pyqtSignal(int)
    status_text = pyqtSignal(str)
    telemetry_snap = pyqtSignal(object)
    proactive_announce = pyqtSignal(str)
    listen_trigger = pyqtSignal()
    context_update = pyqtSignal(str, float, bool, str)


class JarvanApp:
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.bridge = Bridge()
        self.continuous_mode = False
        self.tts_muted = False
        self.busy = False

        self.sphere = SphereWindow()
        self.hud = HUDPanel()
        self.tel_panel = TelemetryPanel()
        self.ctx_panel = ContextPanel()

        self.sfx = SFX(enabled=True, volume=0.6)

        self.bridge.state_changed.connect(self._on_state_changed)
        self.bridge.audio_level.connect(self.sphere.set_audio_level)
        self.bridge.user_said.connect(self.hud.show_user)
        self.bridge.stream_begin.connect(self.hud.begin_stream)
        self.bridge.stream_token.connect(self.hud.append_stream)
        self.bridge.assistant_said.connect(lambda t: self.hud.set_karaoke_text(t))
        self.bridge.karaoke_text.connect(self.hud.set_karaoke_text)
        self.bridge.karaoke_word.connect(self.hud.highlight_word)
        self.bridge.status_text.connect(self.hud.set_status)
        self.bridge.telemetry_snap.connect(self.tel_panel.update_snap)
        self.bridge.proactive_announce.connect(self._on_proactive)
        self.bridge.listen_trigger.connect(self._toggle_listen_trigger)
        self.bridge.context_update.connect(self.ctx_panel.update_context)

        self.splash = SplashWindow(
            university=settings.ui.university if hasattr(settings, "ui") else "UNIVERSIDAD DE MAGALLANES",
            subtitle="Prototipo de Asistente IA Local",
        )
        self.splash.finished.connect(self._after_splash)
        self.splash.show_and_run(total_ms=2600)
        QTimer.singleShot(120, lambda: self.sfx.play("boot"))

        self.llm = None
        self.stt = None
        self.tts = None
        self.agent = None
        self.telemetry = Telemetry()
        self.mic_meter = None
        self.tts_meter = None
        self.wakeword = None
        self.proactive = None
        self.tray = None
        self.health = None
        self.filler: Filler = Filler(on_say=self._filler_say, delay_s=1.4, cooldown_s=10.0)
        self._filler_active = False

        threading.Thread(target=self._bootstrap_async, daemon=True).start()

    def _bootstrap_async(self) -> None:
        try:
            self.bridge.status_text.emit("inicializando núcleo")
            self.llm = OllamaClient()
            self.health = check_health(self.llm)
            self.bridge.status_text.emit("cargando whisper")
            self.stt = SpeechToText()
            self.bridge.status_text.emit("cargando tts")
            self.tts = TextToSpeech()
            self.bridge.status_text.emit("ensamblando agente")
            self.agent = JarvanAgent(
                llm=self.llm,
                on_confirm=lambda step: True,
                on_token=lambda t: self.bridge.stream_token.emit(t),
                on_status=lambda s: self.bridge.status_text.emit(s),
            )
            self.mic_meter = AudioMeter(on_level=lambda lv: self.bridge.audio_level.emit(lv))
            self.tts_meter = make_output_meter(on_level=lambda lv: self.bridge.audio_level.emit(lv))

            self.proactive = Proactive(
                on_announce=lambda t: self.bridge.proactive_announce.emit(t),
                interval_s=60.0,
            )

            if self.health.ollama_up:
                self.llm.warmup(settings.llm.router_model)
                self.llm.warmup(settings.llm.embed_model)
        except Exception as e:
            logger.exception("bootstrap")
            self.bridge.status_text.emit(f"error: {e}")

    def _after_splash(self) -> None:
        self.sphere.show()
        self.tel_panel.show()
        self.ctx_panel.show()
        self.tray = TrayIcon(self.app, self.sphere, self.hud, self.tel_panel)
        self.tray.show()

        self.sphere.request_listen.connect(self._toggle_listen_trigger)
        self._install_shortcuts()

        self.tel_timer = QTimer()
        self.tel_timer.timeout.connect(
            lambda: self.bridge.telemetry_snap.emit(self.telemetry.sample())
        )
        self.tel_timer.start(500)

        self.ctx_timer = QTimer()
        self.ctx_timer.timeout.connect(self._refresh_context)
        self.ctx_timer.start(1000)
        self._refresh_context()

        QTimer.singleShot(2400, self._boot_greeting)

    def _install_shortcuts(self) -> None:
        for key, slot in [
            (Qt.Key_Space, self._toggle_listen_trigger),
            (Qt.Key_Escape, self.app.quit),
            (Qt.Key_F7, self._toggle_wakeword),
            (Qt.Key_F8, self._toggle_continuous),
            (Qt.Key_F9, self._toggle_mute),
        ]:
            sc = QShortcut(QKeySequence(key), self.sphere)
            sc.setContext(Qt.ApplicationShortcut)
            sc.activated.connect(slot)

    def _refresh_context(self) -> None:
        try:
            ctx = gather_ctx()
            bat = ctx.battery_pct if ctx.battery_pct is not None else -1.0
            plugged = bool(ctx.battery_plugged) if ctx.battery_plugged is not None else False
            model = settings.llm.planner_model
            self.bridge.context_update.emit(ctx.foreground_window, bat, plugged, model)
        except Exception:
            pass

    def _on_state_changed(self, state: AgentState) -> None:
        self.sphere.set_state(state)
        if state == AgentState.LISTENING:
            self.sfx.play("listen_start")
        elif state == AgentState.SPEAKING:
            pass
        elif state == AgentState.ERROR:
            self.sfx.play("error")

    def _filler_say(self, text: str) -> None:
        if self.tts_muted or not self.tts:
            return
        self._filler_active = True
        try:
            if self.tts_meter:
                self.tts_meter.start()
            self.tts.speak(text, blocking=True)
        except Exception:
            pass
        finally:
            if self.tts_meter:
                self.tts_meter.stop()
            self._filler_active = False

    def _boot_greeting(self) -> None:
        if not self.health or not self.health.ollama_up:
            text = "Ollama no responde, señor. Inicia el servicio y reinicia Jarvan."
            self.bridge.state_changed.emit(AgentState.ERROR)
        elif self.health.models_missing:
            text = "Faltan modelos en el servidor local: " + ", ".join(self.health.models_missing)
            self.bridge.state_changed.emit(AgentState.IDLE)
        else:
            text = greeting()
            self.bridge.state_changed.emit(AgentState.SPEAKING)

        self.bridge.assistant_said.emit(text)
        self._speak_karaoke_async(
            text,
            after=lambda: (
                self.bridge.state_changed.emit(AgentState.IDLE),
                self.proactive and self.proactive.start(),
            ),
        )

    def _speak_karaoke_async(self, text: str, after=None) -> None:
        """Habla y resalta palabras en el HUD en tiempo aproximado."""
        if not text:
            if after:
                try:
                    after()
                except Exception:
                    pass
            return

        self.bridge.karaoke_text.emit(text)

        def _do():
            try:
                if self.tts_meter:
                    self.tts_meter.start()
                if not self.tts_muted and self.tts:
                    self.tts.speak_async(
                        text,
                        on_word=lambda w, i, total: self.bridge.karaoke_word.emit(i),
                    )
                    rate = max(80, settings.tts.rate)
                    sec_per_word = max(0.18, 60.0 / rate * 1.6)
                    n_words = len(text.split())
                    time.sleep(sec_per_word * n_words + 0.4)
                else:
                    n_words = len(text.split())
                    rate = max(80, settings.tts.rate)
                    sec_per_word = max(0.18, 60.0 / rate * 1.6)
                    for i in range(n_words):
                        self.bridge.karaoke_word.emit(i)
                        time.sleep(sec_per_word)
            finally:
                if self.tts_meter:
                    self.tts_meter.stop()
                if after:
                    try:
                        after()
                    except Exception:
                        pass

        threading.Thread(target=_do, daemon=True).start()

    def _toggle_listen_trigger(self) -> None:
        if self.busy or not self.agent:
            return
        threading.Thread(target=self._turn, daemon=True).start()

    def _toggle_continuous(self) -> None:
        self.continuous_mode = not self.continuous_mode
        self.bridge.status_text.emit(
            f"continuo: {'ON' if self.continuous_mode else 'OFF'}"
        )
        self.sfx.play("confirm")
        logger.info(f"modo continuo = {self.continuous_mode}")
        if self.continuous_mode and not self.busy:
            self._toggle_listen_trigger()

    def _toggle_mute(self) -> None:
        self.tts_muted = not self.tts_muted
        self.bridge.status_text.emit(f"voz: {'MUTE' if self.tts_muted else 'ON'}")
        self.sfx.play("pop")
        logger.info(f"tts muted = {self.tts_muted}")

    def _toggle_wakeword(self) -> None:
        if self.wakeword is None:
            self.wakeword = WakeWord(
                on_detected=lambda: self.bridge.listen_trigger.emit(),
                phrase=settings.wake_word.phrase,
            )
        if not self.wakeword.available:
            self.bridge.status_text.emit("wake-word no disponible")
            return
        if self.wakeword._running:
            self.wakeword.stop()
            self.bridge.status_text.emit("wake-word: OFF")
        else:
            self.wakeword.start()
            self.bridge.status_text.emit("wake-word: ON (di 'Jarvan')")
        self.sfx.play("confirm")

    def _on_proactive(self, text: str) -> None:
        if self.busy:
            return
        self.sfx.play("alert")
        self.bridge.assistant_said.emit(text)
        self.bridge.state_changed.emit(AgentState.SPEAKING)
        self._speak_karaoke_async(text, after=lambda: self.bridge.state_changed.emit(AgentState.IDLE))

    def _turn(self) -> None:
        if self.busy:
            return
        self.busy = True
        try:
            if self.proactive:
                self.proactive.mark_user_activity()
            self.telemetry.mark("turn")
            self.bridge.state_changed.emit(AgentState.LISTENING)
            self.bridge.status_text.emit("escuchando")
            if self.mic_meter:
                self.mic_meter.start()
            try:
                text = self.stt.listen_once()
            finally:
                if self.mic_meter:
                    self.mic_meter.stop()
                self.bridge.audio_level.emit(0.0)
                self.sfx.play("listen_end")

            if not text or len(text.strip()) < 2:
                self.bridge.state_changed.emit(AgentState.IDLE)
                self.bridge.status_text.emit("standby")
                return

            low = text.lower()
            if any(w in low for w in ("adiós", "adios", "hasta luego", "chao", "ciao")):
                self._speak_karaoke_async("Hasta luego, señor.", after=self.app.quit)
                return

            self.bridge.user_said.emit(text)
            self.bridge.state_changed.emit(AgentState.THINKING)
            self.bridge.stream_begin.emit()

            self.filler.arm(category="thinking")

            reply = self.agent.handle(text)

            self.filler.disarm()
            while self._filler_active:
                time.sleep(0.05)

            self.bridge.state_changed.emit(AgentState.SPEAKING)
            self.bridge.status_text.emit("hablando")
            self.sfx.play("confirm")

            if reply:
                done = threading.Event()
                self._speak_karaoke_async(reply, after=done.set)
                done.wait(timeout=90)
            self.telemetry.measure("turn")
        except Exception as e:
            logger.exception("Error en pipeline")
            self.bridge.state_changed.emit(AgentState.ERROR)
            self.bridge.assistant_said.emit(f"Error: {e}")
        finally:
            self.filler.disarm()
            self.bridge.state_changed.emit(AgentState.IDLE)
            self.bridge.status_text.emit("standby")
            self.busy = False
            if self.continuous_mode:
                QTimer.singleShot(500, self._toggle_listen_trigger)


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Jarvan")
    _ = JarvanApp(app)
    logger.info("Jarvan listo. Espacio=hablar, F7=wakeword, F8=continuo, F9=mute, Esc=salir.")
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())

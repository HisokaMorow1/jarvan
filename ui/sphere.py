"""Esfera flotante estilo Jarvis. PyQt5, sin marco, sin fondo, top-most.

Mejoras de presentación:
- Boot-up animation (anillos cerrándose).
- Glow multicapa con halo amplio.
- 3 anillos a velocidades distintas + arcos de cuenta atrás.
- 42 partículas orbitales reactivas al audio.
- Núcleo con destello angular tipo arc reactor.
- Waveform circular bajo la esfera.
- Click-through automático en IDLE.
- Reactividad al audio (mic + tts loopback).
"""
from __future__ import annotations

import math
import random
from enum import Enum
from typing import List

from PyQt5.QtCore import QPointF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QConicalGradient, QFont, QPainter, QPen, QRadialGradient
from PyQt5.QtWidgets import QApplication, QWidget


class AgentState(Enum):
    BOOT = "boot"
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"


STATE_PALETTE = {
    AgentState.BOOT: (255, 255, 255),
    AgentState.IDLE: (60, 160, 255),
    AgentState.LISTENING: (60, 230, 160),
    AgentState.THINKING: (255, 180, 60),
    AgentState.SPEAKING: (200, 100, 255),
    AgentState.ERROR: (255, 70, 70),
}


class Particle:
    __slots__ = ("angle", "radius", "speed", "size", "life")

    def __init__(self, r0: float) -> None:
        self.angle = random.uniform(0, math.tau)
        self.radius = r0 + random.uniform(-14, 14)
        self.speed = random.uniform(0.004, 0.025) * random.choice([-1, 1])
        self.size = random.uniform(1.0, 2.8)
        self.life = random.uniform(0.55, 1.0)


class SphereWindow(QWidget):
    request_listen = pyqtSignal()
    closed = pyqtSignal()

    SIZE = 360

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.resize(self.SIZE, self.SIZE)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.SIZE - 30, screen.bottom() - self.SIZE - 60)

        self._t = 0.0
        self._state = AgentState.BOOT
        self._boot_progress = 0.0
        self._audio_level = 0.0
        self._target_level = 0.0
        self._particles: List[Particle] = [Particle(self.SIZE * 0.34) for _ in range(42)]
        self._drag = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

        self._apply_click_through(False)

    def set_state(self, s: AgentState, _message: str = "") -> None:
        self._state = s
        self._apply_click_through(s == AgentState.IDLE)

    def set_audio_level(self, level: float) -> None:
        self._target_level = max(0.0, min(1.0, level))

    def _apply_click_through(self, enabled: bool) -> None:
        try:
            self.setAttribute(Qt.WA_TransparentForMouseEvents, enabled)
        except Exception:
            pass

    def _tick(self) -> None:
        self._t += 0.016
        self._audio_level += (self._target_level - self._audio_level) * 0.18
        if self._state == AgentState.THINKING:
            self._audio_level = 0.30 + 0.18 * math.sin(self._t * 4)
        if self._state == AgentState.BOOT:
            self._boot_progress = min(1.0, self._boot_progress + 0.012)
            if self._boot_progress >= 1.0:
                self.set_state(AgentState.IDLE)
        for p in self._particles:
            p.angle += p.speed * (1 + self._audio_level * 2)
        self.update()

    def paintEvent(self, _evt) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.HighQualityAntialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r, g, b = STATE_PALETTE[self._state]

        if self._state == AgentState.BOOT:
            self._paint_boot(p, cx, cy)
            return

        amp = 0.06 + self._audio_level * 0.22
        pulse = 1 + amp * math.sin(self._t * 4)
        r_core = (self.SIZE * 0.26) * pulse

        glow_r = r_core * 2.7
        glow = QRadialGradient(cx, cy, glow_r)
        glow.setColorAt(0.0, QColor(r, g, b, int(140 + self._audio_level * 100)))
        glow.setColorAt(0.45, QColor(r, g, b, 55))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(glow)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), glow_r, glow_r)

        for i, (mult, alpha, width, speed, span_base) in enumerate(
            [
                (1.55, 90, 1.6, 0.42, 220),
                (1.85, 65, 1.1, -0.28, 180),
                (2.20, 45, 0.8, 0.18, 260),
                (2.55, 28, 0.6, -0.10, 300),
            ]
        ):
            rr = r_core * mult
            pen = QPen(QColor(r, g, b, alpha))
            pen.setWidthF(width)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            start = int((self._t * 60 * speed + i * 37) % 360) * 16
            span = (span_base + int(50 * math.sin(self._t + i))) * 16
            p.drawArc(int(cx - rr), int(cy - rr), int(rr * 2), int(rr * 2), start, span)

        cg = QConicalGradient(cx, cy, (self._t * 60) % 360)
        cg.setColorAt(0.00, QColor(r, g, b, 90))
        cg.setColorAt(0.25, QColor(255, 255, 255, 30))
        cg.setColorAt(0.50, QColor(r, g, b, 90))
        cg.setColorAt(0.75, QColor(255, 255, 255, 30))
        cg.setColorAt(1.00, QColor(r, g, b, 90))
        p.setBrush(cg)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), r_core * 1.18, r_core * 1.18)

        core = QRadialGradient(cx - r_core * 0.28, cy - r_core * 0.28, r_core * 1.5)
        core.setColorAt(0.0, QColor(255, 255, 255, 240))
        core.setColorAt(0.30, QColor(min(255, r + 70), min(255, g + 70), min(255, b + 70), 230))
        core.setColorAt(0.70, QColor(r, g, b, 190))
        core.setColorAt(1.0, QColor(r // 2, g // 2, b // 2, 0))
        p.setBrush(core)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), r_core, r_core)

        p.setPen(QPen(QColor(255, 255, 255, 70), 0.6))
        p.setBrush(Qt.NoBrush)
        for ring_r in (r_core * 0.55, r_core * 0.80):
            p.drawEllipse(QPointF(cx, cy), ring_r, ring_r * 0.35)

        p.setPen(Qt.NoPen)
        for prt in self._particles:
            px = cx + math.cos(prt.angle) * prt.radius * (1 + self._audio_level * 0.4)
            py = cy + math.sin(prt.angle) * prt.radius * (1 + self._audio_level * 0.4)
            a = int(190 * prt.life)
            p.setBrush(QColor(min(255, r + 80), min(255, g + 80), min(255, b + 80), a))
            sz = prt.size * (1 + self._audio_level)
            p.drawEllipse(QPointF(px, py), sz, sz)

        if self._state in (AgentState.SPEAKING, AgentState.LISTENING):
            self._draw_circular_waveform(p, cx, cy, r_core * 3.1, r, g, b)

        for orb_idx, (orb_r, orb_speed, orb_size) in enumerate(
            [(r_core * 2.6, 0.8, 4.0), (r_core * 2.95, -0.55, 3.0)]
        ):
            ang = self._t * orb_speed + orb_idx * math.pi
            ox = cx + math.cos(ang) * orb_r
            oy = cy + math.sin(ang) * orb_r
            halo = QRadialGradient(ox, oy, orb_size * 3)
            halo.setColorAt(0.0, QColor(255, 255, 255, 230))
            halo.setColorAt(0.4, QColor(r, g, b, 180))
            halo.setColorAt(1.0, QColor(r, g, b, 0))
            p.setBrush(halo)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(ox, oy), orb_size * 3, orb_size * 3)

        p.setPen(QPen(QColor(r, g, b, 200)))
        p.setFont(QFont("Consolas", 9, QFont.Bold))
        label = {
            AgentState.IDLE: "J A R V A N",
            AgentState.LISTENING: "L I S T E N I N G",
            AgentState.THINKING: "T H I N K I N G",
            AgentState.SPEAKING: "S P E A K I N G",
            AgentState.ERROR: "E R R O R",
        }.get(self._state, "")
        p.drawText(0, int(cy + glow_r * 0.62), w, 14, Qt.AlignCenter, label)

    def _paint_boot(self, p: QPainter, cx: float, cy: float) -> None:
        prog = self._boot_progress
        r_max = self.SIZE * 0.42
        r = r_max * (1 - prog) + 30 * prog

        glow = QRadialGradient(cx, cy, r * 1.6)
        glow.setColorAt(0.0, QColor(120, 200, 255, int(180 * prog)))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(glow)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), r * 1.6, r * 1.6)

        for i in range(3):
            pen = QPen(QColor(120, 200, 255, 200 - i * 50))
            pen.setWidthF(2 - i * 0.5)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            rr = r + i * 18
            span = int(360 * 16 * prog)
            p.drawArc(int(cx - rr), int(cy - rr), int(rr * 2), int(rr * 2), -90 * 16, span)

        p.setPen(QPen(QColor(255, 255, 255, int(255 * prog))))
        p.setFont(QFont("Consolas", 10, QFont.Bold))
        p.drawText(0, int(cy + r_max + 24), self.width(), 14, Qt.AlignCenter, "BOOTING JARVAN")

    def _draw_circular_waveform(self, p: QPainter, cx: float, cy: float, r0: float, r: int, g: int, b: int) -> None:
        bars = 64
        for i in range(bars):
            ang = (i / bars) * math.tau
            phase = self._t * 5 + i * 0.4
            mag = (math.sin(phase) ** 2) * (10 + self._audio_level * 30)
            x1 = cx + math.cos(ang) * r0
            y1 = cy + math.sin(ang) * r0
            x2 = cx + math.cos(ang) * (r0 + mag)
            y2 = cy + math.sin(ang) * (r0 + mag)
            pen = QPen(QColor(r, g, b, 180))
            pen.setWidthF(1.4)
            p.setPen(pen)
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPos() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e) -> None:
        if self._drag and e.buttons() & Qt.LeftButton:
            self.move(e.globalPos() - self._drag)

    def mouseDoubleClickEvent(self, _e) -> None:
        self.request_listen.emit()

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key_Escape:
            self.closed.emit()
            self.close()
        elif e.key() == Qt.Key_Space:
            self.request_listen.emit()


def run_standalone() -> None:
    import sys

    app = QApplication(sys.argv)
    w = SphereWindow()
    w.show()
    QTimer.singleShot(2200, lambda: w.set_state(AgentState.SPEAKING))
    sys.exit(app.exec_())


if __name__ == "__main__":
    run_standalone()

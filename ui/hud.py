"""HUD lateral Jarvis: transcripción, respuesta karaoke, status.
+ HUD contextual (hora, día, ventana activa, batería) — top-right.

Sin marco, translúcido, transparente a clicks, fade-in/out automático.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Tuple

from PyQt5.QtCore import QPropertyAnimation, Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt5.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QLabel,
    QVBoxLayout,
    QWidget,
)


_ES_WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_ES_MONTHS = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


class HUDPanel(QWidget):
    """Panel principal: usuario + respuesta con efecto karaoke palabra-a-palabra."""

    WIDTH = 480
    HEIGHT = 280

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.resize(self.WIDTH, self.HEIGHT)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.WIDTH - 410, screen.bottom() - self.HEIGHT - 80)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(8)

        self.title = QLabel("J A R V A N")
        self.title.setStyleSheet(
            "color:#62b8ff;font-family:'Consolas';font-size:11px;font-weight:bold;letter-spacing:4px;"
        )
        self.status = QLabel("standby")
        self.status.setStyleSheet(
            "color:#7fd0a8;font-family:'Consolas';font-size:10px;letter-spacing:2px;"
        )
        self.user_line = QLabel("")
        self.user_line.setWordWrap(True)
        self.user_line.setStyleSheet(
            "color:rgba(220,235,255,200);font-family:'Segoe UI';font-size:13px;"
        )

        layout.addWidget(self.title)
        layout.addWidget(self.status)
        layout.addWidget(self.user_line)
        layout.addStretch(1)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)
        self._anim = QPropertyAnimation(self._opacity, b"opacity", self)
        self._anim.setDuration(280)

        self._fade_timer = QTimer(self)
        self._fade_timer.setSingleShot(True)
        self._fade_timer.timeout.connect(self.fade_out)

        self._stream_buf = ""
        self._words: List[str] = []
        self._highlight_idx: int = -1

    def set_status(self, s: str) -> None:
        self.status.setText(s.upper())

    def show_user(self, text: str) -> None:
        self.user_line.setText(f"› {text}")
        self._stream_buf = ""
        self._words = []
        self._highlight_idx = -1
        self.fade_in()
        self.update()

    def begin_stream(self) -> None:
        self._stream_buf = ""
        self._words = []
        self._highlight_idx = -1
        self.fade_in()
        self.update()

    def append_stream(self, delta: str) -> None:
        self._stream_buf += delta
        self._words = self._stream_buf.split()
        self.update()

    def show_assistant(self, text: str, auto_hide_ms: int = 9000) -> None:
        self._stream_buf = text
        self._words = text.split()
        self._highlight_idx = -1
        self.fade_in()
        if auto_hide_ms > 0:
            self._fade_timer.start(auto_hide_ms)
        self.update()

    def set_karaoke_text(self, text: str) -> None:
        self._stream_buf = text
        self._words = text.split()
        self._highlight_idx = -1
        self.fade_in()
        self.update()

    def highlight_word(self, idx: int) -> None:
        self._highlight_idx = idx
        self.update()

    def fade_in(self) -> None:
        self.show()
        self._anim.stop()
        self._anim.setStartValue(self._opacity.opacity())
        self._anim.setEndValue(1.0)
        self._anim.start()

    def fade_out(self) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._opacity.opacity())
        self._anim.setEndValue(0.0)
        self._anim.start()

    def paintEvent(self, _evt) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(6, 6, -6, -6)

        p.setBrush(QColor(8, 18, 32, 200))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(rect, 14, 14)

        p.setBrush(Qt.NoBrush)
        pen = QPen(QColor(98, 184, 255, 180))
        pen.setWidth(1)
        p.setPen(pen)
        p.drawRoundedRect(rect, 14, 14)

        self._draw_corners(p, rect)

        if self._words:
            self._draw_karaoke(p, rect)

    def _draw_karaoke(self, p: QPainter, rect) -> None:
        font_norm = QFont("Segoe UI", 11)
        font_hi = QFont("Segoe UI", 11, QFont.Bold)
        fm = QFontMetrics(font_norm)
        x0 = rect.left() + 22
        y0 = rect.top() + 100
        max_w = rect.width() - 44
        line_h = fm.height() + 4

        x, y = x0, y0
        for i, w in enumerate(self._words):
            ww = fm.horizontalAdvance(w + " ")
            if x + ww > x0 + max_w:
                x = x0
                y += line_h
                if y > rect.bottom() - 30:
                    break
            if i == self._highlight_idx:
                p.setFont(font_hi)
                p.setPen(QColor(255, 255, 255, 250))
            elif i < self._highlight_idx:
                p.setFont(font_norm)
                p.setPen(QColor(160, 210, 255, 220))
            else:
                p.setFont(font_norm)
                p.setPen(QColor(170, 200, 230, 150))
            p.drawText(x, y, w)
            x += ww

    def _draw_corners(self, p: QPainter, rect) -> None:
        pen2 = QPen(QColor(98, 184, 255, 110))
        pen2.setWidth(2)
        p.setPen(pen2)
        corner = 22
        p.drawLine(rect.left() + 4, rect.top() + 16, rect.left() + 4, rect.top() + 4)
        p.drawLine(rect.left() + 4, rect.top() + 4, rect.left() + corner, rect.top() + 4)
        p.drawLine(rect.right() - corner, rect.top() + 4, rect.right() - 4, rect.top() + 4)
        p.drawLine(rect.right() - 4, rect.top() + 4, rect.right() - 4, rect.top() + 16)
        p.drawLine(rect.left() + 4, rect.bottom() - 16, rect.left() + 4, rect.bottom() - 4)
        p.drawLine(rect.left() + 4, rect.bottom() - 4, rect.left() + corner, rect.bottom() - 4)
        p.drawLine(rect.right() - corner, rect.bottom() - 4, rect.right() - 4, rect.bottom() - 4)
        p.drawLine(rect.right() - 4, rect.bottom() - 4, rect.right() - 4, rect.bottom() - 16)


class TelemetryPanel(QWidget):
    """Panel pequeño que muestra GPU/CPU/RAM/VRAM/latencia. Top-left."""

    WIDTH = 240
    HEIGHT = 160

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.resize(self.WIDTH, self.HEIGHT)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.left() + 30, screen.top() + 30)

        self._snap = None
        self._t = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(60)

    def update_snap(self, snap) -> None:
        self._snap = snap
        self.update()

    def _tick(self) -> None:
        self._t += 0.016
        self.update()

    def paintEvent(self, _evt) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(6, 6, -6, -6)

        p.setBrush(QColor(8, 18, 32, 180))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(rect, 10, 10)

        pen = QPen(QColor(98, 184, 255, 160))
        pen.setWidth(1)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(rect, 10, 10)

        p.setPen(QColor(98, 184, 255, 220))
        p.setFont(QFont("Consolas", 9, QFont.Bold))
        p.drawText(rect.left() + 14, rect.top() + 22, "SYSTEM TELEMETRY")

        p.setFont(QFont("Consolas", 9))
        p.setPen(QColor(220, 235, 255, 220))
        if self._snap:
            s = self._snap
            lines = [
                f"GPU  {s.gpu:5.1f} %  {s.gpu_temp:4.0f} C",
                f"VRAM {s.vram_used_mb:5.0f} / {s.vram_total_mb:5.0f} MB",
                f"CPU  {s.cpu:5.1f} %",
                f"RAM  {s.ram:5.1f} %",
                f"LAT  {s.last_latency_ms:6.0f} ms",
            ]
        else:
            lines = ["GPU  ----", "VRAM ----", "CPU  ----", "RAM  ----", "LAT  ----"]
        for i, ln in enumerate(lines):
            p.drawText(rect.left() + 14, rect.top() + 44 + i * 16, ln)


class ContextPanel(QWidget):
    """HUD contextual: reloj, fecha, ventana activa, batería, modelo activo.
    Top-right del escritorio. Estilo cockpit Jarvis."""

    WIDTH = 280
    HEIGHT = 180

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.resize(self.WIDTH, self.HEIGHT)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.WIDTH - 30, screen.top() + 30)

        self._foreground = ""
        self._battery: Tuple[float, bool] = (-1.0, False)
        self._model = ""

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(500)

    def update_context(self, foreground: str, battery_pct: float, plugged: bool, model: str = "") -> None:
        self._foreground = foreground
        self._battery = (battery_pct, plugged)
        if model:
            self._model = model
        self.update()

    def paintEvent(self, _evt) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(6, 6, -6, -6)

        p.setBrush(QColor(8, 18, 32, 180))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(rect, 12, 12)
        pen = QPen(QColor(98, 184, 255, 170))
        pen.setWidth(1)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(rect, 12, 12)

        now = datetime.now()
        clock = now.strftime("%H:%M:%S")
        date_es = f"{_ES_WEEKDAYS[now.weekday()]} {now.day} de {_ES_MONTHS[now.month - 1]}"

        p.setPen(QColor(98, 184, 255, 230))
        p.setFont(QFont("Consolas", 9, QFont.Bold))
        p.drawText(rect.left() + 16, rect.top() + 22, "CONTEXT")

        p.setPen(QColor(255, 255, 255, 235))
        p.setFont(QFont("Consolas", 22, QFont.Bold))
        p.drawText(rect.left() + 16, rect.top() + 56, clock)

        p.setPen(QColor(200, 220, 245, 200))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(rect.left() + 16, rect.top() + 78, date_es.upper())

        y = rect.top() + 104
        p.setPen(QColor(140, 200, 255, 200))
        p.setFont(QFont("Consolas", 8, QFont.Bold))
        p.drawText(rect.left() + 16, y, "FOCO")
        p.setPen(QColor(230, 240, 255, 220))
        p.setFont(QFont("Segoe UI", 9))
        fg = (self._foreground or "—")[:32]
        p.drawText(rect.left() + 16, y + 16, fg)

        y2 = rect.top() + 142
        bat_pct, plugged = self._battery
        if bat_pct >= 0:
            p.setPen(QColor(140, 200, 255, 200))
            p.setFont(QFont("Consolas", 8, QFont.Bold))
            p.drawText(rect.left() + 16, y2, "ENERGÍA")
            col = QColor(120, 230, 160) if bat_pct > 30 or plugged else QColor(255, 180, 80)
            if bat_pct < 15 and not plugged:
                col = QColor(255, 90, 90)
            p.setPen(col)
            p.setFont(QFont("Consolas", 11, QFont.Bold))
            tag = "AC" if plugged else "BAT"
            p.drawText(rect.left() + 78, y2, f"{bat_pct:3.0f}%  {tag}")

        if self._model:
            p.setPen(QColor(140, 200, 255, 160))
            p.setFont(QFont("Consolas", 7))
            p.drawText(rect.left() + 16, rect.bottom() - 10, f"core: {self._model}")

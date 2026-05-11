"""Splash de presentación: logo UMAG + título Jarvan + boot bars.

Aparece al iniciar durante ~2.4s y se desvanece. Sin marco, semitransparente,
centrada. Ideal para abrir la demo de presentación universitaria.
"""
from __future__ import annotations

import math

from PyQt5.QtCore import QPointF, QPropertyAnimation, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PyQt5.QtWidgets import QApplication, QGraphicsOpacityEffect, QWidget


class SplashWindow(QWidget):
    finished = pyqtSignal()

    W = 720
    H = 420

    def __init__(self, university: str = "UNIVERSIDAD DE MAGALLANES", subtitle: str = "Prototipo de Asistente IA Local") -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.resize(self.W, self.H)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            screen.center().x() - self.W // 2,
            screen.center().y() - self.H // 2,
        )

        self._t = 0.0
        self._progress = 0.0
        self._university = university
        self._subtitle = subtitle

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)
        self._anim = QPropertyAnimation(self._opacity, b"opacity", self)
        self._anim.setDuration(400)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def show_and_run(self, total_ms: int = 2400) -> None:
        self.show()
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        QTimer.singleShot(total_ms - 400, self._fade_out)
        QTimer.singleShot(total_ms, self._end)

    def _fade_out(self) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._opacity.opacity())
        self._anim.setEndValue(0.0)
        self._anim.start()

    def _end(self) -> None:
        self.close()
        self.finished.emit()

    def _tick(self) -> None:
        self._t += 0.016
        self._progress = min(1.0, self._progress + 0.01)
        self.update()

    def paintEvent(self, _evt) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.HighQualityAntialiasing, True)
        w, h = self.width(), self.height()

        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, QColor(10, 18, 32, 240))
        bg.setColorAt(1.0, QColor(4, 8, 18, 240))
        rect = self.rect().adjusted(8, 8, -8, -8)
        p.setBrush(bg)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(rect, 18, 18)

        pen = QPen(QColor(98, 184, 255, 200))
        pen.setWidth(1)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(rect, 18, 18)

        self._draw_corners(p, rect)

        cx, cy = w / 2, h / 2 - 40
        for i in range(3):
            r = 50 + i * 18 + math.sin(self._t * 2 + i) * 3
            pen = QPen(QColor(120, 200, 255, 180 - i * 40))
            pen.setWidthF(1.5 - i * 0.4)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            start = int((self._t * 60 + i * 60) % 360) * 16
            span = (240 - i * 30) * 16
            p.drawArc(int(cx - r), int(cy - r), int(r * 2), int(r * 2), start, span)

        core = QRadialGradient(cx, cy, 36)
        core.setColorAt(0.0, QColor(255, 255, 255, 240))
        core.setColorAt(0.5, QColor(120, 200, 255, 200))
        core.setColorAt(1.0, QColor(40, 100, 200, 0))
        p.setBrush(core)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), 36, 36)

        p.setPen(QColor(230, 245, 255))
        p.setFont(QFont("Consolas", 28, QFont.Bold))
        p.drawText(0, int(cy + 90), w, 40, Qt.AlignCenter, "J A R V A N")

        p.setPen(QColor(98, 184, 255, 220))
        p.setFont(QFont("Consolas", 9, QFont.Bold))
        p.drawText(0, int(cy + 132), w, 18, Qt.AlignCenter, self._subtitle.upper())

        p.setPen(QColor(150, 200, 240, 180))
        p.setFont(QFont("Consolas", 8))
        p.drawText(0, int(cy + 156), w, 14, Qt.AlignCenter, self._university)

        bar_w = 320
        bar_h = 4
        bx = (w - bar_w) // 2
        by = int(cy + 188)
        p.setBrush(QColor(30, 60, 100, 150))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(bx, by, bar_w, bar_h, 2, 2)
        grad = QLinearGradient(bx, 0, bx + bar_w, 0)
        grad.setColorAt(0.0, QColor(60, 160, 255))
        grad.setColorAt(1.0, QColor(160, 220, 255))
        p.setBrush(grad)
        p.drawRoundedRect(bx, by, int(bar_w * self._progress), bar_h, 2, 2)

        p.setPen(QColor(98, 184, 255, 160))
        p.setFont(QFont("Consolas", 7))
        msgs = ["init core", "loading ollama", "warming models", "calibrating sensors", "ready"]
        idx = min(len(msgs) - 1, int(self._progress * len(msgs)))
        p.drawText(0, by + 18, w, 12, Qt.AlignCenter, msgs[idx].upper())

    def _draw_corners(self, p: QPainter, rect: QRectF) -> None:
        pen = QPen(QColor(98, 184, 255, 200))
        pen.setWidth(2)
        p.setPen(pen)
        c = 28
        r = rect
        p.drawLine(r.left(), r.top() + c, r.left(), r.top())
        p.drawLine(r.left(), r.top(), r.left() + c, r.top())
        p.drawLine(r.right() - c, r.top(), r.right(), r.top())
        p.drawLine(r.right(), r.top(), r.right(), r.top() + c)
        p.drawLine(r.left(), r.bottom() - c, r.left(), r.bottom())
        p.drawLine(r.left(), r.bottom(), r.left() + c, r.bottom())
        p.drawLine(r.right() - c, r.bottom(), r.right(), r.bottom())
        p.drawLine(r.right(), r.bottom(), r.right(), r.bottom() - c)

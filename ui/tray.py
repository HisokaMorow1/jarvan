"""Tray icon: mostrar/ocultar esfera, HUD y telemetría. Salida limpia."""
from __future__ import annotations

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap, QRadialGradient
from PyQt5.QtWidgets import QAction, QMenu, QSystemTrayIcon


def _make_icon() -> QIcon:
    pm = QPixmap(QSize(64, 64))
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    g = QRadialGradient(32, 32, 30)
    g.setColorAt(0.0, QColor(255, 255, 255, 240))
    g.setColorAt(0.5, QColor(80, 180, 255, 220))
    g.setColorAt(1.0, QColor(20, 60, 130, 0))
    p.setBrush(g)
    p.setPen(Qt.NoPen)
    p.drawEllipse(8, 8, 48, 48)
    p.end()
    return QIcon(pm)


class TrayIcon(QSystemTrayIcon):
    def __init__(self, app, sphere, hud, telemetry_panel) -> None:
        super().__init__(_make_icon())
        self.setToolTip("Jarvan")
        self._app = app
        self._sphere = sphere
        self._hud = hud
        self._tel = telemetry_panel

        menu = QMenu()

        a_listen = QAction("Escuchar (Espacio)", menu)
        a_listen.triggered.connect(lambda: sphere.request_listen.emit())
        menu.addAction(a_listen)

        menu.addSeparator()

        self.a_sphere = QAction("Mostrar esfera", menu, checkable=True, checked=True)
        self.a_sphere.toggled.connect(lambda v: sphere.setVisible(v))
        menu.addAction(self.a_sphere)

        self.a_hud = QAction("Mostrar HUD", menu, checkable=True, checked=True)
        self.a_hud.toggled.connect(lambda v: hud.setVisible(v))
        menu.addAction(self.a_hud)

        self.a_tel = QAction("Mostrar telemetría", menu, checkable=True, checked=True)
        self.a_tel.toggled.connect(lambda v: telemetry_panel.setVisible(v))
        menu.addAction(self.a_tel)

        menu.addSeparator()

        a_exit = QAction("Salir", menu)
        a_exit.triggered.connect(app.quit)
        menu.addAction(a_exit)

        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self._sphere.request_listen.emit()

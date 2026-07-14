from __future__ import annotations

from typing import Optional

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter
from PyQt6.QtWidgets import QWidget


class ColorBarWidget(QWidget):
    """Vertical gradient legend showing the current palette and temp range."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(70)
        self.setMinimumHeight(160)
        self._lut: Optional[np.ndarray] = None
        self._tmin = 0.0
        self._tmax = 1.0
        self._fahrenheit = False

    def set_data(self, lut: np.ndarray, tmin: float, tmax: float, fahrenheit: bool) -> None:
        self._lut = lut
        self._tmin = tmin
        self._tmax = tmax
        self._fahrenheit = fahrenheit
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        margin_top, margin_bottom = 10, 10
        bar_w = 22
        bar_x = 8
        bar_h = self.height() - margin_top - margin_bottom

        if self._lut is not None:
            grad = QLinearGradient(0, margin_top, 0, margin_top + bar_h)
            n = self._lut.shape[0]
            for i in range(0, n, 4):
                b, g, r = self._lut[n - 1 - i, 0]
                grad.setColorAt(i / (n - 1), QColor(int(r), int(g), int(b)))
            painter.fillRect(bar_x, margin_top, bar_w, bar_h, grad)
            painter.setPen(Qt.GlobalColor.gray)
            painter.drawRect(bar_x, margin_top, bar_w, bar_h)

        painter.setPen(Qt.GlobalColor.white)
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)

        def fmt(c):
            v = c * 9.0 / 5.0 + 32.0 if self._fahrenheit else c
            return f"{v:.1f} °{'F' if self._fahrenheit else 'C'}"

        painter.drawText(bar_x + bar_w + 6, margin_top + 10, fmt(self._tmax))
        painter.drawText(bar_x + bar_w + 6, margin_top + bar_h, fmt(self._tmin))
        mid = (self._tmin + self._tmax) / 2
        painter.drawText(bar_x + bar_w + 6, margin_top + bar_h // 2 + 4, fmt(mid))

from __future__ import annotations

from typing import Optional

import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel


class VideoLabel(QLabel):
    """Displays the composited thermal frame and reports click position in
    *source* (un-scaled sensor) pixel coordinates for the spot meter."""

    clicked = pyqtSignal(int, int)
    rightClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(320, 240)
        self.setStyleSheet("background-color: #000000;")
        self._src_size = (1, 1)
        self.setMouseTracking(True)

    def set_source_size(self, w: int, h: int) -> None:
        self._src_size = (w, h)

    def set_frame_bgr(self, frame_bgr: np.ndarray) -> None:
        h, w, ch = frame_bgr.shape
        qimg = QImage(frame_bgr.data, w, h, ch * w, QImage.Format.Format_BGR888)
        pix = QPixmap.fromImage(qimg.copy())
        self.setPixmap(pix.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.rightClicked.emit()
            return
        pm = self.pixmap()
        if pm is None or pm.isNull():
            return
        scaled = pm.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
        off_x = (self.width() - scaled.width()) / 2
        off_y = (self.height() - scaled.height()) / 2
        x = event.position().x() - off_x
        y = event.position().y() - off_y
        if 0 <= x < scaled.width() and 0 <= y < scaled.height():
            sx = int(x / scaled.width() * self._src_size[0])
            sy = int(y / scaled.height() * self._src_size[1])
            self.clicked.emit(sx, sy)

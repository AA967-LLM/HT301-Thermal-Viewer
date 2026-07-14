"""Background thread owning the HT301Camera. Same pattern as v1: all
cap.read()/cap.set() calls happen on this single thread since OpenCV
VideoCapture isn't safe to share across threads. GPU processing (denoise/
super-res/colorize) happens in the GUI thread's on_frame handler instead of
here, to avoid CUDA-context-per-thread complications."""
from __future__ import annotations

import queue
import time
from typing import Callable

from PyQt6.QtCore import QThread, pyqtSignal

from app.core.camera import HT301Camera, HT301Error


class CaptureThread(QThread):
    frameReady = pyqtSignal(object)     # FrameInfo
    error = pyqtSignal(str)
    opened = pyqtSignal(int, int)       # width, height
    fps = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._commands: "queue.Queue[Callable]" = queue.Queue()
        self._running = False

    def submit(self, fn: Callable[[HT301Camera], None]) -> None:
        self._commands.put(fn)

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        try:
            cam = HT301Camera()
        except HT301Error as e:
            self.error.emit(str(e))
            return
        except Exception as e:  # noqa: BLE001
            self.error.emit(f"Unexpected error opening camera: {e}")
            return

        self.opened.emit(cam.width, cam.height)
        self._running = True

        frame_count = 0
        t_last_fps = time.monotonic()

        try:
            while self._running:
                while True:
                    try:
                        fn = self._commands.get_nowait()
                    except queue.Empty:
                        break
                    try:
                        fn(cam)
                    except Exception as e:  # noqa: BLE001
                        self.error.emit(f"Command failed: {e}")

                try:
                    info = cam.read()
                except Exception as e:  # noqa: BLE001
                    self.error.emit(f"Read failed: {e}")
                    time.sleep(0.05)
                    continue

                if info is not None:
                    self.frameReady.emit(info)
                    frame_count += 1
                else:
                    # Avoid a tight spin (and flooding stderr with MSMF
                    # warnings) when the device stops delivering frames.
                    time.sleep(0.02)

                now = time.monotonic()
                if now - t_last_fps >= 0.5:
                    self.fps.emit(frame_count / (now - t_last_fps))
                    frame_count = 0
                    t_last_fps = now
        finally:
            cam.release()

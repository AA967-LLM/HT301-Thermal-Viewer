"""Frame -> displayable image processing: normalize, colorize, upscale, annotate."""
from __future__ import annotations

from typing import Optional, Tuple

import cv2
import numpy as np


def c_to_f(c):
    return c * 9.0 / 5.0 + 32.0


def fmt_temp_ui(c: float, fahrenheit: bool) -> str:
    """For Qt labels (which render Unicode fine) -- '29.3 °C' with a real degree sign."""
    v = c_to_f(c) if fahrenheit else c
    return f"{v:.1f} °{'F' if fahrenheit else 'C'}"


def fmt_temp(c: float, fahrenheit: bool) -> str:
    """ASCII-only, no degree sign -- for cv2.putText overlays. OpenCV's
    Hershey fonts can't render the Unicode degree sign; use fmt_temp_ui()
    for anything drawn by Qt instead."""
    v = c_to_f(c) if fahrenheit else c
    return f"{v:.1f}{'F' if fahrenheit else 'C'}"


def normalize_to_u8(temp_c: np.ndarray, tmin: float, tmax: float) -> np.ndarray:
    span = max(tmax - tmin, 0.05)
    norm = (temp_c - tmin) * (255.0 / span)
    return np.clip(norm, 0, 255).astype(np.uint8)


def colorize(gray_u8: np.ndarray, lut: np.ndarray) -> np.ndarray:
    return cv2.applyColorMap(gray_u8, lut)


def upscale(img: np.ndarray, scale: int, smooth: bool = True) -> np.ndarray:
    if scale <= 1:
        return img
    h, w = img.shape[:2]
    interp = cv2.INTER_CUBIC if smooth else cv2.INTER_NEAREST
    return cv2.resize(img, (w * scale, h * scale), interpolation=interp)


class RangeSmoother:
    """Exponential moving average over auto tmin/tmax to avoid flicker."""

    def __init__(self, alpha: float = 0.2):
        self.alpha = alpha
        self._tmin: Optional[float] = None
        self._tmax: Optional[float] = None

    def reset(self):
        self._tmin = None
        self._tmax = None

    def update(self, tmin: float, tmax: float) -> Tuple[float, float]:
        if self._tmin is None:
            self._tmin, self._tmax = tmin, tmax
        else:
            a = self.alpha
            self._tmin = (1 - a) * self._tmin + a * tmin
            self._tmax = (1 - a) * self._tmax + a * tmax
        return self._tmin, self._tmax


def flip_point(pt_xy: Tuple[int, int], width: int, height: int, flip_h: bool, flip_v: bool) -> Tuple[int, int]:
    x, y = pt_xy
    if flip_h:
        x = width - 1 - x
    if flip_v:
        y = height - 1 - y
    return (x, y)


_ROTATE_CV = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}


def rotate_frame(arr: np.ndarray, rotation: int) -> np.ndarray:
    if rotation == 0:
        return arr
    return cv2.rotate(arr, _ROTATE_CV[rotation])


def rotate_point(pt_xy: Tuple[int, int], width: int, height: int, rotation: int) -> Tuple[int, int]:
    x, y = pt_xy
    if rotation == 0:
        return (x, y)
    if rotation == 90:
        return (height - 1 - y, x)
    if rotation == 180:
        return (width - 1 - x, height - 1 - y)
    if rotation == 270:
        return (y, width - 1 - x)
    raise ValueError(f"rotation must be 0/90/180/270, got {rotation}")


def _put_label(img, text, org, color, scale_font=0.45):
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale_font, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale_font, color, 1, cv2.LINE_AA)


def draw_overlay(
    img_bgr: np.ndarray,
    scale: int,
    fahrenheit: bool,
    min_point: Optional[Tuple[int, int]] = None,
    min_c: float = 0.0,
    max_point: Optional[Tuple[int, int]] = None,
    max_c: float = 0.0,
    center_point: Optional[Tuple[int, int]] = None,
    center_c: float = 0.0,
    show_minmax: bool = True,
    show_center: bool = True,
    spot: Optional[Tuple[int, int, float]] = None,
) -> np.ndarray:
    img = img_bgr

    def marker(pt_xy, temp_c, color):
        x, y = int(pt_xy[0] * scale), int(pt_xy[1] * scale)
        r = max(4, scale)
        cv2.drawMarker(img, (x, y), color, markerType=cv2.MARKER_CROSS,
                        markerSize=r * 2, thickness=2, line_type=cv2.LINE_AA)
        _put_label(img, fmt_temp(temp_c, fahrenheit), (x + r + 2, y - r), color)

    if show_minmax and min_point is not None and max_point is not None:
        marker(min_point, min_c, (255, 160, 60))
        marker(max_point, max_c, (40, 40, 255))
    if show_center and center_point is not None:
        cx, cy = int(center_point[0] * scale), int(center_point[1] * scale)
        cv2.drawMarker(img, (cx, cy), (255, 255, 255), markerType=cv2.MARKER_CROSS,
                        markerSize=14, thickness=1, line_type=cv2.LINE_AA)
        _put_label(img, fmt_temp(center_c, fahrenheit), (cx + 10, cy + 16), (255, 255, 255))

    if spot is not None:
        sx, sy, stemp = spot
        x, y = int(sx * scale), int(sy * scale)
        cv2.circle(img, (x, y), 8, (0, 255, 255), 2, cv2.LINE_AA)
        _put_label(img, fmt_temp(stemp, fahrenheit), (x + 12, y + 4), (0, 255, 255))

    return img

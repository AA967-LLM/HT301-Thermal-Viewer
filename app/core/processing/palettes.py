"""Color palettes (look-up tables) for false-color thermal rendering.

Each entry in PALETTES maps a name to a callable that returns a
(256, 1, 3) uint8 BGR array suitable for cv2.LUT(gray_u8, lut).
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import cv2
import numpy as np


def _lut_from_control_points(points: List[Tuple[int, Tuple[int, int, int]]]) -> np.ndarray:
    """points: list of (position 0-255, (R, G, B)), sorted by position."""
    positions = np.array([p[0] for p in points], dtype=np.float64)
    colors = np.array([p[1] for p in points], dtype=np.float64)  # (N, 3) RGB
    xs = np.arange(256, dtype=np.float64)
    r = np.interp(xs, positions, colors[:, 0])
    g = np.interp(xs, positions, colors[:, 1])
    b = np.interp(xs, positions, colors[:, 2])
    bgr = np.stack([b, g, r], axis=1)  # OpenCV wants BGR
    return np.clip(bgr, 0, 255).astype(np.uint8).reshape(256, 1, 3)


def _ironbow() -> np.ndarray:
    return _lut_from_control_points([
        (0, (0, 0, 0)),
        (20, (10, 0, 35)),
        (60, (60, 0, 100)),
        (100, (125, 10, 100)),
        (140, (190, 40, 45)),
        (180, (230, 100, 0)),
        (210, (245, 170, 0)),
        (240, (250, 220, 60)),
        (255, (255, 255, 220)),
    ])


def _rainbow_hc() -> np.ndarray:
    return _lut_from_control_points([
        (0, (0, 0, 20)),
        (32, (10, 0, 130)),
        (64, (0, 90, 220)),
        (96, (0, 190, 190)),
        (128, (0, 220, 60)),
        (160, (200, 230, 0)),
        (192, (255, 150, 0)),
        (224, (255, 60, 0)),
        (255, (255, 255, 255)),
    ])


def _arctic() -> np.ndarray:
    return _lut_from_control_points([
        (0, (10, 0, 40)),
        (60, (20, 30, 130)),
        (120, (40, 150, 220)),
        (170, (180, 230, 255)),
        (200, (255, 255, 255)),
        (225, (255, 200, 120)),
        (255, (255, 90, 30)),
    ])


def _lava() -> np.ndarray:
    return _lut_from_control_points([
        (0, (0, 0, 0)),
        (60, (60, 0, 10)),
        (120, (170, 0, 20)),
        (170, (230, 90, 0)),
        (210, (250, 170, 20)),
        (240, (255, 230, 120)),
        (255, (255, 255, 255)),
    ])


def _glowbow() -> np.ndarray:
    return _lut_from_control_points([
        (0, (5, 0, 30)),
        (50, (60, 0, 110)),
        (100, (170, 0, 160)),
        (150, (255, 40, 90)),
        (200, (255, 150, 0)),
        (255, (255, 255, 150)),
    ])


def _whitehot() -> np.ndarray:
    v = np.arange(256, dtype=np.uint8)
    return np.stack([v, v, v], axis=1).reshape(256, 1, 3)


def _blackhot() -> np.ndarray:
    v = (255 - np.arange(256)).astype(np.uint8)
    return np.stack([v, v, v], axis=1).reshape(256, 1, 3)


def _from_cv_colormap(cmap: int):
    def build() -> np.ndarray:
        gray = np.arange(256, dtype=np.uint8).reshape(256, 1)
        return cv2.applyColorMap(gray, cmap).reshape(256, 1, 3)
    return build


_BUILDERS = {
    "Ironbow": _ironbow,
    "Rainbow HC": _rainbow_hc,
    "Arctic": _arctic,
    "Lava": _lava,
    "Glowbow": _glowbow,
    "White Hot": _whitehot,
    "Black Hot": _blackhot,
    "Inferno": _from_cv_colormap(cv2.COLORMAP_INFERNO),
    "Turbo": _from_cv_colormap(cv2.COLORMAP_TURBO),
    "Jet": _from_cv_colormap(cv2.COLORMAP_JET),
    "Hot": _from_cv_colormap(cv2.COLORMAP_HOT),
}

PALETTE_NAMES = list(_BUILDERS.keys())

_cache: Dict[str, np.ndarray] = {}


def get_palette(name: str) -> np.ndarray:
    if name not in _cache:
        if name not in _BUILDERS:
            raise KeyError(f"Unknown palette: {name}")
        _cache[name] = _BUILDERS[name]()
    return _cache[name]

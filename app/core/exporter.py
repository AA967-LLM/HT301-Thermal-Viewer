"""
Dual-layer capture export: every snapshot writes a viewable PNG *and* the
raw per-pixel temperature array (.npy) plus a JSON sidecar with every
radiometric parameter active at capture time, all sharing one basename.
This is the data-preservation foundation the whole pro measurement suite
(reprocessing, batch export, PDF reports) depends on.

Auto-exports to the user's real Pictures\\Thermal Camera folder -- resolved
via the Windows Known Folder API (SHGetKnownFolderPath) rather than a
hardcoded `~\\Pictures` guess, since that guess breaks under OneDrive
folder redirection or a relocated user profile.
"""
from __future__ import annotations

import ctypes
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

APP_SUBFOLDER = "Thermal Camera"

# FOLDERID_Pictures, see:
# https://learn.microsoft.com/windows/win32/shell/knownfolderid
_FOLDERID_PICTURES = "{33E28130-4E1E-4676-835A-98395C3BC3BB}"


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort), ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_str(cls, guid_str: str) -> "_GUID":
        guid = cls()
        ctypes.windll.ole32.CLSIDFromString(ctypes.c_wchar_p(guid_str), ctypes.byref(guid))
        return guid


def get_pictures_dir() -> Path:
    """Resolve the real Windows Pictures folder, honoring redirection."""
    if sys.platform != "win32":
        return Path.home() / "Pictures"
    try:
        buf = ctypes.c_wchar_p()
        guid = _GUID.from_str(_FOLDERID_PICTURES)
        result = ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, 0, ctypes.byref(buf))
        if result == 0 and buf.value:
            path = Path(buf.value)
            ctypes.windll.ole32.CoTaskMemFree(buf)
            return path
    except Exception:
        pass
    return Path.home() / "Pictures"


def get_export_root() -> Path:
    return get_pictures_dir() / APP_SUBFOLDER


class Exporter:
    def __init__(self, root: Optional[Path] = None):
        self.root = root or get_export_root()

    def _day_dir(self, when: datetime) -> Path:
        d = self.root / when.strftime("%Y-%m-%d")
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_capture(self, rendered_bgr: np.ndarray, temp_c: np.ndarray, metadata: dict,
                      out_dir: Optional[Path] = None) -> dict:
        """Writes <basename>.png, <basename>_tempC.npy, <basename>.json.

        `metadata` should include whatever radiometric/display state matters
        for reprocessing (emissivity, distance, humidity, ambient, reflected,
        correction, palette, range mode, rotation, mirror, min/max/avg/center
        temps, serial, firmware). Caller owns exactly what goes in it.
        """
        now = datetime.now()
        day_dir = out_dir or self._day_dir(now)
        basename = f"HT301_{now.strftime('%Y%m%d_%H%M%S_%f')[:-3]}"

        png_path = day_dir / f"{basename}.png"
        npy_path = day_dir / f"{basename}_tempC.npy"
        json_path = day_dir / f"{basename}.json"

        cv2.imwrite(str(png_path), rendered_bgr)
        np.save(npy_path, temp_c.astype(np.float32))

        sidecar = dict(metadata)
        sidecar["timestamp"] = now.isoformat()
        sidecar["image_shape"] = list(temp_c.shape)
        json_path.write_text(json.dumps(sidecar, indent=2, default=_json_default), encoding="utf-8")

        return {"png": png_path, "npy": npy_path, "json": json_path}


def _json_default(o):
    if hasattr(o, "__dict__"):
        return o.__dict__
    try:
        return asdict(o)
    except TypeError:
        return str(o)

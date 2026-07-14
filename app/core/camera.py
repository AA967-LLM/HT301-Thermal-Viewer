"""
Driver for the HT-301 / T2S+ / InfiRay "Tiny1" family of Y16 UVC thermal
cameras, on Windows.

These cameras expose a standard UVC video interface plus a vendor
extension unit that is (ab)used through OpenCV's CAP_PROP_ZOOM property to:
  * switch the stream between a colorized preview and "raw16" mode, where
    every pixel is the sensor's 14-bit ADC value,
  * push radiometric parameters (emissivity, distance, humidity, ambient
    and reflected temperature, an operator correction offset),
  * trigger a flat-field (shutter) calibration,
  * switch between the -20..120C and -20..450C measurement ranges.

Every raw16 frame carries, appended after the visible image, several rows
of metadata: per-frame calibration coefficients, the sensor's own min/max/
average/center readings, FPA and shutter temperatures, serial number and
firmware string.

The wire protocol was reverse-engineered by the open-source community,
most notably stawel/ht301_hacklib (GPLv3):
    https://github.com/stawel/ht301_hacklib
with the Windows CAP_MSMF fix contributed by JoJoBond in that project's
issue tracker (#2). This module is an independent re-implementation of the
same protocol for this project; only the openly published wire-format
knowledge (register offsets, the Planck-law temperature formula, the
atmospheric-transmittance model) is reused, no code was copied.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np

ROWS_SPECIAL_DATA = 4
ZERO_C = 273.15
SUPPORTED_RESOLUTIONS = {(240, 180), (256, 192), (384, 288), (640, 512)}

# Vendor extension-unit commands, sent via cap.set(CAP_PROP_ZOOM, value)
_CMD_RAW16 = 0x8004
_CMD_CALIBRATE = 0x8000
_CMD_RANGE_NORMAL = 0x8020
_CMD_RANGE_HIGH = 0x8021

_SET_CORRECTION = 0 * 4
_SET_REFLECTION = 1 * 4
_SET_AMBIENT = 2 * 4
_SET_HUMIDITY = 3 * 4
_SET_EMISSIVITY = 4 * 4
_SET_DISTANCE = 5 * 4


class HT301Error(RuntimeError):
    pass


@dataclass
class FrameInfo:
    raw: np.ndarray             # (h, w) uint16 raw ADC image
    temp_c: np.ndarray          # (h, w) float32 temperature in Celsius
    min_c: float
    max_c: float
    center_c: float
    avg_c: float
    min_point: Tuple[int, int]
    max_point: Tuple[int, int]
    center_point: Tuple[int, int]
    fpa_temp_c: float
    shutter_temp_c: float
    core_temp_c: float
    emissivity: float
    distance: float
    humidity: float
    ambient_c: float
    reflected_c: float
    serial: str
    firmware: str


def _read_u16(arr: np.ndarray, offset: int) -> int:
    return int(arr[offset])


def _read_f32(arr: np.ndarray, offset: int) -> float:
    return float(arr[offset:offset + 2].view(np.float32)[0])


def _read_ascii(arr_u16: np.ndarray, offset: int, n_u16: int) -> str:
    b = arr_u16[offset:offset + n_u16].view(np.uint8)
    return b.tobytes().split(b"\x00")[0].decode("ascii", errors="replace")


class HT301Camera:
    """Driver for the HT-301 / T2S+ / InfiRay Y16 UVC thermal cameras."""

    def __init__(self, index: Optional[int] = None, backend: int = cv2.CAP_MSMF):
        self.backend = backend
        self.cap: Optional[cv2.VideoCapture] = None
        self.width = 0
        self.height = 0  # image height, metadata rows excluded
        self._image_pixels = 0
        self._amount_pixels = 0
        self._user_area = 0
        self._fpa_off = 0.0
        self._fpa_div = 1.0
        self._cal_00_offset = 390.0
        self._cal_00_fpamul = 7.05
        self.range_high = False
        self._corr_m = 1.0
        self._corr_b = 0.0

        # user-adjustable radiometric parameters, pushed to the camera
        self.emissivity = 0.95
        self.distance_m = 2
        self.humidity = 0.45
        self.ambient_c = 20.0
        self.reflected_c = 20.0
        self.correction = 0.0

        if index is None:
            index = self._discover()
        self._open(index)

    # -- device discovery ---------------------------------------------------
    @classmethod
    def _discover(cls) -> int:
        for i in range(8):
            cap = cv2.VideoCapture(i, cv2.CAP_MSMF)
            try:
                if not cap.isOpened():
                    continue
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                if (w, h - ROWS_SPECIAL_DATA) in SUPPORTED_RESOLUTIONS:
                    return i
            finally:
                cap.release()
        raise HT301Error(
            "No HT-301-compatible camera found on indices 0-7. "
            "Make sure it is plugged in, drivers are installed, and no "
            "other application (e.g. the Xtherm app) is holding it open."
        )

    def _open(self, index: int) -> None:
        cap = cv2.VideoCapture(index, self.backend)
        if not cap.isOpened():
            raise HT301Error(f"Could not open camera at index {index}")
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if (w, h - ROWS_SPECIAL_DATA) not in SUPPORTED_RESOLUTIONS:
            cap.release()
            raise HT301Error(f"Device at index {index} has resolution {w}x{h}, not a known HT-301 mode")

        self.cap = cap
        self.width = w
        self.height = h - ROWS_SPECIAL_DATA
        self._image_pixels = self.width * self.height
        self._init_resolution_constants()

        self.cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
        self.cap.set(cv2.CAP_PROP_ZOOM, _CMD_RAW16)
        self.calibrate()
        self.push_parameters()

    def _init_resolution_constants(self) -> None:
        w = self.width
        if w == 640:
            self._fpa_off, self._fpa_div, self._amount_pixels = 6867, 33.8, w * 3
        elif w == 384:
            self._fpa_off, self._fpa_div, self._amount_pixels = 7800, 36.0, w * 3
        elif w == 256:
            self._fpa_off, self._fpa_div, self._amount_pixels = 8617, 37.682, w
            self._cal_00_offset, self._cal_00_fpamul = 170.0, 0.0
        elif w == 240:
            self._fpa_off, self._fpa_div, self._amount_pixels = 7800, 36.0, w
        else:
            raise HT301Error(f"Unsupported sensor width {w}")
        self._user_area = self._amount_pixels + 127

    # -- control commands -----------------------------------------------
    def calibrate(self) -> None:
        """Trigger a flat-field (shutter) calibration. The shutter clicks and briefly blocks the view."""
        self.cap.set(cv2.CAP_PROP_ZOOM, _CMD_CALIBRATE)

    def set_range_high(self, high: bool) -> None:
        """Switch between -20..120C (default) and -20..450C measurement ranges."""
        self.cap.set(cv2.CAP_PROP_ZOOM, _CMD_RANGE_HIGH if high else _CMD_RANGE_NORMAL)
        self.range_high = high
        self._corr_m, self._corr_b = (1.17, -40.9) if high else (1.0, 0.0)

    def _send_float(self, position: int, value: float) -> None:
        b = np.array([value], dtype=np.float32).view(np.uint8)
        for i in range(4):
            self.cap.set(cv2.CAP_PROP_ZOOM, ((position + i) << 8) | int(b[i]))

    def _send_u16(self, position: int, value: int) -> None:
        b = np.array([value], dtype=np.uint16).view(np.uint8)
        for i in range(2):
            self.cap.set(cv2.CAP_PROP_ZOOM, ((position + i) << 8) | int(b[i]))

    def push_parameters(self) -> None:
        """Send the current emissivity/distance/humidity/ambient/reflected/correction to the camera."""
        self._send_float(_SET_CORRECTION, self.correction)
        self._send_float(_SET_REFLECTION, self.reflected_c)
        self._send_float(_SET_AMBIENT, self.ambient_c)
        self._send_float(_SET_HUMIDITY, self.humidity)
        self._send_float(_SET_EMISSIVITY, self.emissivity)
        self._send_u16(_SET_DISTANCE, int(self.distance_m))

    # -- frame reading --------------------------------------------------
    def read(self) -> Optional[FrameInfo]:
        ret, frame_raw = self.cap.read()
        if not ret or frame_raw is None:
            return None
        u16 = frame_raw.view(np.uint16).ravel()
        if u16.size < self._image_pixels + self._amount_pixels + 40:
            return None

        image = u16[:self._image_pixels].reshape(self.height, self.width)
        meta = u16
        base = self._image_pixels

        shutter_raw = _read_u16(meta, base + self._amount_pixels + 1)
        shutter_c = shutter_raw / 10.0 - ZERO_C
        core_raw = _read_u16(meta, base + self._amount_pixels + 2)
        core_c = core_raw / 10.0 - ZERO_C

        cal_00 = float(_read_u16(meta, base + self._amount_pixels))
        cal_01 = _read_f32(meta, base + self._amount_pixels + 3)
        cal_02 = _read_f32(meta, base + self._amount_pixels + 5)
        cal_03 = _read_f32(meta, base + self._amount_pixels + 7)
        cal_04 = _read_f32(meta, base + self._amount_pixels + 9)
        cal_05 = _read_f32(meta, base + self._amount_pixels + 11)

        correction = _read_f32(meta, base + self._user_area)
        reflected_c = _read_f32(meta, base + self._user_area + 2)
        ambient_c = _read_f32(meta, base + self._user_area + 4)
        humidity = _read_f32(meta, base + self._user_area + 6)
        emissivity = _read_f32(meta, base + self._user_area + 8)
        distance = _read_u16(meta, base + self._user_area + 10)

        fpa_raw = _read_u16(meta, base + 1)
        max_x = _read_u16(meta, base + 2)
        max_y = _read_u16(meta, base + 3)
        max_raw = _read_u16(meta, base + 4)
        min_x = _read_u16(meta, base + 5)
        min_y = _read_u16(meta, base + 6)
        min_raw = _read_u16(meta, base + 7)
        avg_raw = _read_u16(meta, base + 8)
        center_raw = _read_u16(meta, base + 12)

        fpa_c = 20.0 - (float(fpa_raw) - self._fpa_off) / self._fpa_div

        distance_adj = min(20.0, float(distance))
        atm = self._atmospheric_transmittance(humidity, ambient_c, distance_adj)
        numerator_sub = (1.0 - emissivity) * atm * (reflected_c + ZERO_C) ** 4 + (1.0 - atm) * (ambient_c + ZERO_C) ** 4
        denominator = max(emissivity * atm, 1e-6)

        cal_a = cal_02 / (2.0 * cal_01)
        cal_b = (cal_02 * cal_02) / (4.0 * cal_01 * cal_01)
        cal_c = cal_01 * shutter_c ** 2 + shutter_c * cal_02
        cal_d = cal_03 * fpa_c ** 2 + cal_04 * fpa_c + cal_05

        cal_00_corr = 0
        if not self.range_high:
            cal_00_corr = int(self._cal_00_offset - fpa_c * self._cal_00_fpamul)
        table_offset = cal_00 - max(0, cal_00_corr)

        temp_table = self._temperature_table(
            cal_01, cal_c, cal_d, cal_a, cal_b, numerator_sub, denominator,
            table_offset, distance_adj, ambient_c, correction,
        )

        temp_c = temp_table[np.clip(image, 0, len(temp_table) - 1)]

        serial = _read_ascii(meta, base + self._amount_pixels + 32, 3)
        firmware = _read_ascii(meta, base + self._amount_pixels + 24, 8)

        return FrameInfo(
            raw=image,
            temp_c=temp_c,
            min_c=float(temp_table[min_raw]),
            max_c=float(temp_table[max_raw]),
            center_c=float(temp_table[center_raw]),
            avg_c=float(temp_table[avg_raw]),
            min_point=(int(min_x), int(min_y)),
            max_point=(int(max_x), int(max_y)),
            center_point=(self.width // 2, self.height // 2),
            fpa_temp_c=fpa_c,
            shutter_temp_c=shutter_c,
            core_temp_c=core_c,
            emissivity=emissivity,
            distance=float(distance),
            humidity=humidity,
            ambient_c=ambient_c,
            reflected_c=reflected_c,
            serial=serial,
            firmware=firmware,
        )

    @staticmethod
    def _water_vapor_coeff(humidity: float, t_atm: float) -> float:
        h1, h2, h3, h4 = 1.5587, 0.06939, -2.7816e-4, 6.8455e-7
        return humidity * math.exp(h1 + h2 * t_atm + h3 * t_atm ** 2 + h4 * t_atm ** 3)

    def _atmospheric_transmittance(self, humidity: float, t_atm: float, distance: float) -> float:
        k_atm = 1.9
        neg_sqrt_d = -math.sqrt(max(distance, 0.0))
        sqrt_w = math.sqrt(max(self._water_vapor_coeff(humidity, t_atm), 0.0))
        a1, a2 = 0.006569, 0.01262
        b1, b2 = -0.002276, -0.00667
        return k_atm * math.exp(neg_sqrt_d * (a1 + b1 * sqrt_w)) + (1.0 - k_atm) * math.exp(neg_sqrt_d * (a2 + b2 * sqrt_w))

    def _temperature_table(self, cal_01, cal_c, cal_d, cal_a, cal_b,
                            numerator_sub, denominator, table_offset,
                            distance_adj, ambient_c, correction) -> np.ndarray:
        x = np.arange(16384, dtype=np.float64)
        with np.errstate(invalid="ignore", divide="ignore"):
            n = np.sqrt(np.abs(((x - table_offset) * cal_d + cal_c) / cal_01 + cal_b))
            n = np.nan_to_num(n)
            wtot = np.power(n - cal_a + ZERO_C, 4)
            ratio = (wtot - numerator_sub) / denominator
            ttot = np.sign(ratio) * np.power(np.abs(ratio), 0.25) - ZERO_C
            table = ttot + (distance_adj * 0.85 - 1.125) * (ttot - ambient_c) / 100.0 + correction
        table = self._corr_m * table + self._corr_b
        return np.nan_to_num(table, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None

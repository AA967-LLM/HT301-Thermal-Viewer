from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QFormLayout, QGroupBox,
    QLabel, QComboBox, QPushButton, QRadioButton, QButtonGroup, QDoubleSpinBox,
    QSpinBox, QSlider, QCheckBox, QMessageBox, QFileDialog, QScrollArea,
)

from app.core.camera import FrameInfo, HT301Camera
from app.core.processing import palettes
from app.core.processing import render as proc
from app.core.exporter import Exporter, get_export_root

from .capture_thread import CaptureThread
from .widgets.video_view import VideoLabel
from .widgets.colorbar import ColorBarWidget
from .theme import DARK_QSS

APP_DATA_DIR = Path.home() / "AppData" / "Local" / "HT301Viewer"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HT-301 Thermal Viewer")
        self.resize(1180, 760)
        self.setMinimumSize(900, 600)
        self.setStyleSheet(DARK_QSS)

        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

        self.latest_info: Optional[FrameInfo] = None
        self.range_smoother = proc.RangeSmoother(alpha=0.15)
        self.spot: Optional[tuple] = None
        self.sensor_size = (384, 288)
        self._last_disp_size = None

        self._mirror_axis = "h"
        self._mirror_settle_timer = QTimer(self)
        self._mirror_settle_timer.setSingleShot(True)
        self._mirror_settle_timer.timeout.connect(self._settle_mirror_axis)

        self.settings = self._load_settings()
        custom_root = self.settings.get("export_root")
        self.exporter = Exporter(root=Path(custom_root) if custom_root else None)
        self.video_writer: Optional[cv2.VideoWriter] = None
        self.recording = False
        self.snapshot_pending = False

        self._build_ui()
        self._build_shortcuts()
        self.combo_rotation.currentIndexChanged.connect(self._on_rotation_changed)

        self.thread = CaptureThread()
        self.thread.frameReady.connect(self.on_frame)
        self.thread.error.connect(self.on_error)
        self.thread.opened.connect(self.on_opened)
        self.thread.fps.connect(self.on_fps)
        self.thread.start()

        self.statusBar().showMessage("Connecting to camera...")

    # ================= settings persistence =================
    def _settings_path(self) -> Path:
        return APP_DATA_DIR / "settings.json"

    def _load_settings(self) -> dict:
        try:
            return json.loads(self._settings_path().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_settings(self) -> None:
        self._settings_path().write_text(json.dumps(self.settings, indent=2), encoding="utf-8")

    # ================= UI construction =================
    def _build_ui(self):
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        self.video_label = VideoLabel()
        self.video_label.clicked.connect(self.on_video_clicked)
        self.video_label.rightClicked.connect(self.on_video_right_clicked)
        layout.addWidget(self.video_label, stretch=1)

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setSpacing(12)
        panel_layout.addWidget(self._build_readout_group())
        panel_layout.addWidget(self._build_display_group())
        panel_layout.addWidget(self._build_radiometric_group())
        panel_layout.addWidget(self._build_actions_group())
        panel_layout.addWidget(self._build_export_group())
        panel_layout.addStretch(1)

        # Wrapped in a scroll area so a short window scrolls the panel
        # instead of Qt force-compressing every row to fit (that failure
        # mode caused real overlapping-text bugs before).
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedWidth(340)
        scroll.setWidget(panel)

        layout.addWidget(scroll)
        self.setCentralWidget(central)
        self.statusBar()

    def _build_readout_group(self):
        box = QGroupBox("Readout")
        grid = QGridLayout(box)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        grid.setContentsMargins(8, 14, 8, 8)
        self.lbl_max = QLabel("-- °C"); self.lbl_min = QLabel("-- °C")
        self.lbl_center = QLabel("-- °C"); self.lbl_avg = QLabel("-- °C")
        for lbl, color in ((self.lbl_max, "#ff4d4d"), (self.lbl_min, "#4da6ff"),
                           (self.lbl_center, "#ffffff"), (self.lbl_avg, "#c9cdd3")):
            lbl.setStyleSheet(f"font-size: 13pt; font-weight: 700; color: {color};")
        grid.addWidget(QLabel("Max"), 0, 0); grid.addWidget(self.lbl_max, 0, 1)
        grid.addWidget(QLabel("Min"), 1, 0); grid.addWidget(self.lbl_min, 1, 1)
        grid.addWidget(QLabel("Center"), 2, 0); grid.addWidget(self.lbl_center, 2, 1)
        grid.addWidget(QLabel("Average"), 3, 0); grid.addWidget(self.lbl_avg, 3, 1)
        self.colorbar = ColorBarWidget()
        grid.addWidget(self.colorbar, 0, 2, 4, 1)
        self.lbl_fps = QLabel("FPS: --")
        self.lbl_fps.setStyleSheet("color: #7c8794;")
        grid.addWidget(self.lbl_fps, 4, 0, 1, 2)
        self.lbl_spot = QLabel("Spot: (click image)")
        self.lbl_spot.setStyleSheet("color: #ffd24d;")
        grid.addWidget(self.lbl_spot, 5, 0, 1, 3)
        return box

    def _build_display_group(self):
        box = QGroupBox("Display")
        v = QVBoxLayout(box)
        v.setSpacing(10)
        v.setContentsMargins(8, 14, 8, 8)

        row = QHBoxLayout()
        row.addWidget(QLabel("Palette"))
        self.combo_palette = QComboBox()
        self.combo_palette.addItems(palettes.PALETTE_NAMES)
        self.combo_palette.setCurrentText("Ironbow")
        row.addWidget(self.combo_palette, stretch=1)
        v.addLayout(row)

        range_row = QHBoxLayout()
        self.radio_auto = QRadioButton("Auto range")
        self.radio_manual = QRadioButton("Manual range")
        self.radio_auto.setChecked(True)
        g = QButtonGroup(self); g.addButton(self.radio_auto); g.addButton(self.radio_manual)
        range_row.addWidget(self.radio_auto); range_row.addWidget(self.radio_manual)
        v.addLayout(range_row)

        self.manual_range_widget = QWidget()
        manual_row = QHBoxLayout(self.manual_range_widget)
        manual_row.setContentsMargins(0, 0, 0, 0)
        self.spin_tmin = QDoubleSpinBox(); self.spin_tmin.setRange(-40, 550); self.spin_tmin.setValue(15); self.spin_tmin.setSuffix(" °C")
        self.spin_tmax = QDoubleSpinBox(); self.spin_tmax.setRange(-40, 550); self.spin_tmax.setValue(35); self.spin_tmax.setSuffix(" °C")
        manual_row.addWidget(QLabel("Min")); manual_row.addWidget(self.spin_tmin)
        manual_row.addWidget(QLabel("Max")); manual_row.addWidget(self.spin_tmax)
        v.addWidget(self.manual_range_widget)
        self.manual_range_widget.setVisible(False)
        self.radio_manual.toggled.connect(self.manual_range_widget.setVisible)

        units_row = QHBoxLayout()
        self.radio_celsius = QRadioButton("Celsius"); self.radio_fahrenheit = QRadioButton("Fahrenheit")
        self.radio_celsius.setChecked(True)
        ug = QButtonGroup(self); ug.addButton(self.radio_celsius); ug.addButton(self.radio_fahrenheit)
        units_row.addWidget(self.radio_celsius); units_row.addWidget(self.radio_fahrenheit)
        v.addLayout(units_row)

        scale_row = QHBoxLayout()
        scale_row.addWidget(QLabel("Zoom"))
        self.slider_scale = QSlider(Qt.Orientation.Horizontal)
        self.slider_scale.setRange(1, 6); self.slider_scale.setValue(3)
        self.lbl_scale = QLabel("3x")
        self.slider_scale.valueChanged.connect(lambda v: self.lbl_scale.setText(f"{v}x"))
        scale_row.addWidget(self.slider_scale, stretch=1); scale_row.addWidget(self.lbl_scale)
        v.addLayout(scale_row)

        marker_row = QHBoxLayout()
        self.chk_minmax = QCheckBox("Min/Max"); self.chk_minmax.setChecked(True)
        self.chk_center = QCheckBox("Center"); self.chk_center.setChecked(True)
        marker_row.addWidget(self.chk_minmax); marker_row.addWidget(self.chk_center)
        v.addLayout(marker_row)

        flip_row = QHBoxLayout()
        self.chk_mirror = QCheckBox("Mirror"); self.chk_mirror.setChecked(True)
        flip_row.addWidget(self.chk_mirror)
        v.addLayout(flip_row)

        rotate_row = QHBoxLayout()
        rotate_row.addWidget(QLabel("Orientation"))
        self.combo_rotation = QComboBox()
        self.combo_rotation.addItems(["0", "90 CW", "180", "270 CW"])
        rotate_row.addWidget(self.combo_rotation, stretch=1)
        v.addLayout(rotate_row)
        self.btn_rotate = QPushButton("Rotate 90°")
        self.btn_rotate.clicked.connect(self._cycle_rotation)
        v.addWidget(self.btn_rotate)

        return box

    def _build_radiometric_group(self):
        box = QGroupBox("Radiometric parameters")
        outer = QVBoxLayout(box)
        outer.setSpacing(10)
        outer.setContentsMargins(8, 14, 8, 8)

        form = QFormLayout()
        form.setSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.spin_emissivity = QDoubleSpinBox(); self.spin_emissivity.setRange(0.01, 1.0)
        self.spin_emissivity.setSingleStep(0.01); self.spin_emissivity.setValue(0.95)
        self.spin_distance = QSpinBox(); self.spin_distance.setRange(0, 20); self.spin_distance.setValue(2); self.spin_distance.setSuffix(" m")
        self.spin_humidity = QDoubleSpinBox(); self.spin_humidity.setRange(0.0, 1.0)
        self.spin_humidity.setSingleStep(0.05); self.spin_humidity.setValue(0.45)
        self.spin_ambient = QDoubleSpinBox(); self.spin_ambient.setRange(-40, 100); self.spin_ambient.setValue(20.0); self.spin_ambient.setSuffix(" °C")
        self.spin_reflected = QDoubleSpinBox(); self.spin_reflected.setRange(-40, 500); self.spin_reflected.setValue(20.0); self.spin_reflected.setSuffix(" °C")
        self.spin_correction = QDoubleSpinBox(); self.spin_correction.setRange(-20, 20); self.spin_correction.setValue(0.0); self.spin_correction.setSuffix(" °C")
        for name, widget in [("Emissivity", self.spin_emissivity), ("Distance", self.spin_distance), ("Humidity", self.spin_humidity),
                              ("Ambient temp", self.spin_ambient), ("Reflected temp", self.spin_reflected), ("Correction", self.spin_correction)]:
            form.addRow(name, widget)
        outer.addLayout(form)

        self.btn_apply_params = QPushButton("Apply to camera")
        self.btn_apply_params.clicked.connect(self.apply_radiometric_params)
        outer.addWidget(self.btn_apply_params)
        self.chk_high_range = QCheckBox("High range (-20..450 °C)")
        self.chk_high_range.toggled.connect(self.on_high_range_toggled)
        outer.addWidget(self.chk_high_range)
        return box

    def _build_actions_group(self):
        box = QGroupBox("Actions")
        v = QVBoxLayout(box)
        v.setSpacing(10)
        v.setContentsMargins(8, 14, 8, 8)
        row1 = QHBoxLayout()
        self.btn_calibrate = QPushButton("Calibrate (FFC)")
        self.btn_calibrate.clicked.connect(self.on_calibrate)
        self.btn_snapshot = QPushButton("Snapshot")
        self.btn_snapshot.clicked.connect(self.on_snapshot)
        row1.addWidget(self.btn_calibrate); row1.addWidget(self.btn_snapshot)
        v.addLayout(row1)
        row2 = QHBoxLayout()
        self.btn_record = QPushButton("Start Recording")
        self.btn_record.setObjectName("recordBtn"); self.btn_record.setCheckable(True)
        self.btn_record.toggled.connect(self.on_record_toggled)
        self.btn_fullscreen = QPushButton("Maximize"); self.btn_fullscreen.setCheckable(True)
        self.btn_fullscreen.toggled.connect(self.on_fullscreen_toggled)
        row2.addWidget(self.btn_record); row2.addWidget(self.btn_fullscreen)
        v.addLayout(row2)
        hint = QLabel("Space=snapshot  R=record  C=calibrate  F=maximize  T=rotate  Right-click=clear spot")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #7c8794; font-size: 9pt;")
        v.addWidget(hint)
        return box

    def _build_export_group(self):
        box = QGroupBox("Export Location")
        v = QVBoxLayout(box)
        v.setSpacing(8)
        v.setContentsMargins(8, 14, 8, 8)
        self.lbl_export_path = QLabel(str(self.exporter.root))
        self.lbl_export_path.setWordWrap(True)
        self.lbl_export_path.setStyleSheet("color: #9fb4c7; font-size: 9pt;")
        v.addWidget(self.lbl_export_path)
        row = QHBoxLayout()
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._browse_export_location)
        btn_reset = QPushButton("Reset")
        btn_reset.clicked.connect(self._reset_export_location)
        row.addWidget(btn_browse); row.addWidget(btn_reset)
        v.addLayout(row)
        return box

    def _build_shortcuts(self):
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, activated=self.on_snapshot)
        QShortcut(QKeySequence(Qt.Key.Key_R), self, activated=lambda: self.btn_record.toggle())
        QShortcut(QKeySequence(Qt.Key.Key_C), self, activated=self.on_calibrate)
        QShortcut(QKeySequence(Qt.Key.Key_F), self, activated=lambda: self.btn_fullscreen.toggle())
        QShortcut(QKeySequence(Qt.Key.Key_T), self, activated=self._cycle_rotation)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self._exit_fullscreen)

    def _rotation_degrees(self) -> int:
        return (0, 90, 180, 270)[self.combo_rotation.currentIndex()]

    def _cycle_rotation(self):
        self.combo_rotation.setCurrentIndex((self.combo_rotation.currentIndex() + 1) % 4)

    def _on_rotation_changed(self, _index: int):
        self._mirror_settle_timer.start(3000)

    def _settle_mirror_axis(self):
        new_axis = "v" if self._rotation_degrees() in (90, 270) else "h"
        if new_axis != self._mirror_axis:
            self._mirror_axis = new_axis
            self.statusBar().showMessage(f"Mirror axis adjusted for {self._rotation_degrees()} deg orientation", 3000)

    # ================= capture thread callbacks =================
    def on_opened(self, w: int, h: int):
        self.sensor_size = (w, h)
        self.video_label.set_source_size(w, h)
        self.statusBar().showMessage(f"Connected  |  sensor {w}x{h}  |  backend MSMF")

    def on_error(self, msg: str):
        self.statusBar().showMessage(f"Error: {msg}")
        QMessageBox.critical(self, "Camera error", msg)

    def on_fps(self, fps: float):
        self.lbl_fps.setText(f"FPS: {fps:.1f}")

    def on_frame(self, info: FrameInfo):
        self.latest_info = info
        fahrenheit = self.radio_fahrenheit.isChecked()
        scale = self.slider_scale.value()
        mirror_on = self.chk_mirror.isChecked()
        flip_h = mirror_on and self._mirror_axis == "h"
        flip_v = mirror_on and self._mirror_axis == "v"
        w, h = self.sensor_size
        rotation = self._rotation_degrees()

        temp_c = info.temp_c
        if flip_h:
            temp_c = np.fliplr(temp_c)
        if flip_v:
            temp_c = np.flipud(temp_c)
        min_point = proc.flip_point(info.min_point, w, h, flip_h, flip_v)
        max_point = proc.flip_point(info.max_point, w, h, flip_h, flip_v)
        center_point = proc.flip_point(info.center_point, w, h, flip_h, flip_v)

        if rotation != 0:
            temp_c = proc.rotate_frame(temp_c, rotation)
            min_point = proc.rotate_point(min_point, w, h, rotation)
            max_point = proc.rotate_point(max_point, w, h, rotation)
            center_point = proc.rotate_point(center_point, w, h, rotation)
        if flip_h or flip_v or rotation != 0:
            temp_c = np.ascontiguousarray(temp_c)

        disp_w, disp_h = (h, w) if rotation in (90, 270) else (w, h)
        if (disp_w, disp_h) != self._last_disp_size:
            self.video_label.set_source_size(disp_w, disp_h)
            self._last_disp_size = (disp_w, disp_h)

        if self.radio_auto.isChecked():
            tmin, tmax = self.range_smoother.update(info.min_c, info.max_c)
        else:
            self.range_smoother.reset()
            tmin, tmax = self.spin_tmin.value(), self.spin_tmax.value()
            if fahrenheit:
                tmin, tmax = (tmin - 32) * 5 / 9, (tmax - 32) * 5 / 9

        lut = palettes.get_palette(self.combo_palette.currentText())
        gray = proc.normalize_to_u8(temp_c, tmin, tmax)
        color = proc.colorize(gray, lut)
        color = proc.upscale(color, scale)

        spot = None
        if self.spot is not None:
            sx, sy = self.spot
            if 0 <= sy < temp_c.shape[0] and 0 <= sx < temp_c.shape[1]:
                spot = (sx, sy, float(temp_c[sy, sx]))
                self.lbl_spot.setText(f"Spot ({sx},{sy}): {proc.fmt_temp_ui(spot[2], fahrenheit)}")

        color = proc.draw_overlay(
            color, scale, fahrenheit,
            min_point=min_point, min_c=info.min_c, max_point=max_point, max_c=info.max_c,
            center_point=center_point, center_c=info.center_c,
            show_minmax=self.chk_minmax.isChecked(), show_center=self.chk_center.isChecked(), spot=spot,
        )

        color = np.ascontiguousarray(color)
        self.video_label.set_frame_bgr(color)
        self.colorbar.set_data(lut, tmin, tmax, fahrenheit)
        self.lbl_max.setText(proc.fmt_temp_ui(info.max_c, fahrenheit))
        self.lbl_min.setText(proc.fmt_temp_ui(info.min_c, fahrenheit))
        self.lbl_center.setText(proc.fmt_temp_ui(info.center_c, fahrenheit))
        self.lbl_avg.setText(proc.fmt_temp_ui(info.avg_c, fahrenheit))

        if self.recording:
            self._write_recording_frame(color)
        if self.snapshot_pending:
            self.snapshot_pending = False
            self._save_snapshot(color, temp_c, info)

    # ================= user interactions =================
    def on_video_clicked(self, sx: int, sy: int):
        self.spot = (sx, sy)

    def on_video_right_clicked(self):
        self.spot = None
        self.lbl_spot.setText("Spot: (click image)")

    def apply_radiometric_params(self):
        e, d, h, a, r, c = (self.spin_emissivity.value(), self.spin_distance.value(), self.spin_humidity.value(),
                            self.spin_ambient.value(), self.spin_reflected.value(), self.spin_correction.value())

        def cmd(cam: HT301Camera):
            cam.emissivity, cam.distance_m, cam.humidity = e, d, h
            cam.ambient_c, cam.reflected_c, cam.correction = a, r, c
            cam.push_parameters()

        self.thread.submit(cmd)
        self.statusBar().showMessage("Radiometric parameters sent to camera", 3000)

    def on_calibrate(self):
        self.thread.submit(lambda cam: cam.calibrate())
        self.statusBar().showMessage("Calibrating (flat-field correction)...", 2000)

    def on_high_range_toggled(self, checked: bool):
        self.thread.submit(lambda cam: cam.set_range_high(checked))
        self.range_smoother.reset()

    def on_snapshot(self):
        self.snapshot_pending = True

    def _save_snapshot(self, color_bgr: np.ndarray, temp_c: np.ndarray, info: FrameInfo):
        metadata = {
            "emissivity": self.spin_emissivity.value(), "distance_m": self.spin_distance.value(),
            "humidity": self.spin_humidity.value(), "ambient_c": self.spin_ambient.value(),
            "reflected_c": self.spin_reflected.value(), "correction": self.spin_correction.value(),
            "palette": self.combo_palette.currentText(), "range_mode": "auto" if self.radio_auto.isChecked() else "manual",
            "rotation": self._rotation_degrees(), "mirror": self.chk_mirror.isChecked(),
            "min_c": info.min_c, "max_c": info.max_c, "avg_c": info.avg_c, "center_c": info.center_c,
            "serial": info.serial, "firmware": info.firmware,
        }
        paths = self.exporter.save_capture(color_bgr, temp_c, metadata)
        self.statusBar().showMessage(f"Saved {paths['png'].name}", 4000)

    def on_record_toggled(self, checked: bool):
        self.recording = checked
        self.btn_record.setText("Stop Recording" if checked else "Start Recording")
        if not checked and self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None
            self.statusBar().showMessage("Recording saved", 3000)

    def _write_recording_frame(self, color_bgr: np.ndarray):
        if self.video_writer is None:
            out_dir = self.exporter._day_dir(datetime.now())
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = out_dir / f"HT301_{stamp}.mp4"
            h, w = color_bgr.shape[:2]
            fourcc = cv2.VideoWriter.fourcc(*"mp4v")
            self.video_writer = cv2.VideoWriter(str(path), fourcc, 25.0, (w, h))
            self.statusBar().showMessage(f"Recording to {path.name}", 3000)
        self.video_writer.write(color_bgr)

    def on_fullscreen_toggled(self, checked: bool):
        self.showMaximized() if checked else self.showNormal()

    def _exit_fullscreen(self):
        if self.isFullScreen() or self.isMaximized():
            self.btn_fullscreen.setChecked(False)

    def _browse_export_location(self):
        chosen = QFileDialog.getExistingDirectory(self, "Choose export folder for pictures and video", str(self.exporter.root))
        if not chosen:
            return
        self.exporter.root = Path(chosen)
        self.settings["export_root"] = chosen
        self._save_settings()
        self.lbl_export_path.setText(str(self.exporter.root))
        self.statusBar().showMessage(f"Export location set to {chosen}", 4000)

    def _reset_export_location(self):
        self.exporter.root = get_export_root()
        self.settings.pop("export_root", None)
        self._save_settings()
        self.lbl_export_path.setText(str(self.exporter.root))
        self.statusBar().showMessage("Export location reset to Pictures\\Thermal Camera", 4000)

    def closeEvent(self, event):
        self.thread.stop()
        self.thread.wait(2000)
        if self.video_writer is not None:
            self.video_writer.release()
        super().closeEvent(event)

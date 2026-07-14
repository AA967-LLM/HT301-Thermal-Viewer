DARK_QSS = """
QMainWindow, QWidget {
    background-color: #14161a;
    color: #e6e8eb;
    font-family: 'Segoe UI', sans-serif;
    font-size: 10pt;
}
QGroupBox {
    border: 1px solid #2a2e35;
    border-radius: 6px;
    margin-top: 10px;
    padding: 8px 6px 6px 6px;
    font-weight: 600;
    font-size: 10pt;
    color: #9fb4c7;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}
QLabel { color: #d7dade; font-size: 10pt; }
QLabel[role="value"] {
    font-size: 15pt;
    font-weight: 700;
    color: #ffffff;
}
QLabel[role="hint"] { color: #7c8794; font-size: 8pt; }
QPushButton {
    background-color: #1f2329;
    border: 1px solid #343a42;
    border-radius: 5px;
    padding: 6px 12px;
    color: #e6e8eb;
    font-size: 10pt;
    min-height: 22px;
}
QPushButton:hover { background-color: #2a2f37; border-color: #4a5560; }
QPushButton:pressed { background-color: #14171b; }
QPushButton:checked {
    background-color: #2f6fed;
    border-color: #2f6fed;
    color: white;
}
QPushButton#recordBtn:checked {
    background-color: #d33a3a;
    border-color: #d33a3a;
}
QComboBox, QDoubleSpinBox, QSpinBox {
    background-color: #1c1f24;
    border: 1px solid #343a42;
    border-radius: 4px;
    padding: 3px 6px;
    color: #e6e8eb;
    font-size: 10pt;
    min-height: 22px;
}
QDoubleSpinBox, QSpinBox {
    padding-right: 20px;
}
QComboBox QAbstractItemView {
    background-color: #1c1f24;
    selection-background-color: #2f6fed;
    font-size: 10pt;
}
QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    min-height: 11px;
    border-left: 1px solid #343a42;
    border-bottom: 1px solid #2a2e35;
    background-color: #23272e;
}
QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    min-height: 11px;
    border-left: 1px solid #343a42;
    background-color: #23272e;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #2f6fed;
}
QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {
    background-color: #1c50b0;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    width: 7px; height: 7px;
    image: none;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    width: 7px; height: 7px;
    image: none;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #2a2e35;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #2f6fed;
    width: 14px;
    margin: -6px 0;
    border-radius: 7px;
}
QRadioButton, QCheckBox { color: #d7dade; spacing: 6px; font-size: 10pt; min-height: 20px; }
QStatusBar { background-color: #101215; color: #8b95a1; font-size: 9pt; }
QSplitter::handle { background-color: #14161a; }
QTabWidget::pane { border: 1px solid #2a2e35; border-radius: 6px; top: -1px; }
QTabBar::tab {
    background-color: #1c1f24;
    color: #d7dade;
    font-size: 10pt;
    min-height: 26px;
    padding: 6px 12px;
    border: 1px solid #2a2e35;
    border-bottom: none;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #2f6fed;
    color: white;
}
QListWidget {
    background-color: #1c1f24;
    color: #e6e8eb;
    font-size: 10pt;
    border: 1px solid #2a2e35;
}
"""

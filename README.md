<div align="center">
  <img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/solid/temperature-high.svg" width="80" height="80" alt="Thermal Camera Icon"/>
  
  <h1>🔥 HT-301 Thermal Viewer v2</h1>
  
  <p><b>High-Performance USB Thermal Camera Software for Professionals and Hobbyists</b></p>

  <p>
    <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge&logo=open-source-initiative&logoColor=white" alt="License: MIT"></a>
    <img src="https://img.shields.io/badge/Python-3.10+-green.svg?style=for-the-badge&logo=python&logoColor=white" alt="Python Version">
    <img src="https://img.shields.io/badge/UI-PyQt6-red.svg?style=for-the-badge&logo=qt&logoColor=white" alt="PyQt6 UI">
    <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey.svg?style=for-the-badge&logo=windows&logoColor=white" alt="Platform">
  </p>

  <p>
    <i>#ThermalImaging &nbsp; #HVAC &nbsp; #Electrical &nbsp; #Thermography &nbsp; #HT301 &nbsp; #InfiRay &nbsp; #DIY &nbsp; #OpenSource</i>
  </p>
</div>

---

## 🌟 Overview

The **HT-301** is a high-performance, USB-connected thermal camera originally designed for Android smartphones, offering a professional-grade **384 × 288 pixel resolution** and a smooth **25Hz refresh rate**. 

This project (**v2**) is a ground-up rebuild of the desktop viewer suite, designed to unlock the camera's full potential for **HVAC technicians**, **electricians**, **electronics repair specialists**, and **DIY hobbyists**. It provides a lightweight, highly responsive, and robust viewer with radiometric capabilities, bypassing the limitations of mobile apps and delivering a true desktop-class analysis experience.

## ✨ Key Features

- **High-Resolution & High Framerate**: Full support for the native 384×288 sensor at 25Hz.
- **Radiometric Analysis**: Real-time multi-ROI (Region of Interest) engine. Track points, lines, bounding boxes, and polygons with live Min/Max/Avg/Std temperature readouts.
- **Dynamic Palettes & Isotherms**: Apply standard thermal palettes (Iron, Rainbow, White Hot, etc.) and configure custom isotherm banding to highlight specific temperature ranges.
- **Professional Export Workflow**: Dual-layer save format. Captures the standard visualization (`.png`) alongside the raw radiometric temperature array (`.npy`) and a metadata sidecar (`.json`) automatically sorted by date into your `Pictures\Thermal Camera` directory.
- **Lightweight & Portable**: Stripped of unnecessary bloat. Uses a pure CPU-fallback pipeline for max compatibility across laptops and field computers (no massive multi-GB GPU dependencies required, fully relying on efficient OpenCV/NumPy processing).
- **Responsive UI**: Built on PyQt6 with a scalable, high-DPI aware glassmorphic and modern styling format.

## 🛠️ Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/AA967-LLM/HT301-Thermal-Viewer.git
   cd HT301-Thermal-Viewer
   ```

2. **Set up a Python environment:**
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Linux/macOS
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch the viewer:**
   ```bash
   python app/main.py
   ```

## 👷 Usage Scenarios

<details>
  <summary><b>❄️ HVAC & Insulation</b></summary>
  Instantly identify energy leaks, missing insulation, or blocked ducts. Use the continuous export mode and wide FOV to rapidly document an entire building envelope and attach the auto-generated images to client reports.
</details>

<details>
  <summary><b>⚡ Electrical & Panels</b></summary>
  Spot overloaded circuits, failing breakers, or loose connections before they become fire hazards. The live multi-ROI feature allows you to place measurement probes on individual phases and compare the delta-T instantly.
</details>

<details>
  <summary><b>🔌 Electronics Repair (PCB Diagnostics)</b></summary>
  Identify shorted capacitors or overheating ICs on densely packed PCBs. The manual temperature scaling allows you to narrow the thermal span to a fraction of a degree, making faint heat signatures glow vividly.
</details>

## 🤝 Credits & Acknowledgements

* **Core Developer / Architect:** [AA967-LLM](https://github.com/AA967-LLM) & Google Antigravity Council (Alpha, Zeta, Omega).
* **Hardware:** Developed for the HTI HT-301 / InfiRay T3S camera hardware.
* Special thanks to the open-source thermography community for their pioneering work on reverse-engineering USB thermal protocols.

## 📜 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for more details. 

*You are free to use, modify, and distribute this software in commercial and non-commercial settings, provided credit is given.*

---
<div align="center">
  <i>Built with 💡 for the open-source engineering community.</i>
</div>

# HT-301 Viewer v2 -- Handoff / Progress Log

**Purpose of this file**: if the current AI assistant runs out of budget mid-build,
a different tool (Gemini CLI, another Claude session, a human) can read this
file and continue without re-deriving context. Update it after every
meaningful milestone, not just at the end.

## Project

v1 (in the parent directory, `..\`) is a complete, working, tested live
radiometric viewer for the HT-301/InfiRay thermal camera. It is NOT being
touched -- v2 is a ground-up rebuild in this `v2\` directory with its own
venv, aimed at "one universal app that does it all": GPU-accelerated image
processing, a proper capture/export pipeline, a professional measurement
suite, and workflow features (gallery, sessions, reports).

Feature scope was set by a 5-member AI council (Claude + Groq/Llama-3.3-70B +
DeepSeek-chat + 2 Claude sub-personas). Full transcripts: `design/council_responses/*.md`.
User approved **all four phases** of the synthesized plan (see below).

## Critical architecture correction vs. the council's advice

The council (and DeepSeek/Groq specifically) suggested `cv2.cuda.*` for GPU
acceleration. **This does not work** with the standard pip `opencv-python`
wheel -- CUDA support requires building OpenCV from source, which is not
practical here. Real GPU acceleration stack instead:

- **PyTorch with CUDA wheels** (`pip install torch --index-url
  https://download.pytorch.org/whl/cu1XX`) -- prebuilt, no source build,
  works immediately on this machine's NVIDIA GPU. Used for denoising /
  super-resolution inference.
- **ONNX Runtime** as the portable fallback path for machines without
  NVIDIA: `onnxruntime-directml` (DirectML, works on any DX12 GPU --
  Intel Xe, AMD Radeon iGPU/dGPU -- no vendor toolkit needed) or plain
  `onnxruntime` (CPU) if no GPU at all.
- Hardware is detected ONCE at startup (`app/core/hardware.py`), the chosen
  backend is cached in a singleton, and every processing module asks that
  singleton which device to use. No per-frame hardware probing.
- Plain `cv2` (CPU) stays for classical ops (LUT colorize, resize, drawing)
  -- these are already fast enough at 384x288 (proven in v1).
- Super-resolution: use OpenCV's `dnn_superres` module with a **pretrained**
  FSRCNN/ESPCN model (downloaded once, cached locally), not a custom-trained
  model -- there's no training data/pipeline available in this project.
  True multi-frame super-res (DeepSeek's MFSR idea, using handheld jitter)
  is a stretch goal noted in Phase 2 but may ship as simple multi-frame
  temporal averaging + single-frame pretrained SR if time runs out.

## GPU on this machine

NVIDIA GeForce RTX 4080 Laptop GPU, driver 591.86, 12282 MiB VRAM, compute
capability 8.9 (Ada Lovelace). Install PyTorch via
`pip install torch --index-url https://download.pytorch.org/whl/cu124`
(driver is current enough for cu124/cu126 wheels). Plenty of VRAM headroom
for denoise/SR models at 384x288 input.

## Phase plan (user approved: build all four)

1. **Foundation** -- dual-layer capture (PNG + raw `.npy` + JSON sidecar)
   auto-exported to `Pictures\Thermal Camera\YYYY-MM-DD\`; GPU/CPU backend
   auto-detect; persistent multi-ROI engine (point/line/box/polygon with
   live min/max/avg/std); ported live-view GUI. **Must be tested against
   the real camera before Phase 2 starts.**
2. **GPU image quality** -- temporal+spatial denoising, pretrained
   super-resolution, hardware video encode (ffmpeg NVENC/QSV/AMF, fallback
   to existing mp4v cv2.VideoWriter).
3. **Pro measurement suite** -- delta-T alarms between ROIs, isotherm
   banding, condensation/moisture-risk overlay (reuses existing
   humidity/ambient params), ROI trend logging + strip chart, Kalman
   hot/cold-spot tracker.
4. **Universal-app workflow** -- gallery/filmstrip browser (SQLite index +
   thumbnails), session/project containers, batch export/reprocess, PDF
   report generation, keyboard-driven capture, presets ("looks"), plugin
   hook system.

## Directory layout (planned)

```
v2/
  .venv/                  isolated venv for v2 (already created)
  design/                 dev-time only, not shipped
    ai_council.py           council brainstorm script
    offload.py               code-gen offload helper (see below)
    council_responses/       saved council transcripts
  app/
    core/
      camera.py              ported from v1 ht301/camera.py (protocol unchanged)
      hardware.py             GPU/CPU backend detection singleton
      roi.py                   ROI engine (point/line/box/polygon, stats)
      exporter.py              dual-layer save + auto-export to Pictures
      session.py                session/project manifest
      presets.py                 named parameter bundle save/load
      plugins.py                  plugin hook loader
      processing/
        denoise.py               temporal+spatial denoise
        superres.py               pretrained SR wrapper
        palettes.py               ported from v1
        overlay.py                 ROI/isotherm/alarm drawing
        tracker.py                  Kalman hot/cold-spot tracker
        video_encode.py             ffmpeg hardware encoder wrapper
      gallery_index.py           SQLite thumbnail/metadata index
      report.py                   PDF report generator
    gui/
      capture_thread.py
      main_window.py
      widgets/  (video_view, colorbar, roi_tools, gallery_view, trend_chart, theme)
  main.py
  requirements.txt
```

## Offloading to cloud LLMs to save budget

`design/offload.py` sends a spec (markdown file describing ONE module: exact
class/function signatures, behavior, edge cases) to DeepSeek / Groq / NVIDIA
NIM and saves the raw generated source. Working providers as of this build
(verified with live auth check, keys never printed): `deepseek`, `groq`,
`nvidia`. All keys load from `D:\Google antigravity\.env\.env` -- never
hardcode a key value in any file in this repo.

Pattern used: write `design/specs/<module>.md` with the exact contract, run
`offload.py --provider <p> --spec design/specs/<module>.md --out app/core/<module>.py`,
then the reviewing assistant reads the generated file, fixes/tightens it,
and runs it against the real camera/data before marking the task done.
Used mainly for Phase 3/4 leaf modules (report generator, gallery index,
presets, plugin loader) where correctness is easy to verify by inspection
and unit-testing in isolation. Phase 1 foundation and the hardware/ROI/
camera core were hand-written for tight correctness control, not offloaded.

## Status

- [x] AI council run, synthesized, user approved all 4 phases
- [x] Offload helper + this handoff doc created
- [x] GPU environment checked: RTX 4080 Laptop, driver 591.86, compute 8.9
- [x] v2/app scaffolded (app/core, app/core/processing, app/gui, app/gui/widgets)
- [x] Core deps installed in v2/.venv: opencv-python, numpy, PyQt6, pyqtgraph,
      reportlab, torch 2.6.0+cu124 (CUDA confirmed working), kornia 0.8.3
- [x] `app/core/camera.py` -- ported verbatim from v1, protocol unchanged
- [x] `app/core/processing/palettes.py` -- ported verbatim from v1
- [x] `app/core/hardware.py` -- CUDA/DirectML/CPU backend singleton (hand-written)
- [x] `app/core/roi.py` -- multi-ROI engine: point/line/rect/polygon + stats + JSON persistence (hand-written)
- [x] `app/core/exporter.py` -- dual-layer save (PNG+npy+JSON) to real Windows
      Pictures\Thermal Camera via SHGetKnownFolderPath, not a hardcoded path (hand-written)
- [x] `app/core/processing/render.py` -- normalize/colorize/upscale/overlay
      (ported from v1) + draw_rois/isotherm_overlay/moisture_risk_overlay (new, hand-written)
- [x] `app/core/processing/denoise.py` -- kornia bilateral (GPU) + cv2 CPU fallback, temporal EMA (hand-written)
- [x] `app/core/processing/superres.py` -- GPU bicubic+unsharp detail enhance,
      NOT a learned SR model (see "critical architecture correction" above) (hand-written)
- [x] `app/core/processing/video_encode.py` -- ffmpeg hw encoder (NVENC
      confirmed working via real probe, min probe size 320x240 -- 64x64 gives
      false negative on NVENC's minimum dimension) with mp4v CPU fallback (hand-written)
- [x] `app/core/processing/tracker.py` -- Kalman hot/cold-spot tracker
      (offloaded to DeepSeek, reviewed, no changes needed)
- [x] `app/core/gallery_index.py` -- SQLite capture index + thumbnails
      (offloaded to DeepSeek, reviewed, fixed a scan_folder double-count bug)
- [x] `app/core/session.py` -- session/project manifest (offloaded to DeepSeek, reviewed, no changes needed)
- [x] `app/core/report.py` -- PDF report generator via reportlab (offloaded
      to DeepSeek, reviewed; layout not yet visually verified -- generate one
      real report and eyeball it before considering Phase 4 done)
- [x] `app/core/presets.py`, `app/core/plugins.py` -- hand-written, trivial
- [x] GUI layer built: `app/gui/capture_thread.py`, `app/gui/main_window.py`
      (Live / ROI-Alarms / Capture tabs), `app/gui/widgets/*` (video_view w/
      ROI click-to-draw, colorbar, trend_chart via pyqtgraph, gallery_view dialog)
- [x] App launches against the real camera, confirmed alive and actively
      processing: real process (venv python.exe on Windows spawns a ~4MB
      stub PID that execs a second real PID -- look at the SECOND python.exe
      process, not the one Start-Process returns) showed 970MB working set,
      249 CPU-seconds over ~17s wall time, and appeared in
      `nvidia-smi --query-compute-apps` as an active CUDA context. No
      crashes, no real stderr errors (one harmless QFont cosmetic warning).
      Fixed one real bug found this way: capture_thread's read loop spun
      at 100% CPU with no delay on failed frame grabs, flooding stderr with
      MSMF warnings -- added a 20ms sleep on `info is None`.
- [ ] **NOT individually click-tested**: ROI drawing (point/line/rect/
      polygon), delta-T alarm, isotherm band, moisture overlay, hot/cold
      tracker, trend chart window, session create/end, gallery dialog,
      preset save/apply, PDF report generation, plugin reload. These are
      all wired in code and imports/launches cleanly, but there's no
      screenshot/GUI-automation tool available in this environment to
      click-test them -- the user needs to exercise these and report back
      any bugs found.
- [ ] v2 packaged as standalone exe (holding off until user confirms core
      features work -- PyInstaller with torch+cuda+kornia will produce a
      very large exe (~2-4GB) and take a while, don't build until the app
      itself is confirmed good)

## Bugs found and fixed after initial ship

1. **Denoise defaulted ON**, making the image look "diffused" vs v1's crisp
   look. Fixed: default OFF, and lightened the params for when it IS enabled
   (`app/core/processing/denoise.py` defaults: temporal_alpha 0.35->0.65,
   spatial_strength 1.0->0.5 -- higher alpha = less smoothing).
2. **Layout collapse/overlap under high DPI** (this machine: 2560x1600
   physical @ 150% scale, AppliedDPI 144). Root cause: `theme.py` used
   pixel-unit `font-size` (e.g. `12px`), which doesn't reliably rescale
   across a window state change (e.g. maximize) on Windows -- switched
   everything to `pt` units, added `min-height` floors to every interactive
   control, explicit `setSpacing()`/`setContentsMargins()` on every layout
   (was relying on style defaults, which computed too tight under this
   DPI/style combo -- this was a SEPARATE bug from the DPI one, visible even
   in maximized/plenty-of-space screenshots), wrapped each tab's content in
   a `QScrollArea` so oversized content scrolls instead of getting
   force-compressed, converted the radiometric-parameters grid to
   `QFormLayout` (more robust than hand-rolled QGridLayout for label:field
   rows), and manual-range min/max fields now hide unless "Manual range" is
   selected (also just reduces clutter).
3. Fixed via `design/_screenshot_test.py` -- renders the real MainWindow
   off-screen and grabs pixel-accurate PNGs via Qt's `widget.grab()` at both
   normal and maximized window states. **Reuse this for any future layout
   bug report instead of guessing** -- iterate: screenshot -> Read the PNG
   -> diagnose from the actual pixels -> fix -> re-screenshot -> confirm.
4. Spin box up/down arrows were invisible/unclickable out of the box (Qt
   quirk: styling a QSpinBox via QSS without defining the button
   subcontrols breaks native button geometry), then briefly rendered as
   "one square" after a bad first fix attempt -- actually the same DPI
   font-size bug from #2 collapsing the row height out from under the
   buttons. Fixed together with #2; explicit `::up-button`/`::down-button`/
   `::up-arrow`/`::down-arrow` QSS now in `theme.py`.
5. Fullscreen (`showFullScreen()`) switched to maximize (`showMaximized()`)
   -- avoids a class of Windows compositor/DPI quirk with real OS fullscreen.
   Added `QApplication.setHighDpiScaleFactorRoundingPolicy(PassThrough)` in
   `app/main.py` (must be called before QApplication is constructed).
6. Units: added `fmt_temp_ui()` in `render.py` for proper "29.3 °C" with a
   real Unicode degree sign, used by every Qt-rendered label. The original
   `fmt_temp()` stays ASCII-only ("29.3C", no degree sign) because it's also
   used for `cv2.putText` on-image overlays -- OpenCV's Hershey fonts can't
   render the Unicode degree sign.
7. Added user-configurable export location (Capture tab: browse/reset,
   persisted in `%LOCALAPPDATA%\HT301Viewer\settings.json`). Sessions and
   the gallery dialog were hardcoded to the default Pictures path -- fixed
   to respect the override too.

## Major pivot: stripped back to a lightweight build

After using the full 4-phase build, the user's verdict: no visible
difference from v1 day-to-day, and torch+CUDA is a multi-GB dependency with
no business being in a "runs on any laptop, no fuss" app. Explicit
instruction: strip all the bloat, keep it crisp and lightweight, ship it.

**Deleted entirely** (not just unused -- removed from disk): `hardware.py`,
`roi.py`, `gallery_index.py`, `session.py`, `presets.py`, `plugins.py`,
`report.py`, `processing/denoise.py`, `processing/superres.py`,
`processing/tracker.py`, `processing/video_encode.py`,
`gui/widgets/trend_chart.py`, `gui/widgets/gallery_view.py`. That's all of
Phase 2 (GPU pipeline), Phase 3 (measurement suite), and Phase 4 (workflow)
except the one feature kept.

**Kept**: live view (camera.py/palettes.py/render.py unchanged), mirror/
rotate, radiometric params, calibrate/snapshot/record (back to plain
`cv2.VideoWriter`, no ffmpeg hardware-encode complexity), and the ONE
addition worth keeping from the whole exercise: **configurable export
location** with dual-layer save (PNG + raw `.npy` temperature array + JSON
metadata sidecar) auto-organized into `Pictures\Thermal Camera\YYYY-MM-DD\`.

**requirements.txt** is back to exactly v1's: `opencv-python`, `numpy`,
`PyQt6`. venv recreated from scratch (was bloated with torch/kornia/
pyqtgraph/reportlab + their transitive deps even after `pip uninstall`,
recreating was cleaner than chasing leftover packages) -- 384MB vs. what
would have been several GB with the CUDA-enabled torch wheel.

**Packaged**: `dist\HT301_ThermalViewer_v2.exe`, 88.7MB (comparable to v1's
93MB), confirmed launches standalone without the dev venv/Python installed.

**UI structure simplified back to v1's single-panel layout** (no tabs --
there's only one feature set now, tabs would be pointless indirection).
Kept the QScrollArea wrapping the panel and the pt-unit font fix from the
earlier DPI bug fixes, since those are pure layout-robustness improvements
with zero dependency cost, not "bloat" in any sense that matters here.

If reviving any of the deleted Phase 2/3/4 code later: it's not lost, just
not on disk -- this HANDOFF.md's earlier sections describe what each
removed module did and why, and git history (if this ever gets committed)
would have the full implementations.

## If resuming here

The single highest-priority next step is the GUI layer. Suggested order:
1. `app/gui/capture_thread.py` -- same QThread-owns-camera pattern as v1
   (`..\gui\capture_thread.py`), but the frame-processing pipeline (denoise
   -> upscale -> colorize -> ROI/isotherm overlay) should probably run
   *inside* the capture thread too (not the GUI thread) since it's now
   doing real GPU work per frame -- profile this once running; if it's fast
   enough (RTX 4080 should make this a non-issue) keep it simple in the
   capture thread like v1 did.
2. `app/gui/main_window.py` -- start from v1's `..\gui\main_window.py` as a
   base (same live-view + controls), then add: ROI toolbar (add point/line/
   rect/polygon, list with live stats), export-on-capture wired to
   `exporter.Exporter`, and menu/panel entries for Phase 3/4 features as
   they're wired in. Get Phase 1 (live view + ROI + auto-export) working
   and tested against the real camera FIRST, commit that as a working
   milestone mentally, THEN layer in Phase 2 (denoise/SR toggle, hw-encoded
   recording) and Phase 3/4 features incrementally -- each should be
   independently testable, don't build all the UI at once untested.
3. Test command once main.py exists:
   `..\v2\.venv\Scripts\python.exe app\main.py`

## How to resume

1. `cd "D:\Google antigravity\CREATIONS\HTI_thermal\v2"`
2. Camera protocol/math is identical to v1 -- if in doubt, diff against
   `..\ht301\camera.py` (known-good, tested against the real device).
3. Run `..\v2\.venv\Scripts\python.exe app\main.py` to launch (once it exists).
4. Check the Status checklist above for what's actually done vs. planned --
   do not trust a phase is complete without seeing its checkbox checked AND
   a note that it was tested against the real camera.

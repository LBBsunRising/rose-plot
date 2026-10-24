"""Capture the redesigned UI in every important state."""
from __future__ import annotations

import ctypes
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

QA_DIR = Path(__file__).resolve().parent
AFTER = QA_DIR / "after"
AFTER.mkdir(parents=True, exist_ok=True)


def pump(root, seconds: float) -> None:
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.02)


def shot(root, name: str) -> None:
    from PIL import ImageGrab

    root.attributes("-topmost", True)
    root.lift()
    root.focus_force()
    root.update()
    time.sleep(0.55)
    root.update()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    w, h = root.winfo_width(), root.winfo_height()
    ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(AFTER / name)
    root.attributes("-topmost", False)
    print("shot:", name, (w, h))


def crop2x(source: Path, box: tuple[int, int, int, int], name: str) -> None:
    from PIL import Image

    with Image.open(source) as image:
        region = image.crop(box)
        doubled = region.resize((region.width * 2, region.height * 2), Image.LANCZOS)
        doubled.save(AFTER / name)
        print("crop2x:", name, doubled.size)


def main() -> int:
    import tkinter as tk

    import matplotlib

    matplotlib.use("TkAgg", force=True)
    from rosechart import main_window as mw

    prefs = QA_DIR / "tmp_prefs.json"
    if prefs.exists():
        prefs.unlink()
    root = tk.Tk()
    app = mw.RoseChartApp(root, prefs_path=prefs)
    pump(root, 2.4)
    shot(root, "01_palette.png")

    app._select_right_tab(1)
    pump(root, 0.7)
    shot(root, "02_style.png")
    app._select_right_tab(2)
    pump(root, 0.7)
    shot(root, "03_export.png")
    app._select_right_tab(0)
    app._apply_palette("tech_neon")
    pump(root, 0.8)
    shot(root, "04_palette_neon.png")
    app.pages["palette"].scroll.canvas.yview_moveto(0.42)
    pump(root, 0.5)
    shot(root, "04b_palette_library.png")
    app.pages["palette"].scroll.canvas.yview_moveto(0.0)
    pump(root, 0.4)

    # drag a label and capture the custom-layout state
    chart = app.chart
    label = next(iter(chart.handles))
    handle = chart.handles[label]
    renderer = app.canvas.get_renderer()
    bbox = handle.text.get_window_extent(renderer=renderer)
    app._on_canvas_press(
        SimpleNamespace(button=1, x=(bbox.x0 + bbox.x1) / 2, y=(bbox.y0 + bbox.y1) / 2, dblclick=False)
    )
    target = chart.axis.transData.transform((handle.line_end_x - 0.12, handle.y + 0.16))
    app._on_canvas_motion(SimpleNamespace(button=1, x=float(target[0]), y=float(target[1])))
    pump(root, 0.35)
    shot(root, "05a_dragging_mid.png")
    app._on_canvas_release(SimpleNamespace(button=1, x=float(target[0]), y=float(target[1])))
    pump(root, 0.7)
    shot(root, "05_dragging.png")
    app._clear_layout()
    pump(root, 0.5)
    app._apply_palette("legacy_project")
    pump(root, 0.6)

    # empty state: disable the project column, then show chart 1
    app.col_a_var.set(mw.NO_COLUMN)
    app._on_columns_changed()
    app._on_chart_tab("chart1")
    pump(root, 0.9)
    shot(root, "06_empty_state.png")
    app.col_a_var.set("开发类别")
    app._on_columns_changed()
    pump(root, 0.9)

    # minimum window size
    root.geometry(f"{mw.W.px(1440)}x{mw.W.px(870)}")
    pump(root, 1.1)
    shot(root, "07_small_window.png")

    # scrolled inspector states
    app._select_right_tab(1)
    pump(root, 0.5)
    app.pages["style"].scroll.canvas.yview_moveto(1.0)
    pump(root, 0.5)
    shot(root, "12_style_bottom.png")
    app._select_right_tab(0)
    pump(root, 0.5)
    app.pages["palette"].scroll.canvas.yview_moveto(0.55)
    pump(root, 0.5)
    shot(root, "13_palette_mid.png")
    app.pages["palette"].scroll.canvas.yview_moveto(0.0)
    pump(root, 0.4)

    # detail crops at 2x for typography inspection
    app.root.geometry(f"{mw.W.px(1520)}x{mw.W.px(940)}")
    pump(root, 1.0)
    shot(root, "08_default.png")
    crop2x(AFTER / "08_default.png", (20, 130, 420, 850), "09_left_panel_2x.png")
    crop2x(AFTER / "08_default.png", (1350, 120, 1890, 930), "10_right_panel_2x.png")
    crop2x(AFTER / "08_default.png", (430, 110, 1300, 225), "11_toolbar_2x.png")
    crop2x(AFTER / "03_export.png", (1350, 250, 1890, 1050), "14_export_panel_2x.png")
    crop2x(AFTER / "07_small_window.png", (420, 130, 1400, 980), "15_small_canvas_2x.png")

    from PIL import Image

    with Image.open(AFTER / "01_palette.png") as image:
        thumb = image.resize((480, round(image.height * 480 / image.width)), Image.LANCZOS)
        thumb.save(QA_DIR / "evidence" / "01_palette_480.png")
        print("thumb: evidence/01_palette_480.png", thumb.size)

    app._save_prefs()
    root.destroy()
    if prefs.exists():
        prefs.unlink()
    print("OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)

"""Screenshot the style / export tabs and exercise the real widget callbacks."""
from __future__ import annotations

import ctypes
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

QA_DIR = Path(__file__).resolve().parent / "gui"
QA_DIR.mkdir(parents=True, exist_ok=True)


def pump(root, seconds: float = 0.5) -> None:
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
    time.sleep(0.5)
    root.update()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    w, h = root.winfo_width(), root.winfo_height()
    ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(QA_DIR / name)
    root.attributes("-topmost", False)
    print("screenshot:", name, (w, h))


def main() -> int:
    import tkinter as tk

    import matplotlib

    matplotlib.use("TkAgg", force=True)
    from rosechart import main_window as mw

    root = tk.Tk()
    tmp_prefs = QA_DIR / 'tmp_prefs.json'
    if tmp_prefs.exists():
        tmp_prefs.unlink()
    app = mw.RoseChartApp(root, prefs_path=tmp_prefs)
    pump(root, 2.4)

    app._select_right_tab(1)
    pump(root, 0.8)
    shot(root, "07_style_tab.png")

    # use the real widgets so signal wiring is covered
    app._style_rows["inner_radius"].set_value(0.42, notify=True)
    app._style_rows["outer_radius"].set_value(1.02, notify=True)
    app._style_rows["label_font_size"].set_value(19, notify=True)
    app.show_value_var.set(False)
    app._on_check("show_value", app.show_value_var)
    app.center_var.set("共 {total} 项\n{n} 个类别")
    pump(root, 1.0)
    print("style after widget changes:", app.style.inner_radius, app.style.label_font_size, app.style.show_value)
    shot(root, "08_style_widgets.png")

    app._select_right_tab(2)
    pump(root, 0.8)
    shot(root, "09_export_tab.png")

    app._on_chart_tab("chart2")
    pump(root, 1.0)
    shot(root, "10_chart2.png")

    app._save_prefs()
    root.destroy()
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

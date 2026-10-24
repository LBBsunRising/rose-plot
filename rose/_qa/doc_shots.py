"""Capture clean documentation screenshots from a fresh (default) state."""
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
    time.sleep(0.6)
    root.update()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    w, h = root.winfo_width(), root.winfo_height()
    ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(QA_DIR / name)
    root.attributes("-topmost", False)
    print("shot:", name, (w, h))


def main() -> int:
    import tkinter as tk

    import matplotlib

    matplotlib.use("TkAgg", force=True)
    from rosechart import main_window as mw

    prefs = QA_DIR / "doc_prefs.json"
    if prefs.exists():
        prefs.unlink()
    root = tk.Tk()
    app = mw.RoseChartApp(root, prefs_path=prefs)
    pump(root, 2.4)

    shot(root, "doc_01_palette.png")
    app._select_right_tab(1)
    pump(root, 0.7)
    shot(root, "doc_02_style.png")
    app._select_right_tab(2)
    pump(root, 0.7)
    shot(root, "doc_03_export.png")

    # a colourful palette preview for the README gallery
    app._select_right_tab(0)
    app._apply_palette("tech_neon")
    pump(root, 0.8)
    shot(root, "doc_04_tech_palette.png")

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

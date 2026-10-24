"""Measure the proposed drag fast-path components on the 12-category dataset."""
from __future__ import annotations

import ctypes
import sys
import time
import tkinter as tk
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import matplotlib

matplotlib.use("TkAgg", force=True)

PERF = Path(__file__).resolve().parent
PREFS = PERF / "tmp_prefs5.json"


def pump(root, seconds):
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        root.update()
        time.sleep(0.01)


def draw_ms(app, n=6):
    vals = []
    for _ in range(n):
        t0 = time.perf_counter()
        app.canvas.draw()
        vals.append((time.perf_counter() - t0) * 1000)
    return sum(vals) / len(vals)


def remove_checker(app):
    n = 0
    for ax in list(app.figure.axes):
        if ax.get_zorder() < -50:
            app.figure.delaxes(ax)
            n += 1
    return n


def main() -> int:
    from rosechart import main_window as mw

    if PREFS.exists():
        PREFS.unlink()
    root = tk.Tk()
    app = mw.RoseChartApp(root, prefs_path=PREFS)
    pump(root, 2.4)
    many = ROOT / "_qa" / "edge" / "many_categories.xlsx"
    app.load_file(str(many), silent=True)
    pump(root, 1.2)
    lines = []
    lines.append(f"labels={len(app.chart.handles)} | dpi={app._dpi:.1f}")
    base = draw_ms(app)
    lines.append(f"baseline draw: {base:.1f} ms")
    remove_checker(app)
    no_check = draw_ms(app)
    lines.append(f"without checkerboard: {no_check:.1f} ms")
    # hide all but the first label
    for index, handle in enumerate(app.chart.handles.values()):
        if index:
            handle.text.set_visible(False)
            handle.line.set_visible(False)
    fast = draw_ms(app)
    lines.append(f"without checkerboard + only active label visible: {fast:.1f} ms")
    report = "\n".join(lines)
    print(report)
    (PERF / "bench_variants.txt").write_text(report, encoding="utf-8")
    app._save_prefs()
    root.destroy()
    if PREFS.exists():
        PREFS.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

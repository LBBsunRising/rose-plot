"""Measure how much of resize / slider lag comes from rendering vs Tk itself."""
from __future__ import annotations

import ctypes
import statistics
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
PREFS = PERF / "tmp_prefs3.json"


def pump(root: tk.Tk, seconds: float) -> None:
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        root.update()
        time.sleep(0.01)


def measure_resize(app, root, *, disable_render: bool) -> list[float]:
    original = app._on_stage_configure
    if disable_render:
        app._on_stage_configure = lambda _e=None: None  # type: ignore[method-assign]
    values: list[float] = []
    try:
        for index in range(8):
            width = 1520 - index * 10
            height = 940 - index * 8
            t0 = time.perf_counter()
            root.geometry(f"{app.root.winfo_width() // 1 and width}x{height}")
            for _ in range(3):
                root.update()
                time.sleep(0.02)
            values.append(time.perf_counter() - t0)
    finally:
        app._on_stage_configure = original  # type: ignore[method-assign]
    return values


def measure_slider(app, root, *, disable_render: bool) -> list[float]:
    original = app._render_soon
    if disable_render:
        app._render_soon = lambda *_a, **_k: None  # type: ignore[method-assign]
    values: list[float] = []
    try:
        for index in range(25):
            value = 0.30 + 0.005 * index
            t0 = time.perf_counter()
            app._on_style_slider("inner_radius", value)
            root.update()
            values.append(time.perf_counter() - t0)
    finally:
        app._render_soon = original  # type: ignore[method-assign]
    return values


def main() -> int:
    from rosechart import main_window as mw

    if PREFS.exists():
        PREFS.unlink()
    root = tk.Tk()
    app = mw.RoseChartApp(root, prefs_path=PREFS)
    pump(root, 2.4)
    lines = []
    normal = measure_resize(app, root, disable_render=False)
    pump(root, 0.5)
    no_render = measure_resize(app, root, disable_render=True)
    lines.append(f"resize step (normal):        {statistics.mean(normal)*1000:.0f} ms")
    lines.append(f"resize step (render frozen): {statistics.mean(no_render)*1000:.0f} ms")

    slider_normal = measure_slider(app, root, disable_render=False)
    pump(root, 0.4)
    slider_none = measure_slider(app, root, disable_render=True)
    lines.append(f"slider step (normal):        {statistics.mean(slider_normal)*1000:.0f} ms")
    lines.append(f"slider step (render skipped):{statistics.mean(slider_none)*1000:.0f} ms")

    # label drag with rendering disabled (input handling only)
    chart = app.chart
    if chart is not None:
        canvas = app.canvas
        label = next(iter(chart.handles))
        handle = chart.handles[label]
        renderer = canvas.get_renderer()
        bbox = handle.text.get_window_extent(renderer=renderer)
        app._on_canvas_press(
            type("E", (), {"button": 1, "x": (bbox.x0 + bbox.x1) / 2, "y": (bbox.y0 + bbox.y1) / 2, "dblclick": False})()
        )
        original_draw = canvas.draw_idle
        canvas.draw_idle = lambda *_a, **_k: None  # type: ignore[method-assign]
        values = []
        try:
            for index in range(60):
                target = chart.axis.transData.transform(
                    (handle.line_end_x - 0.0005 * index, handle.y + 0.001 * index)
                )
                t0 = time.perf_counter()
                app._on_canvas_motion(type("E", (), {"button": 1, "x": float(target[0]), "y": float(target[1])})())
                root.update()
                values.append(time.perf_counter() - t0)
            app._on_canvas_release(type("E", (), {"button": 1, "x": float(target[0]), "y": float(target[1])})())
        finally:
            canvas.draw_idle = original_draw  # type: ignore[method-assign]
        lines.append(f"label drag (drawing skipped):{statistics.mean(values)*1000:.2f} ms/event")

    report = "\n".join(lines)
    print(report)
    (PERF / "bench_interactions.txt").write_text(report, encoding="utf-8")
    app._save_prefs()
    root.destroy()
    if PREFS.exists():
        PREFS.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Deeper read-only breakdown: where frame time goes, plus candidate fast paths."""
from __future__ import annotations

import ctypes
import math
import statistics
import sys
import time
import tkinter as tk
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

import matplotlib

matplotlib.use("TkAgg", force=True)

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

PERF = Path(__file__).resolve().parent
PREFS = PERF / "tmp_prefs2.json"


def pump(root: tk.Tk, seconds: float) -> None:
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        root.update()
        time.sleep(0.01)


def ms(values: list[float]) -> float:
    return statistics.mean(values) * 1000 if values else float("nan")


def attach_timing(app):
    timings = {"draw": [], "fit": [], "rows": [], "build": []}
    counts = {"draw": 0}

    original_draw = app.canvas.draw

    def timed_draw(*args, **kwargs):
        t0 = time.perf_counter()
        result = original_draw(*args, **kwargs)
        timings["draw"].append(time.perf_counter() - t0)
        counts["draw"] += 1
        return result

    app.canvas.draw = timed_draw  # type: ignore[method-assign]

    original_fit = app._fit_preview

    def timed_fit(*args, **kwargs):
        t0 = time.perf_counter()
        result = original_fit(*args, **kwargs)
        timings["fit"].append(time.perf_counter() - t0)
        return result

    app._fit_preview = timed_fit  # type: ignore[method-assign]

    original_rows = app._rebuild_category_rows

    def timed_rows(*args, **kwargs):
        t0 = time.perf_counter()
        result = original_rows(*args, **kwargs)
        timings["rows"].append(time.perf_counter() - t0)
        return result

    app._rebuild_category_rows = timed_rows  # type: ignore[method-assign]

    def restore():
        app.canvas.draw = original_draw  # type: ignore[method-assign]
        app._fit_preview = original_fit  # type: ignore[method-assign]
        app._rebuild_category_rows = original_rows  # type: ignore[method-assign]

    return timings, counts, restore


def measure_agg(app, *, remove_checker: bool = False) -> list[float]:
    from rosechart import ui_widgets as W
    from rosechart.chart import RoseChart

    spec = app._build_spec("chart1")
    values: list[float] = []
    for _ in range(6):
        figure = Figure(figsize=(12, 8), dpi=app._dpi)
        canvas = FigureCanvasAgg(figure)
        chart = RoseChart(spec, figure, preview=True, preview_bg=W.PREVIEW_BG)
        if remove_checker:
            for ax in list(figure.axes):
                if ax.get_zorder() < -50:
                    figure.delaxes(ax)
        chart.refresh_label_backplates()
        t0 = time.perf_counter()
        canvas.draw()
        values.append(time.perf_counter() - t0)
    return values


def drag_lite_variant(app, root) -> dict[str, list[float]]:
    """Measure a 'drag-time simplification' fast path in-memory."""
    from rosechart import ui_widgets as W

    chart = app.chart
    # hide checkerboard
    for ax in list(app.figure.axes):
        if ax.get_zorder() < -50:
            app.figure.delaxes(ax)
    # drop halo effects and only keep the hovered label's leader line visible
    first = True
    for handle in chart.handles.values():
        handle.text.set_path_effects([])
        if not first:
            handle.text.set_visible(False)
            handle.line.set_visible(False)
        first = False
    # lower preview dpi
    old_dpi = app.figure.get_dpi()
    app.figure.set_dpi(42)
    # simulate drag
    canvas = app.canvas
    label = next(iter(chart.handles))
    handle = chart.handles[label]
    renderer = canvas.get_renderer()
    bbox = handle.text.get_window_extent(renderer=renderer)
    app._on_canvas_press(
        SimpleNamespace(button=1, x=(bbox.x0 + bbox.x1) / 2, y=(bbox.y0 + bbox.y1) / 2, dblclick=False)
    )
    frames: list[float] = []
    draws: list[float] = []
    original_draw = canvas.draw

    def timed(*a, **k):
        t0 = time.perf_counter()
        r = original_draw(*a, **k)
        draws.append(time.perf_counter() - t0)
        return r

    canvas.draw = timed  # type: ignore[method-assign]
    try:
        for index in range(40):
            target = chart.axis.transData.transform(
                (handle.line_end_x - 0.0008 * index, handle.y + 0.04 * math.sin(index / 6))
            )
            t0 = time.perf_counter()
            app._on_canvas_motion(SimpleNamespace(button=1, x=float(target[0]), y=float(target[1])))
            root.update()
            frames.append(time.perf_counter() - t0)
        app._on_canvas_release(
            SimpleNamespace(button=1, x=float(target[0]), y=float(target[1]))
        )
    finally:
        canvas.draw = original_draw  # type: ignore[method-assign]
    return {"frames": frames, "draws": draws, "dpi": old_dpi}


def canvas_overlay_cost(root, width: int = 900, height: int = 600) -> list[float]:
    frame = tk.Frame(root)
    frame.place(x=0, y=0, width=width, height=height)
    canvas = tk.Canvas(frame, width=width, height=height, bg="#EDF2F8", highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    line = canvas.create_line(100, 100, 200, 120, 260, 120, fill="#0F766E", width=2)
    text = canvas.create_text(280, 120, text="软件开发 12", fill="#0F766E", font=("Microsoft YaHei UI", 16, "bold"), anchor="w")
    values: list[float] = []
    for index in range(80):
        y = 120 + 2 * math.sin(index / 5)
        t0 = time.perf_counter()
        canvas.coords(text, 280, y)
        canvas.coords(line, 100, 100, 200, y, 260, y)
        root.update_idletasks()
        values.append(time.perf_counter() - t0)
    frame.destroy()
    return values


def main() -> int:
    from rosechart import main_window as mw

    if PREFS.exists():
        PREFS.unlink()
    root = tk.Tk()
    app = mw.RoseChartApp(root, prefs_path=PREFS)
    pump(root, 2.5)
    lines: list[str] = []
    lines.append(f"preview dpi: {app._dpi:.1f} | figure inches: {app.figure.get_size_inches()}")

    # baseline TkAgg draw
    tk_draw = []
    for _ in range(8):
        t0 = time.perf_counter()
        app.canvas.draw()
        tk_draw.append(time.perf_counter() - t0)
    lines.append(f"TkAgg draw          : {ms(tk_draw):.1f} ms")

    agg_draw = measure_agg(app)
    agg_nocheck = measure_agg(app, remove_checker=True)
    lines.append(f"纯 Agg draw         : {ms(agg_draw):.1f} ms")
    lines.append(f"纯 Agg 无棋盘格     : {ms(agg_nocheck):.1f} ms")
    lines.append(f"棋盘格成本(Agg)     : {ms(agg_draw) - ms(agg_nocheck):.1f} ms")
    lines.append(f"Tk 图像上传/后端差  : {ms(tk_draw) - ms(agg_draw):.1f} ms")

    # slider render decomposition
    timings, counts, restore = attach_timing(app)
    t0 = time.perf_counter()
    app._render_current()
    total = time.perf_counter() - t0
    restore()
    lines.append("")
    lines.append(f"_render_current total: {total*1000:.1f} ms | draw calls: {counts['draw']} "
                 f"({ms(timings['draw']):.1f} ms total) | fit: {ms(timings['fit']):.1f} ms | "
                 f"category rows: {ms(timings['rows']):.1f} ms")

    # drag-lite fast path
    app._render_current()
    pump(root, 0.3)
    lite = drag_lite_variant(app, root)
    lines.append("")
    lines.append(f"drag-lite（低dpi42+无棋盘+无描边+仅拖拽标签）frame: {ms(lite['frames']):.1f} ms | "
                 f"draw: {ms(lite['draws']):.1f} ms")
    app._render_current()
    pump(root, 0.3)

    # Tk canvas overlay cost
    overlay = canvas_overlay_cost(root)
    lines.append(f"Tk Canvas overlay 移动标签: {ms(overlay):.2f} ms/帧")

    # PhotoImage upload cost estimate
    try:
        from PIL import Image, ImageTk

        image = Image.new("RGBA", (900, 600), (255, 255, 255, 200))
        upload: list[float] = []
        for _ in range(10):
            t0 = time.perf_counter()
            photo = ImageTk.PhotoImage(image)
            upload.append(time.perf_counter() - t0)
            del photo
        lines.append(f"PIL Image → Tk PhotoImage 上传 900x600: {ms(upload):.1f} ms")
    except Exception as exc:
        lines.append(f"PIL/Tk upload 测量失败: {exc}")

    report = "\n".join(lines)
    print(report)
    (PERF / "bench_breakdown.txt").write_text(report, encoding="utf-8")
    app._save_prefs()
    root.destroy()
    if PREFS.exists():
        PREFS.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

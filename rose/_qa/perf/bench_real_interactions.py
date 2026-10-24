"""Measure busy time triggered by real slider dragging and window resizing."""
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
PREFS = PERF / "tmp_prefs4.json"


def pump(root: tk.Tk, seconds: float) -> None:
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        root.update()
        time.sleep(0.005)


def main() -> int:
    from rosechart import main_window as mw

    if PREFS.exists():
        PREFS.unlink()
    root = tk.Tk()
    app = mw.RoseChartApp(root, prefs_path=PREFS)
    pump(root, 2.5)

    render_times: list[float] = []
    original_render = app._render_current

    def timed_render():
        t0 = time.perf_counter()
        original_render()
        render_times.append(time.perf_counter() - t0)

    app._render_current = timed_render  # type: ignore[method-assign]
    lines: list[str] = []
    # Slider drag: user moves every ~70ms, app debounces render by 40ms.
    before = len(render_times)
    wall0 = time.perf_counter()
    for index in range(20):
        app._on_style_slider("inner_radius", 0.30 + 0.004 * index)
        pump(root, 0.07)
    wall = time.perf_counter() - wall0
    renders = render_times[before:]
    lines.append(
        f"滑杆拖动 20 步 / {wall*1000:.0f}ms：触发渲染 {len(renders)} 次，"
        f"渲染平均 {statistics.mean(renders)*1000:.0f}ms，"
        f"主线程渲染占用 {sum(renders)/wall*100:.0f}%"
    )

    # window resize: 8 geometry changes at ~80ms spacing
    resize_renders: list[float] = []
    original_fit = app._fit_preview

    def timed_fit():
        t0 = time.perf_counter()
        original_fit()
        resize_renders.append(time.perf_counter() - t0)

    app._fit_preview = timed_fit  # type: ignore[method-assign]
    wall0 = time.perf_counter()
    for index in range(8):
        width = 1520 - index * 10
        height = 940 - index * 8
        root.geometry(f"{width}x{height}")
        pump(root, 0.08)
    resize_wall = time.perf_counter() - wall0
    app._fit_preview = original_fit  # type: ignore[method-assign]
    if resize_renders:
        lines.append(
            f"窗口缩放 8 步 / {resize_wall*1000:.0f}ms：fit/重绘 {len(resize_renders)} 次，"
            f"平均 {statistics.mean(resize_renders)*1000:.0f}ms，"
            f"占用 {sum(resize_renders)/resize_wall*100:.0f}%"
        )

    app._render_current = original_render  # type: ignore[method-assign]
    report = "\n".join(lines)
    print(report)
    (PERF / "bench_real_interactions.txt").write_text(report, encoding="utf-8")
    app._save_prefs()
    root.destroy()
    if PREFS.exists():
        PREFS.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

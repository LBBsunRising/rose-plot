"""Read-only performance analysis for RoseChart Studio.

The application code is NOT modified. This script instantiates the real window,
simulates drag gestures and measures where frame time goes, plus measures
candidate optimizations by monkey-patching runtime only.
"""
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
PERF.mkdir(parents=True, exist_ok=True)
PREFS = PERF / "tmp_prefs.json"


def stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)
    return {
        "n": len(values),
        "mean_ms": statistics.mean(values) * 1000,
        "p50_ms": ordered[len(ordered) // 2] * 1000,
        "p95_ms": ordered[max(0, int(len(ordered) * 0.95) - 1)] * 1000,
        "max_ms": max(values) * 1000,
    }


def fmt(label: str, values: list[float]) -> str:
    s = stats(values)
    if not s:
        return f"{label}: no data"
    return (
        f"{label}: mean {s['mean_ms']:.1f}ms | p50 {s['p50_ms']:.1f}ms | "
        f"p95 {s['p95_ms']:.1f}ms | max {s['max_ms']:.1f}ms "
        f"(~{1000 / max(1e-9, s['mean_ms']):.0f} fps if each frame)"
    )


def pump(root: tk.Tk, seconds: float) -> None:
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        root.update()
        time.sleep(0.01)


def bench_draw(canvas, n: int = 10) -> list[float]:
    values: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        canvas.draw()
        values.append(time.perf_counter() - t0)
    return values


def bench_rebuild(app, key: str, n: int = 8) -> list[float]:
    from rosechart.chart import RoseChart

    spec = app._build_spec(key)
    figure = Figure(figsize=(12, 8), dpi=100)
    FigureCanvasAgg(figure)
    values: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter()
        chart = RoseChart(spec, figure, preview=True, preview_bg="#EDF2F8")
        # emulate the panel's post-build steps
        chart.refresh_label_backplates()
        values.append(time.perf_counter() - t0)
    return values


def drag_bench(app, root: tk.Tk, *, motions: int = 70, settle: float = 0.0) -> dict[str, list[float]]:
    """Simulate a label drag; returns frame / handler / matplotlib-draw timings."""
    chart = app.chart
    canvas = app.canvas
    label = next(iter(chart.handles))
    handle = chart.handles[label]
    renderer = canvas.get_renderer()
    bbox = handle.text.get_window_extent(renderer=renderer)
    press = SimpleNamespace(
        button=1,
        x=(bbox.x0 + bbox.x1) / 2,
        y=(bbox.y0 + bbox.y1) / 2,
        dblclick=False,
    )
    app._on_canvas_press(press)

    frames: list[float] = []
    handlers: list[float] = []
    draws: list[float] = []
    original_draw = canvas.draw

    def timed_draw(*args, **kwargs):
        t0 = time.perf_counter()
        result = original_draw(*args, **kwargs)
        draws.append(time.perf_counter() - t0)
        return result

    canvas.draw = timed_draw  # type: ignore[method-assign]
    try:
        for index in range(motions):
            data_x = handle.line_end_x - 0.0006 * index
            data_y = handle.y + 0.05 * math.sin(index / 7.0)
            target = chart.axis.transData.transform((data_x, data_y))
            motion = SimpleNamespace(button=1, x=float(target[0]), y=float(target[1]))
            t0 = time.perf_counter()
            app._on_canvas_motion(motion)
            t1 = time.perf_counter()
            root.update()
            t2 = time.perf_counter()
            handlers.append(t1 - t0)
            frames.append(t2 - t0)
            if settle:
                time.sleep(settle)
        release = SimpleNamespace(button=1, x=float(target[0]), y=float(target[1]))
        app._on_canvas_release(release)
        root.update()
    finally:
        canvas.draw = original_draw  # type: ignore[method-assign]
    return {"frames": frames, "handlers": handlers, "draws": draws}


def drag_variant(app, root: tk.Tk) -> dict[str, list[float]]:
    """Re-run a drag after mutating runtime artist state (no source changes)."""
    return drag_bench(app, root, motions=40)


def main() -> int:
    from rosechart import main_window as mw

    if PREFS.exists():
        PREFS.unlink()
    root = tk.Tk()
    app = mw.RoseChartApp(root, prefs_path=PREFS)
    pump(root, 2.5)
    print("app ready; labels:", len(app.chart.handles), "| preview dpi:", round(app._dpi, 1))

    lines: list[str] = []
    lines.append("=" * 78)
    lines.append("A. 基线：静态帧成本")
    lines.append(fmt("  canvas.draw()（整幅重绘）", bench_draw(app.canvas)))
    lines.append(fmt("  RoseChart 重建 + 后置处理", bench_rebuild(app, "chart1")))
    lines.append(fmt("  _render_current()（重建+布局+绘制）", [0.0]))

    # slider drag: rebuild + full draw per step (the app debounces 40ms)
    render_times: list[float] = []
    for _ in range(8):
        t0 = time.perf_counter()
        app._render_current()
        root.update()
        render_times.append(time.perf_counter() - t0)
    lines.append(fmt("  滑杆一步 = 重建+绘制", render_times))

    # label drag
    base = drag_bench(app, root)
    lines.append("")
    lines.append("B. 拖动标签：真实事件循环下每步成本")
    lines.append(fmt("  从鼠标事件到画面更新（含 Tk）", base["frames"]))
    lines.append(fmt("  仅 app._on_canvas_motion 处理", base["handlers"]))
    lines.append(fmt("  其中 matplotlib canvas.draw()", base["draws"]))
    if base["frames"]:
        mean = statistics.mean(base["frames"])
        lines.append(f"  估算：仅处理+重绘约 {1/mean:.0f} 次/秒；鼠标通常 100–125 次/秒")

    # micro: backplate + text extents
    chart = app.chart
    plate_times: list[float] = []
    for _ in range(40):
        t0 = time.perf_counter()
        chart.refresh_label_backplates()
        plate_times.append(time.perf_counter() - t0)
    lines.append(fmt("  refresh_label_backplates()", plate_times))

    # variant 1: no path effects (halo)
    for handle in chart.handles.values():
        handle.text.set_path_effects([])
    no_effects = drag_variant(app, root)
    lines.append("")
    lines.append("C. 候选优化的实测收益（运行时临时关闭，不改源码）")
    lines.append(fmt("  C1 去掉标签白描边：frame", no_effects["frames"]))
    lines.append(fmt("  C1 去掉标签白描边：draw ", no_effects["draws"]))

    # restore a clean chart before next variant
    app._render_current()
    pump(root, 0.3)

    # variant 2: remove checkerboard axes (figure-level imshow)
    chart = app.chart
    removed = 0
    for ax in list(app.figure.axes):
        if ax.get_zorder() < -50:
            app.figure.delaxes(ax)
            removed += 1
    no_checker = drag_variant(app, root)
    lines.append(fmt(f"C2 去掉棋盘格（{removed} 个背景轴）：frame", no_checker["frames"]))
    lines.append(fmt("C2 去掉棋盘格：draw ", no_checker["draws"]))

    app._render_current()
    pump(root, 0.3)

    # variant 3: no backplates
    chart = app.chart
    original_plate = chart.refresh_label_backplates
    chart.refresh_label_backplates = lambda: None  # type: ignore[method-assign]
    no_plate = drag_variant(app, root)
    chart.refresh_label_backplates = original_plate  # type: ignore[method-assign]
    lines.append(fmt("C3 关闭标签底板检测：frame", no_plate["frames"]))
    lines.append(fmt("C3 关闭标签底板检测：draw ", no_plate["draws"]))

    app._render_current()
    pump(root, 0.3)

    # variant 4: lower preview dpi
    chart = app.chart
    old_dpi = app.figure.get_dpi()
    app.figure.set_dpi(max(28.0, old_dpi * 0.55))
    low_dpi = drag_variant(app, root)
    lines.append(fmt(f"C4 预览 dpi {old_dpi:.0f}→{app.figure.get_dpi():.0f}：frame", low_dpi["frames"]))
    lines.append(fmt("C4 低 dpi：draw ", low_dpi["draws"]))
    app.figure.set_dpi(old_dpi)
    app._render_current()
    pump(root, 0.3)

    # blit feasibility
    canvas = app.canvas
    lines.append("")
    lines.append("D. matplotlib 脏矩形/位图 blit 可行性")
    lines.append(f"  has canvas.copy_from_bbox: {hasattr(canvas, 'copy_from_bbox')}")
    lines.append(f"  has canvas.blit: {hasattr(canvas, 'blit')}")
    try:
        canvas.draw()
        bg = canvas.copy_from_bbox(app.figure.bbox)
        chart = app.chart
        handle = next(iter(chart.handles.values()))
        t0 = time.perf_counter()
        for _ in range(30):
            handle.text.set_position((handle.text_x, handle.y + 0.001))
            canvas.restore_region(bg)
            chart.axis.draw_artist(handle.text)
            chart.axis.draw_artist(handle.line)
            canvas.blit(app.figure.bbox)
        blit_time = (time.perf_counter() - t0) / 30
        lines.append(f"  尝试 blit 30 帧：平均 {blit_time*1000:.1f}ms/帧")
        try:
            from PIL import ImageGrab

            root.attributes("-topmost", True)
            root.update()
            time.sleep(0.4)
            x, y = root.winfo_rootx(), root.winfo_rooty()
            ImageGrab.grab(bbox=(x, y, x + root.winfo_width(), y + root.winfo_height())).save(
                PERF / "blit_screen.png"
            )
            lines.append("  已保存 blit 后的窗口截图 blit_screen.png 供核对")
        except Exception as exc:
            lines.append(f"  截图失败：{exc}")
        try:
            from matplotlib.backends.backend_agg import FigureCanvasAgg

            lines.append(
                "  FigureCanvasTkAgg 继承链："
                + " -> ".join(cls.__name__ for cls in type(canvas).__mro__[:4])
            )
        except Exception:
            pass
    except Exception as exc:
        lines.append(f"  blit 尝试失败：{type(exc).__name__}: {exc}")

    # E. 12-label case
    app._render_current()
    pump(root, 0.2)
    many = ROOT / "_qa" / "edge" / "many_categories.xlsx"
    if many.is_file():
        app.load_file(str(many), silent=True)
        pump(root, 1.2)
        lines.append("")
        lines.append(f"E. 12 个类别的场景（labels={len(app.chart.handles) if app.chart else 0}）")
        base12 = drag_bench(app, root, motions=40)
        lines.append(fmt("  拖动 frame", base12["frames"]))
        lines.append(fmt("  拖动 draw", base12["draws"]))
        lines.append(fmt("  静态 draw", bench_draw(app.canvas, 8)))

    # F. window resize cost
    lines.append("")
    lines.append("F. 窗口缩放（拖动窗口边缘）")
    sizes = [(1520, 940), (1500, 930), (1480, 910), (1460, 900), (1440, 870)]
    resize_times: list[float] = []
    for width, height in sizes:
        t0 = time.perf_counter()
        root.geometry(f"{mw.W.px(width)}x{mw.W.px(height)}")
        for _ in range(4):
            root.update()
            time.sleep(0.02)
        resize_times.append(time.perf_counter() - t0)
    lines.append(fmt("  每次窗口尺寸变更到重绘完成（含 90ms 防抖）", resize_times))

    report = "\n".join(lines)
    print(report)
    (PERF / "bench_report.txt").write_text(report, encoding="utf-8")

    app._save_prefs()
    root.destroy()
    if PREFS.exists():
        PREFS.unlink()
    print("\nreport saved to", PERF / "bench_report.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

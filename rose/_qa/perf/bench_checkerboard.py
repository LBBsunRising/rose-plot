"""Read-only comparison of checkerboard rendering techniques (Agg + TkAgg alpha)."""
from __future__ import annotations

import ctypes
import statistics
import sys
import time
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

import numpy as np
import tkinter as tk
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import ListedColormap
from matplotlib.figure import Figure

PERF = Path(__file__).resolve().parent


def timeit(fn, n=8):
    values = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        values.append(time.perf_counter() - t0)
    return statistics.mean(values) * 1000


def checker_data(columns=32, rows=22):
    return (np.indices((rows, columns)).sum(axis=0) % 2).astype(float)


def build_preview():
    from rosechart import ui_widgets as W
    from rosechart.chart import RoseChart, StyleConfig, build_spec
    from rosechart.palettes import assign_colors, label_color

    labels = ["软件开发", "MES改造", "视觉改造"]
    values = [12, 7, 5]
    palette = None
    from rosechart.palettes import palette_by_id

    palette = palette_by_id("legacy_project")
    fills = assign_colors(palette, labels)
    label_colors = {l: label_color(fills[l], "auto") for l in labels}
    spec = build_spec(labels, values, StyleConfig(title="SW项目统计"), fill_colors=fills, label_colors=label_colors)
    return spec


def main() -> int:
    lines: list[str] = []
    dpi = 75.0
    figsize = (12, 8)
    pixels = (int(figsize[0] * dpi), int(figsize[1] * dpi))

    # 1) current: axes.imshow of a 32x22 checkerboard, resampled each draw
    from rosechart import ui_widgets as W
    from rosechart.chart import RoseChart

    spec = build_preview()

    def make_imshow():
        fig = Figure(figsize=figsize, dpi=dpi)
        FigureCanvasAgg(fig)
        RoseChart(spec, fig, preview=True, preview_bg=W.PREVIEW_BG)
        return fig

    fig = make_imshow()
    lines.append(f"1) 当前 imshow 32x22：{timeit(fig.canvas.draw):.1f} ms / 帧")

    # 2) full-resolution precomputed RGBA image via figimage
    pattern = checker_data()
    image = np.kron(pattern, np.ones((pixels[1] // 22 + 1, pixels[0] // 32 + 1)))
    image = image[: pixels[1], : pixels[0]]
    rgb = np.empty((image.shape[0], image.shape[1], 3), dtype=float)
    rgb[image == 0] = 1.0
    rgb[image == 1] = [0.968, 0.976, 0.988]

    def make_figimage():
        fig = Figure(figsize=figsize, dpi=dpi)
        FigureCanvasAgg(fig)
        RoseChart(spec, fig, preview=False)
        fig.figimage(rgb, xo=0, yo=0, origin="lower", zorder=-100)
        return fig

    fig2 = make_figimage()
    lines.append(f"2) figimage 全分辨率预生成：{timeit(fig2.canvas.draw):.1f} ms / 帧")

    # 3) imshow with resample=False
    def make_imshow_noresample():
        fig = Figure(figsize=figsize, dpi=dpi)
        FigureCanvasAgg(fig)
        RoseChart(spec, fig, preview=False)
        ax = fig.add_axes([0, 0, 1, 1], zorder=-100)
        ax.imshow(checker_data(), extent=(0, 1, 0, 1), cmap=ListedColormap(["#FFFFFF", "#F7F9FC"]),
                  interpolation="nearest", resample=False, aspect="auto")
        ax.set_axis_off()
        return fig

    fig3 = make_imshow_noresample()
    lines.append(f"3) imshow resample=False：{timeit(fig3.canvas.draw):.1f} ms / 帧")

    # 4) vector rectangles
    def make_rects():
        fig = Figure(figsize=figsize, dpi=dpi)
        FigureCanvasAgg(fig)
        RoseChart(spec, fig, preview=False)
        from matplotlib.patches import Rectangle

        ax = fig.add_axes([0, 0, 1, 1], zorder=-100)
        ax.set_axis_off()
        columns, rows = 24, 16
        for row in range(rows):
            for column in range(columns):
                if (row + column) % 2:
                    ax.add_patch(
                        Rectangle(
                            (column / columns, row / rows),
                            1 / columns,
                            1 / rows,
                            facecolor="#F7F9FC",
                            edgecolor="none",
                        )
                    )
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        return fig

    fig4 = make_rects()
    lines.append(f"4) 向量矩形 24x16：{timeit(fig4.canvas.draw):.1f} ms / 帧")

    # 5) TkAgg alpha / transparent background feasibility
    root = tk.Tk()
    root.geometry("500x400+1800+800")
    base = tk.Canvas(root, width=420, height=300, bg="#FF0000", highlightthickness=0)
    base.pack()
    for y in range(0, 300, 30):
        for x in range(0, 420, 30):
            if (x // 30 + y // 30) % 2 == 0:
                base.create_rectangle(x, y, x + 30, y + 30, fill="#00FF00", outline="")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

    fig5 = Figure(figsize=(4.2, 3.0), dpi=100)
    fig5.patch.set_alpha(0.0)
    ax5 = fig5.add_subplot(111)
    ax5.set_facecolor("none")
    ax5.set_axis_off()
    ax5.add_patch(__import__("matplotlib.patches", fromlist=["Circle"]).Circle((0.5, 0.5), 0.2, color="#0F766E"))
    canvas5 = FigureCanvasTkAgg(fig5, master=base)
    canvas5.get_tk_widget().place(x=0, y=0, width=420, height=300)
    canvas5.draw()
    root.update()
    time.sleep(0.4)
    try:
        from PIL import ImageGrab

        x0, y0 = root.winfo_rootx(), root.winfo_rooty()
        ImageGrab.grab(bbox=(x0, y0, x0 + 420, y0 + 300)).save(PERF / "tkagg_alpha_test.png")
        lines.append("5) TkAgg 透明背景测试截图：tkagg_alpha_test.png（看红色/绿色是否透出）")
    except Exception as exc:
        lines.append(f"5) 截图失败：{exc}")
    root.destroy()

    report = "\n".join(lines)
    print(report)
    (PERF / "bench_checkerboard.txt").write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

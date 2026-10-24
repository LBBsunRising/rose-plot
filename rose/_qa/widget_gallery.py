"""Visual smoke test for the widget kit (not part of the app)."""
from __future__ import annotations

import ctypes
import sys
import time
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

from rosechart import ui_widgets as W


def main() -> None:
    root = tk.Tk()
    root.title("widget gallery")
    W.setup_fonts(root)
    W.init_styles(root)
    W.install_wheel_router(root)
    root.configure(bg=W.BG)
    root.geometry(f"{W.px(1180)}x{W.px(780)}+{W.px(60)}+{W.px(40)}")

    header = tk.Frame(root, bg=W.PANEL)
    header.pack(fill="x")
    W.BrandMark(header, size=34).pack(side="left", padx=W.px(14), pady=W.px(10))
    tk.Label(header, text="玫瑰图工坊", bg=W.PANEL, fg=W.TEXT, font=W.font(14, "bold")).pack(side="left")
    tk.Label(header, text="RoseChart Studio", bg=W.PANEL, fg=W.TEXT_FAINT, font=W.font(9)).pack(
        side="left", padx=(W.px(8), 0), pady=(W.px(4), 0)
    )
    W.FlatButton(header, "打开 Excel", kind="secondary").pack(side="right", padx=(W.px(8), W.px(14)), pady=W.px(10))
    W.FlatButton(header, "导出 PNG", kind="primary").pack(side="right", pady=W.px(10))

    body = tk.Frame(root, bg=W.BG)
    body.pack(fill="both", expand=True, padx=W.px(16), pady=W.px(14))

    left = W.Card(body, "数据源", "Workbook")
    left.pack(side="left", fill="y", padx=(0, W.px(12)))
    left.configure(width=W.px(300))
    left.pack_propagate(False)
    tk.Label(left.body, text="Excel 文件", bg=W.PANEL, fg=W.TEXT_MUTED, font=W.font(9.5)).pack(anchor="w")
    row = tk.Frame(left.body, bg=W.PANEL)
    row.pack(fill="x", pady=(W.px(4), W.px(10)))
    ttk_entry = tk.Entry(row)
    from tkinter import ttk

    var = tk.StringVar(value="project_test_data.xlsx")
    ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
    W.FlatButton(row, "浏览…", kind="secondary", padx_=8, pady_=5).pack(side="left", padx=(W.px(6), 0))
    W.Field(left.body, "工作表").pack(fill="x")
    combo = ttk.Combobox(left.body, values=["项目数据", "统计检查"], state="readonly")
    combo.current(0)
    combo.pack(fill="x", pady=(0, W.px(10)))
    W.CheckRow(left.body, "包含空值行", tk.BooleanVar(value=False)).pack(anchor="w")
    W.CheckRow(left.body, "显示百分比", tk.BooleanVar(value=True)).pack(anchor="w", pady=(W.px(2), W.px(10)))

    tk.Label(left.body, text="类别分布", bg=W.PANEL, fg=W.TEXT, font=W.font(10, "bold")).pack(anchor="w")
    table = W.DataTable(left.body, height=5)
    table.pack(fill="x", pady=(W.px(4), 0))
    table.set_rows([("软件开发", 12, 50.0), ("MES改造", 7, 29.17), ("视觉改造", 5, 20.83)])

    middle = tk.Frame(body, bg=W.BG)
    middle.pack(side="left", fill="both", expand=True)
    seg = W.SegmentedControl(
        middle,
        [("chart1", "SW项目统计"), ("chart2", "SW项目状态统计")],
        initial="chart1",
    )
    seg.pack(anchor="w")
    preview = tk.Frame(middle, bg=W.PREVIEW_BG, highlightthickness=1, highlightbackground=W.BORDER)
    preview.pack(fill="both", expand=True, pady=(W.px(10), 0))
    tk.Label(preview, text="预览区域", bg=W.PREVIEW_BG, fg=W.TEXT_FAINT, font=W.font(11)).place(
        relx=0.5, rely=0.5, anchor="center"
    )

    right = W.ScrollFrame(body, bg=W.BG, width=W.px(330))
    right.pack(side="right", fill="y", padx=(W.px(12), 0))
    palette_card = W.Card(right.inner, "配色方案", "12 套")
    palette_card.pack(fill="x", pady=(0, W.px(12)))
    gallery = tk.Frame(palette_card.body, bg=W.PANEL)
    gallery.pack(fill="x")
    sample = [
        ("原版·霓虹青", ["#6AFFFF", "#E0A6E5", "#EBE082", "#CCCCCC"], "原版", "推荐"),
        ("商务·石板蓝", ["#1D4ED8", "#3B82F6", "#93C5FD", "#DBEAFE"], "商务", ""),
        ("莫兰迪·暮色", ["#8A9A8B", "#B7A99A", "#C9ADA7", "#9B8EA9"], "莫兰迪", ""),
        ("马卡龙·甜点", ["#F9A8D4", "#A7F3D0", "#FDE68A", "#BFDBFE"], "马卡龙", "推荐"),
    ]
    for index, (name, colors, group, tag) in enumerate(sample):
        card = W.PaletteCard(
            gallery, name, colors, group=group, tag=tag, selected=index == 0
        )
        card.pack(side="left", padx=W.px(4), pady=W.px(4))

    style_card = W.Card(right.inner, "样式调节")
    style_card.pack(fill="x", pady=(0, W.px(12)))
    dpi_var = tk.DoubleVar(value=3.2)
    W.SliderRow(style_card.body, "边框宽度", dpi_var, 0, 8, formatter=lambda v: f"{v:.1f}").pack(
        fill="x", pady=(0, W.px(8))
    )
    radius_var = tk.DoubleVar(value=0.3)
    W.SliderRow(style_card.body, "内半径", radius_var, 0.05, 0.6, formatter=lambda v: f"{v:.2f}").pack(
        fill="x", pady=(0, W.px(8))
    )
    color_row = tk.Frame(style_card.body, bg=W.PANEL)
    color_row.pack(fill="x")
    tk.Label(color_row, text="标签颜色", bg=W.PANEL, fg=W.TEXT_MUTED, font=W.font(9.5)).pack(side="left")
    W.ColorButton(color_row, "#0F766E").pack(side="right")

    footer = W.StatusBar(root)
    footer.pack(fill="x", side="bottom")
    footer.set_message("已加载 project_test_data.xlsx · 项目数据（24 行）")
    footer.set_stats("3 个类别 · 4 种状态")

    root.attributes("-topmost", True)
    root.lift()
    root.update()
    time.sleep(0.8)
    root.update()

    from PIL import ImageGrab

    x, y = root.winfo_rootx(), root.winfo_rooty()
    w, h = root.winfo_width(), root.winfo_height()
    out = Path(__file__).with_name("widget_gallery.png")
    ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(out)
    print("saved", out, (w, h))
    root.destroy()


if __name__ == "__main__":
    main()

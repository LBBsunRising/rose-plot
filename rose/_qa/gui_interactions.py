"""Second round of GUI interaction tests (titles, colors, files, resize, export)."""
from __future__ import annotations

import ctypes
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

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
EDGE_DIR = Path(__file__).resolve().parent / "edge"


def pump(root, seconds: float = 0.5) -> None:
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.02)


def shot(root, name: str) -> Path:
    from PIL import ImageGrab

    root.attributes("-topmost", True)
    root.lift()
    root.focus_force()
    root.update()
    time.sleep(0.55)
    root.update()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    w, h = root.winfo_width(), root.winfo_height()
    target = QA_DIR / name
    ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(target)
    root.attributes("-topmost", False)
    print("screenshot:", target.name, (w, h))
    return target


def main() -> int:
    import tkinter as tk

    import matplotlib

    matplotlib.use("TkAgg", force=True)
    from rosechart import main_window as mw

    failures: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        print(f"[{'PASS' if condition else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
        if not condition:
            failures.append(name)

    root = tk.Tk()
    tmp_prefs = QA_DIR / 'tmp_prefs.json'
    if tmp_prefs.exists():
        tmp_prefs.unlink()
    app = mw.RoseChartApp(root, prefs_path=tmp_prefs)
    pump(root, 2.2)

    # ---- title / subtitle editing through the real entry vars ----
    app.title_var.set("项目统计 · 2026 Q4")
    app.subtitle_var.set("数据来源：项目管理台账")
    pump(root, 0.9)
    check(
        "标题写入当前图",
        app.chart_states["chart1"].get("title") == "项目统计 · 2026 Q4"
        and app.chart_states["chart1"].get("subtitle") == "数据来源：项目管理台账",
        str(app.chart_states["chart1"].get("title")),
    )
    shot(root, "11_title_subtitle.png")
    app.title_var.set("SW项目统计")
    app.subtitle_var.set("")
    pump(root, 0.6)

    # ---- category color override ----
    original_ask = mw.colorchooser.askcolor
    mw.colorchooser.askcolor = lambda **kwargs: ((239, 68, 68), "#EF4444")
    try:
        target_label = app.counts["chart1"][0][0]
        app._pick_category_color(target_label)
        pump(root, 0.7)
        overrides = app.chart_states["chart1"].get("overrides") or {}
        check("类别颜色覆盖生效", overrides.get(target_label) == "#EF4444", str(overrides))
        app._reset_category_color(target_label)
        pump(root, 0.6)
        check(
            "类别颜色覆盖可重置",
            target_label not in (app.chart_states["chart1"].get("overrides") or {}),
        )
        # ---- custom background ----
        mw.colorchooser.askcolor = lambda **kwargs: ((248, 250, 252), "#F8FAFC")
        app._pick_background_color()
        pump(root, 0.7)
        check("自定义背景生效", app.style.background in ("#F8FAFC", "#F8FAFC"), app.style.background)
        shot(root, "12_custom_background.png")
        app.background_control.set_value("transparent", notify=False)
        app.style.background = "transparent"
        app._render_current()
        pump(root, 0.4)
    finally:
        mw.colorchooser.askcolor = original_ask

    # ---- left-side label drag ----
    chart = app.chart
    left_labels = [h for h in chart.handles.values() if h.side < 0]
    check("存在左侧标签", bool(left_labels))
    if left_labels:
        handle = left_labels[0]
        renderer = app.canvas.get_renderer()
        bbox = handle.text.get_window_extent(renderer=renderer)
        press = SimpleNamespace(
            button=1,
            x=(bbox.x0 + bbox.x1) / 2,
            y=(bbox.y0 + bbox.y1) / 2,
            dblclick=False,
        )
        app._on_canvas_press(press)
        target = chart.axis.transData.transform((handle.line_end_x + 0.2, handle.y - 0.15))
        app._on_canvas_motion(SimpleNamespace(button=1, x=float(target[0]), y=float(target[1])))
        app._on_canvas_release(SimpleNamespace(button=1, x=float(target[0]), y=float(target[1])))
        pump(root, 0.5)
        check("左侧标签可拖动", bool(app.chart_states["chart1"].get("layout")))
        shot(root, "13_left_label_drag.png")
        app._clear_layout()
        pump(root, 0.4)

    # ---- font / display toggles ----
    fonts = list(app.font_combo["values"])
    if len(fonts) > 1:
        app.font_var.set(fonts[1])
        app._on_font_changed()
        pump(root, 0.7)
        check("字体切换生效", app.style.font_family == fonts[1], app.style.font_family)
    app.show_name_var.set(False)
    app._on_check("show_name", app.show_name_var)
    pump(root, 0.6)
    check("隐藏类别名称生效", app.style.show_name is False)
    app.show_name_var.set(True)
    app._on_check("show_name", app.show_name_var)
    pump(root, 0.5)

    # ---- load edge-case Excel through the GUI ----
    for filename, expect_chart in (
        ("many_categories.xlsx", True),
        ("other_columns.xlsx", True),
        ("single_category.xlsx", True),
    ):
        path = EDGE_DIR / filename
        ok = app.load_file(str(path), silent=True)
        pump(root, 1.0)
        check(f"加载 {filename}", ok and app.chart is not None)
        check(f"识别 {filename} 列", bool(app.column_a), f"a={app.column_a!r} b={app.column_b!r}")
        shot(root, f"14_load_{filename.replace('.xlsx', '')}.png")

    # ---- sheet switching on the original workbook ----
    example = ROOT / "examples" / "project_test_data.xlsx"
    app.load_file(str(example))
    pump(root, 0.8)
    first_counts = list(app.counts["chart1"])
    app.sheet_combo.configure(values=app.sheet_data.sheets)
    app.sheet_var.set("统计检查")
    app._on_sheet_changed()
    pump(root, 1.0)
    check("切换工作表生效", app.sheet_name == "统计检查" and app.counts["chart1"] != first_counts,
          f"sheet={app.sheet_name} counts={app.counts['chart1']}")
    app.sheet_var.set("项目数据")
    app._on_sheet_changed()
    pump(root, 0.8)

    # ---- column switch to unused -> placeholder ----
    app.col_b_var.set(mw.NO_COLUMN)
    app._on_columns_changed()
    pump(root, 0.8)
    check("状态列可关闭", not app.counts["chart2"] and app.column_b == "")
    app._on_chart_tab("chart2")
    pump(root, 0.6)
    check("无数据图表显示占位", app.chart is None)
    shot(root, "15_empty_second_chart.png")
    app._on_chart_tab("chart1")
    app.col_b_var.set("状态")
    app._on_columns_changed()
    pump(root, 0.8)
    check("状态列可恢复", bool(app.counts["chart2"]))

    # ---- window resize fits preview ----
    old_dpi = app._dpi
    root.geometry(f"{mw.W.px(1180)}x{mw.W.px(760)}")
    pump(root, 1.2)
    check("窗口缩放后重新适配", app._dpi != old_dpi, f"{old_dpi} -> {app._dpi}")
    shot(root, "16_small_window.png")
    root.geometry(f"{mw.W.px(1600)}x{mw.W.px(980)}")
    pump(root, 1.2)
    shot(root, "17_large_window.png")

    # ---- GUI export to SVG ----
    original_info = mw.messagebox.showinfo
    original_error = mw.messagebox.showerror
    mw.messagebox.showinfo = lambda *a, **k: None  # type: ignore[assignment]
    mw.messagebox.showerror = lambda *a, **k: None  # type: ignore[assignment]
    try:
        export_dir = QA_DIR / "export_svg"
        if export_dir.exists():
            for stale in export_dir.glob("*"):
                if stale.is_file():
                    stale.unlink()
        app.output_dir_var.set(str(export_dir))
        app.filename_var.set("vector_{title}")
        app.format_control.set_value("svg")
        app._on_format_changed("svg")
        app._on_export_option_changed()
        app._export(all_charts=False)
        pump(root, 1.0)
        svg_files = sorted(export_dir.glob("*.svg"))
        check("GUI 导出 SVG", len(svg_files) == 1 and svg_files[0].stat().st_size > 2000,
              f"{len(svg_files)} file(s)")
        # restore png for the next tests
        app.format_control.set_value("png")
        app._on_format_changed("png")
    finally:
        mw.messagebox.showinfo = original_info  # type: ignore[assignment]
        mw.messagebox.showerror = original_error  # type: ignore[assignment]

    app._save_prefs()
    root.destroy()
    print("\nRESULT:", "ALL PASS" if not failures else f"FAILURES: {failures}")
    return 0 if not failures else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)

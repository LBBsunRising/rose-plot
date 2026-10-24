"""End-to-end GUI smoke test with real window screenshots and simulated drags."""
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


def screenshot(root, name: str) -> Path:
    from PIL import ImageGrab

    root.attributes("-topmost", True)
    root.lift()
    root.focus_force()
    root.update()
    time.sleep(0.6)
    root.update()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    w, h = root.winfo_width(), root.winfo_height()
    target = QA_DIR / name
    ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(target)
    root.attributes("-topmost", False)
    print(f"screenshot: {target} ({w}x{h})")
    return target


def pump(root, seconds: float = 0.6) -> None:
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.02)


def wait_for(root, predicate, timeout: float = 2.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return True
        pump(root, 0.1)
    return predicate()


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
    pump(root, 2.2)

    failures: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        status = "PASS" if condition else "FAIL"
        print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
        if not condition:
            failures.append(name)

    check("示例数据已自动加载", app.chart is not None and bool(app.counts["chart1"]))
    check("两张图都有统计", bool(app.counts["chart1"]) and bool(app.counts["chart2"]))
    print("chart1 counts:", app.counts["chart1"])
    print("chart2 counts:", app.counts["chart2"])
    print("active title:", app.chart_states["chart1"].get("title"), "| palette:", app.chart_states["chart1"].get("palette_id"))
    screenshot(root, "01_startup.png")

    # ---- palette recommendation UI ----
    rec_cards = app.rec_grid.winfo_children()
    gallery_cards = app.gallery_frame.winfo_children()
    check("推荐配色卡片 >= 4", len(rec_cards) >= 4, f"{len(rec_cards)} 张")
    check("全部配色卡片 >= 10", len(gallery_cards) >= 10, f"{len(gallery_cards)} 张")

    app._apply_palette("business_steel")
    pump(root, 0.8)
    check(
        "切换配色生效",
        app.chart_states["chart1"].get("palette_id") == "business_steel",
        str(app.chart_states["chart1"].get("palette_id")),
    )
    screenshot(root, "02_palette_business.png")

    # ---- drag a label with simulated mouse events ----
    chart = app.chart
    assert chart is not None
    label = next(iter(chart.handles))
    handle = chart.handles[label]
    renderer = app.canvas.get_renderer()
    bbox = handle.text.get_window_extent(renderer=renderer)
    start_x = (bbox.x0 + bbox.x1) / 2
    start_y = (bbox.y0 + bbox.y1) / 2
    press = SimpleNamespace(button=1, x=start_x, y=start_y, xdata=handle.y, ydata=handle.y, dblclick=False)
    app._on_canvas_press(press)
    before = (handle.y, handle.line_end_x)
    target_data_x = handle.line_end_x - 0.12
    target_data_y = handle.y + 0.14
    target_px = chart.axis.transData.transform((target_data_x, target_data_y))
    motion = SimpleNamespace(button=1, x=float(target_px[0]), y=float(target_px[1]))
    app._on_canvas_motion(motion)
    release = SimpleNamespace(button=1, x=float(target_px[0]), y=float(target_px[1]))
    app._on_canvas_release(release)
    pump(root, 0.6)
    after = (handle.y, handle.line_end_x)
    check("拖拽标签改变了位置", abs(after[0] - before[0]) > 0.05, f"{before} -> {after}")
    check("布局已记录", bool(app.chart_states["chart1"].get("layout")), str(app.chart_states["chart1"].get("layout")))
    screenshot(root, "03_drag_label.png")

    # ---- undo / redo ----
    app._undo_layout()
    check(
        "撤销后布局恢复",
        wait_for(root, lambda: not app.chart_states["chart1"].get("layout")),
        str(app.chart_states["chart1"].get("layout")),
    )
    app._redo_layout()
    check(
        "重做后布局回填",
        wait_for(root, lambda: bool(app.chart_states["chart1"].get("layout"))),
    )

    # ---- double click reset ----
    app._clear_layout()
    check(
        "清除自定义布局",
        wait_for(root, lambda: not app.chart_states["chart1"].get("layout")),
        str(app.chart_states["chart1"].get("layout")),
    )

    # ---- style changes ----
    app._on_style_slider("inner_radius", 0.40)
    app._on_style_slider("label_font_size", 24)
    app._on_style_slider("start_angle", 110)
    pump(root, 0.8)
    check("样式参数生效", abs(app.style.inner_radius - 0.40) < 1e-6)
    screenshot(root, "04_style_tuned.png")

    # ---- switch to second chart ----
    app._on_chart_tab("chart2")
    pump(root, 0.9)
    check("切换到状态图", app.active_chart == "chart2" and app.chart is not None)
    print("chart2 title:", app.chart_states["chart2"].get("title"), "| palette:", app.chart_states["chart2"].get("palette_id"))
    app._apply_palette("tech_neon")
    pump(root, 0.8)
    screenshot(root, "05_chart2_neon.png")

    # ---- export (suppress modal dialogs) ----
    original_info = mw.messagebox.showinfo
    original_error = mw.messagebox.showerror
    mw.messagebox.showinfo = lambda *a, **k: None  # type: ignore[assignment]
    mw.messagebox.showerror = lambda *a, **k: None  # type: ignore[assignment]
    try:
        app.output_dir_var.set(str(QA_DIR / "export"))
        app.width_var.set("1200")
        app.height_var.set("800")
        app.dpi_var.set(100)
        app.transparent_var.set(True)
        app.filename_var.set("qa_{title}")
        app._on_export_option_changed()
        app._export(all_charts=True)
        pump(root, 1.0)
        exported = sorted((QA_DIR / "export").glob("qa_*"))
        check("导出两张 PNG", len(exported) == 2, ", ".join(path.name for path in exported))
        from PIL import Image

        for path in exported:
            with Image.open(path) as image:
                check(
                    f"{path.name} 尺寸/透明",
                    image.size == (1200, 800) and image.mode in ("RGBA", "LA"),
                    f"{image.size} {image.mode}",
                )

        # ---- clipboard copy ----
        app._copy_current_image()
        pump(root, 0.6)
        import ctypes

        check("复制图片到剪贴板", bool(ctypes.windll.user32.IsClipboardFormatAvailable(8)))
        screenshot(root, "06b_clipboard_ready.png")

        # ---- project save / load ----
        project_path = QA_DIR / "qa_project.roseproj"
        from rosechart import prefs as prefs_mod

        prefs_mod.save_project(project_path, app._project_snapshot())
        state = prefs_mod.load_project(project_path)
        check("项目文件可读", bool(state and state.get("charts")))
    finally:
        mw.messagebox.showinfo = original_info  # type: ignore[assignment]
        mw.messagebox.showerror = original_error  # type: ignore[assignment]

    app._on_chart_tab("chart1")
    app._apply_palette("legacy_project")
    pump(root, 0.8)
    screenshot(root, "06_final.png")

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

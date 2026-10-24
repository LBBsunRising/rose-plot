"""RoseChart Studio - desktop entry point.

The portable runtime lives in ``.venv`` next to this file; double click
``RoseChart.exe`` (or ``start.bat``) to open the app. This module only handles
process level concerns (DPI awareness, crash logging, CLI flags) and delegates
the UI to :mod:`rosechart.main_window`.
"""
from __future__ import annotations

import argparse
import ctypes
import sys
import traceback
from datetime import datetime
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

LOG_PATH = APP_DIR / "rosechart_error.log"


def set_dpi_awareness() -> None:
    """Make the Tk UI crisp on high-DPI Windows screens."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def set_app_user_model_id() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("RoseChart.Studio.2")
    except Exception:
        pass


def write_crash_log(exc: BaseException) -> None:
    try:
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} =====\n")
            handle.write("".join(traceback.format_exception(exc)))
    except OSError:
        pass


def show_fatal_error(message: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("RoseChart Studio 启动失败", message)
        root.destroy()
    except Exception:
        pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RoseChart Studio 玫瑰图工坊")
    parser.add_argument("--file", help="启动后自动打开的 Excel 文件")
    parser.add_argument(
        "--smoke",
        type=float,
        default=0.0,
        help="冒烟测试：显示界面 N 秒后自动退出（供打包验证使用）",
    )
    parser.add_argument("--debug", action="store_true", help="显示完整错误追踪")
    return parser.parse_args(argv)


def redirect_working_dir() -> None:
    """Keep third-party logs (e.g. IME debug logs) out of the program folder."""
    import os
    import tempfile

    try:
        base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
        target = Path(base) / "RoseChartStudio"
        target.mkdir(parents=True, exist_ok=True)
        os.chdir(target)
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    set_dpi_awareness()
    set_app_user_model_id()
    redirect_working_dir()

    try:
        import matplotlib

        matplotlib.use("TkAgg", force=True)
        import tkinter as tk

        from rosechart.main_window import RoseChartApp

        root = tk.Tk()
        app = RoseChartApp(root)

        def report_callback_error(exc, value, tb) -> None:  # pragma: no cover
            write_crash_log(value)
            try:
                from tkinter import messagebox

                messagebox.showerror(
                    "RoseChart 遇到问题",
                    f"{value}\n\n详细信息已写入：\n{LOG_PATH}",
                    parent=root,
                )
            except Exception:
                pass

        root.report_callback_exception = report_callback_error
        if args.file:
            root.after(80, lambda: app.load_file(args.file))
        if args.smoke > 0:
            root.after(int(args.smoke * 1000), app._on_close)
        root.mainloop()
        return 0
    except BaseException as exc:  # noqa: BLE001 - last line of defence
        write_crash_log(exc)
        message = f"程序遇到错误：{exc}\n\n详细信息已写入：\n{LOG_PATH}"
        if args.debug:
            message += "\n\n" + "".join(traceback.format_exception(exc))
        show_fatal_error(message)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

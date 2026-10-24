"""RoseChart Studio main window."""
from __future__ import annotations

import copy
import datetime
import re
import tkinter as tk
from dataclasses import asdict
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from . import __version__
from . import data as data_mod
from . import prefs as prefs_mod
from . import ui_widgets as W
from .chart import (
    TRANSPARENT,
    RoseChart,
    StyleConfig,
    available_cjk_fonts,
    build_spec,
    configure_chinese_font,
    render_bytes,
)
from .palettes import (
    PALETTES,
    Palette,
    assign_colors,
    contrast_ratio,
    label_color,
    luminance,
    mix_colors,
    palette_by_id,
    recommend_palettes,
)

APP_TITLE = "玫瑰图工坊"
APP_SUBTITLE = "RoseChart Studio"
APP_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = APP_DIR / "assets"
ICON_PATH = ASSETS_DIR / "icon.ico"
ICON_PNG = ASSETS_DIR / "icon_256.png"

CHART_KEYS = ("chart1", "chart2")
CHART_LABELS = {"chart1": "项目统计", "chart2": "状态统计"}
NO_COLUMN = "（不使用）"
SIZE_PRESETS = {
    "1200 × 800": (1200, 800),
    "1600 × 1067": (1600, 1067),
    "1920 × 1280": (1920, 1280),
    "2560 × 1707": (2560, 1707),
    "自定义": None,
}
FORMAT_LABELS = {"png": "PNG 图片", "svg": "SVG 矢量", "pdf": "PDF 矢量"}
LEFT_WIDTH = 314
RIGHT_WIDTH = 394
LABEL_MIN_CONTRAST = 4.0


def _shorten(text: str, limit: int = 46) -> str:
    text = str(text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _sanitize_filename(text: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", str(text)).strip(" .")
    return cleaned or "rose-chart"


class RoseChartApp:
    def __init__(self, root: tk.Tk, prefs_path: str | Path | None = None) -> None:
        self.root = root
        self.prefs = prefs_mod.Preferences(Path(prefs_path) if prefs_path else None)
        self.prefs.load()
        project = copy.deepcopy(self.prefs.project)

        self.chart_states: dict[str, dict] = {}
        for key in CHART_KEYS:
            state = prefs_mod.default_chart_state(key)
            state.update(project.get("charts", {}).get(key, {}) or {})
            state.setdefault("layout", {})
            state.setdefault("overrides", {})
            self.chart_states[key] = state
        self.style: StyleConfig = prefs_mod.style_from_dict(project.get("style"))
        self.export_state: dict = prefs_mod.default_project_state()["export"]
        self.export_state.update(project.get("export", {}) or {})
        self.active_chart: str = project.get("active") if project.get("active") in CHART_KEYS else "chart1"
        self.file_path: str = str(project.get("file") or "")
        self.sheet_name: str = str(project.get("sheet") or "")
        self.column_a: str = str(project.get("column_a") or "")
        self.column_b: str = str(project.get("column_b") or "")

        self.sheet_data: data_mod.SheetData | None = None
        self.counts: dict[str, list[tuple[str, int]]] = {key: [] for key in CHART_KEYS}
        self.chart: RoseChart | None = None
        self.figure = Figure(figsize=(12, 8), dpi=100)
        self.canvas: FigureCanvasTkAgg | None = None
        self.preview_widget: tk.Widget | None = None
        self._drag: dict | None = None
        self._hover_label: str | None = None
        self._undo: dict[str, list[dict]] = {key: [] for key in CHART_KEYS}
        self._redo: dict[str, list[dict]] = {key: [] for key in CHART_KEYS}
        self._render_after: str | None = None
        self._fit_after: str | None = None
        self._prefs_after: str | None = None
        self._title_after: str | None = None
        self._suppress = False
        self._dpi = 100
        self._busy = False

        W.setup_fonts(root)
        configure_chinese_font(self.style.font_family)
        W.init_styles(root)
        self._style_font = W.FONT_FAMILY

        self._setup_window()
        self._build_menu()
        self._build_header()
        self._build_statusbar()
        self._build_body()
        W.install_wheel_router(root)
        self._bind_shortcuts()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._sync_all_controls()
        self.root.after(120, self._bootstrap)

    # ------------------------------------------------------------------
    # Window / chrome
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.root.title(f"{APP_TITLE} · {APP_SUBTITLE}")
        self.root.configure(bg=W.BG)
        self.root.minsize(W.px(1440), W.px(870))
        geometry = self.prefs.window_geometry()
        restored = self._apply_saved_geometry(geometry)
        if not restored:
            width, height = W.px(1520), W.px(940)
            x = max(0, (self.root.winfo_screenwidth() - width) // 2)
            y = max(0, (self.root.winfo_screenheight() - height) // 2 - W.px(12))
            self.root.geometry(f"{width}x{height}+{x}+{y}")
        if ICON_PATH.is_file():
            try:
                self.root.iconbitmap(default=str(ICON_PATH))
            except tk.TclError:
                pass

    def _apply_saved_geometry(self, geometry: str) -> bool:
        match = re.match(r"^(\d+)x(\d+)([+-]\d+)([+-]\d+)$", geometry or "")
        if not match:
            return False
        width, height, x, y = (int(match.group(i)) for i in (1, 2, 3, 4))
        width, height = max(W.px(1440), width), max(W.px(870), height)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = max(-width + W.px(120), min(x, screen_w - W.px(160)))
        y = max(0, min(y, screen_h - W.px(120)))
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        if self.prefs.data.get("window", {}).get("zoomed"):
            try:
                self.root.state("zoomed")
            except tk.TclError:
                pass
        return True

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=W.PANEL)
        header.pack(fill="x", side="top")
        inner = tk.Frame(header, bg=W.PANEL)
        inner.pack(fill="x", padx=W.px(20), pady=W.px(11))

        logo: tk.Widget | None = None
        self._logo_image = None
        if ICON_PNG.is_file():
            try:
                from PIL import Image, ImageTk

                size = W.px(34)
                image = Image.open(ICON_PNG).convert("RGBA").resize((size, size), Image.LANCZOS)
                self._logo_image = ImageTk.PhotoImage(image)
                logo = tk.Label(inner, image=self._logo_image, bg=W.PANEL, bd=0)
            except Exception:
                logo = None
        if logo is None:
            logo = W.BrandMark(inner, size=34)
        logo.pack(side="left")

        title_box = tk.Frame(inner, bg=W.PANEL)
        title_box.pack(side="left", padx=(W.px(12), 0))
        tk.Label(
            title_box, text=APP_TITLE, bg=W.PANEL, fg=W.TEXT, font=W.font(14, "bold"), anchor="w"
        ).pack(anchor="w")
        tk.Label(
            title_box, text=APP_SUBTITLE, bg=W.PANEL, fg=W.TEXT_MUTED, font=W.font(9.5), anchor="w"
        ).pack(anchor="w")

        self.header_file = tk.Label(
            inner,
            text="未加载 Excel",
            bg=W.PANEL,
            fg=W.TEXT_MUTED,
            font=W.font(10.5),
            anchor="w",
        )
        self.header_file.pack(side="left", padx=(W.px(24), 0))

        self.header_export_button = W.FlatButton(
            inner, "导出设置", kind="secondary", command=lambda: self._select_right_tab(2)
        )
        self.header_export_button.pack(side="right", padx=(W.px(10), 0))
        W.Tooltip(self.header_export_button, "打开导出面板（Ctrl+E 直接导出当前图）")
        W.FlatButton(
            inner, "打开 Excel", kind="secondary", command=self._open_file
        ).pack(side="right")

        border = tk.Frame(self.root, bg=W.BORDER, height=1)
        border.pack(fill="x", side="top")

    def _build_statusbar(self) -> None:
        self.status = W.StatusBar(self.root)
        self.status.pack(fill="x", side="bottom")
        self.status.set_message("正在启动…", "busy")

    def _build_body(self) -> None:
        body = tk.Frame(self.root, bg=W.BG)
        body.pack(fill="both", expand=True, padx=W.px(16), pady=(W.px(12), W.px(12)))

        self.left_panel = W.InspectorPanel(body, width=W.px(LEFT_WIDTH))
        self.left_panel.pack(side="left", fill="y")

        self.right_area = tk.Frame(body, bg=W.BG, width=W.px(RIGHT_WIDTH))
        self.right_area.pack(side="right", fill="y")
        self.right_area.pack_propagate(False)

        self.center_area = tk.Frame(body, bg=W.BG)
        self.center_area.pack(side="left", fill="both", expand=True, padx=W.px(14))

        self._build_left_panel()
        self._build_preview_panel()
        self._build_right_panel()

    # ------------------------------------------------------------------
    # Left panel
    # ------------------------------------------------------------------

    def _build_left_panel(self) -> None:
        parent = self.left_panel.inner

        source = W.Card(parent, "数据")
        source.pack(fill="x", pady=(0, W.px(26)))
        tk.Label(
            source.body, text="Excel 文件", bg=W.PANEL, fg=W.TEXT_MUTED,
            font=W.font(10), anchor="w",
        ).pack(anchor="w", pady=(0, W.px(5)))
        file_row = tk.Frame(source.body, bg=W.PANEL)
        file_row.pack(fill="x")
        self.file_var = tk.StringVar()
        file_shell = tk.Frame(
            file_row,
            bg=W.PANEL_ALT,
            highlightthickness=1,
            highlightbackground=W.BORDER,
            highlightcolor=W.BORDER,
        )
        file_shell.pack(side="left", fill="x", expand=True)
        self.file_display = tk.Label(
            file_shell,
            textvariable=self.file_var,
            bg=W.PANEL_ALT,
            fg=W.TEXT,
            font=W.font(10.5),
            anchor="w",
            padx=W.px(9),
            pady=W.px(7),
        )
        self.file_display.pack(fill="x")
        W.FlatButton(
            file_row, "浏览…", kind="secondary", command=self._open_file, padx_=11, pady_=6
        ).pack(side="left", padx=(W.px(6), 0))

        self.sheet_var = tk.StringVar()
        tk.Label(
            source.body, text="工作表", bg=W.PANEL, fg=W.TEXT_MUTED,
            font=W.font(10), anchor="w",
        ).pack(anchor="w", pady=(W.px(12), W.px(5)))
        self.sheet_combo = ttk.Combobox(
            source.body, textvariable=self.sheet_var, state="readonly", values=[]
        )
        self.sheet_combo.pack(fill="x")
        self.sheet_combo.bind("<<ComboboxSelected>>", self._on_sheet_changed)

        tk.Label(
            source.body, text="统计列", bg=W.PANEL, fg=W.TEXT,
            font=W.font(10.5, "bold"), anchor="w",
        ).pack(anchor="w", pady=(W.px(20), W.px(8)))

        self.col_a_var = tk.StringVar()
        self.col_b_var = tk.StringVar()
        col_a_row = tk.Frame(source.body, bg=W.PANEL)
        col_a_row.pack(fill="x")
        tk.Label(
            col_a_row, text="类别列", bg=W.PANEL, fg=W.TEXT_MUTED, font=W.font(10),
            anchor="w", width=W.px(7),
        ).pack(side="left")
        self.col_a_combo = ttk.Combobox(
            col_a_row, textvariable=self.col_a_var, state="readonly", values=[NO_COLUMN]
        )
        self.col_a_combo.pack(side="left", fill="x", expand=True)
        col_b_row = tk.Frame(source.body, bg=W.PANEL)
        col_b_row.pack(fill="x", pady=(W.px(7), 0))
        tk.Label(
            col_b_row, text="状态列", bg=W.PANEL, fg=W.TEXT_MUTED, font=W.font(10),
            anchor="w", width=W.px(7),
        ).pack(side="left")
        self.col_b_combo = ttk.Combobox(
            col_b_row, textvariable=self.col_b_var, state="readonly", values=[NO_COLUMN]
        )
        self.col_b_combo.pack(side="left", fill="x", expand=True)
        self.col_a_combo.bind("<<ComboboxSelected>>", self._on_columns_changed)
        self.col_b_combo.bind("<<ComboboxSelected>>", self._on_columns_changed)

        sort_row = tk.Frame(source.body, bg=W.PANEL)
        sort_row.pack(fill="x", pady=(W.px(7), 0))
        tk.Label(
            sort_row, text="排序", bg=W.PANEL, fg=W.TEXT_MUTED, font=W.font(10),
            anchor="w", width=W.px(7),
        ).pack(side="left")
        self.sort_var = tk.StringVar(value="数量从多到少")
        self.sort_combo = ttk.Combobox(
            sort_row,
            textvariable=self.sort_var,
            state="readonly",
            values=["数量从多到少", "数量从少到多", "按名称"],
            width=W.px(12),
        )
        self.sort_combo.pack(side="left", fill="x", expand=True)
        self.sort_combo.bind("<<ComboboxSelected>>", self._on_sort_changed)

        data_card = W.Card(parent, "数据概览", "点击行定位标签")
        data_card.pack(fill="x")
        self.data_card = data_card
        self.table1 = W.DataTable(
            data_card.body, height=4, on_select=lambda label: self._highlight_label("chart1", label)
        )
        self._table_caption(data_card.body, CHART_LABELS["chart1"], self.table1, first=True)
        self.table2 = W.DataTable(
            data_card.body, height=4, on_select=lambda label: self._highlight_label("chart2", label)
        )
        self._table_caption(data_card.body, CHART_LABELS["chart2"], self.table2)

    def _table_caption(self, parent: tk.Misc, text: str, table: W.DataTable, *, first: bool = False):
        row = tk.Frame(parent, bg=W.PANEL)
        row.pack(fill="x", pady=(0 if first else W.px(14), W.px(4)))
        tk.Label(
            row, text=text, bg=W.PANEL, fg=W.TEXT, font=W.font(10, "bold"), anchor="w"
        ).pack(side="left")
        count = tk.Label(
            row, text="", bg=W.PANEL, fg=W.TEXT_MUTED, font=W.font(9.5), anchor="e"
        )
        count.pack(side="right")
        table.pack(fill="x")
        table._caption_label = count  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Center preview
    # ------------------------------------------------------------------

    def _build_preview_panel(self) -> None:
        toolbar = tk.Frame(self.center_area, bg=W.BG)
        toolbar.pack(fill="x", pady=(0, W.px(10)))
        self.chart_tabs = W.SegmentedControl(
            toolbar,
            [(key, CHART_LABELS[key]) for key in CHART_KEYS],
            command=self._on_chart_tab,
            initial=self.active_chart,
        )
        self.chart_tabs.pack(side="left")

        self.redo_button = W.IconButton(
            toolbar, "redo", self._redo_layout, bg=W.BG, tooltip="重做标签调整 (Ctrl+Y)"
        )
        self.redo_button.pack(side="right")
        self.undo_button = W.IconButton(
            toolbar, "undo", self._undo_layout, bg=W.BG, tooltip="撤销标签调整 (Ctrl+Z)"
        )
        self.undo_button.pack(side="right", padx=(0, W.px(2)))
        self.auto_button = W.FlatButton(
            toolbar,
            "自动排列",
            kind="secondary",
            command=self._auto_arrange,
            padx_=12,
            pady_=6,
            size=10,
        )
        self.auto_button.pack(side="right", padx=(0, W.px(6)))
        self.auto_button.set_enabled(False)
        W.Tooltip(self.auto_button, "恢复所有标签的自动位置 (Ctrl+R)")

        card = tk.Frame(
            self.center_area,
            bg=W.PANEL,
            highlightthickness=1,
            highlightbackground=W.BORDER,
        )
        card.pack(fill="both", expand=True)
        stage_holder = tk.Frame(card, bg=W.PANEL)
        stage_holder.pack(fill="both", expand=True, padx=W.px(10), pady=(W.px(10), 0))

        self.preview_stage = tk.Frame(
            stage_holder,
            bg=W.PREVIEW_BG,
            highlightthickness=1,
            highlightbackground=W.BORDER,
        )
        self.preview_stage.pack(fill="both", expand=True)
        self.preview_stage.bind("<Configure>", self._on_stage_configure)

        self.canvas = FigureCanvasTkAgg(self.figure, master=self.preview_stage)
        self.preview_widget = self.canvas.get_tk_widget()
        self.preview_widget.configure(bg=W.PREVIEW_BG, highlightthickness=0, bd=0)
        self.preview_widget.place(
            relx=0.5, rely=0.5, anchor="center", width=W.px(600), height=W.px(400)
        )
        self.canvas.mpl_connect("button_press_event", self._on_canvas_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_canvas_motion)
        self.canvas.mpl_connect("button_release_event", self._on_canvas_release)
        self.canvas.mpl_connect("figure_leave_event", self._on_canvas_leave)

        self._build_empty_state()

        tk.Frame(card, bg=W.BORDER, height=1).pack(
            fill="x", padx=W.px(12), pady=(W.px(8), 0)
        )
        hint_bar = tk.Frame(card, bg=W.PANEL)
        hint_bar.pack(fill="x", padx=W.px(14), pady=(W.px(5), W.px(8)))
        self.preview_hint = tk.Label(
            hint_bar,
            text="拖动标签微调位置 · 双击标签复位",
            bg=W.PANEL,
            fg=W.TEXT_MUTED,
            font=W.font(10),
            anchor="w",
        )
        self.preview_hint.pack(side="left")
        self.layout_state = tk.Label(
            hint_bar,
            text="布局：自动",
            bg=W.PANEL,
            fg=W.TEXT_MUTED,
            font=W.font(9.5),
            anchor="e",
        )
        self.layout_state.pack(side="right")

    def _build_empty_state(self) -> None:
        overlay = tk.Frame(self.preview_stage, bg=W.PREVIEW_BG)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        center = tk.Frame(overlay, bg=W.PREVIEW_BG)
        center.place(relx=0.5, rely=0.46, anchor="center")

        glyph = tk.Canvas(
            center, width=W.px(76), height=W.px(76), bg=W.PREVIEW_BG,
            highlightthickness=0, bd=0,
        )
        glyph.pack()
        size = W.px(76)
        margin = W.px(6)
        box = (margin, margin, size - margin, size - margin)
        petal_colors = ["#0F766E", "#0891B2", "#67C7BE", "#D9A441", "#D9A0C8", "#93A8BC"]
        step = 360.0 / len(petal_colors)
        for index, base in enumerate(petal_colors):
            fill = W.mix(base, "#FFFFFF", 0.55)
            glyph.create_arc(
                *box,
                start=90 - index * step,
                extent=-step + 3.0,
                fill=fill,
                outline=fill,
            )
        hole = size * 0.34
        glyph.create_oval(
            size / 2 - hole / 2,
            size / 2 - hole / 2,
            size / 2 + hole / 2,
            size / 2 + hole / 2,
            fill=W.PREVIEW_BG,
            outline="",
        )

        self.empty_title = tk.Label(
            center,
            text="还没有可预览的数据",
            bg=W.PREVIEW_BG,
            fg=W.TEXT,
            font=W.font(13, "bold"),
        )
        self.empty_title.pack(pady=(W.px(10), W.px(4)))
        self.empty_message = tk.Label(
            center,
            text="打开 Excel 后会自动生成两张玫瑰图",
            bg=W.PREVIEW_BG,
            fg=W.TEXT_MUTED,
            font=W.font(10.5),
        )
        self.empty_message.pack()
        self.empty_hint = tk.Label(
            center,
            text="图表生成后，可直接拖动数据标签调整位置",
            bg=W.PREVIEW_BG,
            fg=W.TEXT_MUTED,
            font=W.font(10),
        )
        self.empty_hint.pack(pady=(W.px(3), W.px(14)))
        self.empty_open_button = W.FlatButton(
            center, "打开 Excel", kind="primary", command=self._open_file
        )
        self.empty_open_button.pack()
        self._empty_button_visible = True
        self.empty_overlay = overlay

    # ------------------------------------------------------------------
    # Right panel
    # ------------------------------------------------------------------

    def _build_right_panel(self) -> None:
        tab_holder = tk.Frame(self.right_area, bg=W.BG)
        tab_holder.pack(fill="x", pady=(W.px(1), W.px(7)))
        self.right_tabs = W.Tabs(
            tab_holder,
            ["配色", "样式", "导出"],
            command=self._on_right_tab,
            initial=0,
        )
        self.right_tabs.pack(fill="x")

        self.pages_holder = tk.Frame(self.right_area, bg=W.BG)
        self.pages_holder.pack(fill="both", expand=True)
        self.pages: dict[str, W.InspectorPanel] = {}
        for key in ("palette", "style", "export"):
            page = W.InspectorPanel(self.pages_holder, width=W.px(RIGHT_WIDTH))
            self.pages[key] = page
        self._build_palette_page(self.pages["palette"].inner)
        self._build_style_page(self.pages["style"].inner)
        self._build_export_page(self.pages["export"].inner)
        self._show_right_page("palette")

    def _show_right_page(self, key: str) -> None:
        for page_key, page in self.pages.items():
            if page_key == key:
                page.pack(fill="both", expand=True)
                page.scroll_to_top()
            else:
                page.pack_forget()

    def _on_right_tab(self, index: int) -> None:
        keys = ("palette", "style", "export")
        self._show_right_page(keys[max(0, min(index, len(keys) - 1))])

    # -- palette page ---------------------------------------------------

    def _build_palette_page(self, parent: tk.Misc) -> None:
        current_row = tk.Frame(parent, bg=W.PANEL)
        current_row.pack(fill="x", pady=(0, W.px(22)))
        tk.Label(
            current_row, text="当前方案", bg=W.PANEL, fg=W.TEXT_MUTED, font=W.font(10)
        ).pack(side="left")
        self.current_swatches = tk.Canvas(
            current_row, height=W.px(16), bg=W.PANEL, highlightthickness=0, bd=0
        )
        self.current_swatches.pack(side="left", padx=(W.px(10), W.px(8)))
        self.current_name = tk.Label(
            current_row, text="", bg=W.PANEL, fg=W.TEXT, font=W.font(10.5, "bold")
        )
        self.current_name.pack(side="left")
        self.current_meta = tk.Label(
            current_row, text="", bg=W.PANEL, fg=W.TEXT_MUTED, font=W.font(9.5)
        )
        self.current_meta.pack(side="right")

        rec_card = W.Card(parent, "推荐配色")
        rec_card.pack(fill="x", pady=(0, W.px(26)))
        self.rec_card = rec_card
        self.rec_hint = tk.Label(
            rec_card.body,
            text="",
            bg=W.PANEL,
            fg=W.TEXT_MUTED,
            font=W.font(10),
            anchor="w",
            justify="left",
        )
        self.rec_hint.pack(anchor="w", pady=(0, W.px(8)))
        self.rec_grid = tk.Frame(rec_card.body, bg=W.PANEL)
        self.rec_grid.pack(fill="x")
        for column in (0, 1):
            self.rec_grid.grid_columnconfigure(column, weight=1)
        self.palette_note = tk.Label(
            rec_card.body,
            text="",
            bg=W.PANEL,
            fg=W.WARNING,
            font=W.font(10),
            anchor="w",
            justify="left",
            wraplength=W.px(330),
        )
        self.palette_note.pack(anchor="w", pady=(W.px(7), 0))

        all_card = W.Card(parent, "全部配色方案")
        self.all_card = all_card
        filter_row = tk.Frame(all_card.body, bg=W.PANEL)
        filter_row.pack(fill="x", pady=(0, W.px(8)))
        tk.Label(
            filter_row, text="色系", bg=W.PANEL, fg=W.TEXT_MUTED, font=W.font(10)
        ).pack(side="left")
        self.group_var = tk.StringVar(value="全部色系")
        self.group_combo = ttk.Combobox(
            filter_row,
            textvariable=self.group_var,
            state="readonly",
            values=["全部色系"],
            width=W.px(12),
        )
        self.group_combo.pack(side="right")
        self.group_combo.bind("<<ComboboxSelected>>", lambda _e: self._rebuild_palette_gallery())
        self.gallery_frame = tk.Frame(all_card.body, bg=W.PANEL)
        self.gallery_frame.pack(fill="x")
        for column in (0, 1):
            self.gallery_frame.grid_columnconfigure(column, weight=1)

        label_card = W.Card(parent, "标签配色")
        label_card.pack(fill="x", pady=(0, W.px(26)))
        self.label_card = label_card
        self.label_mode_control = W.SegmentedControl(
            label_card.body,
            [
                ("match", "跟随扇区"),
                ("auto", "自动加深"),
                ("single", "统一深色"),
            ],
            command=self._on_label_mode,
            initial=self.chart_states[self.active_chart].get("label_mode", "auto"),
            bg=W.PANEL,
        )
        self.label_mode_control.pack(fill="x")
        color_row = tk.Frame(label_card.body, bg=W.PANEL)
        color_row.pack(fill="x", pady=(W.px(10), 0))
        tk.Label(
            color_row,
            text="统一标签色",
            bg=W.PANEL,
            fg=W.TEXT_MUTED,
            font=W.font(10),
        ).pack(side="left")
        self.label_color_button = W.ColorButton(
            color_row,
            self.chart_states[self.active_chart].get("label_single_color", "#334155"),
            command=self._pick_single_label_color,
        )
        self.label_color_button.pack(side="right")

        category_card = W.Card(parent, "类别颜色")
        category_card.pack(fill="x", pady=(0, W.px(26)))
        self.category_card = category_card
        self.category_rows = tk.Frame(category_card.body, bg=W.PANEL)
        self.category_rows.pack(fill="x")
        # The full palette library is intentionally the quiet, last section.
        all_card.pack(fill="x")

    def _rebuild_palette_gallery(self) -> None:
        for child in self.gallery_frame.winfo_children():
            child.destroy()
        for child in self.rec_grid.winfo_children():
            child.destroy()
        groups = ["全部色系"]
        for palette in PALETTES:
            if palette.group not in groups:
                groups.append(palette.group)
        if self.group_var.get() not in groups:
            self.group_var.set(groups[0])
        self.group_combo.configure(values=groups)

        counts = self._visible_counts()
        n_labels = len(counts)
        current_id = self.chart_states[self.active_chart].get("palette_id", "")
        current = self._palette_for(self.chart_states[self.active_chart])
        self.current_swatches.delete("all")
        x_cursor = 0
        for color in current.colors:
            self.current_swatches.create_rectangle(
                x_cursor, 0, x_cursor + W.px(14), W.px(16),
                fill=color, outline="",
            )
            x_cursor += W.px(16)
        self.current_swatches.configure(width=max(W.px(14), x_cursor))
        self.current_name.configure(text=current.name)
        self.current_meta.configure(text=f"{len(current.colors)} 色")
        recommendations = []
        try:
            recommendations = list(recommend_palettes(max(1, n_labels), limit=4))
        except Exception:
            recommendations = []
        if not recommendations:
            recommendations = list(PALETTES[:4])
        rec_ids = {palette.id for palette in recommendations}
        if n_labels:
            if self.rec_card.winfo_manager() == "":
                self.rec_card.pack(fill="x", pady=(0, W.px(26)), before=self.label_card)
            self.rec_hint.configure(text=f"为 {n_labels} 个类别推荐")
            for index, palette in enumerate(recommendations[:4]):
                card = W.PaletteCard(
                    self.rec_grid,
                    palette.name,
                    palette.colors,
                    group=palette.group,
                    tag="",
                    selected=palette.id == current_id,
                    command=lambda pid=palette.id: self._apply_palette(pid),
                )
                card.grid(
                    row=index // 2, column=index % 2,
                    padx=W.px(4), pady=W.px(4), sticky="n",
                )
        else:
            if self.rec_card.winfo_manager() != "":
                self.rec_card.pack_forget()
            self.rec_hint.configure(text="打开 Excel 后显示推荐方案")

        current_palette = self._palette_for(self.chart_states[self.active_chart])
        available_colors = len(current_palette.colors)
        if n_labels > available_colors:
            self.palette_note.configure(
                text=f"当前方案只有 {available_colors} 种颜色，{n_labels} 个类别会循环复用。"
            )
            if self.palette_note.winfo_manager() == "":
                self.palette_note.pack(anchor="w", pady=(W.px(7), 0))
        else:
            if self.palette_note.winfo_manager() != "":
                self.palette_note.pack_forget()

        chosen_group = self.group_var.get()
        filtered = [
            palette
            for palette in PALETTES
            if chosen_group == "全部色系" or palette.group == chosen_group
        ]
        for index, palette in enumerate(filtered):
            duplicated = palette.id == current_id and palette.id in rec_ids
            card = W.PaletteCard(
                self.gallery_frame,
                palette.name,
                palette.colors,
                group=palette.group,
                tag="已选" if duplicated else "",
                selected=palette.id == current_id and not duplicated,
                command=lambda pid=palette.id: self._apply_palette(pid),
            )
            card.grid(row=index // 2, column=index % 2, padx=W.px(4), pady=W.px(4), sticky="n")

    def _rebuild_category_rows(self) -> None:
        for child in self.category_rows.winfo_children():
            child.destroy()
        state = self.chart_states[self.active_chart]
        counts = self._visible_counts()
        if not counts:
            tk.Label(
                self.category_rows,
                text="暂无数据",
                bg=W.PANEL,
                fg=W.TEXT_MUTED,
                font=W.font(10),
                anchor="w",
            ).pack(anchor="w")
            return
        palette = self._palette_for(state)
        labels = [label for label, _value in counts]
        colors = assign_colors(palette, labels, state.get("overrides") or {})
        total = sum(value for _label, value in counts) or 1
        for label, value in counts:
            row = tk.Frame(self.category_rows, bg=W.PANEL)
            row.pack(fill="x", pady=W.px(3))
            override = (state.get("overrides") or {}).get(label)
            color_button = W.ColorButton(
                row,
                colors.get(label, "#CCCCCC"),
                command=lambda label=label: self._pick_category_color(label),
                size=20,
            )
            color_button.pack(side="left")
            tk.Label(
                row,
                text=_shorten(label, 12),
                bg=W.PANEL,
                fg=W.TEXT,
                font=W.font(10.5),
                anchor="w",
            ).pack(side="left", padx=(W.px(8), 0))
            tk.Label(
                row,
                text=f"{value} · {value / total * 100:.0f}%",
                bg=W.PANEL,
                fg=W.TEXT_MUTED,
                font=W.font(10),
            ).pack(side="right")
            if override:
                reset = tk.Label(
                    row,
                    text="重置",
                    bg=W.PANEL,
                    fg=W.PRIMARY,
                    font=W.font(10, "underline"),
                    cursor="hand2",
                )
                reset.pack(side="right", padx=(0, W.px(8)))
                reset.bind(
                    "<Button-1>",
                    lambda _e, label=label: self._reset_category_color(label),
                )

    # -- style page -----------------------------------------------------

    def _build_style_page(self, parent: tk.Misc) -> None:
        self._style_rows: dict[str, W.SliderRow] = {}
        style = self.style

        title_card = W.Card(parent, "标题", "当前图")
        title_card.pack(fill="x", pady=(0, W.px(26)))
        self.title_var = tk.StringVar()
        self.subtitle_var = tk.StringVar()
        tk.Label(
            title_card.body, text="主标题", bg=W.PANEL, fg=W.TEXT_MUTED, font=W.font(10)
        ).pack(anchor="w")
        self.title_entry = ttk.Entry(title_card.body, textvariable=self.title_var)
        self.title_entry.pack(fill="x", pady=(W.px(3), W.px(8)))
        tk.Label(
            title_card.body, text="副标题（可留空）", bg=W.PANEL, fg=W.TEXT_MUTED, font=W.font(10)
        ).pack(anchor="w")
        ttk.Entry(title_card.body, textvariable=self.subtitle_var).pack(
            fill="x", pady=(W.px(3), 0)
        )
        self.title_var.trace_add("write", lambda *_a: self._on_title_changed())
        self.subtitle_var.trace_add("write", lambda *_a: self._on_title_changed())

        geom = W.Card(parent, "图形几何")
        geom.pack(fill="x", pady=(0, W.px(26)))
        self._add_slider(geom.body, "内半径", "inner_radius", 0.05, 0.65, lambda v: f"{v:.2f}")
        self._add_slider(geom.body, "外半径", "outer_radius", 0.5, 1.05, lambda v: f"{v:.2f}")
        self._add_slider(geom.body, "起始角度", "start_angle", 0, 360, lambda v: f"{v:.0f}°", step=1)
        self._add_slider(geom.body, "扇区间隙", "gap_ratio", 0.0, 0.8, lambda v: f"{v * 100:.0f}%")
        self._add_slider(geom.body, "扇区圆角", "corner_radius", 0.0, 0.14, lambda v: f"{v:.3f}")
        self._add_slider(geom.body, "描边宽度", "edge_width", 0.0, 8.0, lambda v: f"{v:.1f}")

        label_card = W.Card(parent, "标签与文字")
        label_card.pack(fill="x", pady=(0, W.px(26)))
        self._add_slider(label_card.body, "标签字号", "label_font_size", 8, 42, lambda v: f"{v:.0f}pt", step=1)
        self._add_slider(label_card.body, "标签线长度", "label_wire_scale", 0.3, 2.0, lambda v: f"{v:.2f}")
        self._add_slider(label_card.body, "标签线宽度", "label_line_width", 0.2, 3.0, lambda v: f"{v:.1f}")
        self._add_slider(label_card.body, "标题字号", "title_font_size", 14, 52, lambda v: f"{v:.0f}pt", step=1)

        check_holder = tk.Frame(label_card.body, bg=W.PANEL)
        check_holder.pack(fill="x", pady=(W.px(4), 0))
        self.show_name_var = tk.BooleanVar(value=style.show_name)
        self.show_value_var = tk.BooleanVar(value=style.show_value)
        self.show_percent_var = tk.BooleanVar(value=style.show_percent)
        W.CheckRow(
            check_holder, "类别名称", self.show_name_var,
            lambda: self._on_check("show_name", self.show_name_var),
        ).pack(anchor="w", pady=W.px(3))
        W.CheckRow(
            check_holder, "数量", self.show_value_var,
            lambda: self._on_check("show_value", self.show_value_var),
        ).pack(anchor="w", pady=W.px(3))
        W.CheckRow(
            check_holder, "百分比", self.show_percent_var,
            lambda: self._on_check("show_percent", self.show_percent_var),
        ).pack(anchor="w", pady=W.px(3))

        suffix_row = tk.Frame(label_card.body, bg=W.PANEL)
        suffix_row.pack(fill="x", pady=(W.px(8), 0))
        tk.Label(
            suffix_row, text="数值后缀", bg=W.PANEL, fg=W.TEXT_MUTED, font=W.font(10)
        ).pack(side="left")
        self.suffix_var = tk.StringVar(value=style.value_suffix)
        suffix_entry = ttk.Entry(suffix_row, textvariable=self.suffix_var, width=W.px(10))
        suffix_entry.pack(side="right")
        self.suffix_var.trace_add("write", lambda *_a: self._on_suffix_changed())

        decimals_row = tk.Frame(label_card.body, bg=W.PANEL)
        decimals_row.pack(fill="x", pady=(W.px(8), 0))
        tk.Label(
            decimals_row, text="百分比小数位", bg=W.PANEL, fg=W.TEXT_MUTED, font=W.font(10)
        ).pack(side="left")
        self.decimals_var = tk.StringVar(value=str(style.percent_decimals))
        decimals_entry = ttk.Entry(
            decimals_row, textvariable=self.decimals_var, width=W.px(5)
        )
        decimals_entry.pack(side="right")
        decimals_entry.bind("<FocusOut>", lambda _e: self._on_decimals_changed())
        decimals_entry.bind("<Return>", lambda _e: self._on_decimals_changed())

        font_row = tk.Frame(label_card.body, bg=W.PANEL)
        font_row.pack(fill="x", pady=(W.px(8), 0))
        tk.Label(
            font_row, text="字体", bg=W.PANEL, fg=W.TEXT_MUTED, font=W.font(10)
        ).pack(side="left")
        families = available_cjk_fonts() or [W.FONT_FAMILY]
        self.font_var = tk.StringVar(value=style.font_family if style.font_family in families else families[0])
        self.font_combo = ttk.Combobox(
            font_row, textvariable=self.font_var, values=families, state="readonly", width=W.px(13)
        )
        self.font_combo.pack(side="right")
        self.font_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_font_changed())

        center_card = W.Card(parent, "中心文字")
        center_card.pack(fill="x", pady=(0, W.px(26)))
        self.center_var = tk.StringVar(value=style.center_text)
        ttk.Entry(center_card.body, textvariable=self.center_var).pack(fill="x")
        tk.Label(
            center_card.body,
            text="可留空；占位符 {total} {n} {max}",
            bg=W.PANEL,
            fg=W.TEXT_MUTED,
            font=W.font(10),
        ).pack(anchor="w", pady=(W.px(4), 0))
        self.center_var.trace_add("write", lambda *_a: self._on_center_changed())

        background_card = W.Card(parent, "画布背景")
        background_card.pack(fill="x")
        self.background_control = W.SegmentedControl(
            background_card.body,
            [("transparent", "透明"), ("#FFFFFF", "白色"), ("custom", "自定义")],
            command=self._on_background_mode,
            initial="transparent",
            bg=W.PANEL,
        )
        self.background_control.pack(fill="x")
        bg_row = tk.Frame(background_card.body, bg=W.PANEL)
        bg_row.pack(fill="x", pady=(W.px(10), 0))
        tk.Label(
            bg_row,
            text="自定义背景色（不透明导出时生效）",
            bg=W.PANEL,
            fg=W.TEXT_MUTED,
            font=W.font(10),
        ).pack(side="left")
        self.background_color_button = W.ColorButton(
            bg_row,
            self.style.background if self.style.background not in (TRANSPARENT, "#FFFFFF") else "#F8FAFC",
            command=self._pick_background_color,
        )
        self.background_color_button.pack(side="right")

    def _add_slider(
        self,
        parent: tk.Misc,
        label: str,
        field: str,
        from_: float,
        to: float,
        formatter,
        step: float | None = None,
    ) -> None:
        variable = tk.DoubleVar(value=float(getattr(self.style, field)))
        row = W.SliderRow(
            parent,
            label,
            variable,
            from_,
            to,
            command=lambda value, field=field: self._on_style_slider(field, value),
            formatter=formatter,
            step=step,
        )
        row.pack(fill="x", pady=(0, W.px(9)))
        self._style_rows[field] = row

    # -- export page ----------------------------------------------------

    def _build_export_page(self, parent: tk.Misc) -> None:
        export = self.export_state
        settings = W.Card(parent, "导出设置")
        settings.pack(fill="x", pady=(0, W.px(26)))

        tk.Label(
            settings.body, text="图片格式", bg=W.PANEL, fg=W.TEXT_MUTED, font=W.font(10)
        ).pack(anchor="w")
        current_format = str(export.get("format", "png")).lower()
        self.format_control = W.SegmentedControl(
            settings.body,
            [("png", "PNG"), ("svg", "SVG"), ("pdf", "PDF")],
            command=self._on_format_changed,
            initial=current_format if current_format in FORMAT_LABELS else "png",
            bg=W.PANEL,
        )
        self.format_control.pack(fill="x", pady=(W.px(5), W.px(14)))

        size_row = tk.Frame(settings.body, bg=W.PANEL)
        size_row.pack(fill="x")
        tk.Label(
            size_row, text="尺寸", bg=W.PANEL, fg=W.TEXT_MUTED, font=W.font(10)
        ).pack(side="left")
        self.size_var = tk.StringVar(value=self._preset_name_for(export))
        self.size_combo = ttk.Combobox(
            size_row,
            textvariable=self.size_var,
            values=list(SIZE_PRESETS.keys()),
            state="readonly",
            width=W.px(12),
        )
        self.size_combo.pack(side="right")
        self.size_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_size_preset_changed())

        self.width_var = tk.StringVar(value=str(export.get("width", 1200)))
        self.height_var = tk.StringVar(value=str(export.get("height", 800)))
        self.dpi_var = tk.StringVar(value=str(int(export.get("dpi", 100))))
        dims_row = tk.Frame(settings.body, bg=W.PANEL)
        dims_row.pack(fill="x", pady=(W.px(12), 0))
        self.width_spin = self._dimension_widget(dims_row, "宽", self.width_var)
        self.width_spin.pack(side="left")
        tk.Label(dims_row, text=" × ", bg=W.PANEL, fg=W.TEXT_MUTED, font=W.font(10)).pack(side="left")
        self.height_spin = self._dimension_widget(dims_row, "高", self.height_var)
        self.height_spin.pack(side="left")
        tk.Label(dims_row, text="px", bg=W.PANEL, fg=W.TEXT_MUTED, font=W.font(10)).pack(
            side="left", padx=(W.px(6), 0)
        )
        self.dim_hint = tk.Label(
            settings.body, text="", bg=W.PANEL, fg=W.TEXT_MUTED, font=W.font(9.5),
            anchor="w",
        )
        self.dim_hint.pack(anchor="w", pady=(W.px(4), 0))
        dpi_row = tk.Frame(settings.body, bg=W.PANEL)
        dpi_row.pack(fill="x", pady=(W.px(10), 0))
        tk.Label(dpi_row, text="DPI", bg=W.PANEL, fg=W.TEXT_MUTED, font=W.font(10)).pack(
            side="left"
        )
        self.dpi_spin = ttk.Entry(dpi_row, textvariable=self.dpi_var, width=W.px(7))
        self.dpi_spin.pack(side="right")
        self.dpi_spin.bind("<FocusOut>", lambda _e: self._on_export_option_changed())
        self.dpi_spin.bind("<Return>", lambda _e: self._on_export_option_changed())

        self.transparent_var = tk.BooleanVar(value=bool(export.get("transparent", True)))
        W.CheckRow(
            settings.body,
            "透明背景（适合 PPT）",
            self.transparent_var,
            self._on_export_option_changed,
        ).pack(anchor="w", pady=(W.px(8), 0))

        tk.Label(
            settings.body, text="文件名模板", bg=W.PANEL, fg=W.TEXT_MUTED, font=W.font(10)
        ).pack(anchor="w", pady=(W.px(10), W.px(3)))
        self.filename_var = tk.StringVar(value=str(export.get("filename", "{title}")))
        ttk.Entry(settings.body, textvariable=self.filename_var).pack(fill="x")
        tk.Label(
            settings.body,
            text="可用占位符：{title} {sheet} {date} {index}",
            bg=W.PANEL,
            fg=W.TEXT_MUTED,
            font=W.font(10),
        ).pack(anchor="w", pady=(W.px(4), 0))
        self.filename_var.trace_add("write", lambda *_a: self._on_export_option_changed())

        tk.Label(
            settings.body, text="输出目录", bg=W.PANEL, fg=W.TEXT_MUTED, font=W.font(10)
        ).pack(anchor="w", pady=(W.px(10), W.px(3)))
        dir_row = tk.Frame(settings.body, bg=W.PANEL)
        dir_row.pack(fill="x")
        self.output_dir_var = tk.StringVar(value=str(export.get("output_dir", data_mod.DEFAULT_OUTPUT_DIR)))
        ttk.Entry(dir_row, textvariable=self.output_dir_var).pack(side="left", fill="x", expand=True)
        W.FlatButton(
            dir_row, "选择", kind="secondary", command=self._choose_output_dir, padx_=10, pady_=6
        ).pack(side="left", padx=(W.px(6), 0))

        action_card = W.Card(parent, "生成文件")
        action_card.pack(fill="x")
        W.FlatButton(
            action_card.body,
            "导出当前图",
            kind="primary",
            command=self._export_current,
            bold=True,
            pady_=8,
        ).pack(fill="x")
        W.FlatButton(
            action_card.body,
            "导出两张图",
            kind="secondary",
            command=self._export_all,
        ).pack(fill="x", pady=(W.px(10), 0))
        W.FlatButton(
            action_card.body,
            "复制当前图为图片",
            kind="secondary",
            command=self._copy_current_image,
        ).pack(fill="x", pady=(W.px(8), 0))
        W.FlatButton(
            action_card.body,
            "打开输出目录",
            kind="ghost",
            command=self._open_output_dir,
        ).pack(fill="x", pady=(W.px(8), 0))
        tk.Label(
            action_card.body,
            text="导出会保留当前样式与标签位置。",
            bg=W.PANEL,
            fg=W.TEXT_MUTED,
            font=W.font(10),
            wraplength=W.px(320),
            justify="left",
            anchor="w",
        ).pack(anchor="w", pady=(W.px(10), 0))

    def _dimension_widget(
        self,
        parent: tk.Misc,
        name: str,
        variable: tk.StringVar,
        *,
        label_visible: bool = True,
    ):
        holder = tk.Frame(parent, bg=W.PANEL)
        if label_visible:
            tk.Label(holder, text=name, bg=W.PANEL, fg=W.TEXT_MUTED, font=W.font(10)).pack(
                side="left", padx=(0, W.px(3))
            )
        spin = ttk.Entry(holder, textvariable=variable, width=W.px(6))
        spin.pack(side="left")
        spin.bind("<FocusOut>", lambda _e: self._on_export_option_changed())
        spin.bind("<Return>", lambda _e: self._on_export_option_changed())
        holder._spin = spin  # type: ignore[attr-defined]
        return holder

    @staticmethod
    def _preset_name_for(export: dict) -> str:
        width = int(export.get("width", 1200))
        height = int(export.get("height", 800))
        for name, size in SIZE_PRESETS.items():
            if size and size == (width, height):
                return name
        return "自定义"

    # ------------------------------------------------------------------
    # Menu / shortcuts
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root, tearoff=0)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="打开 Excel…", accelerator="Ctrl+O", command=self._open_file)
        file_menu.add_command(label="打开项目…", command=self._open_project)
        file_menu.add_command(label="保存项目", accelerator="Ctrl+S", command=self._save_project)
        file_menu.add_command(label="项目另存为…", command=self._save_project_as)
        file_menu.add_separator()
        file_menu.add_command(label="导出当前图", accelerator="Ctrl+E", command=self._export_current)
        file_menu.add_command(label="导出两张图", command=self._export_all)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self._on_close)
        menubar.add_cascade(label="文件", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="撤销标签调整", accelerator="Ctrl+Z", command=self._undo_layout)
        edit_menu.add_command(label="重做标签调整", accelerator="Ctrl+Y", command=self._redo_layout)
        edit_menu.add_command(label="自动排列标签", accelerator="Ctrl+R", command=self._auto_arrange)
        edit_menu.add_command(label="清除全部自定义位置", command=self._clear_layout)
        menubar.add_cascade(label="编辑", menu=edit_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="配色面板", command=lambda: self._select_right_tab(0))
        view_menu.add_command(label="样式面板", command=lambda: self._select_right_tab(1))
        view_menu.add_command(label="导出面板", command=lambda: self._select_right_tab(2))
        view_menu.add_separator()
        view_menu.add_command(label="项目统计图", command=lambda: self._on_chart_tab("chart1"))
        view_menu.add_command(label="状态统计图", command=lambda: self._on_chart_tab("chart2"))
        menubar.add_cascade(label="视图", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="使用说明", accelerator="F1", command=self._show_help)
        help_menu.add_command(label="关于", command=self._show_about)
        menubar.add_cascade(label="帮助", menu=help_menu)
        self.root.config(menu=menubar)

    def _bind_shortcuts(self) -> None:
        bindings = {
            "<Control-o>": lambda _e: self._open_file(),
            "<Control-O>": lambda _e: self._open_file(),
            "<Control-s>": lambda _e: self._save_project(),
            "<Control-S>": lambda _e: self._save_project(),
            "<Control-e>": lambda _e: self._export_current(),
            "<Control-E>": lambda _e: self._export_current(),
            "<Control-z>": lambda _e: self._undo_layout(),
            "<Control-Z>": lambda _e: self._undo_layout(),
            "<Control-y>": lambda _e: self._redo_layout(),
            "<Control-Y>": lambda _e: self._redo_layout(),
            "<Control-r>": lambda _e: self._auto_arrange(),
            "<Control-R>": lambda _e: self._auto_arrange(),
            "<F1>": lambda _e: self._show_help(),
        }
        for sequence, handler in bindings.items():
            self.root.bind(sequence, handler)

    def _select_right_tab(self, index: int) -> None:
        self.right_tabs.select(index)
        self._on_right_tab(index)

    # ------------------------------------------------------------------
    # Bootstrap / session restore
    # ------------------------------------------------------------------

    def _bootstrap(self) -> None:
        candidate = Path(self.file_path) if self.file_path else None
        if candidate and candidate.is_file():
            if self.load_file(str(candidate), self.sheet_name or None, self.column_a or None, self.column_b or None, silent=True):
                return
        example = data_mod.find_default_example()
        if example:
            self.load_file(str(example), silent=True)
            return
        self._show_placeholder("请选择 Excel 文件开始")
        self.status.set_message("未找到示例数据，请打开一个 Excel 文件", "info")

    def load_file(
        self,
        path: str,
        sheet: str | None = None,
        column_a: str | None = None,
        column_b: str | None = None,
        *,
        silent: bool = False,
    ) -> bool:
        self._set_busy(True, "正在读取 Excel…")
        try:
            sheets = data_mod.list_sheets(path)
            chosen_sheet = sheet if sheet in sheets else (sheets[0] if sheets else "")
            sheet_data = data_mod.load_sheet(path, chosen_sheet)
            self.sheet_data = sheet_data
            self.file_path = str(Path(path))
            self.sheet_name = chosen_sheet
            self.sheet_var.set(chosen_sheet)
            self.sheet_combo.configure(values=sheets)
            self.file_var.set(_shorten(Path(path).name, 34))
            self.header_file.configure(text=_shorten(Path(path).name, 46))
            columns = [NO_COLUMN] + sheet_data.columns
            detected_a, detected_b = data_mod.detect_columns(sheet_data.columns)
            col_a = column_a if column_a in sheet_data.columns else detected_a
            col_b = column_b if column_b in sheet_data.columns else detected_b
            if col_a is None and self.column_a in sheet_data.columns:
                col_a = self.column_a
            if col_b is None and self.column_b in sheet_data.columns:
                col_b = self.column_b
            if col_a is None:
                col_a = sheet_data.columns[0] if sheet_data.columns else ""
            if col_b == col_a:
                col_b = None
            self.col_a_combo.configure(values=columns)
            self.col_b_combo.configure(values=columns)
            self.col_a_var.set(col_a or NO_COLUMN)
            self.col_b_var.set(col_b or NO_COLUMN)
            self.column_a = col_a or ""
            self.column_b = col_b or ""
            self.prefs.add_recent_file(path)
            self._refresh_counts()
            self._sync_chart_state_after_load()
            self._update_tables()
            self._render_current()
            self._rebuild_palette_gallery()
            total_rows = sheet_data.row_count
            self.status.set_message(
                f"已读取 {Path(path).name} · {chosen_sheet} · {total_rows} 行", "info"
            )
            self._update_status_stats()
            self._schedule_prefs_save()
            self._set_busy(False)
            return True
        except data_mod.DataError as exc:
            self._set_busy(False)
            if not silent:
                messagebox.showerror("读取失败", str(exc), parent=self.root)
            self.status.set_message("Excel 读取失败", "error")
            return False
        except Exception as exc:  # pragma: no cover - defensive
            self._set_busy(False)
            if not silent:
                messagebox.showerror("读取失败", str(exc), parent=self.root)
            self.status.set_message("Excel 读取失败", "error")
            return False

    def _sync_chart_state_after_load(self) -> None:
        # Keep the SW defaults for the classic columns; adapt for other workbooks.
        columns = {"chart1": self.column_a, "chart2": self.column_b}
        legacy_columns = {"chart1": "开发类别", "chart2": "状态"}
        factory_titles = {"chart1": "SW项目统计", "chart2": "SW项目状态统计"}
        for key in CHART_KEYS:
            state = self.chart_states[key]
            title = str(state.get("title") or "").strip()
            column = columns[key]
            if not column:
                continue
            if not title:
                state["title"] = f"{column}统计"
            elif title == factory_titles[key] and column != legacy_columns[key]:
                state["title"] = f"{column}统计"
        self._sync_title_entries()

    def _open_file(self) -> None:
        filename = filedialog.askopenfilename(
            parent=self.root,
            title="选择 Excel 文件",
            filetypes=data_mod.EXCEL_FILE_TYPES,
        )
        if filename:
            self.load_file(filename)

    def _on_sheet_changed(self, _event=None) -> None:
        if not self.sheet_data:
            return
        sheet = self.sheet_var.get()
        if sheet and sheet != self.sheet_data.sheet:
            self.load_file(str(self.sheet_data.path), sheet=sheet)

    # ------------------------------------------------------------------
    # Data / counts
    # ------------------------------------------------------------------

    def _refresh_counts(self) -> None:
        self.counts = {key: [] for key in CHART_KEYS}
        if self.sheet_data is None:
            return
        dataframe = self.sheet_data.dataframe
        for key, column in (("chart1", self.column_a), ("chart2", self.column_b)):
            if column and column in dataframe.columns:
                try:
                    self.counts[key] = data_mod.value_counts(dataframe, column)
                except data_mod.DataError:
                    self.counts[key] = []

    def _visible_counts(self) -> list[tuple[str, int]]:
        counts = self.counts.get(self.active_chart) or []
        state = self.chart_states[self.active_chart]
        return data_mod.sort_pairs(counts, str(state.get("sort_mode", "count_desc")))

    def _on_columns_changed(self, _event=None) -> None:
        if self._suppress or self.sheet_data is None:
            return
        self.column_a = "" if self.col_a_var.get() == NO_COLUMN else self.col_a_var.get()
        self.column_b = "" if self.col_b_var.get() == NO_COLUMN else self.col_b_var.get()
        self._refresh_counts()
        self._update_tables()
        self._render_current()
        self._rebuild_palette_gallery()
        self._rebuild_category_rows()
        self._update_status_stats()
        self._schedule_prefs_save()

    def _on_sort_changed(self, _event=None) -> None:
        mapping = {
            "数量从多到少": "count_desc",
            "数量从少到多": "count_asc",
            "按名称": "name",
        }
        mode = mapping.get(self.sort_var.get(), "count_desc")
        self.chart_states[self.active_chart]["sort_mode"] = mode
        self._update_tables()
        self._render_current()
        self._schedule_prefs_save()

    def _update_tables(self) -> None:
        for key, table in (("chart1", self.table1), ("chart2", self.table2)):
            counts = self.counts.get(key) or []
            total = sum(value for _label, value in counts) or 1
            sorted_counts = data_mod.sort_pairs(
                counts, str(self.chart_states[key].get("sort_mode", "count_desc"))
            )
            rows = [(label, value, value / total * 100.0) for label, value in sorted_counts]
            table.set_rows(rows)
            caption = getattr(table, "_caption_label", None)
            if caption is not None:
                if counts:
                    caption.configure(text=f"{len(counts)} 类")
                else:
                    caption.configure(text="未选择统计列")
        if getattr(self, "data_card", None) is not None and self.data_card.hint_label:
            has_rows = bool(self.counts["chart1"] or self.counts["chart2"])
            self.data_card.hint_label.configure(text="点击行定位标签" if has_rows else "")

    def _update_status_stats(self) -> None:
        parts = []
        if self.counts["chart1"]:
            parts.append(f"类别 {len(self.counts['chart1'])}")
        if self.counts["chart2"]:
            parts.append(f"状态 {len(self.counts['chart2'])}")
        self.status.set_stats(" · ".join(parts))

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _palette_for(self, state: dict, key: str | None = None) -> Palette:
        try:
            return palette_by_id(str(state.get("palette_id") or ""))
        except KeyError:
            chart_key = key or self.active_chart
            fallback_id = "legacy_project" if chart_key == "chart1" else "legacy_status"
            try:
                return palette_by_id(fallback_id)
            except KeyError:
                return PALETTES[0]

    def _ensure_label_contrast(self, color: str, background: str) -> str:
        """Darken/lighten an auto label colour until it is comfortably readable."""
        if contrast_ratio(color, background) >= LABEL_MIN_CONTRAST:
            return color
        target = "#0F172A" if luminance(background) >= 0.5 else "#FFFFFF"
        for step in range(1, 11):
            candidate = mix_colors(color, target, step / 10.0)
            if contrast_ratio(candidate, background) >= LABEL_MIN_CONTRAST:
                return candidate
        return target

    def _build_spec(self, key: str):
        state = self.chart_states[key]
        pairs = data_mod.sort_pairs(self.counts.get(key) or [], str(state.get("sort_mode", "count_desc")))
        labels = [label for label, _value in pairs]
        values = [value for _label, value in pairs]
        palette = self._palette_for(state)
        fill_colors = assign_colors(palette, labels, state.get("overrides") or {})
        background = self.style.background
        label_background = "#FFFFFF" if background == TRANSPARENT else background
        mode = str(state.get("label_mode", "auto"))
        single = str(state.get("label_single_color", "#334155"))
        label_colors = {}
        for label in labels:
            color = label_color(
                fill_colors.get(label, "#CCCCCC"),
                mode,
                single=single,
                background=label_background,
            )
            if mode == "auto":
                color = self._ensure_label_contrast(color, label_background)
            label_colors[label] = color
        style = self.style.copy()
        style.title = str(state.get("title", ""))
        style.subtitle = str(state.get("subtitle", ""))
        return build_spec(labels, values, style, fill_colors=fill_colors, label_colors=label_colors)

    def _render_current(self) -> None:
        self._render_after = None
        key = self.active_chart
        if not self.counts.get(key):
            self.chart = None
            self.auto_button.set_enabled(False)
            self.preview_hint.configure(text="")
            reason = "该图表未配置统计列" if self.sheet_data else "请选择 Excel 文件"
            self._show_placeholder(reason)
            self.layout_state.configure(text="无数据")
            self._update_layout_buttons()
            return
        try:
            spec = self._build_spec(key)
            self.chart = RoseChart(spec, self.figure, preview=True, preview_bg=W.PREVIEW_BG)
            offsets = self.chart_states[key].get("layout") or {}
            if offsets:
                self.chart.apply_layout_offsets(offsets)
        except Exception as exc:  # pragma: no cover - defensive
            self.chart = None
            self._show_placeholder(f"绘制失败：{exc}")
            self.status.set_message("绘制失败，请检查数据", "error")
            return
        self._hide_placeholder()
        self.auto_button.set_enabled(True)
        self.preview_hint.configure(text="拖动标签微调位置 · 双击标签复位")
        self._fit_preview()
        self.canvas.draw()
        self.chart.refresh_label_backplates()
        self.canvas.draw_idle()
        custom = bool(self.chart_states[key].get("layout"))
        self.layout_state.configure(text="布局：自定义" if custom else "布局：自动")
        self._update_layout_buttons()
        self._rebuild_category_rows()

    def _render_soon(self, delay: int = 60) -> None:
        if self._render_after is not None:
            try:
                self.root.after_cancel(self._render_after)
            except tk.TclError:
                pass
        self._render_after = self.root.after(delay, self._render_current)

    def _on_stage_configure(self, _event=None) -> None:
        if self._fit_after is not None:
            try:
                self.root.after_cancel(self._fit_after)
            except tk.TclError:
                pass
        self._fit_after = self.root.after(90, self._fit_preview)

    def _fit_preview(self) -> None:
        self._fit_after = None
        if self.canvas is None or self.preview_widget is None:
            return
        width = self.preview_stage.winfo_width()
        height = self.preview_stage.winfo_height()
        if width < 80 or height < 80:
            return
        pad = W.px(6)
        dpi = min((width - pad * 2) / 12.0, (height - pad * 2) / 8.0)
        dpi = max(36.0, min(160.0, dpi))
        if abs(dpi - self._dpi) < 0.4:
            return
        self._dpi = dpi
        self.figure.set_dpi(dpi)
        image_w = max(1, int(round(12 * dpi)))
        image_h = max(1, int(round(8 * dpi)))
        self.preview_widget.place(
            relx=0.5, rely=0.5, anchor="center", width=image_w, height=image_h
        )
        self.canvas.draw_idle()

    def _show_placeholder(self, text: str) -> None:
        self.preview_hint.configure(text="")
        if self.sheet_data is None:
            self.empty_title.configure(text="还没有可预览的数据")
            self.empty_message.configure(text="打开 Excel 后会自动生成两张玫瑰图")
            self.empty_hint.configure(text="图表生成后，可直接拖动数据标签调整位置")
            if not self._empty_button_visible:
                self.empty_open_button.pack()
                self._empty_button_visible = True
        else:
            self.empty_title.configure(text="这张图暂时没有数据")
            self.empty_message.configure(text=text)
            self.empty_hint.configure(text="在左侧「统计列」中换一列，或切换到另一张图")
            if self._empty_button_visible:
                self.empty_open_button.pack_forget()
                self._empty_button_visible = False
        self.empty_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.empty_overlay.lift()

    def _hide_placeholder(self) -> None:
        self.empty_overlay.place_forget()

    def _highlight_label(self, key: str, label: str) -> None:
        def apply() -> None:
            if self.chart is None:
                return
            handle = self.chart.handles.get(label)
            if handle is None:
                return
            self.chart.set_hover(handle)
            self._hover_label = label
            self.canvas.draw_idle()
            self.status.set_message(f"已定位「{label}」", "info")

        if key != self.active_chart:
            self._on_chart_tab(key)
            self.root.after(180, apply)
        else:
            apply()

    # ------------------------------------------------------------------
    # Label interaction
    # ------------------------------------------------------------------

    def _set_cursor(self, cursor: str) -> None:
        if self.preview_widget is not None:
            try:
                self.preview_widget.configure(cursor=cursor)
            except tk.TclError:
                pass

    def _on_canvas_press(self, event) -> None:
        if self.chart is None or event.button != 1:
            return
        if self.canvas is None:
            return
        renderer = self.canvas.get_renderer()
        handle = self.chart.hit_test(event.x, event.y, renderer)
        if handle is None:
            return
        if getattr(event, "dblclick", False):
            self._push_undo()
            self.chart.reset_label(handle.label)
            self._commit_layout()
            self._set_cursor("hand2")
            self.status.set_message(f"已恢复“{handle.label}”的自动位置", "info")
            self.canvas.draw_idle()
            return
        inverse = self.chart.axis.transData.inverted()
        data_x, data_y = inverse.transform((event.x, event.y))
        self._drag = {
            "label": handle.label,
            "x0": handle.line_end_x,
            "y0": handle.y,
            "data_x0": data_x,
            "data_y0": data_y,
            "base_layout": copy.deepcopy(self.chart.layout_offsets()),
            "moved": False,
        }
        self._hover_label = handle.label
        self.chart.set_hover(handle)
        self._set_cursor("fleur")
        self.status.set_message(f"拖动“{handle.label}”调整位置，松开鼠标完成", "info")
        self.canvas.draw_idle()

    def _on_canvas_motion(self, event) -> None:
        if self.chart is None or self.canvas is None:
            return
        drag = self._drag
        if drag is not None:
            try:
                data_x, data_y = self.chart.axis.transData.inverted().transform((event.x, event.y))
            except Exception:
                return
            new_y = drag["y0"] + (data_y - drag["data_y0"])
            new_x = drag["x0"] + (data_x - drag["data_x0"])
            self.chart.set_label_position(drag["label"], y=new_y, line_end_x=new_x)
            if abs(new_y - drag["y0"]) > 0.004 or abs(new_x - drag["x0"]) > 0.004:
                drag["moved"] = True
            self.canvas.draw_idle()
            return
        renderer = self.canvas.get_renderer()
        handle = self.chart.hit_test(event.x, event.y, renderer)
        label = handle.label if handle else None
        if label != self._hover_label:
            self._hover_label = label
            self.chart.set_hover(handle)
            self._set_cursor("hand2" if handle else "arrow")
            self.canvas.draw_idle()
            if handle:
                self.status.set_message(f"“{handle.label}”：按住拖动可调整标签位置", "info")

    def _on_canvas_release(self, _event) -> None:
        if self._drag is None:
            return
        drag = self._drag
        self._drag = None
        self._set_cursor("hand2" if self._hover_label else "arrow")
        if drag.get("moved"):
            self._undo[self.active_chart].append(drag["base_layout"])
            if len(self._undo[self.active_chart]) > 80:
                self._undo[self.active_chart].pop(0)
            self._redo[self.active_chart].clear()
            if self.chart is not None and self.chart.fit_labels_inside():
                self.canvas.draw_idle()
            self._commit_layout()
            self.status.set_message(
                f"已调整“{drag['label']}”的位置 · Ctrl+Z 可撤销", "info"
            )
        if self.chart is not None:
            handle = self.chart.handles.get(drag["label"]) if drag else None
            self.chart.set_hover(handle if self._hover_label else None)
        if self.canvas is not None:
            self.canvas.draw_idle()

    def _on_canvas_leave(self, _event) -> None:
        self._hover_label = None
        if self.chart is not None:
            self.chart.set_hover(None)
        if self.canvas is not None:
            self.canvas.draw_idle()

    def _commit_layout(self) -> None:
        if self.chart is None:
            return
        offsets = {
            label: [round(offset[0], 5), round(offset[1], 5)]
            for label, offset in self.chart.layout_offsets().items()
        }
        self.chart_states[self.active_chart]["layout"] = offsets
        self.layout_state.configure(text="布局：自定义" if offsets else "布局：自动")
        self._update_layout_buttons()
        self._schedule_prefs_save()

    def _push_undo(self, layout: dict | None = None) -> None:
        current = copy.deepcopy(layout if layout is not None else (self.chart_states[self.active_chart].get("layout") or {}))
        self._undo[self.active_chart].append(current)
        if len(self._undo[self.active_chart]) > 80:
            self._undo[self.active_chart].pop(0)
        self._redo[self.active_chart].clear()

    def _apply_layout(self, offsets: dict) -> None:
        self.chart_states[self.active_chart]["layout"] = copy.deepcopy(offsets)
        if self.chart is not None:
            self.chart.apply_layout_offsets(offsets)
            self.chart.refresh_label_backplates()
            self.canvas.draw_idle()
        self.layout_state.configure(text="布局：自定义" if offsets else "布局：自动")
        self._update_layout_buttons()
        self._schedule_prefs_save()

    def _undo_layout(self) -> None:
        stack = self._undo[self.active_chart]
        if not stack:
            self.status.set_message("没有可撤销的标签调整", "info")
            return
        current = copy.deepcopy(self.chart_states[self.active_chart].get("layout") or {})
        previous = stack.pop()
        self._redo[self.active_chart].append(current)
        self._apply_layout(previous)
        self.status.set_message("已撤销标签调整", "info")

    def _redo_layout(self) -> None:
        stack = self._redo[self.active_chart]
        if not stack:
            self.status.set_message("没有可重做的标签调整", "info")
            return
        current = copy.deepcopy(self.chart_states[self.active_chart].get("layout") or {})
        target = stack.pop()
        self._undo[self.active_chart].append(current)
        self._apply_layout(target)
        self.status.set_message("已重做标签调整", "info")

    def _auto_arrange(self) -> None:
        if self.chart is None:
            return
        self._push_undo()
        self.chart.reset_all_labels()
        self._commit_layout()
        self.canvas.draw_idle()
        self.status.set_message("已恢复自动排列", "info")

    def _clear_layout(self) -> None:
        self._push_undo()
        self._apply_layout({})
        if self.chart is not None:
            self.chart.reset_all_labels()
            self.canvas.draw_idle()
        self.status.set_message("已清除全部自定义标签位置", "info")

    def _update_layout_buttons(self) -> None:
        has_undo = bool(self._undo[self.active_chart])
        has_redo = bool(self._redo[self.active_chart])
        try:
            self.undo_button.set_enabled(has_undo)
            self.redo_button.set_enabled(has_redo)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Chart tab / palettes / style handlers
    # ------------------------------------------------------------------

    def _on_chart_tab(self, key: str) -> None:
        if key not in CHART_KEYS or key == self.active_chart:
            return
        if self._drag is not None:
            self._drag = None
        self.active_chart = key
        self.chart_tabs.set_value(key)
        self._suppress = True
        try:
            self._sync_all_controls(for_chart=True)
        finally:
            self._suppress = False
        self._render_current()
        self._rebuild_palette_gallery()
        self._rebuild_category_rows()
        self._schedule_prefs_save()

    def _apply_palette(self, palette_id: str) -> None:
        state = self.chart_states[self.active_chart]
        if state.get("palette_id") == palette_id:
            return
        state["palette_id"] = palette_id
        self._rebuild_palette_gallery()
        self._render_current()
        try:
            palette = palette_by_id(palette_id)
            self.status.set_message(f"已应用配色方案：{palette.name}", "info")
        except KeyError:
            pass
        self._schedule_prefs_save()

    def _on_label_mode(self, mode: str) -> None:
        self.chart_states[self.active_chart]["label_mode"] = mode
        self._rebuild_category_rows()
        self._render_current()
        self._schedule_prefs_save()

    def _pick_single_label_color(self) -> None:
        state = self.chart_states[self.active_chart]
        initial = str(state.get("label_single_color", "#334155"))
        _rgb, chosen = colorchooser.askcolor(color=initial, parent=self.root, title="选择统一标签颜色")
        if chosen:
            state["label_single_color"] = chosen
            self.label_color_button.set_color(chosen)
            if state.get("label_mode") != "single":
                state["label_mode"] = "single"
                self.label_mode_control.set_value("single")
            self._render_current()
            self._schedule_prefs_save()

    def _pick_category_color(self, label: str) -> None:
        state = self.chart_states[self.active_chart]
        counts = dict(self.counts.get(self.active_chart) or [])
        palette = self._palette_for(state)
        current = assign_colors(palette, [label], state.get("overrides") or {}).get(label, "#CCCCCC")
        _rgb, chosen = colorchooser.askcolor(
            color=current, parent=self.root, title=f"选择“{label}”的颜色"
        )
        if not chosen:
            return
        state.setdefault("overrides", {})[label] = chosen
        self._rebuild_category_rows()
        self._render_current()
        self.status.set_message(f"已更新“{label}”的颜色", "info")
        self._schedule_prefs_save()

    def _reset_category_color(self, label: str) -> None:
        state = self.chart_states[self.active_chart]
        overrides = state.setdefault("overrides", {})
        if overrides.pop(label, None) is not None:
            self._rebuild_category_rows()
            self._render_current()
            self.status.set_message(f"已恢复“{label}”的配色方案颜色", "info")
            self._schedule_prefs_save()

    def _on_style_slider(self, field: str, value: float) -> None:
        setattr(self.style, field, value)
        self._render_soon(40)
        self._schedule_prefs_save()

    def _on_check(self, field: str, variable: tk.BooleanVar) -> None:
        setattr(self.style, field, bool(variable.get()))
        self._render_soon(30)
        self._schedule_prefs_save()

    def _on_suffix_changed(self) -> None:
        if self._suppress:
            return
        self.style.value_suffix = self.suffix_var.get()
        self._render_soon(220)
        self._schedule_prefs_save()

    def _on_decimals_changed(self) -> None:
        if self._suppress:
            return
        try:
            value = int(self.decimals_var.get())
        except (tk.TclError, ValueError):
            return
        self.style.percent_decimals = max(0, min(4, value))
        self._render_soon(30)
        self._schedule_prefs_save()

    def _on_center_changed(self) -> None:
        if self._suppress:
            return
        self.style.center_text = self.center_var.get()
        self._render_soon(240)
        self._schedule_prefs_save()

    def _on_font_changed(self) -> None:
        family = self.font_var.get()
        if not family:
            return
        self.style.font_family = family
        configure_chinese_font(family)
        self._render_soon(30)
        self._schedule_prefs_save()

    def _on_background_mode(self, mode: str) -> None:
        if mode == "transparent":
            self.style.background = TRANSPARENT
        elif mode == "#FFFFFF":
            self.style.background = "#FFFFFF"
        else:
            current = self.background_color_button.color
            self.style.background = current
        self._render_soon(30)
        self._schedule_prefs_save()

    def _pick_background_color(self) -> None:
        current = self.background_color_button.color
        _rgb, chosen = colorchooser.askcolor(color=current, parent=self.root, title="选择画布背景色")
        if chosen:
            self.background_color_button.set_color(chosen)
            self.style.background = chosen
            self.background_control.set_value("custom")
            self._render_soon(30)
            self._schedule_prefs_save()

    def _on_title_changed(self) -> None:
        if self._suppress:
            return
        if self._title_after is not None:
            try:
                self.root.after_cancel(self._title_after)
            except tk.TclError:
                pass
        self._title_after = self.root.after(220, self._apply_title_change)

    def _apply_title_change(self) -> None:
        self._title_after = None
        state = self.chart_states[self.active_chart]
        state["title"] = self.title_var.get()
        state["subtitle"] = self.subtitle_var.get()
        self._render_soon(20)
        self._schedule_prefs_save()

    def _sync_title_entries(self) -> None:
        state = self.chart_states[self.active_chart]
        self._suppress = True
        try:
            self.title_var.set(str(state.get("title", "")))
            self.subtitle_var.set(str(state.get("subtitle", "")))
            self.title_entry.icursor("end")
        finally:
            self._suppress = False

    # -- export handlers ------------------------------------------------

    def _on_format_changed(self, fmt: str) -> None:
        self.export_state["format"] = fmt
        self._schedule_prefs_save()

    def _on_size_preset_changed(self) -> None:
        preset = SIZE_PRESETS.get(self.size_var.get())
        if preset is not None:
            width, height = preset
            self.width_var.set(str(width))
            self.height_var.set(str(height))
        self._sync_dimension_state()
        self._on_export_option_changed()

    def _sync_dimension_state(self) -> None:
        custom = self.size_var.get() == "自定义"
        for holder in (getattr(self, "width_spin", None), getattr(self, "height_spin", None)):
            spin = getattr(holder, "_spin", None)
            if spin is None:
                continue
            try:
                spin.configure(state="normal" if custom else "disabled")
            except tk.TclError:
                pass
        if getattr(self, "dim_hint", None) is not None:
            self.dim_hint.configure(
                text=(
                    "按像素输入宽度与高度"
                    if custom
                    else "尺寸由上方预设决定，选择「自定义」后可修改"
                )
            )

    def _on_export_option_changed(self) -> None:
        if self._suppress:
            return
        self.export_state["format"] = self.format_control.get()
        self.export_state["width"] = self._safe_int(self.width_var.get(), 1200, 100, 8000)
        self.export_state["height"] = self._safe_int(self.height_var.get(), 800, 100, 8000)
        try:
            dpi = int(str(self.dpi_var.get()).strip())
        except (tk.TclError, ValueError):
            dpi = 100
        self.export_state["dpi"] = max(50, min(600, dpi))
        self.export_state["transparent"] = bool(self.transparent_var.get())
        self.export_state["filename"] = self.filename_var.get() or "{title}"
        self.export_state["output_dir"] = self.output_dir_var.get()
        self.export_state["preset"] = self.size_var.get()
        self._schedule_prefs_save()

    @staticmethod
    def _safe_int(raw: str, fallback: int, minimum: int, maximum: int) -> int:
        try:
            value = int(float(raw))
        except (TypeError, ValueError):
            return fallback
        return max(minimum, min(maximum, value))

    def _choose_output_dir(self) -> None:
        directory = filedialog.askdirectory(
            parent=self.root,
            title="选择输出目录",
            initialdir=self.output_dir_var.get() or str(data_mod.DEFAULT_OUTPUT_DIR),
        )
        if directory:
            self.output_dir_var.set(directory)
            self.export_state["output_dir"] = directory
            self._schedule_prefs_save()

    def _open_output_dir(self) -> None:
        directory = Path(self.output_dir_var.get() or data_mod.DEFAULT_OUTPUT_DIR)
        try:
            directory.mkdir(parents=True, exist_ok=True)
            import os

            if os.name == "nt":
                os.startfile(directory)  # type: ignore[attr-defined]
            else:
                import subprocess

                subprocess.Popen(["xdg-open", str(directory)])
        except Exception as exc:
            messagebox.showerror("无法打开目录", str(exc), parent=self.root)

    def _export_targets(self, all_charts: bool) -> list[tuple[str, str]]:
        targets: list[tuple[str, str]] = []
        for index, key in enumerate(CHART_KEYS):
            if not all_charts and key != self.active_chart:
                continue
            if not self.counts.get(key):
                continue
            targets.append((key, CHART_LABELS[key]))
        return targets

    def _copy_current_image(self) -> None:
        key = self.active_chart
        if not self.counts.get(key):
            messagebox.showwarning("暂无可复制内容", "当前图表没有数据。", parent=self.root)
            return
        self._on_export_option_changed()
        width = int(self.export_state.get("width", 1200))
        height = int(self.export_state.get("height", 800))
        dpi = int(self.export_state.get("dpi", 100))
        transparent = bool(self.export_state.get("transparent", True))
        self._set_busy(True, "正在复制到剪贴板…")
        try:
            import io

            from PIL import Image

            spec = self._build_spec(key)
            data = render_bytes(
                spec,
                width=width,
                height=height,
                dpi=dpi,
                transparent=transparent,
                fmt="png",
                layout=self.chart_states[key].get("layout") or {},
            )
            image = Image.open(io.BytesIO(data)).convert("RGBA")
            self._copy_image_to_clipboard(image)
        except Exception as exc:  # pragma: no cover - platform dependent
            self._set_busy(False)
            messagebox.showerror("复制失败", str(exc), parent=self.root)
            self.status.set_message("复制到剪贴板失败", "error")
            return
        self._set_busy(False)
        title = str(self.chart_states[key].get("title") or CHART_LABELS[key])
        self.status.set_message(f"已复制「{title}」到剪贴板，可直接粘贴到 PPT / Word", "info")

    @staticmethod
    def _copy_image_to_clipboard(image) -> None:
        import ctypes
        import io

        buffer = io.BytesIO()
        image.convert("RGBA").save(buffer, "BMP")
        data = buffer.getvalue()[14:]  # strip BITMAPFILEHEADER, keep BITMAPINFO + pixels
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
        user32.OpenClipboard.argtypes = [ctypes.c_void_p]
        user32.SetClipboardData.restype = ctypes.c_void_p
        user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]

        GMEM_MOVEABLE = 0x0002
        CF_DIB = 8
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            raise OSError("无法分配剪贴板内存")
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            kernel32.GlobalFree(handle)
            raise OSError("无法锁定剪贴板内存")
        try:
            ctypes.memmove(ctypes.c_void_p(pointer), data, len(data))
        finally:
            kernel32.GlobalUnlock(handle)
        if not user32.OpenClipboard(None):
            kernel32.GlobalFree(handle)
            raise OSError("剪贴板被其他程序占用")
        try:
            user32.EmptyClipboard()
            if not user32.SetClipboardData(CF_DIB, handle):
                kernel32.GlobalFree(handle)
                raise OSError("无法写入剪贴板")
        finally:
            user32.CloseClipboard()

    def _export_current(self) -> None:
        self._export(all_charts=False)

    def _export_all(self) -> None:
        self._export(all_charts=True)

    def _export(self, *, all_charts: bool) -> None:
        self._on_export_option_changed()
        targets = self._export_targets(all_charts)
        if not targets:
            messagebox.showwarning("暂无可导出内容", "当前没有可导出的图表数据。", parent=self.root)
            return
        fmt = str(self.export_state.get("format", "png")).lower()
        if fmt not in FORMAT_LABELS:
            fmt = "png"
        width = int(self.export_state.get("width", 1200))
        height = int(self.export_state.get("height", 800))
        dpi = int(self.export_state.get("dpi", 100))
        transparent = bool(self.export_state.get("transparent", True))
        output_dir = Path(self.output_dir_var.get() or data_mod.DEFAULT_OUTPUT_DIR)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("无法创建输出目录", str(exc), parent=self.root)
            return
        template = self.filename_var.get() or "{title}"
        self._set_busy(True, "正在导出图片…")
        exported: list[Path] = []
        try:
            for index, (key, fallback_title) in enumerate(targets):
                state = self.chart_states[key]
                title = str(state.get("title") or fallback_title)
                filename = (
                    template.replace("{title}", title)
                    .replace("{sheet}", self.sheet_name or "sheet")
                    .replace("{date}", datetime.date.today().isoformat())
                    .replace("{index}", str(index + 1))
                )
                filename = _sanitize_filename(filename)
                suffix = f".{fmt}"
                if not filename.lower().endswith(suffix):
                    filename += suffix
                target = output_dir / filename
                spec = self._build_spec(key)
                from .chart import export_chart

                export_chart(
                    spec,
                    target,
                    width=width,
                    height=height,
                    dpi=dpi,
                    transparent=transparent,
                    fmt=fmt,
                    layout=self.chart_states[key].get("layout") or {},
                )
                exported.append(target)
        except Exception as exc:  # pragma: no cover - defensive
            self._set_busy(False)
            messagebox.showerror("导出失败", str(exc), parent=self.root)
            self.status.set_message("导出失败", "error")
            return
        self._set_busy(False)
        names = "\n".join(str(path) for path in exported)
        self.status.set_message(f"已导出 {len(exported)} 张图片到 {output_dir}", "info")
        messagebox.showinfo(
            "导出完成",
            f"已生成 {len(exported)} 个文件：\n\n{names}",
            parent=self.root,
        )

    # ------------------------------------------------------------------
    # Project save / load
    # ------------------------------------------------------------------

    def _project_snapshot(self) -> dict:
        return {
            "file": self.file_path,
            "sheet": self.sheet_name,
            "column_a": self.column_a,
            "column_b": self.column_b,
            "mode": "both",
            "active": self.active_chart,
            "charts": copy.deepcopy(self.chart_states),
            "style": asdict(self.style),
            "export": copy.deepcopy(self.export_state),
        }

    def _save_project(self) -> None:
        if not self.file_path:
            messagebox.showinfo("还没有数据", "请先打开一个 Excel 文件。", parent=self.root)
            return
        target = Path(self.file_path).with_suffix(prefs_mod.PROJECT_SUFFIX)
        try:
            saved = prefs_mod.save_project(target, self._project_snapshot())
        except OSError as exc:
            messagebox.showerror("保存失败", str(exc), parent=self.root)
            return
        self.status.set_message(f"项目已保存：{saved.name}", "info")

    def _save_project_as(self) -> None:
        target = filedialog.asksaveasfilename(
            parent=self.root,
            title="保存项目",
            defaultextension=prefs_mod.PROJECT_SUFFIX,
            filetypes=[("玫瑰图项目", f"*{prefs_mod.PROJECT_SUFFIX}")],
            initialfile="rosechart_project" + prefs_mod.PROJECT_SUFFIX,
        )
        if not target:
            return
        try:
            saved = prefs_mod.save_project(target, self._project_snapshot())
        except OSError as exc:
            messagebox.showerror("保存失败", str(exc), parent=self.root)
            return
        self.status.set_message(f"项目已保存：{saved.name}", "info")

    def _open_project(self) -> None:
        target = filedialog.askopenfilename(
            parent=self.root,
            title="打开项目",
            filetypes=[("玫瑰图项目", f"*{prefs_mod.PROJECT_SUFFIX}"), ("所有文件", "*.*")],
        )
        if not target:
            return
        state = prefs_mod.load_project(target)
        if not state:
            messagebox.showerror("无法打开", "文件不是有效的玫瑰图项目。", parent=self.root)
            return
        for key in CHART_KEYS:
            merged = prefs_mod.default_chart_state(key)
            merged.update(state.get("charts", {}).get(key, {}) or {})
            merged.setdefault("layout", {})
            merged.setdefault("overrides", {})
            self.chart_states[key] = merged
        self.style = prefs_mod.style_from_dict(state.get("style"))
        self.export_state = prefs_mod.default_project_state()["export"]
        self.export_state.update(state.get("export", {}) or {})
        self.active_chart = state.get("active") if state.get("active") in CHART_KEYS else "chart1"
        file_path = str(state.get("file") or "")
        self._sync_all_controls()
        if file_path and Path(file_path).is_file():
            self.load_file(
                file_path,
                state.get("sheet") or None,
                state.get("column_a") or None,
                state.get("column_b") or None,
            )
        else:
            self.status.set_message("项目已打开，但数据文件不存在，请重新选择 Excel", "error")
            self._render_current()
        self._rebuild_palette_gallery()
        self.status.set_message(f"已打开项目：{Path(target).name}", "info")

    # ------------------------------------------------------------------
    # UI sync
    # ------------------------------------------------------------------

    def _sync_all_controls(self, *, for_chart: bool = False) -> None:
        self._suppress = True
        try:
            self.chart_tabs.set_value(self.active_chart)
            state = self.chart_states[self.active_chart]
            self._sync_title_entries()
            self.label_mode_control.set_value(str(state.get("label_mode", "auto")))
            self.label_color_button.set_color(str(state.get("label_single_color", "#334155")))
            sort_mapping = {"count_desc": "数量从多到少", "count_asc": "数量从少到多", "name": "按名称"}
            self.sort_var.set(sort_mapping.get(str(state.get("sort_mode", "count_desc")), "数量从多到少"))
            # style controls
            for field, row in self._style_rows.items():
                row.set_value(float(getattr(self.style, field)))
            self.show_name_var.set(bool(self.style.show_name))
            self.show_value_var.set(bool(self.style.show_value))
            self.show_percent_var.set(bool(self.style.show_percent))
            self.suffix_var.set(self.style.value_suffix)
            self.decimals_var.set(str(int(self.style.percent_decimals)))
            self.center_var.set(self.style.center_text)
            families = list(self.font_combo["values"])
            if self.style.font_family in families:
                self.font_var.set(self.style.font_family)
            if self.style.background == TRANSPARENT:
                self.background_control.set_value("transparent")
            elif self.style.background == "#FFFFFF":
                self.background_control.set_value("#FFFFFF")
            else:
                self.background_control.set_value("custom")
                self.background_color_button.set_color(self.style.background)
            # export controls
            self.format_control.set_value(str(self.export_state.get("format", "png")).lower())
            self.size_var.set(self._preset_name_for(self.export_state))
            self.width_var.set(str(self.export_state.get("width", 1200)))
            self.height_var.set(str(self.export_state.get("height", 800)))
            self.dpi_var.set(str(int(self.export_state.get("dpi", 100))))
            self.transparent_var.set(bool(self.export_state.get("transparent", True)))
            self.filename_var.set(str(self.export_state.get("filename", "{title}")))
            self.output_dir_var.set(str(self.export_state.get("output_dir", data_mod.DEFAULT_OUTPUT_DIR)))
            self._sync_dimension_state()
        finally:
            self._suppress = False
        if for_chart:
            self._rebuild_category_rows()

    def _schedule_prefs_save(self) -> None:
        if self._prefs_after is not None:
            try:
                self.root.after_cancel(self._prefs_after)
            except tk.TclError:
                pass
        self._prefs_after = self.root.after(1200, self._save_prefs)

    def _save_prefs(self) -> None:
        self._prefs_after = None
        self.prefs.data["project"] = self._project_snapshot()
        try:
            self.prefs.set_window_geometry(self.root.geometry(), self.root.state() == "zoomed")
        except tk.TclError:
            pass
        self.prefs.save()

    def _on_close(self) -> None:
        self._save_prefs()
        self.root.destroy()

    # ------------------------------------------------------------------
    # Busy / help
    # ------------------------------------------------------------------

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = busy
        try:
            self.root.configure(cursor="watch" if busy else "")
        except tk.TclError:
            pass
        if busy and message:
            self.status.set_message(message, "busy")
        self.root.update_idletasks()

    def _show_help(self) -> None:
        messagebox.showinfo(
            "使用说明",
            "1. 点击“打开 Excel”，选择工作表和统计列。\n"
            "2. 中间为实时预览，右侧“配色”“样式”“导出”三个面板可随时调整。\n"
            "3. 鼠标拖动图中的数据标签可以微调位置，双击标签恢复自动位置。\n"
            "4. Ctrl+Z / Ctrl+Y 撤销重做，Ctrl+R 恢复自动排列。\n"
            "5. “导出”面板可选择尺寸、DPI、透明背景，并一次导出两张图。\n"
            "6. 文件菜单可保存/打开 .roseproj 项目，保留配色与标签位置。",
            parent=self.root,
        )

    def _show_about(self) -> None:
        messagebox.showinfo(
            f"关于 {APP_TITLE}",
            f"{APP_TITLE} · {APP_SUBTITLE}\n版本 {__version__}\n\n"
            "从 Excel 直接生成南丁格尔玫瑰图，支持色系推荐、"
            "标签拖拽布局与高清导出。\n\n"
            "便携运行：无需安装 Python，双击 RoseChart.exe 即可。",
            parent=self.root,
        )


def run() -> None:
    import matplotlib

    matplotlib.use("TkAgg")
    root = tk.Tk()
    RoseChartApp(root)
    root.mainloop()

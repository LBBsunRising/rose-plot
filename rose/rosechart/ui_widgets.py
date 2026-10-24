"""Tk widget kit for RoseChart Studio.

Design language: a calm data workbench. The chart is the only loud element;
the chrome is built from cool neutrals, hairline panel borders, a single teal
accent and a compact but readable type scale.
"""
from __future__ import annotations

import math
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
from typing import Callable, Iterable, Sequence

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

BG = "#F2F5F9"            # application canvas
PANEL = "#FFFFFF"         # inspector surface
PANEL_ALT = "#F7FAFC"     # inset surface
PANEL_SOFT = "#F1F5F9"    # segmented control base
PANEL_HOVER = "#E9EFF6"   # hovered neutral
BORDER = "#E3E9F1"        # hairline
BORDER_STRONG = "#D2DCE7" # hover / active hairline
TEXT = "#182230"          # primary ink
TEXT_MUTED = "#5C6B7F"    # secondary ink (>= 5.5:1 on white)
TEXT_FAINT = "#8494A7"    # decorative only
PRIMARY = "#0F766E"       # brand teal (from app icon / chart accent)
PRIMARY_DARK = "#0B5D57"
PRIMARY_SOFT = "#E7F3F1"
PRIMARY_SOFT_HOVER = "#D9EBE8"
ACCENT = "#0891B2"
ACCENT_SOFT = "#E0F2FE"
SUCCESS = "#16A34A"
WARNING = "#B45309"
DANGER = "#C0392B"
DANGER_SOFT = "#FBEAE8"
PREVIEW_BG = "#EDF2F8"    # canvas behind the chart
SURFACE_INSET = "#F8FAFC"
SHADOW = "#DCE4EE"

FONT_FAMILY = "Microsoft YaHei UI"

SCALE = 1.0


def set_scale(value: float) -> None:
    global SCALE
    SCALE = max(0.75, min(2.5, float(value)))


def px(value: float) -> int:
    return int(round(value * SCALE))


def setup_fonts(root: tk.Misc) -> str:
    """Pick a Chinese-capable UI font and set Tk point scaling."""
    global FONT_FAMILY
    try:
        dpi = float(root.winfo_fpixels("1i"))
    except Exception:
        dpi = 96.0
    try:
        root.tk.call("tk", "scaling", dpi / 72.0)
    except Exception:
        pass
    set_scale(dpi / 96.0)
    available = set(tkfont.families(root))
    for candidate in (
        "Microsoft YaHei UI",
        "Microsoft YaHei",
        "SimHei",
        "PingFang SC",
        "Noto Sans CJK SC",
    ):
        if candidate in available:
            FONT_FAMILY = candidate
            break
    return FONT_FAMILY


def font(size: float = 10.5, weight: str = "normal") -> tuple[str, int, str]:
    return (FONT_FAMILY, int(round(size)), weight)


# Type scale (points at 96 DPI; Tk scaling applies on top)
SIZE_MICRO = 9.5      # palette tags / non-essential metadata
SIZE_CAPTION = 10.0   # hints
SIZE_BODY = 10.5      # default interface text
SIZE_SECTION = 11.5   # section titles
SIZE_TITLE = 14.0     # app title
SIZE_DISPLAY = 13.0   # empty-state title


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(char * 2 for char in value)
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def rgb_to_hex(rgb: Sequence[int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(max(0, min(255, int(c))) for c in rgb[:3]))


def mix(first: str, second: str, amount: float) -> str:
    amount = max(0.0, min(1.0, float(amount)))
    a = hex_to_rgb(first)
    b = hex_to_rgb(second)
    return rgb_to_hex([a[i] + (b[i] - a[i]) * amount for i in range(3)])


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------


def round_rect_points(
    x0: float, y0: float, x1: float, y1: float, radius: float, steps: int = 6
) -> list[float]:
    radius = max(0.0, min(radius, (x1 - x0) / 2.0, (y1 - y0) / 2.0))
    points: list[float] = []
    corners = (
        (x1 - radius, y0 + radius, -90.0, 0.0),
        (x1 - radius, y1 - radius, 0.0, 90.0),
        (x0 + radius, y1 - radius, 90.0, 180.0),
        (x0 + radius, y0 + radius, 180.0, 270.0),
    )
    for cx, cy, start, end in corners:
        for index in range(steps + 1):
            angle = math.radians(start + (end - start) * index / steps)
            points.extend((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def round_rect(
    canvas: tk.Canvas, x0: float, y0: float, x1: float, y1: float, radius: float, **kwargs
):
    points = round_rect_points(x0, y0, x1, y1, radius)
    return canvas.create_polygon(points, smooth=False, **kwargs)


def truncated_text(text: str, max_width: float, text_font: tuple, root: tk.Misc) -> str:
    measure = tkfont.Font(root=root, font=text_font).measure
    if measure(text) <= max_width:
        return text
    ellipsis = "…"
    trimmed = text
    while trimmed and measure(trimmed + ellipsis) > max_width:
        trimmed = trimmed[:-1]
    return (trimmed + ellipsis) if trimmed else ellipsis


def parent_background(widget: tk.Misc, fallback: str = PANEL) -> str:
    try:
        return str(widget.cget("bg"))
    except (tk.TclError, AttributeError):
        return fallback


# ---------------------------------------------------------------------------
# ttk theme
# ---------------------------------------------------------------------------


def init_styles(root: tk.Misc) -> None:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        return

    style.configure(".", font=font(SIZE_BODY), background=BG, foreground=TEXT)
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=TEXT, font=font(SIZE_BODY))
    style.configure("Card.TFrame", background=PANEL)
    style.configure("Card.TLabel", background=PANEL, foreground=TEXT, font=font(SIZE_BODY))
    style.configure("Muted.TLabel", background=BG, foreground=TEXT_MUTED, font=font(SIZE_CAPTION))
    style.configure("CardMuted.TLabel", background=PANEL, foreground=TEXT_MUTED, font=font(SIZE_CAPTION))

    style.configure(
        "TEntry",
        fieldbackground=PANEL,
        background=PANEL,
        foreground=TEXT,
        bordercolor=BORDER_STRONG,
        lightcolor=PANEL,
        darkcolor=PANEL,
        insertcolor=TEXT,
        relief="flat",
        padding=(px(9), px(7)),
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", PRIMARY), ("hover", BORDER_STRONG)],
        lightcolor=[("focus", PANEL)],
        darkcolor=[("focus", PANEL)],
        fieldbackground=[("disabled", PANEL_ALT), ("readonly", PANEL_ALT)],
        foreground=[("disabled", TEXT_FAINT)],
    )

    style.configure(
        "TCombobox",
        fieldbackground=PANEL,
        background=PANEL,
        foreground=TEXT,
        arrowcolor=TEXT_MUTED,
        bordercolor=BORDER_STRONG,
        lightcolor=PANEL,
        darkcolor=PANEL,
        padding=(px(9), px(7)),
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", PANEL), ("disabled", PANEL_ALT)],
        selectbackground=[("readonly", PANEL), ("!readonly", PRIMARY_SOFT)],
        selectforeground=[("readonly", TEXT), ("!readonly", TEXT)],
        bordercolor=[("focus", PRIMARY), ("hover", BORDER_STRONG)],
        arrowcolor=[("disabled", TEXT_FAINT)],
    )
    root.option_add("*TCombobox*Listbox.background", PANEL)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", PRIMARY_SOFT)
    root.option_add("*TCombobox*Listbox.selectForeground", PRIMARY_DARK)
    root.option_add("*TCombobox*Listbox.font", font(SIZE_BODY))
    root.option_add("*TCombobox*Listbox.borderWidth", 1)

    style.configure(
        "TSpinbox",
        fieldbackground=PANEL,
        background=PANEL,
        foreground=TEXT,
        arrowcolor=TEXT_MUTED,
        bordercolor=BORDER_STRONG,
        lightcolor=PANEL,
        darkcolor=PANEL,
        padding=(px(8), px(6)),
    )
    style.map(
        "TSpinbox",
        bordercolor=[("focus", PRIMARY), ("hover", BORDER_STRONG)],
        fieldbackground=[("disabled", PANEL_ALT)],
    )

    style.configure("TSeparator", background=BORDER)

    style.configure(
        "Slim.Vertical.TScrollbar",
        background=BORDER_STRONG,
        troughcolor=PANEL,
        bordercolor=PANEL,
        darkcolor=BORDER_STRONG,
        lightcolor=BORDER_STRONG,
        arrowcolor=TEXT_MUTED,
        gripcount=0,
        relief="flat",
        arrowsize=px(9),
        width=px(9),
    )
    style.map("Slim.Vertical.TScrollbar", background=[("active", TEXT_FAINT)])

    style.configure(
        "Data.Treeview",
        background=PANEL,
        fieldbackground=PANEL,
        foreground=TEXT,
        rowheight=px(27),
        borderwidth=0,
        relief="flat",
        font=font(SIZE_CAPTION + 0.5),
    )
    style.configure(
        "Data.Treeview.Heading",
        background=PANEL,
        foreground=TEXT_MUTED,
        font=font(SIZE_MICRO, "bold"),
        relief="flat",
        borderwidth=0,
        padding=(px(3), px(5)),
    )
    style.map(
        "Data.Treeview",
        background=[("selected", PRIMARY_SOFT)],
        foreground=[("selected", PRIMARY_DARK)],
    )
    style.map("Data.Treeview.Heading", background=[("active", PANEL)])
    try:
        style.layout("Data.Treeview", [("Data.Treeview.treearea", {"sticky": "nswe"})])
    except tk.TclError:
        pass


# ---------------------------------------------------------------------------
# Buttons
# ---------------------------------------------------------------------------


class RoundedButton(tk.Canvas):
    """Canvas rounded button so the control language matches across the app."""

    _KINDS = {
        "primary": {
            "bg": PRIMARY,
            "fg": "#FFFFFF",
            "hover": PRIMARY_DARK,
            "pressed": "#094A46",
            "outline": "",
            "disabled_bg": "#CFE0DE",
            "disabled_fg": "#FFFFFF",
        },
        "secondary": {
            "bg": PANEL,
            "fg": TEXT,
            "hover": PANEL_ALT,
            "pressed": PANEL_SOFT,
            "outline": BORDER_STRONG,
            "disabled_bg": PANEL_ALT,
            "disabled_fg": TEXT_FAINT,
        },
        "soft": {
            "bg": PRIMARY_SOFT,
            "fg": PRIMARY_DARK,
            "hover": PRIMARY_SOFT_HOVER,
            "pressed": "#CDE3DF",
            "outline": "",
            "disabled_bg": PANEL_ALT,
            "disabled_fg": TEXT_FAINT,
        },
        "ghost": {
            "bg": PANEL,
            "fg": TEXT_MUTED,
            "hover": PANEL_SOFT,
            "pressed": PANEL_HOVER,
            "outline": "",
            "disabled_bg": PANEL,
            "disabled_fg": TEXT_FAINT,
        },
        "danger": {
            "bg": DANGER,
            "fg": "#FFFFFF",
            "hover": "#A93226",
            "pressed": "#8F2A21",
            "outline": "",
            "disabled_bg": "#EBD3D0",
            "disabled_fg": "#FFFFFF",
        },
    }

    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command: Callable[[], None] | None = None,
        *,
        kind: str = "secondary",
        size: float = SIZE_BODY,
        bold: bool = False,
        padx_: float = 15,
        pady_: float = 7,
        width: int | None = None,
        height: float | None = None,
        bg: str | None = None,
    ) -> None:
        self._kind = kind if kind in self._KINDS else "secondary"
        self._text = str(text)
        self._command = command
        self._size = float(size)
        self._bold = bool(bold)
        self._compact = pady_ < 6
        self._button_height = float(height) if height else (28.0 if self._compact else 32.0)
        self._radius = 7.0 if not self._compact else 6.0
        self._parent_bg = bg or parent_background(parent)
        self._enabled = True
        self._hover = False
        self._pressed = False
        self._focused = False
        text_font = font(self._size, "bold" if self._bold else "normal")
        measure = tkfont.Font(root=parent, font=text_font).measure(self._text)
        self._min_width = max(px(44), measure + px(padx_) * 2)
        if width:
            self._min_width = max(self._min_width, px(width * 8))
        super().__init__(
            parent,
            width=self._min_width,
            height=px(self._button_height),
            bg=self._parent_bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            takefocus=1,
        )
        self.bind("<Configure>", lambda _e: self._redraw())
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<FocusIn>", self._on_focus)
        self.bind("<FocusOut>", self._on_blur)
        self.bind("<Key-space>", self._on_key)
        self.bind("<Key-Return>", self._on_key)
        self._redraw()

    # -- public API -----------------------------------------------------
    def set_text(self, text: str) -> None:
        if str(text) == self._text:
            return
        self._text = str(text)
        measure = tkfont.Font(root=self, font=self._font()).measure(self._text)
        self._min_width = max(px(44), measure + px(30))
        self.configure(width=self._min_width)
        self._redraw()

    def set_kind(self, kind: str) -> None:
        if kind in self._KINDS:
            self._kind = kind
            self._redraw()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        self.configure(cursor="hand2" if self._enabled else "arrow")
        self._redraw()

    def invoke(self) -> None:
        if self._enabled and self._command:
            self._command()

    # -- drawing --------------------------------------------------------
    def _font(self) -> tuple[str, int, str]:
        return font(self._size, "bold" if self._bold else "normal")

    def _colors(self) -> dict[str, str]:
        palette = dict(self._KINDS[self._kind])
        if not self._enabled:
            palette["bg"] = palette["disabled_bg"]
            palette["fg"] = palette["disabled_fg"]
            palette["outline"] = ""
            return palette
        if self._pressed:
            palette["bg"] = palette["pressed"]
        elif self._hover:
            palette["bg"] = palette["hover"]
        return palette

    def _redraw(self) -> None:
        self.delete("all")
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1:
            width = self._min_width
        if height <= 1:
            height = px(self._button_height)
        colors = self._colors()
        radius = px(self._radius)
        round_rect(
            self,
            px(0.5),
            px(0.5),
            width - px(0.5),
            height - px(0.5),
            radius,
            fill=colors["bg"],
            outline=colors["outline"],
            width=max(1, px(1)),
        )
        if self._focused and self._enabled:
            round_rect(
                self,
                px(2),
                px(2),
                width - px(2),
                height - px(2),
                max(1, radius - px(1)),
                fill="",
                outline=mix(PRIMARY, colors["bg"], 0.55),
                width=max(1, px(1.5)),
            )
        offset = px(1) if self._pressed else 0
        self.create_text(
            width / 2,
            height / 2 + offset,
            text=self._text,
            fill=colors["fg"],
            font=self._font(),
        )

    # -- events ---------------------------------------------------------
    def _on_press(self, _event=None) -> None:
        if not self._enabled:
            return
        self._pressed = True
        self.focus_set()
        self._redraw()

    def _on_release(self, event=None) -> None:
        if not self._enabled:
            return
        was_pressed = self._pressed
        self._pressed = False
        self._redraw()
        if was_pressed and event is not None:
            try:
                inside = (
                    0 <= event.x <= self.winfo_width()
                    and 0 <= event.y <= self.winfo_height()
                )
            except tk.TclError:
                inside = False
            if inside:
                self.invoke()

    def _on_enter(self, _event=None) -> None:
        if not self._enabled:
            return
        self._hover = True
        self._redraw()

    def _on_leave(self, _event=None) -> None:
        self._hover = False
        self._pressed = False
        self._redraw()

    def _on_focus(self, _event=None) -> None:
        self._focused = True
        self._redraw()

    def _on_blur(self, _event=None) -> None:
        self._focused = False
        self._redraw()

    def _on_key(self, _event=None) -> None:
        if self._enabled:
            self.invoke()


# Backwards compatible alias used by the existing window code.
FlatButton = RoundedButton


class IconButton(tk.Canvas):
    """Compact square icon button (currently undo / redo)."""

    _GLYPHS = {"undo": "↶", "redo": "↷"}

    def __init__(
        self,
        parent: tk.Misc,
        icon: str,
        command: Callable[[], None] | None = None,
        *,
        size: float = 28,
        bg: str | None = None,
        tooltip: str | None = None,
    ) -> None:
        self._icon = icon
        self._command = command
        self._size = float(size)
        self._parent_bg = bg or parent_background(parent)
        self._enabled = True
        self._hover = False
        self._pressed = False
        self._focused = False
        super().__init__(
            parent,
            width=px(self._size),
            height=px(self._size),
            bg=self._parent_bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            takefocus=1,
        )
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<FocusIn>", lambda _e: self._set_focus(True))
        self.bind("<FocusOut>", lambda _e: self._set_focus(False))
        self.bind("<Key-space>", lambda _e: self.invoke())
        self.bind("<Key-Return>", lambda _e: self.invoke())
        self._redraw()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        self.configure(cursor="hand2" if enabled else "arrow")
        self._redraw()

    def invoke(self) -> None:
        if self._enabled and self._command:
            self._command()

    def _set_focus(self, focused: bool) -> None:
        self._focused = focused
        self._redraw()

    def _redraw(self) -> None:
        self.delete("all")
        width = self.winfo_width() if self.winfo_width() > 1 else px(self._size)
        height = self.winfo_height() if self.winfo_height() > 1 else px(self._size)
        if not self._enabled:
            fill = ""
            ink = TEXT_FAINT
        elif self._pressed:
            fill = PANEL_HOVER
            ink = TEXT
        elif self._hover:
            fill = PANEL_SOFT
            ink = TEXT
        else:
            fill = ""
            ink = TEXT
        if fill:
            round_rect(self, 1, 1, width - 1, height - 1, px(7), fill=fill, outline="")
        if self._focused and self._enabled:
            round_rect(
                self, 1, 1, width - 1, height - 1, px(7), fill="", outline=PRIMARY, width=px(1)
            )
        self.create_text(
            width / 2,
            height / 2 - px(1),
            text=self._GLYPHS.get(self._icon, "?"),
            fill=ink,
            font=font(self._size * 0.52, "normal"),
        )

    def _on_press(self, _event=None) -> None:
        if not self._enabled:
            return
        self._pressed = True
        self.focus_set()
        self._redraw()

    def _on_release(self, event=None) -> None:
        if not self._enabled:
            return
        was = self._pressed
        self._pressed = False
        self._redraw()
        if was and event is not None:
            self.invoke()

    def _on_enter(self, _event=None) -> None:
        if not self._enabled:
            return
        self._hover = True
        self._redraw()

    def _on_leave(self, _event=None) -> None:
        self._hover = False
        self._pressed = False
        self._redraw()


# ---------------------------------------------------------------------------
# Surfaces / layout
# ---------------------------------------------------------------------------


class Card(tk.Frame):
    """Borderless section inside an inspector panel (title + content)."""

    def __init__(
        self,
        parent: tk.Misc,
        title: str | None = None,
        hint: str | None = None,
        *,
        padding: float = 0,
        bg: str = PANEL,
    ) -> None:
        super().__init__(parent, bg=bg)
        self._bg = bg
        self.hint_label: tk.Label | None = None
        if title:
            header = tk.Frame(self, bg=bg)
            header.pack(fill="x")
            tk.Label(
                header,
                text=title,
                bg=bg,
                fg=TEXT,
                font=font(SIZE_SECTION, "bold"),
                anchor="w",
            ).pack(side="left")
            if hint:
                self.hint_label = tk.Label(
                    header,
                    text=hint,
                    bg=bg,
                    fg=TEXT_MUTED,
                    font=font(SIZE_CAPTION),
                    anchor="e",
                )
                self.hint_label.pack(side="right")
        self.body = tk.Frame(self, bg=bg)
        self.body.pack(fill="both", expand=True, pady=(px(10), 0) if title else 0)


class InspectorPanel(tk.Frame):
    """A continuous white inspector surface with a scrollable inner column."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        width: int,
        bg: str = PANEL,
    ) -> None:
        super().__init__(
            parent,
            bg=bg,
            width=width,
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
        )
        self.pack_propagate(False)
        self.scroll = ScrollFrame(self, bg=bg)
        self.scroll.pack(fill="both", expand=True)
        self.inner = tk.Frame(self.scroll.inner, bg=bg)
        self.inner.pack(fill="both", expand=True, padx=px(18), pady=(px(16), px(20)))

    def scroll_to_top(self) -> None:
        self.scroll.scroll_to_top()


class Divider(tk.Frame):
    def __init__(self, parent: tk.Misc, *, color: str = BORDER, pad_y: float = 8) -> None:
        super().__init__(parent, bg=color, height=1)
        self.pack_propagate(False)
        self.pack(fill="x", pady=px(pad_y))


class SegmentedControl(tk.Canvas):
    """Rounded segmented control drawn on a canvas (soft base, white chip)."""

    def __init__(
        self,
        parent: tk.Misc,
        options: Sequence[tuple[str, str]],
        command: Callable[[str], None] | None = None,
        *,
        initial: str | None = None,
        bg: str = PANEL,
        size: float = SIZE_CAPTION + 0.5,
        pad: float = 3,
    ) -> None:
        self._seg_defs = [(str(key), str(label)) for key, label in options]
        self._keys = [key for key, _label in self._seg_defs]
        self._labels = {key: label for key, label in self._seg_defs}
        self._command = command
        self._value = initial or (self._keys[0] if self._keys else "")
        self._size = float(size)
        self._pad = px(pad)
        self._height = px(34)
        self._parent_bg = bg
        self._hover_index: int | None = None
        self._pressed_index: int | None = None
        self._focused = False
        measure = tkfont.Font(root=parent, font=self._font(False)).measure
        self._natural_widths = [max(px(54), measure(label) + px(28)) for _key, label in self._seg_defs]
        natural = sum(self._natural_widths) + self._pad * 2
        super().__init__(
            parent,
            width=natural,
            height=self._height,
            bg=bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            takefocus=1,
        )
        self.bind("<Configure>", lambda _e: self._redraw())
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Motion>", self._on_motion)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<FocusIn>", self._on_focus)
        self.bind("<FocusOut>", self._on_blur)
        self.bind("<Key-Left>", lambda _e: self._step(-1))
        self.bind("<Key-Right>", lambda _e: self._step(1))
        self._redraw()

    def _font(self, selected: bool) -> tuple[str, int, str]:
        return font(self._size, "bold" if selected else "normal")

    # -- geometry -------------------------------------------------------
    def _segments(self) -> list[tuple[float, float]]:
        width = self.winfo_width() if self.winfo_width() > 1 else int(self["width"])
        inner = width - self._pad * 2
        base = sum(self._natural_widths) or 1
        extra = max(0.0, inner - base)
        count = max(1, len(self._seg_defs))
        widths = [w + extra / count for w in self._natural_widths]
        segments: list[tuple[float, float]] = []
        x = self._pad
        for segment_width in widths:
            segments.append((x, x + segment_width))
            x += segment_width
        return segments

    # -- drawing --------------------------------------------------------
    def _redraw(self) -> None:
        self.delete("all")
        width = self.winfo_width() if self.winfo_width() > 1 else int(self["width"])
        height = self.winfo_height() if self.winfo_height() > 1 else self._height
        if width <= 1:
            return
        round_rect(
            self, 1, 1, width - 1, height - 1, px(9),
            fill=PANEL_SOFT, outline=BORDER, width=1,
        )
        selected_index = self._keys.index(self._value) if self._value in self._keys else 0
        for index, ((x0, x1), (key, label)) in enumerate(zip(self._segments(), self._seg_defs)):
            pad_y = self._pad
            selected = index == selected_index
            hovered = self._hover_index == index and not selected
            if selected:
                round_rect(
                    self, x0 + px(1), pad_y, x1 - px(1), height - pad_y, px(7),
                    fill=PANEL, outline=BORDER_STRONG, width=1,
                )
            elif hovered:
                round_rect(
                    self, x0 + px(1), pad_y, x1 - px(1), height - pad_y, px(7),
                    fill=PANEL_HOVER, outline="",
                )
            text_color = TEXT if selected else TEXT_MUTED
            self.create_text(
                (x0 + x1) / 2,
                height / 2,
                text=label,
                fill=text_color,
                font=self._font(selected),
            )
        if self._focused:
            round_rect(
                self, 2, 2, width - 2, height - 2, px(8),
                fill="", outline=mix(PRIMARY, PANEL_SOFT, 0.55), width=px(1.5),
            )

    # -- events ---------------------------------------------------------
    def _index_at(self, x: float) -> int | None:
        for index, (x0, x1) in enumerate(self._segments()):
            if x0 <= x <= x1:
                return index
        return None

    def _on_press(self, event) -> None:
        self.focus_set()
        self._pressed_index = self._index_at(event.x)
        self._redraw()

    def _on_release(self, event) -> None:
        index = self._index_at(event.x)
        if index is not None and index == self._pressed_index:
            self.set_value(self._keys[index], notify=True)
        self._pressed_index = None
        self._redraw()

    def _on_motion(self, event) -> None:
        index = self._index_at(event.x)
        if index != self._hover_index:
            self._hover_index = index
            self._redraw()

    def _on_enter(self, _event=None) -> None:
        self._hover_index = None
        self._redraw()

    def _on_leave(self, _event=None) -> None:
        self._hover_index = None
        self._pressed_index = None
        self._redraw()

    def _on_focus(self, _event=None) -> None:
        self._focused = True
        self._redraw()

    def _on_blur(self, _event=None) -> None:
        self._focused = False
        self._redraw()

    def _step(self, direction: int) -> None:
        if not self._keys:
            return
        index = self._keys.index(self._value) if self._value in self._keys else 0
        index = max(0, min(len(self._keys) - 1, index + direction))
        self.set_value(self._keys[index], notify=True)

    # -- public API -----------------------------------------------------
    def set_value(self, value: str, notify: bool = False) -> None:
        if value not in self._keys:
            return
        changed = value != self._value
        self._value = value
        self._redraw()
        if notify and changed and self._command:
            self._command(value)

    def get(self) -> str:
        return self._value


class Tabs(tk.Frame):
    """Underline tab bar; one navigation grammar for the whole window."""

    def __init__(
        self,
        parent: tk.Misc,
        labels: Sequence[str],
        command: Callable[[int], None] | None = None,
        *,
        bg: str = BG,
        initial: int = 0,
    ) -> None:
        super().__init__(parent, bg=bg)
        self._command = command
        self._buttons: list[tk.Button] = []
        self._indicators: list[tk.Frame] = []
        self._index = initial
        for index, label in enumerate(labels):
            holder = tk.Frame(self, bg=bg)
            holder.pack(side="left", padx=(0, px(20)))
            button = tk.Button(
                holder,
                text=label,
                command=lambda i=index: self.select(i),
                relief="flat",
                bd=0,
                highlightthickness=0,
                bg=bg,
                fg=TEXT_MUTED,
                activebackground=bg,
                activeforeground=TEXT,
                font=font(SIZE_BODY + 0.5, "normal"),
                cursor="hand2",
                padx=0,
                pady=px(7),
                takefocus=1,
            )
            button.pack()
            button.bind("<Enter>", lambda _e, b=button: self._hover(b, True), add="+")
            button.bind("<Leave>", lambda _e, b=button: self._hover(b, False), add="+")
            indicator = tk.Frame(holder, bg=bg, height=px(2))
            indicator.pack(fill="x")
            self._buttons.append(button)
            self._indicators.append(indicator)
        self.select(initial, notify=False)

    def _hover(self, button: tk.Button, active: bool) -> None:
        if button is self._buttons[self._index]:
            return
        button.configure(fg=TEXT if active else TEXT_MUTED)

    def select(self, index: int, notify: bool = True) -> None:
        if not self._buttons:
            return
        self._index = max(0, min(index, len(self._buttons) - 1))
        for position, button in enumerate(self._buttons):
            if position == self._index:
                button.configure(fg=TEXT, font=font(SIZE_BODY + 0.5, "bold"))
                self._indicators[position].configure(bg=PRIMARY)
            else:
                button.configure(fg=TEXT_MUTED, font=font(SIZE_BODY + 0.5, "normal"))
                self._indicators[position].configure(bg=self["bg"])
        if notify and self._command:
            self._command(self._index)

    @property
    def index(self) -> int:
        return self._index


# ---------------------------------------------------------------------------
# Scrolling
# ---------------------------------------------------------------------------

_SCROLL_FRAMES: list["ScrollFrame"] = []
_WHEEL_ROUTER_INSTALLED = False


def install_wheel_router(root: tk.Misc) -> None:
    global _WHEEL_ROUTER_INSTALLED
    if _WHEEL_ROUTER_INSTALLED:
        return
    _WHEEL_ROUTER_INSTALLED = True

    def _route(event) -> None:
        try:
            widget = root.winfo_containing(event.x_root, event.y_root)
        except (KeyError, tk.TclError):
            return
        node = widget
        while node is not None:
            if isinstance(node, ScrollFrame):
                node.scroll_by_event(event)
                return
            node = getattr(node, "master", None)

    root.bind_all("<MouseWheel>", _route, add="+")


class ScrollFrame(tk.Frame):
    def __init__(self, parent: tk.Misc, *, bg: str = BG, width: int | None = None) -> None:
        super().__init__(parent, bg=bg)
        self._bg = bg
        self.canvas = tk.Canvas(
            self, bg=bg, highlightthickness=0, bd=0, **({"width": width} if width else {})
        )
        self.vbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview, style="Slim.Vertical.TScrollbar"
        )
        self.canvas.configure(yscrollcommand=self._on_scroll)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        _SCROLL_FRAMES.append(self)
        self._theme_scrollbar(visible=False)

    def destroy(self) -> None:
        try:
            _SCROLL_FRAMES.remove(self)
        except ValueError:
            pass
        super().destroy()

    def _theme_scrollbar(self, visible: bool) -> None:
        managed = bool(self.vbar.winfo_manager())
        if visible and not managed:
            # Pack before the canvas so the packer reserves the slim track width.
            self.vbar.pack(side="right", fill="y", before=self.canvas)
        elif not visible and managed:
            self.vbar.pack_forget()

    def _on_scroll(self, first: str, last: str) -> None:
        self.vbar.set(first, last)
        try:
            needs = float(first) > 0.0 or float(last) < 1.0
        except ValueError:
            needs = False
        self._theme_scrollbar(needs)

    def _on_inner_configure(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)

    def scroll_by_event(self, event) -> None:
        delta = int(getattr(event, "delta", 0))
        if delta == 0:
            return
        self.canvas.yview_scroll(int(-delta / 120) * 3, "units")

    def scroll_to_top(self) -> None:
        self.canvas.yview_moveto(0.0)


# ---------------------------------------------------------------------------
# Form rows
# ---------------------------------------------------------------------------


class Field(tk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        label: str,
        *,
        hint: str | None = None,
        bg: str = PANEL,
        label_width: int | None = None,
    ) -> None:
        super().__init__(parent, bg=bg)
        self.label = tk.Label(
            self,
            text=label,
            bg=bg,
            fg=TEXT_MUTED,
            font=font(SIZE_CAPTION + 0.5),
            anchor="w",
            width=label_width or 0,
        )
        self.label.pack(anchor="w", pady=(0, px(4)))
        self.hint = hint


class EntryRow(tk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        label: str,
        variable: tk.Variable,
        *,
        hint: str | None = None,
        bg: str = PANEL,
    ) -> None:
        super().__init__(parent, bg=bg)
        tk.Label(
            self, text=label, bg=bg, fg=TEXT_MUTED, font=font(SIZE_CAPTION + 0.5), anchor="w"
        ).pack(anchor="w", pady=(0, px(4)))
        self.entry = ttk.Entry(self, textvariable=variable)
        self.entry.pack(fill="x")
        if hint:
            tk.Label(
                self, text=hint, bg=bg, fg=TEXT_MUTED, font=font(SIZE_CAPTION), anchor="w"
            ).pack(anchor="w", pady=(px(3), 0))


class SliderRow(tk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        label: str,
        variable: tk.DoubleVar,
        from_: float,
        to: float,
        *,
        command: Callable[[float], None] | None = None,
        formatter: Callable[[float], str] | None = None,
        bg: str = PANEL,
        step: float | None = None,
    ) -> None:
        super().__init__(parent, bg=bg)
        self._bg = bg
        self._variable = variable
        self._command = command
        self._formatter = formatter or (lambda value: f"{value:g}")
        self._silent = False
        header = tk.Frame(self, bg=bg)
        header.pack(fill="x")
        tk.Label(
            header, text=label, bg=bg, fg=TEXT_MUTED, font=font(SIZE_CAPTION + 0.5), anchor="w"
        ).pack(side="left")
        self.value_label = tk.Label(
            header, text=self._formatter(float(variable.get())), bg=bg, fg=TEXT, font=font(SIZE_CAPTION + 0.5, "bold")
        )
        self.value_label.pack(side="right")
        self.slider = Slider(self, variable, from_, to, command=self._on_slider, step=step, bg=bg)
        self.slider.pack(fill="x", pady=(px(2), 0))

    def _on_slider(self, value: float) -> None:
        self.value_label.configure(text=self._formatter(value))
        if self._command and not self._silent:
            self._command(value)

    def set_value(self, value: float, notify: bool = False) -> None:
        self._silent = True
        try:
            self.slider.set_value(float(value), notify=False)
        finally:
            self._silent = False
        self.value_label.configure(text=self._formatter(float(value)))
        if notify and self._command:
            self._command(float(value))


class Slider(tk.Canvas):
    def __init__(
        self,
        parent: tk.Misc,
        variable: tk.DoubleVar,
        from_: float,
        to: float,
        command: Callable[[float], None] | None = None,
        *,
        step: float | None = None,
        bg: str = PANEL,
        height: float = 22,
    ) -> None:
        super().__init__(
            parent,
            bg=bg,
            height=px(height),
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            takefocus=1,
        )
        self._variable = variable
        self._from = float(from_)
        self._to = float(to) if float(to) != float(from_) else float(from_) + 1.0
        self._command = command
        self._step = step
        self._bg = bg
        self._hover = False
        self._dragging = False
        self._focused = False
        self._pad = px(8)
        self.bind("<Configure>", lambda _e: self._redraw())
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<FocusIn>", lambda _e: self._set_focus(True))
        self.bind("<FocusOut>", lambda _e: self._set_focus(False))
        self._trace = variable.trace_add("write", self._on_var_write)
        self._redraw()

    def _value(self) -> float:
        try:
            return float(self._variable.get())
        except (tk.TclError, ValueError):
            return self._from

    def _fraction(self, value: float) -> float:
        return max(0.0, min(1.0, (value - self._from) / (self._to - self._from)))

    def _on_var_write(self, *_args) -> None:
        self._redraw()

    def _redraw(self) -> None:
        self.delete("all")
        width = self.winfo_width()
        height = self.winfo_height()
        if width <= 1:
            return
        pad = self._pad
        track_radius = max(1, px(2))
        knob_radius = px(8)
        center_y = height / 2.0
        x0, x1 = pad, max(pad + 1, width - pad)
        fraction = self._fraction(self._value())
        knob_x = x0 + (x1 - x0) * fraction
        round_rect(
            self, x0, center_y - track_radius, x1, center_y + track_radius, track_radius,
            fill="#E6ECF3", outline="",
        )
        if knob_x > x0 + 1:
            round_rect(
                self, x0, center_y - track_radius, knob_x, center_y + track_radius,
                track_radius, fill=PRIMARY, outline="",
            )
        active = self._hover or self._dragging or self._focused
        ring = active or self._focused
        shadow = knob_radius + (px(1) if active else 0)
        self.create_oval(
            knob_x - shadow + px(1), center_y - shadow + px(1),
            knob_x + shadow + px(1), center_y + shadow + px(1),
            fill=SHADOW if active else "", outline="",
        )
        self.create_oval(
            knob_x - shadow, center_y - shadow, knob_x + shadow, center_y + shadow,
            fill="#FFFFFF", outline=PRIMARY if ring else BORDER_STRONG,
            width=px(2.5) if active else px(2),
        )

    def _pick(self, event) -> None:
        pad = self._pad
        width = self.winfo_width()
        usable = max(1.0, width - pad * 2)
        fraction = max(0.0, min(1.0, (event.x - pad) / usable))
        value = self._from + (self._to - self._from) * fraction
        if self._step:
            value = round(value / self._step) * self._step
        self._set_value(value, notify=True)

    def _set_value(self, value: float, notify: bool = False) -> None:
        value = max(min(self._from, self._to), min(max(self._from, self._to), float(value)))
        self._variable.set(value)
        self._redraw()
        if notify and self._command:
            self._command(value)

    def _on_press(self, event) -> None:
        self._dragging = True
        self.focus_set()
        self._pick(event)

    def _on_drag(self, event) -> None:
        if self._dragging:
            self._pick(event)

    def _on_release(self, _event) -> None:
        self._dragging = False
        self._redraw()

    def _on_enter(self, _event=None) -> None:
        self._hover = True
        self._redraw()

    def _on_leave(self, _event=None) -> None:
        self._hover = False
        self._redraw()

    def _set_focus(self, focused: bool) -> None:
        self._focused = focused
        self._redraw()

    def set_value(self, value: float, notify: bool = False) -> None:
        self._set_value(value, notify=notify)


class CheckRow(tk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        variable: tk.BooleanVar,
        command: Callable[[], None] | None = None,
        *,
        bg: str = PANEL,
    ) -> None:
        super().__init__(parent, bg=bg, cursor="hand2")
        self._variable = variable
        self._command = command
        self._bg = bg
        self._size = 18
        self.canvas = tk.Canvas(
            self, width=px(self._size), height=px(self._size),
            bg=bg, highlightthickness=0, bd=0, cursor="hand2",
        )
        self.canvas.pack(side="left")
        self.label = tk.Label(
            self, text=text, bg=bg, fg=TEXT, font=font(SIZE_CAPTION + 0.5),
            anchor="w", cursor="hand2",
        )
        self.label.pack(side="left", padx=(px(8), 0))
        for widget in (self, self.canvas, self.label):
            widget.bind("<Button-1>", self._toggle)
        self._trace = variable.trace_add("write", lambda *_a: self._redraw())
        self._redraw()

    def _toggle(self, _event=None) -> None:
        try:
            self._variable.set(not bool(self._variable.get()))
        except tk.TclError:
            return
        if self._command:
            self._command()

    def _redraw(self) -> None:
        self.canvas.delete("all")
        size = px(self._size)
        checked = bool(self._variable.get())
        fill = PRIMARY if checked else "#FFFFFF"
        outline = PRIMARY if checked else BORDER_STRONG
        round_rect(
            self.canvas, px(1), px(1), size - px(1), size - px(1), px(5),
            fill=fill, outline=outline, width=px(1.5),
        )
        if checked:
            self.canvas.create_line(
                size * 0.28, size * 0.52,
                size * 0.44, size * 0.68,
                size * 0.73, size * 0.33,
                fill="#FFFFFF", width=max(2, px(2)), capstyle="round", joinstyle="round",
            )


class ColorButton(tk.Canvas):
    def __init__(
        self,
        parent: tk.Misc,
        color: str,
        command: Callable[[], None] | None = None,
        *,
        size: int = 22,
        bg: str = PANEL,
    ) -> None:
        super().__init__(
            parent, width=px(size), height=px(size),
            bg=bg, highlightthickness=0, bd=0, cursor="hand2",
        )
        self._size = size
        self._command = command
        self._color = color
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", lambda _e: self.itemconfigure(self._shape, outline=PRIMARY))
        self.bind("<Leave>", lambda _e: self.itemconfigure(self._shape, outline=BORDER))
        self._shape = None
        self.set_color(color)

    def set_color(self, color: str) -> None:
        self._color = color
        self.delete("all")
        self._shape = round_rect(
            self, px(1), px(1), px(self._size - 1), px(self._size - 1), px(6),
            fill=color, outline=BORDER, width=1,
        )

    @property
    def color(self) -> str:
        return self._color

    def _on_click(self, _event) -> None:
        if self._command:
            self._command()


class PaletteCard(tk.Canvas):
    WIDTH = 168
    HEIGHT = 100

    def __init__(
        self,
        parent: tk.Misc,
        name: str,
        colors: Sequence[str],
        *,
        group: str = "",
        tag: str = "",
        selected: bool = False,
        command: Callable[[], None] | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        self._width = width or self.WIDTH
        self._height = height or self.HEIGHT
        super().__init__(
            parent,
            width=px(self._width),
            height=px(self._height),
            bg=parent_background(parent),
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            takefocus=1,
        )
        self._name = name
        self._colors = list(colors)
        self._group = group
        self._tag = tag
        self._selected = selected
        self._command = command
        self._hover = False
        self.bind("<Button-1>", lambda _e: self._command and self._command())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<FocusIn>", lambda _e: self._set_focus(True))
        self.bind("<FocusOut>", lambda _e: self._set_focus(False))
        self.bind("<Key-space>", lambda _e: self._command and self._command())
        self.bind("<Key-Return>", lambda _e: self._command and self._command())
        self._focused = False
        self._redraw()

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self._redraw()

    def _set_focus(self, focused: bool) -> None:
        self._focused = focused
        self._redraw()

    def _on_enter(self, _event=None) -> None:
        self._hover = True
        self._redraw()

    def _on_leave(self, _event=None) -> None:
        self._hover = False
        self._redraw()

    def _redraw(self) -> None:
        self.delete("all")
        w, h = px(self._width), px(self._height)
        if self._selected:
            border, width = PRIMARY, px(2)
            fill = mix(PANEL, PRIMARY_SOFT, 0.45)
        elif self._hover:
            border, width = BORDER_STRONG, px(1)
            fill = PANEL_ALT
        else:
            border, width = BORDER, px(1)
            fill = PANEL
        if self._focused:
            border, width = PRIMARY_DARK, px(2)
        round_rect(self, px(1), px(1), w - px(1), h - px(1), px(10), fill=fill, outline=border, width=width)

        pad = px(12)
        swatch_top = px(12)
        swatch_h = px(24)
        count = max(1, len(self._colors))
        gap = px(2)
        reserve = px(18) if self._selected else 0
        bar_w = max(px(4), (w - pad * 2 - reserve - gap * (count - 1)) / count)
        for index, color in enumerate(self._colors):
            x0 = pad + index * (bar_w + gap)
            round_rect(
                self, x0, swatch_top, x0 + bar_w, swatch_top + swatch_h,
                px(4) if count > 1 else px(5), fill=color, outline="",
            )

        name_font = font(SIZE_CAPTION + 0.5, "bold")
        show_tag = self._tag in ("推荐", "已选") and not self._selected
        name_width = w - pad * 2 - (px(52) if show_tag else px(20))
        name = truncated_text(self._name, name_width, name_font, self)
        self.create_text(
            pad, swatch_top + swatch_h + px(9),
            text=name, anchor="nw", fill=TEXT, font=name_font,
        )
        meta = f"{len(self._colors)} 色"
        if meta:
            self.create_text(
                pad, swatch_top + swatch_h + px(28),
                text=truncated_text(meta, w - pad * 2 - px(12), font(SIZE_MICRO), self),
                anchor="nw", fill=TEXT_MUTED, font=font(SIZE_MICRO),
            )
        if show_tag:
            pill_w = px(42)
            pill_h = px(19)
            pill_x1 = w - pad
            pill_x0 = pill_x1 - pill_w
            pill_y0 = swatch_top + swatch_h + px(6)
            pill_fill = PRIMARY_SOFT if self._tag == "推荐" else PANEL_SOFT
            pill_text = PRIMARY_DARK if self._tag == "推荐" else TEXT_MUTED
            round_rect(
                self, pill_x0, pill_y0, pill_x1, pill_y0 + pill_h, px(9),
                fill=pill_fill, outline="",
            )
            self.create_text(
                (pill_x0 + pill_x1) / 2, pill_y0 + pill_h / 2,
                text=self._tag, fill=pill_text, font=font(SIZE_MICRO, "bold"),
            )
        if self._selected:
            cx = w - pad - px(7)
            cy = swatch_top + swatch_h / 2
            self.create_oval(cx - px(7), cy - px(7), cx + px(7), cy + px(7), fill=PRIMARY, outline="")
            self.create_text(cx, cy, text="✓", fill="#FFFFFF", font=font(8, "bold"))


class BrandMark(tk.Canvas):
    """Small logo glyph used when no icon asset is available."""

    def __init__(self, parent: tk.Misc, size: int = 36, *, bg: str = PANEL) -> None:
        super().__init__(
            parent, width=px(size), height=px(size), bg=bg, highlightthickness=0, bd=0
        )
        self._size = size
        self.bind("<Configure>", lambda _e: self._redraw())
        self._redraw()

    def _redraw(self) -> None:
        self.delete("all")
        size = px(self._size)
        if size <= 0:
            return
        round_rect(self, 0, 0, size, size, size * 0.28, fill="#0B3B38", outline="")
        colors = ["#6AFFFF", "#34D399", "#E0A6E5", "#FDE68A", "#F87171", "#60A5FA"]
        inset = size * 0.12
        diameter = size - inset * 2
        steps = len(colors)
        step = 360.0 / steps
        for index, color in enumerate(colors):
            self.create_arc(
                inset, inset, inset + diameter, inset + diameter,
                start=90 - index * step, extent=-step + 2.0,
                fill=color, outline="#0B3B38", width=max(1, int(size * 0.015)),
            )
        hole = size * 0.52
        self.create_oval(
            size / 2 - hole / 2, size / 2 - hole / 2,
            size / 2 + hole / 2, size / 2 + hole / 2,
            fill="#0B3B38", outline="",
        )


class StatusBar(tk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, bg=PANEL, height=px(34))
        self.pack_propagate(False)
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", side="top")
        inner = tk.Frame(self, bg=PANEL)
        inner.pack(fill="both", expand=True, padx=px(18))
        self._dot = tk.Canvas(
            inner, width=px(8), height=px(8), bg=PANEL, highlightthickness=0, bd=0
        )
        self._dot.pack(side="left")
        self._dot_id = self._dot.create_oval(px(1), px(1), px(7), px(7), fill=SUCCESS, outline="")
        self.message = tk.Label(
            inner, text="就绪", bg=PANEL, fg=TEXT_MUTED, font=font(SIZE_CAPTION), anchor="w"
        )
        self.message.pack(side="left", padx=(px(9), 0))
        self.stats = tk.Label(
            inner, text="", bg=PANEL, fg=TEXT_MUTED, font=font(SIZE_CAPTION), anchor="e"
        )
        self.stats.pack(side="right")

    def set_message(self, text: str, level: str = "info") -> None:
        colors = {"info": SUCCESS, "busy": WARNING, "error": DANGER}
        self._dot.itemconfigure(self._dot_id, fill=colors.get(level, SUCCESS))
        self.message.configure(text=text, fg=TEXT_MUTED if level == "info" else TEXT)

    def set_stats(self, text: str) -> None:
        self.stats.configure(text=text)


class Tooltip:
    def __init__(self, widget: tk.Misc, text: str, *, delay: int = 420) -> None:
        self._widget = widget
        self._text = text
        self._delay = delay
        self._after_id: str | None = None
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None) -> None:
        self._cancel()
        self._after_id = self._widget.after(self._delay, self._show)

    def _cancel(self) -> None:
        if self._after_id:
            try:
                self._widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _show(self) -> None:
        if self._tip or not self._widget.winfo_exists():
            return
        self._cancel()
        tip = tk.Toplevel(self._widget)
        tip.wm_overrideredirect(True)
        tip.configure(bg=BORDER_STRONG)
        tk.Label(
            tip, text=self._text, bg="#1E293B", fg="#F8FAFC",
            font=font(SIZE_MICRO), padx=px(9), pady=px(5),
        ).pack(padx=1, pady=1)
        x = self._widget.winfo_rootx() + self._widget.winfo_width() // 2
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + px(6)
        tip.wm_geometry(f"+{x - px(30)}+{y}")
        self._tip = tip

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except tk.TclError:
                pass
            self._tip = None


class DataTable(ttk.Treeview):
    """Compact 3-column count table."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        height: int = 5,
        on_select: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(
            parent,
            columns=("label", "count", "share"),
            show="headings",
            height=height,
            style="Data.Treeview",
            selectmode="browse",
        )
        self.heading("label", text="类别", anchor="w")
        self.heading("count", text="数量", anchor="e")
        self.heading("share", text="占比", anchor="e")
        self.column("label", width=px(130), anchor="w", stretch=True)
        self.column("count", width=px(48), anchor="e", stretch=False)
        self.column("share", width=px(68), anchor="e", stretch=False)
        self._on_select = on_select
        self.bind("<ButtonRelease-1>", self._handle_click)

    def set_rows(self, rows: Iterable[tuple[str, int, float]]) -> None:
        self.delete(*self.get_children())
        for label, count, share in rows:
            self.insert("", "end", values=(label, count, f"{share:.2f}%"))
        children = self.get_children()
        if children:
            self.selection_set(children[0])
            self.selection_remove(children[0])

    def _handle_click(self, event) -> None:
        row = self.identify_row(event.y)
        if not row:
            return
        self.selection_set(row)
        if not self._on_select:
            return
        values = self.item(row, "values")
        if values:
            self._on_select(str(values[0]))

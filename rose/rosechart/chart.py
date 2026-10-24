"""Rendering engine for Nightingale rose charts.

The engine is UI-agnostic: it builds a matplotlib figure (optionally inside an
existing figure so an embedded Tk canvas can reuse it), exposes every label as
an editable handle and supports moving labels in data coordinates. The GUI
layer only wires mouse events to :meth:`RoseChart.set_label_position`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import matplotlib
import matplotlib.font_manager as fm
import matplotlib.patheffects as path_effects
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import ListedColormap
from matplotlib.figure import Figure
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath

TRANSPARENT = "transparent"

CJK_FONT_CANDIDATES = [
    "Microsoft YaHei",
    "Microsoft YaHei UI",
    "SimHei",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "DengXian",
    "PingFang SC",
    "Arial Unicode MS",
    "DejaVu Sans",
]


# ---------------------------------------------------------------------------
# Style / spec models
# ---------------------------------------------------------------------------


@dataclass
class StyleConfig:
    """Visual configuration shared by every chart of a document."""

    title: str = "SW项目统计"
    subtitle: str = ""

    font_family: str = "Microsoft YaHei"
    title_font_size: float = 34.0
    title_color: str = "#333333"
    subtitle_font_size: float = 14.0
    subtitle_color: str = "#64748B"

    inner_radius: float = 0.30
    outer_radius: float = 0.98
    start_angle: float = 90.0
    gap_ratio: float = 0.18
    gap_max_degrees: float = 2.0
    corner_radius: float = 0.055
    edge_color: str = "#FFFFFF"
    edge_width: float = 3.2

    label_font_size: float = 21.0
    label_line_width: float = 0.9
    label_wire_scale: float = 1.0
    label_text_gap: float = 0.03
    label_color_mode: str = "auto"  # match | auto | single
    label_single_color: str = "#334155"

    show_name: bool = True
    show_value: bool = True
    show_percent: bool = True
    percent_decimals: int = 2
    value_suffix: str = ""

    center_text: str = ""
    center_font_size: float = 18.0
    center_color: str = "#64748B"

    background: str = TRANSPARENT
    figure_width: float = 12.0
    figure_height: float = 8.0
    dpi: int = 100

    def copy(self) -> "StyleConfig":
        return replace(self)


@dataclass
class ChartSpec:
    """Data + style snapshot needed to draw one chart."""

    labels: list[str] = field(default_factory=list)
    values: list[int] = field(default_factory=list)
    style: StyleConfig = field(default_factory=StyleConfig)
    fill_colors: dict[str, str] = field(default_factory=dict)
    label_colors: dict[str, str] = field(default_factory=dict)
    # Optional custom order (label names). When set it wins over the input order.
    order: list[str] | None = None

    @property
    def total(self) -> int:
        return int(sum(self.values))

    def sorted_pairs(self) -> list[tuple[str, int]]:
        pairs = [(str(label), int(value)) for label, value in zip(self.labels, self.values)]
        if self.order:
            rank = {label: index for index, label in enumerate(self.order)}
            pairs.sort(key=lambda item: (rank.get(item[0], len(rank)), -item[1]))
        return [(label, value) for label, value in pairs if value > 0]


# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------


def available_cjk_fonts() -> list[str]:
    installed = {font.name for font in fm.fontManager.ttflist}
    return [name for name in CJK_FONT_CANDIDATES if name in installed]


def configure_chinese_font(preferred: str | None = None) -> str:
    """Pick a font that can display Chinese text and register it in rcParams."""
    installed = {font.name for font in fm.fontManager.ttflist}
    chosen = ""
    candidates = ([preferred] if preferred else []) + CJK_FONT_CANDIDATES
    for name in candidates:
        if name and name in installed:
            chosen = name
            break
    family = chosen or "sans-serif"
    if chosen:
        matplotlib.rcParams["font.sans-serif"] = [chosen] + [
            name for name in CJK_FONT_CANDIDATES if name != chosen
        ]
    matplotlib.rcParams["font.family"] = "sans-serif"
    matplotlib.rcParams["axes.unicode_minus"] = False
    return family


def resolve_font_family(preferred: str | None = None) -> str:
    installed = {font.name for font in fm.fontManager.ttflist}
    if preferred and preferred in installed:
        matplotlib.rcParams["font.sans-serif"] = [preferred] + [
            name for name in CJK_FONT_CANDIDATES if name != preferred
        ]
        matplotlib.rcParams["font.family"] = "sans-serif"
        matplotlib.rcParams["axes.unicode_minus"] = False
        return preferred
    return configure_chinese_font()


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _polar_point(cx: float, cy: float, radius: float, angle_degrees: float) -> tuple[float, float]:
    radians = np.deg2rad(angle_degrees)
    return cx + radius * float(np.cos(radians)), cy + radius * float(np.sin(radians))


def rounded_annular_sector(
    cx: float,
    cy: float,
    inner_radius: float,
    outer_radius: float,
    theta1: float,
    theta2: float,
    color: str,
    *,
    corner_radius_max: float = 0.055,
    edge_color: str = "#FFFFFF",
    edge_width: float = 3.2,
) -> PathPatch:
    """Annular sector with softly rounded inner/outer corners."""
    span_radians = np.deg2rad(theta2 - theta1)
    thickness = outer_radius - inner_radius
    corner_radius = min(
        max(0.0, corner_radius_max),
        thickness * 0.46,
        inner_radius * span_radians * 0.25,
        outer_radius * span_radians * 0.25,
    )
    outer_inset = np.rad2deg(corner_radius / outer_radius) if outer_radius else 0.0
    inner_inset = np.rad2deg(corner_radius / inner_radius) if inner_radius else 0.0

    outer_start = theta1 + outer_inset
    outer_end = theta2 - outer_inset
    inner_start = theta2 - inner_inset
    inner_end = theta1 + inner_inset
    outer_steps = max(6, int(abs(outer_end - outer_start) / 3.0) + 1)
    inner_steps = max(6, int(abs(inner_start - inner_end) / 3.0) + 1)

    vertices: list[tuple[float, float]] = []
    codes: list[int] = []

    for index, angle in enumerate(np.linspace(outer_start, outer_end, outer_steps)):
        vertices.append(_polar_point(cx, cy, outer_radius, float(angle)))
        codes.append(MplPath.MOVETO if index == 0 else MplPath.LINETO)

    vertices.extend(
        [
            _polar_point(cx, cy, outer_radius, theta2),
            _polar_point(cx, cy, outer_radius - corner_radius, theta2),
        ]
    )
    codes.extend([MplPath.CURVE3, MplPath.CURVE3])
    vertices.append(_polar_point(cx, cy, inner_radius + corner_radius, theta2))
    codes.append(MplPath.LINETO)
    vertices.extend(
        [
            _polar_point(cx, cy, inner_radius, theta2),
            _polar_point(cx, cy, inner_radius, inner_start),
        ]
    )
    codes.extend([MplPath.CURVE3, MplPath.CURVE3])

    for angle in np.linspace(inner_start, inner_end, inner_steps)[1:]:
        vertices.append(_polar_point(cx, cy, inner_radius, float(angle)))
        codes.append(MplPath.LINETO)

    vertices.extend(
        [
            _polar_point(cx, cy, inner_radius, theta1),
            _polar_point(cx, cy, inner_radius + corner_radius, theta1),
        ]
    )
    codes.extend([MplPath.CURVE3, MplPath.CURVE3])
    vertices.append(_polar_point(cx, cy, outer_radius - corner_radius, theta1))
    codes.append(MplPath.LINETO)
    vertices.extend(
        [
            _polar_point(cx, cy, outer_radius, theta1),
            vertices[0],
        ]
    )
    codes.extend([MplPath.CURVE3, MplPath.CURVE3])
    vertices.append(vertices[0])
    codes.append(MplPath.CLOSEPOLY)

    return PathPatch(
        MplPath(vertices, codes),
        facecolor=color,
        edgecolor=edge_color,
        linewidth=max(0.0, edge_width),
        joinstyle="round",
        capstyle="round",
        antialiased=True,
    )


# ---------------------------------------------------------------------------
# Label model
# ---------------------------------------------------------------------------


@dataclass
class LabelHandle:
    label: str
    value: int
    percent: float
    side: int
    direction_x: float
    direction_y: float
    anchor_x: float
    anchor_y: float
    auto_y: float = 0.0
    auto_line_end_x: float = 0.0
    y: float = 0.0
    line_end_x: float = 0.0
    color: str = "#334155"
    elbow_x: float = 0.0
    text_x: float = 0.0
    text: object | None = None
    line: object | None = None

    def offset(self) -> tuple[float, float]:
        return (self.line_end_x - self.auto_line_end_x, self.y - self.auto_y)


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------


class RoseChart:
    """A rendered rose chart with draggable label handles."""

    def __init__(
        self,
        spec: ChartSpec,
        fig: plt.Figure | None = None,
        *,
        preview: bool = False,
        preview_bg: str = "#F5F7FA",
    ) -> None:
        self.spec = spec
        self.style = spec.style
        self.preview = preview
        self.preview_bg = preview_bg
        self.figure = fig if fig is not None else Figure()
        self.figure.clear()
        self.figure.set_size_inches(
            self.style.figure_width, self.style.figure_height, forward=False
        )
        if preview:
            self.figure.patch.set_facecolor(preview_bg)
            self.figure.patch.set_alpha(1.0)
        elif self.style.background == TRANSPARENT:
            self.figure.patch.set_alpha(0.0)
        else:
            self.figure.patch.set_facecolor(self.style.background)
            self.figure.patch.set_alpha(1.0)

        self.axis = self.figure.add_subplot(111)
        self.axis.set_facecolor("none")
        self.axis.set_aspect("equal")
        self.axis.set_xlim(-1.72, 1.72)
        self.axis.set_ylim(-1.22, 1.18)
        self.axis.set_axis_off()
        self.axis.set_position([0.02, 0.04, 0.96, 0.82])

        self.font_family = resolve_font_family(self.style.font_family)
        self._sector_paths: list[MplPath] = []
        self.pairs = spec.sorted_pairs()
        if not self.pairs:
            raise ValueError("没有可绘制的数据：所有数值都为 0 或为空。")
        self.total = float(sum(value for _, value in self.pairs))
        self.maximum_value = float(max(value for _, value in self.pairs))
        self.handles: dict[str, LabelHandle] = {}

        if preview and self.style.background == TRANSPARENT:
            self._draw_checkerboard()
        self._draw_sectors()
        self._draw_center_text()
        self._draw_title()
        self._create_labels()
        self._apply_auto_layout()
        try:
            self.fit_labels_inside()
        except Exception:
            pass
        try:
            self.refresh_label_backplates()
        except Exception:
            pass

    # -- figure helpers ---------------------------------------------------

    def _draw_checkerboard(self) -> None:
        """Full-figure checkerboard so the preview reads as a transparent canvas."""
        columns, rows = 32, 22
        tile = (np.indices((rows, columns)).sum(axis=0) % 2).astype(float)
        background = self.figure.add_axes([0, 0, 1, 1], zorder=-100)
        background.set_axis_off()
        background.imshow(
            tile,
            extent=(0, 1, 0, 1),
            cmap=ListedColormap(["#FFFFFF", "#F7F9FC"]),
            interpolation="nearest",
            zorder=-100,
            aspect="auto",
        )
        background.set_xlim(0, 1)
        background.set_ylim(0, 1)

    def _draw_title(self) -> None:
        style = self.style
        if style.title:
            self.figure.suptitle(
                style.title,
                x=0.5,
                y=0.94,
                fontsize=style.title_font_size,
                fontweight="bold",
                color=style.title_color,
                fontfamily=self.font_family,
            )
        if style.subtitle:
            self.figure.text(
                0.5,
                0.875,
                style.subtitle,
                ha="center",
                va="center",
                fontsize=style.subtitle_font_size,
                color=style.subtitle_color,
                fontfamily=self.font_family,
            )

    def _draw_center_text(self) -> None:
        template = self.style.center_text.strip()
        if not template:
            return
        text = (
            template.replace("{total}", str(int(self.total)))
            .replace("{n}", str(len(self.pairs)))
            .replace("{max}", str(int(self.maximum_value)))
        )
        self.axis.text(
            0.0,
            -0.05,
            text,
            ha="center",
            va="center",
            fontsize=self.style.center_font_size,
            fontweight="bold",
            color=self.style.center_color,
            fontfamily=self.font_family,
            zorder=10,
        )

    # -- sectors ----------------------------------------------------------

    def _draw_sectors(self) -> None:
        style = self.style
        start_angle = float(style.start_angle)
        self.axis.set_xlim(-1.72, 1.72)
        self.axis.set_ylim(-1.22, 1.18)

        for label, value in self.pairs:
            span = value / self.total * 360.0
            end_angle = start_angle - span
            gap = min(float(style.gap_max_degrees), span * float(style.gap_ratio))
            if span > gap:
                theta1 = end_angle + gap / 2.0
                theta2 = start_angle - gap / 2.0
            else:
                theta1, theta2 = end_angle, start_angle
            outer_radius = float(style.inner_radius) + (
                float(style.outer_radius) - float(style.inner_radius)
            ) * (value / self.maximum_value)
            color = self.spec.fill_colors.get(label, "#CCCCCC")
            sector = rounded_annular_sector(
                0.0,
                -0.05,
                float(style.inner_radius),
                outer_radius,
                theta1,
                theta2,
                color,
                corner_radius_max=float(style.corner_radius),
                edge_color=style.edge_color,
                edge_width=style.edge_width,
            )
            self.axis.add_patch(sector)
            self._sector_paths.append(sector.get_path())

            middle_angle = (start_angle + end_angle) / 2.0
            radians = np.deg2rad(middle_angle)
            direction_x = float(np.cos(radians))
            direction_y = float(np.sin(radians))
            anchor_radius = outer_radius + 0.012
            self._pending = getattr(self, "_pending", [])
            self._pending.append(
                {
                    "label": label,
                    "value": value,
                    "direction_x": direction_x,
                    "direction_y": direction_y,
                    "anchor_x": direction_x * anchor_radius,
                    "anchor_y": -0.05 + direction_y * anchor_radius,
                    "outer_radius": outer_radius,
                }
            )
            start_angle = end_angle

    # -- labels -----------------------------------------------------------

    def _label_text(self, label: str, value: int, percent: float) -> str:
        style = self.style
        header_parts: list[str] = []
        if style.show_name:
            header_parts.append(label)
        if style.show_value:
            header_parts.append(f"{value}{style.value_suffix}")
        header = " ".join(header_parts).strip()
        percent_line = ""
        if style.show_percent:
            digits = max(0, min(6, int(style.percent_decimals)))
            percent_line = f"{percent:.{digits}f}%"
        lines = [part for part in (header, percent_line) if part]
        return "\n".join(lines)

    def _min_gap(self) -> float:
        style = self.style
        lines = 1 + int(bool(style.show_percent)) + 0 * int(bool(style.show_name))
        # Convert points to data units so the gap tracks the font size.
        data_per_point = 2.40 / (float(style.figure_height) * 0.82 * 72.0)
        gap = (lines * 1.28 - 0.18) * float(style.label_font_size) * data_per_point
        return max(0.10, min(0.42, gap))

    def _create_labels(self) -> None:
        style = self.style
        min_gap = self._min_gap()
        side_items: dict[int, list[dict[str, object]]] = {-1: [], 1: []}
        for item in getattr(self, "_pending", []):
            side = 1 if float(item["direction_x"]) >= 0.0 else -1
            side_items[side].append(item)

        for side, items in side_items.items():
            self._spread_side(items, min_gap)

        self.axis.set_xlim(-1.72, 1.72)
        self.axis.set_ylim(-1.22, 1.18)

        for item in getattr(self, "_pending", []):
            label = str(item["label"])
            direction_x = float(item["direction_x"])
            direction_y = float(item["direction_y"])
            side = 1 if direction_x >= 0.0 else -1
            anchor_x = float(item["anchor_x"])
            anchor_y = float(item["anchor_y"])
            label_y = float(item.get("label_y", anchor_y))
            extension = (0.15 if side > 0 else 0.65) * float(style.label_wire_scale)
            elbow_x = anchor_x + direction_x * extension
            line_end_x = elbow_x + side * 0.35 * float(style.label_wire_scale)
            line_end_x = min(1.42, line_end_x) if side > 0 else max(-1.42, line_end_x)
            percent = float(item["value"]) / self.total * 100.0
            fill_color = self.spec.fill_colors.get(label, "#CCCCCC")
            color = self.spec.label_colors.get(label, fill_color)
            handle = LabelHandle(
                label=label,
                value=int(item["value"]),
                percent=percent,
                side=side,
                direction_x=direction_x,
                direction_y=direction_y,
                anchor_x=anchor_x,
                anchor_y=anchor_y,
                auto_y=label_y,
                auto_line_end_x=line_end_x,
                y=label_y,
                line_end_x=line_end_x,
                color=color,
                elbow_x=elbow_x,
            )
            self.handles[label] = handle
            self._create_artist(handle)
        self._pending = []

    def _spread_side(self, items: list[dict[str, object]], min_gap: float) -> None:
        if not items:
            return
        for item in items:
            direction_y = float(item["direction_y"])
            outer_radius = float(item["outer_radius"])
            item["desired_y"] = -0.05 + direction_y * (outer_radius + 0.10)

        ordered = sorted(items, key=lambda item: float(item["desired_y"]))
        positions: list[float] = []
        for item in ordered:
            desired = float(item["desired_y"])
            if positions:
                positions.append(max(desired, positions[-1] + min_gap))
            else:
                positions.append(desired)
        lower, upper = -1.06, 1.02
        if positions[-1] > upper:
            shift = positions[-1] - upper
            positions = [position - shift for position in positions]
        for index in range(len(positions) - 2, -1, -1):
            positions[index] = min(positions[index], positions[index + 1] - min_gap)
        if positions[0] < lower:
            shift = lower - positions[0]
            positions = [position + shift for position in positions]
            overflow = positions[-1] - upper
            if overflow > 0:
                positions = [position - overflow for position in positions]
        for item, position in zip(ordered, positions):
            item["label_y"] = position

    def _create_artist(self, handle: LabelHandle) -> None:
        style = self.style
        # White underlay keeps the leader line visible over the checkerboard.
        self.axis.plot(
            [handle.anchor_x, handle.elbow_x, handle.line_end_x],
            [handle.anchor_y, handle.y, handle.y],
            color="#FFFFFF",
            linewidth=float(style.label_line_width) + 1.6,
            solid_capstyle="round",
            zorder=4,
        )
        line, = self.axis.plot(
            [handle.anchor_x, handle.elbow_x, handle.line_end_x],
            [handle.anchor_y, handle.y, handle.y],
            color=handle.color,
            linewidth=float(style.label_line_width),
            solid_capstyle="round",
            zorder=5,
        )
        text_x = handle.line_end_x + handle.side * float(style.label_text_gap)
        text = self.axis.text(
            text_x,
            handle.y,
            self._label_text(handle.label, handle.value, handle.percent),
            ha="left" if handle.side > 0 else "right",
            va="center",
            multialignment="center",
            fontsize=float(style.label_font_size),
            fontweight="bold",
            color=handle.color,
            linespacing=0.92,
            fontfamily=self.font_family,
            zorder=6,
            picker=True,
        )
        # A soft white halo keeps labels readable if the user drags them over a
        # dark sector; on the usual white background it is invisible.
        text.set_path_effects(
            [path_effects.withStroke(linewidth=1.4, foreground="#FFFFFF")]
        )
        handle.line = line
        handle.text = text
        handle.text_x = text_x

    def _apply_auto_layout(self) -> None:
        for handle in self.handles.values():
            self._update_artist(handle)

    def _update_artist(self, handle: LabelHandle) -> None:
        style = self.style
        extension = (0.15 if handle.side > 0 else 0.65) * float(style.label_wire_scale)
        handle.elbow_x = handle.anchor_x + handle.direction_x * extension
        handle.text_x = handle.line_end_x + handle.side * float(style.label_text_gap)
        handle.line.set_data(
            [handle.anchor_x, handle.elbow_x, handle.line_end_x],
            [handle.anchor_y, handle.y, handle.y],
        )
        handle.text.set_position((handle.text_x, handle.y))
        try:
            self.refresh_label_backplates()
        except Exception:
            pass

    # -- public label API -------------------------------------------------

    def set_label_position(self, label: str, *, y: float, line_end_x: float) -> None:
        handle = self.handles.get(label)
        if handle is None:
            return
        handle.y = max(-1.16, min(1.14, float(y)))
        handle.line_end_x = max(-1.46, min(1.46, float(line_end_x)))
        self._update_artist(handle)

    def move_label_delta(self, label: str, *, dy: float = 0.0, dx: float = 0.0) -> None:
        handle = self.handles.get(label)
        if handle is None:
            return
        self.set_label_position(
            label, y=handle.y + dy, line_end_x=handle.line_end_x + dx
        )

    def reset_label(self, label: str) -> None:
        handle = self.handles.get(label)
        if handle is None:
            return
        handle.y = handle.auto_y
        handle.line_end_x = handle.auto_line_end_x
        self._update_artist(handle)

    def reset_all_labels(self) -> None:
        for handle in self.handles.values():
            handle.y = handle.auto_y
            handle.line_end_x = handle.auto_line_end_x
            self._update_artist(handle)

    def layout_offsets(self) -> dict[str, tuple[float, float]]:
        return {
            label: handle.offset()
            for label, handle in self.handles.items()
            if abs(handle.offset()[0]) > 1e-4 or abs(handle.offset()[1]) > 1e-4
        }

    def apply_layout_offsets(self, offsets: Mapping[str, Sequence[float]]) -> None:
        for label, offset in offsets.items():
            handle = self.handles.get(label)
            if handle is None:
                continue
            try:
                dx, dy = float(offset[0]), float(offset[1])
            except (TypeError, ValueError, IndexError):
                continue
            self.set_label_position(
                label,
                y=handle.auto_y + dy,
                line_end_x=handle.auto_line_end_x + dx,
            )

    def auto_positions(self) -> dict[str, tuple[float, float]]:
        return {
            label: (handle.auto_line_end_x, handle.auto_y)
            for label, handle in self.handles.items()
        }

    # -- hit testing ------------------------------------------------------

    def hit_test(self, x: float, y: float, renderer, pad: float = 8.0) -> LabelHandle | None:
        """Return the label under a display-coordinate point, or ``None``."""
        best: LabelHandle | None = None
        best_distance = float("inf")
        for handle in self.handles.values():
            text = handle.text
            if text is None:
                continue
            try:
                bbox = text.get_window_extent(renderer=renderer)
            except Exception:
                continue
            if (
                bbox.x0 - pad <= x <= bbox.x1 + pad
                and bbox.y0 - pad <= y <= bbox.y1 + pad
            ):
                return handle
            segment_x = self.axis.transData.transform(
                [
                    [handle.elbow_x, handle.y],
                    [handle.line_end_x, handle.y],
                ]
            )
            distance = _point_segment_distance(
                x,
                y,
                segment_x[0][0],
                segment_x[0][1],
                segment_x[1][0],
                segment_x[1][1],
            )
            if distance < min(best_distance, pad * 2.0):
                best_distance = distance
                best = handle
        return best

    def fit_labels_inside(self, margin_px: float = 3.0) -> bool:
        """Nudge label anchors so long label text stays inside the plot area."""
        try:
            renderer = self.figure.canvas.get_renderer()
        except Exception:
            return False
        if renderer is None:
            return False
        try:
            axes_bbox = self.axis.get_window_extent(renderer=renderer)
        except Exception:
            return False
        if axes_bbox.width <= 0:
            return False
        data_per_px = 3.44 / axes_bbox.width
        changed = False
        for handle in self.handles.values():
            for _ in range(8):
                try:
                    bbox = handle.text.get_window_extent(renderer=renderer)
                except Exception:
                    break
                if handle.side > 0:
                    overflow = bbox.x1 - (axes_bbox.x1 - margin_px)
                else:
                    overflow = (axes_bbox.x0 + margin_px) - bbox.x0
                if overflow <= 0.5:
                    break
                shift = overflow * data_per_px + 0.008
                new_x = handle.line_end_x - handle.side * shift
                if handle.side > 0:
                    new_x = max(new_x, handle.elbow_x - 0.28)
                else:
                    new_x = min(new_x, handle.elbow_x + 0.28)
                new_x = max(-1.46, min(1.46, new_x))
                delta = new_x - handle.line_end_x
                if abs(delta) < 1e-4:
                    break
                handle.line_end_x = new_x
                handle.auto_line_end_x += delta
                self._update_artist(handle)
                changed = True
        return changed

    def refresh_label_backplates(self) -> None:
        """Add a soft white plate behind labels that sit on top of a sector."""
        try:
            renderer = self.figure.canvas.get_renderer()
        except Exception:
            return
        if renderer is None or not self._sector_paths:
            return
        inverse = self.axis.transData.inverted()
        for handle in self.handles.values():
            text = handle.text
            if text is None:
                continue
            try:
                bbox = text.get_window_extent(renderer=renderer)
            except Exception:
                continue
            points = (
                ((bbox.x0 + bbox.x1) / 2.0, (bbox.y0 + bbox.y1) / 2.0),
                (bbox.x0, bbox.y0),
                (bbox.x1, bbox.y0),
                (bbox.x0, bbox.y1),
                (bbox.x1, bbox.y1),
            )
            covered = False
            for x_px, y_px in points:
                try:
                    data_x, data_y = inverse.transform((x_px, y_px))
                except Exception:
                    continue
                if any(path.contains_point((data_x, data_y)) for path in self._sector_paths):
                    covered = True
                    break
            try:
                text.set_bbox(
                    dict(
                        boxstyle="round,pad=0.22",
                        facecolor="#FFFFFF",
                        alpha=0.82,
                        edgecolor="none",
                    )
                    if covered
                    else None
                )
            except Exception:
                pass

    def set_hover(self, handle: LabelHandle | None) -> None:
        for item in self.handles.values():
            is_active = item is handle
            try:
                item.text.set_fontsize(
                    float(self.style.label_font_size) + (1.5 if is_active else 0.0)
                )
                item.line.set_linewidth(
                    float(self.style.label_line_width) * (2.4 if is_active else 1.0)
                )
            except Exception:
                continue

    # -- export -----------------------------------------------------------

    def export(
        self,
        path: str | Path,
        *,
        width: int | None = None,
        height: int | None = None,
        dpi: int | None = None,
        transparent: bool | None = None,
        fmt: str | None = None,
        layout: Mapping[str, Sequence[float]] | None = None,
    ) -> Path:
        return export_chart(
            self.spec,
            path,
            width=width,
            height=height,
            dpi=dpi,
            transparent=transparent,
            fmt=fmt,
            layout=layout,
        )


def _point_segment_distance(
    px: float, py: float, x1: float, y1: float, x2: float, y2: float
) -> float:
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


# ---------------------------------------------------------------------------
# Convenience builders
# ---------------------------------------------------------------------------


def build_spec(
    labels: Iterable[str],
    values: Iterable[int],
    style: StyleConfig,
    *,
    fill_colors: Mapping[str, str] | None = None,
    label_colors: Mapping[str, str] | None = None,
    order: Sequence[str] | None = None,
) -> ChartSpec:
    return ChartSpec(
        labels=[str(label) for label in labels],
        values=[int(value) for value in values],
        style=style.copy(),
        fill_colors=dict(fill_colors or {}),
        label_colors=dict(label_colors or {}),
        order=list(order) if order else None,
    )


def _prepare_export_style(
    spec: ChartSpec,
    *,
    width: int | None = None,
    height: int | None = None,
    dpi: int | None = None,
) -> tuple[StyleConfig, int, bool]:
    style = spec.style.copy()
    export_dpi = int(dpi or style.dpi or 100)
    if width and height:
        style.figure_width = float(width) / export_dpi
        style.figure_height = float(height) / export_dpi
    elif width:
        ratio = style.figure_height / style.figure_width
        style.figure_width = float(width) / export_dpi
        style.figure_height = style.figure_width * ratio
    elif height:
        ratio = style.figure_width / style.figure_height
        style.figure_height = float(height) / export_dpi
        style.figure_width = style.figure_height * ratio
    transparent = style.background == TRANSPARENT
    return style, export_dpi, transparent


def render_bytes(
    spec: ChartSpec,
    *,
    width: int | None = None,
    height: int | None = None,
    dpi: int | None = None,
    transparent: bool | None = None,
    fmt: str = "png",
    layout: Mapping[str, Sequence[float]] | None = None,
) -> bytes:
    """Render the chart and return the encoded image bytes."""
    import io

    style, export_dpi, default_transparent = _prepare_export_style(
        spec, width=width, height=height, dpi=dpi
    )
    chart_spec = replace(spec, style=style)
    figure = Figure(figsize=(style.figure_width, style.figure_height))
    FigureCanvasAgg(figure)
    chart = RoseChart(chart_spec, figure, preview=False)
    if layout:
        chart.apply_layout_offsets(layout)
    chart.refresh_label_backplates()
    is_transparent = default_transparent if transparent is None else bool(transparent)
    save_kwargs: dict[str, object] = {
        "format": fmt,
        "dpi": export_dpi,
        "transparent": is_transparent,
    }
    if not is_transparent and style.background and style.background != TRANSPARENT:
        save_kwargs["facecolor"] = style.background
    buffer = io.BytesIO()
    figure.savefig(buffer, **save_kwargs)
    figure.clear()
    return buffer.getvalue()


def export_chart(
    spec: ChartSpec,
    path: str | Path,
    *,
    width: int | None = None,
    height: int | None = None,
    dpi: int | None = None,
    transparent: bool | None = None,
    fmt: str | None = None,
    layout: Mapping[str, Sequence[float]] | None = None,
) -> Path:
    """Render ``spec`` at export quality and write it to ``path``."""
    path = Path(path)
    suffix = (fmt or path.suffix.lstrip(".") or "png").lower()
    data = render_bytes(
        spec,
        width=width,
        height=height,
        dpi=dpi,
        transparent=transparent,
        fmt=suffix,
        layout=layout,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path

"""生成色板视觉联系表 ``palettes_contact.png``（QA 产物，可重复生成）。

运行方式::

    rose\\.venv\\python.exe rose\\_qa\\palettes\\build_contact_sheet.py

联系表内容：每套色板一张卡片，包含——
* 色块条（图表扇区填充色）；
* 色板名称 / id / 分组徽标；
* 每个色块对应的 auto 标签色：在白底上用该颜色绘制 hex 文本，
  下方标注实际 WCAG 对比度；
* 卡片脚注：该色板 auto 标签色的最低对比度与标签。

只用 matplotlib 绘制，不依赖网络；输出固定写在脚本同目录。
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ROSE_ROOT = Path(__file__).resolve().parents[2]
if str(ROSE_ROOT) not in sys.path:
    sys.path.insert(0, str(ROSE_ROOT))

from rosechart.palettes import (  # noqa: E402
    PALETTES,
    label_color,
    contrast_ratio,
    mix_colors,
    darken,
    palettes_by_group,
)

OUTPUT_PATH = Path(__file__).with_name("palettes_contact.png")

# ---------------------------------------------------------------------------
# 视觉常量
# ---------------------------------------------------------------------------

PAGE_BG = "#F4F7FB"
CARD_BG = "#FFFFFF"
CARD_BORDER = "#E3E9F1"
INK = "#0F172A"
MUTED = "#64748B"
FAINT = "#94A3B8"
SEPARATOR = "#EDF2F7"

GROUP_ACCENTS = {
    "原版": "#0F766E",
    "商务": "#1F3A5F",
    "科技": "#1B6CFF",
    "莫兰迪": "#8E8A85",
    "马卡龙": "#E36A8C",
    "自然": "#4E7C49",
    "高对比": "#D7263D",
    "极简": "#374151",
    "活力": "#FF9F1C",
    "中国风": "#9D2933",
}

COLUMNS = 4
GAP_X = 0.30
GAP_Y = 0.30
MARGIN = 0.55
CARD_W = (19.4 - 2 * MARGIN - (COLUMNS - 1) * GAP_X) / COLUMNS
CARD_H = 2.70
HEADER_H = 2.10
FOOTER_H = 0.68


def _accent(group: str) -> str:
    return GROUP_ACCENTS.get(group, "#0F766E")


def _font_setup() -> None:
    candidates = [
        "Microsoft YaHei",
        "Noto Sans SC",
        "SimHei",
        "Source Han Sans SC",
        "DejaVu Sans",
    ]
    installed = {font.name for font in matplotlib.font_manager.fontManager.ttflist}
    chosen = [name for name in candidates if name in installed] or ["DejaVu Sans"]
    plt.rcParams["font.sans-serif"] = chosen
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["axes.unicode_minus"] = False


def _rounded(
    ax,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    facecolor: str,
    edgecolor: str = "none",
    linewidth: float = 0.0,
    radius: float = 0.10,
    zorder: float = 2.0,
):
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle=f"round,pad=0,rounding_size={min(radius, width / 2, height / 2)}",
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=linewidth,
        zorder=zorder,
    )
    ax.add_patch(patch)
    return patch


def _pill_width(text: str, font_size: float = 9.0) -> float:
    """根据字符数粗估胶囊宽度（英寸）。"""
    width = 0.0
    for char in text:
        width += font_size / 72.0 if ord(char) > 0x2E80 else font_size / 72.0 * 0.58
    return width + 0.28


def _draw_header(ax, total_width: float, total_height: float, margin: float) -> None:
    ax.text(
        margin,
        total_height - 0.58,
        "RoseChart Studio · 色板联系表",
        ha="left",
        va="top",
        fontsize=24,
        fontweight="bold",
        color=INK,
    )
    ax.text(
        margin,
        total_height - 1.10,
        "内置色板分组展示：色块 = 图表扇区填充色；白底彩色 hex 文本 = label_color(auto) 自动标签色；"
        "每组均标注实际 WCAG 对比度。",
        ha="left",
        va="top",
        fontsize=10.3,
        color=MUTED,
    )
    ax.text(
        margin,
        total_height - 1.48,
        "标签色规则：填充色相对白底对比度 ≥ 3.0 时直接沿用填充色，否则保持色相自动加深到 3.2:1 目标；"
        "白底 / 透明底导出均可安全使用。",
        ha="left",
        va="top",
        fontsize=9.4,
        color=FAINT,
    )

    badge_text = f"{len(PALETTES)} 套色板 · {len(palettes_by_group())} 个分组"
    badge_width = 2.55
    badge_x = total_width - margin - badge_width
    badge_y = total_height - 0.96
    _rounded(
        ax,
        badge_x,
        badge_y,
        badge_width,
        0.46,
        facecolor="#0F766E",
        radius=0.23,
        zorder=2.0,
    )
    ax.text(
        badge_x + badge_width / 2,
        badge_y + 0.23,
        badge_text,
        ha="center",
        va="center",
        fontsize=10.5,
        fontweight="bold",
        color="#FFFFFF",
    )


def _draw_card(
    ax,
    palette,
    x: float,
    top: float,
    width: float,
    height: float,
) -> None:
    accent = _accent(palette.group)
    left = x
    bottom = top - height

    # 卡片阴影 + 卡片主体
    _rounded(
        ax,
        left + 0.035,
        bottom - 0.045,
        width,
        height,
        facecolor="#DEE6F0",
        edgecolor="none",
        radius=0.17,
        zorder=1.0,
    )
    border_color = accent if palette.id.startswith("legacy_") else CARD_BORDER
    border_width = 1.8 if palette.id.startswith("legacy_") else 1.0
    _rounded(
        ax,
        left,
        bottom,
        width,
        height,
        facecolor=CARD_BG,
        edgecolor=border_color,
        linewidth=border_width,
        radius=0.17,
        zorder=2.0,
    )

    # 顶部标题：分组色条 + 色板名
    _rounded(
        ax,
        left + 0.24,
        top - 0.52,
        0.09,
        0.36,
        facecolor=accent,
        edgecolor="none",
        radius=0.045,
        zorder=3.0,
    )
    ax.text(
        left + 0.43,
        top - 0.17,
        palette.name,
        ha="left",
        va="top",
        fontsize=12.6,
        fontweight="bold",
        color=INK,
        zorder=3.0,
    )
    ax.text(
        left + 0.43,
        top - 0.52,
        palette.id,
        ha="left",
        va="top",
        fontsize=8.0,
        fontfamily="DejaVu Sans Mono",
        color=MUTED,
        zorder=3.0,
    )

    # 分组胶囊（右对齐）
    pill_width = max(0.62, _pill_width(palette.group, 8.8))
    pill_height = 0.31
    pill_x = left + width - 0.24 - pill_width
    pill_y = top - 0.53
    pill_bg = mix_colors(accent, "#FFFFFF", 0.86)
    pill_fg = darken(accent, 0.30)
    _rounded(
        ax,
        pill_x,
        pill_y,
        pill_width,
        pill_height,
        facecolor=pill_bg,
        edgecolor="none",
        radius=pill_height / 2,
        zorder=3.0,
    )
    ax.text(
        pill_x + pill_width / 2,
        pill_y + pill_height / 2 - 0.005,
        f"分组 · {palette.group}",
        ha="center",
        va="center",
        fontsize=8.8,
        fontweight="bold",
        color=pill_fg,
        zorder=3.1,
    )

    # 标题分隔线
    ax.plot(
        [left + 0.24, left + width - 0.24],
        [top - 0.70, top - 0.70],
        color=SEPARATOR,
        linewidth=0.9,
        zorder=3.0,
    )

    # 色块条
    swatch_top = top - 0.86
    swatch_height = 0.64
    count = len(palette.colors)
    inner_width = width - 0.48
    swatch_gap = 0.055
    swatch_width = (inner_width - (count - 1) * swatch_gap) / count
    for index, fill in enumerate(palette.colors):
        swatch_x = left + 0.24 + index * (swatch_width + swatch_gap)
        _rounded(
            ax,
            swatch_x,
            swatch_top - swatch_height,
            swatch_width,
            swatch_height,
            facecolor=fill,
            edgecolor=darken(fill, 0.10) if contrast_ratio(fill, "#FFFFFF") < 1.35 else "none",
            linewidth=0.6,
            radius=0.075,
            zorder=3.0,
        )

        # auto 标签色示例（白底上绘制 hex 文本）
        label = label_color(fill, background="#FFFFFF")
        ratio = contrast_ratio(label, "#FFFFFF")
        center_x = swatch_x + swatch_width / 2
        ax.text(
            center_x,
            swatch_top - swatch_height - 0.19,
            label,
            ha="center",
            va="center",
            fontsize=7.3 if count >= 6 else 8.6,
            fontfamily="DejaVu Sans Mono",
            color=label,
            zorder=3.0,
        )
        ax.text(
            center_x,
            swatch_top - swatch_height - 0.40,
            f"{ratio:.2f}:1",
            ha="center",
            va="center",
            fontsize=6.4 if count >= 6 else 7.5,
            color="#8B98A8",
            zorder=3.0,
        )

    # 卡片脚注
    min_ratio = min(
        contrast_ratio(label_color(color, background="#FFFFFF"), "#FFFFFF")
        for color in palette.colors
    )
    note = f"auto 标签最低对比 {min_ratio:.2f}:1"
    if palette.id.startswith("legacy_"):
        note = "含固定标签映射 · " + note
    ax.text(
        left + 0.24,
        bottom + 0.22,
        note,
        ha="left",
        va="center",
        fontsize=7.2,
        color=MUTED,
        zorder=3.0,
    )
    tag_text = " · ".join(palette.tags[:2]) if palette.tags else ""
    if tag_text:
        ax.text(
            left + width - 0.24,
            bottom + 0.22,
            tag_text,
            ha="right",
            va="center",
            fontsize=7.0,
            color=FAINT,
            zorder=3.0,
        )


def build_contact_sheet(output_path: Path = OUTPUT_PATH) -> Path:
    _font_setup()

    cards = [
        palette
        for _group, palettes in palettes_by_group().items()
        for palette in palettes
    ]
    rows = (len(cards) + COLUMNS - 1) // COLUMNS
    total_width = 2 * MARGIN + COLUMNS * CARD_W + (COLUMNS - 1) * GAP_X
    total_height = (
        HEADER_H + rows * CARD_H + (rows - 1) * GAP_Y + FOOTER_H
    )

    figure = plt.figure(figsize=(total_width, total_height), facecolor=PAGE_BG)
    axes = figure.add_axes([0.0, 0.0, 1.0, 1.0])
    axes.set_xlim(0.0, total_width)
    axes.set_ylim(0.0, total_height)
    axes.set_axis_off()
    axes.set_facecolor(PAGE_BG)

    _draw_header(axes, total_width, total_height, MARGIN)

    for index, palette in enumerate(cards):
        row = index // COLUMNS
        column = index % COLUMNS
        x = MARGIN + column * (CARD_W + GAP_X)
        top = total_height - HEADER_H - row * (CARD_H + GAP_Y)
        _draw_card(
            axes,
            palette,
            x,
            top,
            CARD_W,
            CARD_H,
        )

    # 页脚说明
    footer_y = 0.42
    axes.plot(
        [MARGIN, total_width - MARGIN],
        [footer_y + 0.24, footer_y + 0.24],
        color=SEPARATOR,
        linewidth=0.9,
        zorder=1.0,
    )
    axes.text(
        MARGIN,
        footer_y,
        "生成脚本：rose/_qa/palettes/build_contact_sheet.py　·　色板模块：rose/rosechart/palettes.py"
        "　·　自测：rose/tests/test_palettes.py（全部断言通过）",
        ha="left",
        va="center",
        fontsize=8.0,
        color=FAINT,
    )
    axes.text(
        total_width - MARGIN,
        footer_y,
        "WCAG 2.1 对比度 · auto 标签色目标 3.2:1 · 白底 / 透明底通用",
        ha="right",
        va="center",
        fontsize=8.0,
        color=FAINT,
    )

    figure.savefig(
        output_path,
        dpi=140,
        facecolor=PAGE_BG,
        edgecolor="none",
    )
    plt.close(figure)
    return output_path


def main() -> int:
    output = build_contact_sheet()
    print(f"[contact] palettes={len(PALETTES)} rows={(len(PALETTES)+COLUMNS-1)//COLUMNS}")
    print(f"[contact] written: {output}")
    print(f"[contact] size: {output.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

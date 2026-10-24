"""RoseChart Studio 色板库（palette library）。

模块职责：

* 内置 16 套经过调校的图表色板（:class:`Palette`），覆盖
  「原版 / 商务 / 科技 / 莫兰迪 / 马卡龙 / 自然 / 高对比 / 极简 / 活力 / 中国风」
  十个分组，每套色板都适配白底与透明底导出到浅色幻灯片；
* 标签 -> 颜色的确定性分配（:func:`assign_colors`）；
* 任意背景上可读的标签文字颜色推导（:func:`label_color`，含 WCAG 对比度保障）；
* 按标签数量推荐合适色板（:func:`recommend_palettes`，确定性排序）；
* 一组不依赖第三方库的十六进制 / RGB / HSL / WCAG / CIELAB 工具函数。

本模块只使用 Python 标准库，可被 GUI、渲染脚本或测试脚本直接导入，
不会在导入时做任何 I/O 或修改全局状态。

约定：所有对外返回的颜色字符串均为大写 ``#RRGGBB``。
"""

from __future__ import annotations

import colorsys
import math
import re
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

__all__ = [
    "Palette",
    "PALETTES",
    "GROUP_ORDER",
    "DEFAULT_LABEL_COLOR",
    "DEFAULT_BACKGROUND",
    "LABEL_MIN_CONTRAST",
    "palette_by_id",
    "palettes_by_group",
    "assign_colors",
    "label_color",
    "recommend_palettes",
    "palette_scores",
    "contrast_ratio",
    "luminance",
    "hex_to_rgb",
    "rgb_to_hex",
    "normalize_hex",
    "is_hex_color",
    "mix_colors",
    "darken",
    "lighten",
    "rgb_to_hsl",
    "hsl_to_hex",
    "delta_e",
]

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

DEFAULT_LABEL_COLOR = "#334155"
DEFAULT_BACKGROUND = "#FFFFFF"

#: 图表标签（文字）相对背景需要达到的最小 WCAG 对比度。
LABEL_MIN_CONTRAST = 3.0

#: 内部推导标签色时的目标对比度，比 3.0 略高，给 8bit 取整留出余量。
_LABEL_TARGET_CONTRAST = 3.2

#: 色板分组的展示顺序（UI 下拉框 / 联系表按此顺序排列）。
GROUP_ORDER: tuple[str, ...] = (
    "原版",
    "商务",
    "科技",
    "莫兰迪",
    "马卡龙",
    "自然",
    "高对比",
    "极简",
    "活力",
    "中国风",
)

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

_XYZ_WHITE = (0.95047, 1.0, 1.08883)
_LAB_EPSILON = 216.0 / 24389.0  # (6/29)^3
_LAB_KAPPA = 24389.0 / 27.0  # (29/3)^3


# ---------------------------------------------------------------------------
# 基础颜色工具
# ---------------------------------------------------------------------------


def normalize_hex(value: str) -> str:
    """把颜色规范化为 ``#RRGGBB``（大写）。

    支持 ``#aabbcc``、``aabbcc``、``#abc``、``abc`` 等写法；
    非法输入抛出 :class:`ValueError`，非字符串抛出 :class:`TypeError`。
    """

    if not isinstance(value, str):
        raise TypeError(f"颜色必须是字符串，收到 {type(value).__name__}")
    text = value.strip()
    match = _HEX_RE.match(text)
    if match is None:
        raise ValueError(f"不是合法的十六进制颜色：{value!r}")
    digits = match.group(1)
    if len(digits) == 3:
        digits = "".join(ch * 2 for ch in digits)
    return "#" + digits.upper()


def is_hex_color(value: object) -> bool:
    """判断 ``value`` 是否是可解析的十六进制颜色字符串。"""

    try:
        normalize_hex(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return True


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    """``#RRGGBB`` -> ``(r, g, b)``，每个通道为 0–255 的整数。"""

    text = normalize_hex(color)
    return (
        int(text[1:3], 16),
        int(text[3:5], 16),
        int(text[5:7], 16),
    )


def rgb_to_hex(rgb: Sequence[float]) -> str:
    """``(r, g, b)`` -> ``#RRGGBB``；通道会四舍五入并裁剪到 0–255。"""

    components = tuple(rgb)
    if len(components) != 3:
        raise ValueError(f"rgb 必须是 3 个通道，收到 {len(components)} 个")
    channels: list[int] = []
    for component in components:
        channel = int(round(float(component)))
        channels.append(min(255, max(0, channel)))
    return "#{:02X}{:02X}{:02X}".format(*channels)


def _linearize(channel: int) -> float:
    """sRGB 通道 -> 线性光通道（WCAG 定义）。"""

    value = channel / 255.0
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def _delinearize(value: float) -> float:
    """线性光通道 -> sRGB 通道，返回 0–1。"""

    clamped = min(1.0, max(0.0, value))
    if clamped <= 0.0031308:
        return clamped * 12.92
    return 1.055 * (clamped ** (1.0 / 2.4)) - 0.055


def luminance(color: str) -> float:
    """返回 WCAG 相对亮度（0.0–1.0）。"""

    red, green, blue = hex_to_rgb(color)
    return (
        0.2126 * _linearize(red)
        + 0.7152 * _linearize(green)
        + 0.0722 * _linearize(blue)
    )


def contrast_ratio(color_a: str, color_b: str) -> float:
    """返回两色的 WCAG 对比度（1.0–21.0，顺序无关）。"""

    luminance_a = luminance(color_a)
    luminance_b = luminance(color_b)
    lighter = max(luminance_a, luminance_b)
    darker = min(luminance_a, luminance_b)
    return (lighter + 0.05) / (darker + 0.05)


def mix_colors(color_a: str, color_b: str, weight: float = 0.5) -> str:
    """在线性光空间按 ``weight`` 比例混合两色（0 -> a，1 -> b）。

    在线性光空间混合比直接插值 sRGB 更接近真实颜料/光线的过渡，
    中间色不会发灰。
    """

    try:
        amount = float(weight)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"weight 必须是数字，收到 {weight!r}") from exc
    if not 0.0 <= amount <= 1.0:
        raise ValueError(f"weight 必须在 0–1 之间，收到 {weight!r}")

    rgb_a = hex_to_rgb(color_a)
    rgb_b = hex_to_rgb(color_b)
    mixed: list[int] = []
    for channel_a, channel_b in zip(rgb_a, rgb_b):
        linear = (1.0 - amount) * _linearize(channel_a) + amount * _linearize(
            channel_b
        )
        mixed.append(int(round(_delinearize(linear) * 255.0)))
    return rgb_to_hex(mixed)


def rgb_to_hsl(color: str) -> tuple[float, float, float]:
    """``#RRGGBB`` -> ``(hue_度, saturation, lightness)``，后两者为 0–1。"""

    red, green, blue = hex_to_rgb(color)
    hue, lightness, saturation = colorsys.rgb_to_hls(
        red / 255.0, green / 255.0, blue / 255.0
    )
    return (hue * 360.0, saturation, lightness)


def hsl_to_hex(hue: float, saturation: float, lightness: float) -> str:
    """``(hue_度, saturation, lightness)`` -> ``#RRGGBB``。"""

    normalized_hue = (float(hue) % 360.0) / 360.0
    clamped_saturation = min(1.0, max(0.0, float(saturation)))
    clamped_lightness = min(1.0, max(0.0, float(lightness)))
    red, green, blue = colorsys.hls_to_rgb(
        normalized_hue, clamped_lightness, clamped_saturation
    )
    return rgb_to_hex((red * 255.0, green * 255.0, blue * 255.0))


def _clamp_amount(amount: float) -> float:
    try:
        value = float(amount)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"amount 必须是数字，收到 {amount!r}") from exc
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"amount 必须在 0–1 之间，收到 {amount!r}")
    return value


def darken(color: str, amount: float = 0.15) -> str:
    """保持色相与饱和度，把 HSL 亮度降低 ``amount`` 比例（0–1）。"""

    hue, saturation, lightness = rgb_to_hsl(color)
    return hsl_to_hex(hue, saturation, lightness * (1.0 - _clamp_amount(amount)))


def lighten(color: str, amount: float = 0.15) -> str:
    """保持色相与饱和度，把 HSL 亮度向 1.0 提升 ``amount`` 比例（0–1）。"""

    hue, saturation, lightness = rgb_to_hsl(color)
    level = _clamp_amount(amount)
    return hsl_to_hex(hue, saturation, lightness + (1.0 - lightness) * level)


def delta_e(color_a: str, color_b: str) -> float:
    """返回两色的 CIELAB ΔE76 色差（越大越好区分；约 2.3 为刚可察觉）。"""

    lab_a = _hex_to_lab(color_a)
    lab_b = _hex_to_lab(color_b)
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(lab_a, lab_b)))


def _hex_to_lab(color: str) -> tuple[float, float, float]:
    red, green, blue = hex_to_rgb(color)
    linear_r = _linearize(red)
    linear_g = _linearize(green)
    linear_b = _linearize(blue)

    x = 0.4124564 * linear_r + 0.3575761 * linear_g + 0.1804375 * linear_b
    y = 0.2126729 * linear_r + 0.7151522 * linear_g + 0.0721750 * linear_b
    z = 0.0193339 * linear_r + 0.1191920 * linear_g + 0.9503041 * linear_b

    fx = _lab_f(x / _XYZ_WHITE[0])
    fy = _lab_f(y / _XYZ_WHITE[1])
    fz = _lab_f(z / _XYZ_WHITE[2])
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


def _lab_f(value: float) -> float:
    if value > _LAB_EPSILON:
        return max(value, 0.0) ** (1.0 / 3.0)
    return (_LAB_KAPPA * value + 16.0) / 116.0


# ---------------------------------------------------------------------------
# 色板数据模型
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Palette:
    """一套命名的图表色板。

    Attributes:
        id: 稳定英文标识（小写蛇形），用于持久化与查找。
        name: 中文展示名。
        group: 所属分组，见 :data:`GROUP_ORDER`。
        colors: 图表填充色序列，均已规范化为 ``#RRGGBB``。
        tags: 便于检索/筛选的标签。
        description: 一句话说明适用场景。
        named_colors: 可选的「标签 -> 固定颜色」映射（原版色板用于保持旧映射）。
    """

    id: str
    name: str
    group: str
    colors: tuple[str, ...]
    tags: tuple[str, ...] = ()
    description: str = ""
    named_colors: Mapping[str, str] | None = field(
        default=None, compare=False, hash=False
    )

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("Palette.id 必须是非空字符串")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError(f"Palette({self.id!r}).name 必须是非空字符串")
        if not isinstance(self.group, str) or not self.group.strip():
            raise ValueError(f"Palette({self.id!r}).group 必须是非空字符串")

        colors = tuple(normalize_hex(color) for color in self.colors)
        if not colors:
            raise ValueError(f"Palette({self.id!r}).colors 不能为空")
        object.__setattr__(self, "colors", colors)
        object.__setattr__(self, "tags", tuple(str(tag) for tag in self.tags))

        if self.named_colors is not None:
            named: dict[str, str] = {}
            for label, color in self.named_colors.items():
                if not isinstance(label, str):
                    raise TypeError(
                        f"Palette({self.id!r}).named_colors 的键必须是字符串"
                    )
                named[label] = normalize_hex(color)
            object.__setattr__(self, "named_colors", named)


def _palette(
    palette_id: str,
    name: str,
    group: str,
    colors: Sequence[str],
    *,
    tags: Sequence[str] = (),
    description: str = "",
    named_colors: Mapping[str, str] | None = None,
) -> Palette:
    """内部构造辅助函数，减少 16 套色板字面量中的重复参数。"""

    return Palette(
        id=palette_id,
        name=name,
        group=group,
        colors=tuple(colors),
        tags=tuple(tags),
        description=description,
        named_colors=named_colors,
    )


# ---------------------------------------------------------------------------
# 内置色板（16 套 / 10 个分组）
# ---------------------------------------------------------------------------

PALETTES: tuple[Palette, ...] = (
    # ---- 原版：与旧版 render_charts.py 完全一致，保证老项目无缝迁移 ----
    _palette(
        "legacy_project",
        "原版 · 项目类别",
        "原版",
        ("#6AFFFF", "#E0A6E5", "#EBE082", "#CCCCCC"),
        tags=("原版", "项目类别", "兼容", "浅色"),
        description="旧版项目类别统计配色，保留原始标签到颜色的精确映射。",
        named_colors={
            "软件开发": "#6AFFFF",
            "MES改造": "#E0A6E5",
            "视觉改造": "#EBE082",
            "方案review": "#CCCCCC",
            "方案Review": "#CCCCCC",
            "iPhone扫码": "#CCCCCC",
            "运控改造": "#CCCCCC",
        },
    ),
    _palette(
        "legacy_status",
        "原版 · 项目状态",
        "原版",
        ("#FFF45C", "#C2B9B7", "#D54660", "#DA435C"),
        tags=("原版", "项目状态", "兼容"),
        description="旧版项目状态统计配色，保留 On-going / Done / Pause / Delay 映射。",
        named_colors={
            "On-going": "#FFF45C",
            "Done": "#C2B9B7",
            "Pause": "#D54660",
            "Delay": "#DA435C",
        },
    ),
    # ---- 商务：低饱和、稳重，适合正式汇报 ----
    _palette(
        "business_steel",
        "商务 · 钢青",
        "商务",
        ("#17324D", "#24547E", "#3B7DB3", "#6FA8D3", "#A9CBE5", "#D5E6F2", "#7C8B99"),
        tags=("商务", "蓝", "稳重", "汇报"),
        description="深蓝到浅蓝的秩序感渐变，配中性灰收尾，适合年度/季度汇报。",
    ),
    _palette(
        "business_forest",
        "商务 · 墨绿",
        "商务",
        ("#173B35", "#245C50", "#3C8576", "#69AB9B", "#A3CCC2", "#D2E6DF", "#8C7A5B"),
        tags=("商务", "绿", "稳重", "汇报"),
        description="克制的墨绿系，带一点暖棕点缀，适合经营分析与方案评审。",
    ),
    # ---- 科技：明快、有数字感 ----
    _palette(
        "tech_neon",
        "科技 · 霓虹",
        "科技",
        ("#0B1F3A", "#1B6CFF", "#00C2FF", "#00E5C0", "#8B5CF6", "#FF4D8D", "#FFC53D"),
        tags=("科技", "高饱和", "发布会", "大屏"),
        description="深空蓝打底，电光青/紫/粉提亮，适合产品发布与技术大屏。",
    ),
    _palette(
        "tech_deep",
        "科技 · 深空",
        "科技",
        ("#101A33", "#1E3A5F", "#2E5F8A", "#3F8FC4", "#69C4E8", "#A7E0F2", "#4B4E6D"),
        tags=("科技", "蓝", "数据", "中性"),
        description="冷色深空梯度，层次清晰，适合数据密集型仪表盘与架构图。",
    ),
    # ---- 莫兰迪：低饱和灰调，高级感 ----
    _palette(
        "morandi_dusk",
        "莫兰迪 · 暮色",
        "莫兰迪",
        ("#6F6A66", "#8E8A85", "#A8A29A", "#B7A8A0", "#9FAEB2", "#B4BCC4", "#D3CBC4"),
        tags=("莫兰迪", "灰调", "高级感", "留白"),
        description="灰调米褐与雾蓝，低对比但分层柔和，适合品牌感较强的页面。",
    ),
    # ---- 马卡龙：轻柔粉彩，适合轻量、友好场景 ----
    _palette(
        "macaron_pastel",
        "马卡龙 · 粉彩",
        "马卡龙",
        ("#F49AB0", "#F7B267", "#F7D774", "#8FD9A8", "#7FD1D6", "#9BB8E8", "#C3A6E8"),
        tags=("马卡龙", "粉彩", "轻快", "友好"),
        description="低饱和粉彩七色，柔和但彼此可辨，适合培训、运营与活动复盘。",
    ),
    _palette(
        "macaron_berry",
        "马卡龙 · 莓果",
        "马卡龙",
        ("#E36A8C", "#F291A9", "#F7C0B0", "#E8B04B", "#8FCBBF", "#9AA6D9", "#C9B8DD"),
        tags=("马卡龙", "莓果", "温柔", "内容"),
        description="莓果粉与奶油色为主，比粉彩略深一档，投影仪上也更稳。",
    ),
    # ---- 自然：取自森林与海岸 ----
    _palette(
        "nature_forest",
        "自然 · 森野",
        "自然",
        ("#2F5D3A", "#4E7C49", "#7BA05B", "#A8C686", "#D4E0A8", "#C2A878", "#6B5B4B"),
        tags=("自然", "森林", "有机", "可持续"),
        description="苔绿、草绿到暖褐，如林间光影，适合环保/农业/供应链主题。",
    ),
    _palette(
        "nature_ocean",
        "自然 · 海岸",
        "自然",
        ("#1F6F78", "#2E9CA6", "#58C4C8", "#9BD9D8", "#D6E8E3", "#E1C699", "#5C8374"),
        tags=("自然", "海岸", "清透", "旅行"),
        description="海水青与沙滩米色，清透松弛，适合文旅、健康与生活方式内容。",
    ),
    # ---- 高对比：答辩/打印等强区分场景 ----
    _palette(
        "high_contrast",
        "高对比 · 信号",
        "高对比",
        ("#D7263D", "#F46036", "#F2A541", "#2E86AB", "#1B998B", "#3D348B", "#111111"),
        tags=("高对比", "强区分", "打印", "答辩"),
        description="高饱和强区分配色，适合需要一眼分辨类别或投影/打印场景。",
    ),
    # ---- 极简：少即是多 ----
    _palette(
        "minimal_graphite",
        "极简 · 石墨",
        "极简",
        ("#111827", "#374151", "#6B7280", "#9CA3AF", "#D1D5DB", "#F3F4F6", "#0F766E"),
        tags=("极简", "灰阶", "克制", "报告"),
        description="石墨灰阶为主，只留一枚深青强调色，适合分析师风格的单页报告。",
    ),
    # ---- 活力：年轻、有冲击力 ----
    _palette(
        "vibrant_candy",
        "活力 · 糖果",
        "活力",
        ("#EF476F", "#FF9F1C", "#FFD166", "#06D6A0", "#118AB2", "#7B2CBF", "#3A86FF"),
        tags=("活力", "高饱和", "年轻", "活动"),
        description="糖果色高饱和组合，视觉冲击强但不扎眼，适合活动与增长数据。",
    ),
    # ---- 中国风：传统色 ----
    _palette(
        "chinese_vermilion",
        "中国风 · 朱青",
        "中国风",
        ("#9D2933", "#C3272B", "#E8A33D", "#2A8E7F", "#177CB0", "#425066", "#D6ECF0"),
        tags=("中国风", "朱红", "靛青", "国潮"),
        description="胭脂、藤黄、石绿与靛青，取自传统器物的朱青对比，端庄而不沉闷。",
    ),
    _palette(
        "chinese_ink",
        "中国风 · 水墨",
        "中国风",
        ("#1C1C1C", "#3D3D3D", "#5F6F65", "#7A8B8F", "#A8B5A2", "#C9B8A8", "#8B2F2F"),
        tags=("中国风", "水墨", "素雅", "文化"),
        description="墨分五色配一点朱砂，素雅留白，适合文化、政务与品牌叙事内容。",
    ),
)

_PALETTE_INDEX: dict[str, Palette] = {palette.id: palette for palette in PALETTES}


# ---------------------------------------------------------------------------
# 色板查询与标签配色
# ---------------------------------------------------------------------------


def palette_by_id(pid: str) -> Palette:
    """按 id 查找色板（忽略大小写与首尾空白）。

    未找到时抛出 :class:`KeyError`。
    """

    if not isinstance(pid, str):
        raise TypeError(f"色板 id 必须是字符串，收到 {type(pid).__name__}")
    key = pid.strip().lower()
    try:
        return _PALETTE_INDEX[key]
    except KeyError as exc:
        available = ", ".join(palette.id for palette in PALETTES)
        raise KeyError(
            f"未知色板 id：{pid!r}；可用 id：{available}"
        ) from exc


def palettes_by_group() -> dict[str, tuple[Palette, ...]]:
    """按 :data:`GROUP_ORDER` 顺序返回 ``{分组: 色板元组}``。"""

    grouped: dict[str, list[Palette]] = {}
    for palette in PALETTES:
        grouped.setdefault(palette.group, []).append(palette)

    ordered: dict[str, tuple[Palette, ...]] = {}
    for group in GROUP_ORDER:
        if group in grouped:
            ordered[group] = tuple(grouped.pop(group))
    for group in sorted(grouped):
        ordered[group] = tuple(grouped[group])
    return ordered


def _resolve_palette(palette: Palette | str) -> Palette:
    if isinstance(palette, Palette):
        return palette
    if isinstance(palette, str):
        return palette_by_id(palette)
    raise TypeError(
        "palette 必须是 Palette 实例或色板 id 字符串，"
        f"收到 {type(palette).__name__}"
    )


def assign_colors(
    palette: Palette | str,
    labels: Iterable[str],
    overrides: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """把 ``labels`` 确定性地映射到色板颜色。

    规则（按优先级从高到低）：

    1. ``overrides`` 中的标签使用用户指定的颜色（仅覆盖本次出现的标签）；
    2. 命中 ``palette.named_colors`` 的标签使用其固定颜色；
    3. 其余标签按出现顺序循环使用 ``palette.colors``。

    重复标签只保留第一次出现的位置；命中 ``named_colors`` 的标签不占用
    循环索引，保证在原版色板上稳定复现旧映射。
    """

    resolved = _resolve_palette(palette)
    colors = resolved.colors
    if not colors:  # pragma: no cover - Palette 已保证非空
        raise ValueError(f"色板 {resolved.id!r} 没有颜色")

    normalized_overrides: dict[str, str] = {}
    if overrides:
        for label, color in overrides.items():
            normalized_overrides[str(label)] = normalize_hex(color)

    named = resolved.named_colors or {}
    assignment: dict[str, str] = {}
    cycle_index = 0
    for raw_label in labels:
        label = str(raw_label)
        if label in assignment:
            continue
        if label in normalized_overrides:
            assignment[label] = normalized_overrides[label]
            continue
        if label in named:
            assignment[label] = named[label]
            continue
        assignment[label] = colors[cycle_index % len(colors)]
        cycle_index += 1

    return assignment


def _find_label_lightness(
    hue: float,
    saturation: float,
    lightness: float,
    direction: float,
    background: str,
) -> tuple[float, str] | None:
    """沿色相方向微调亮度，返回 ``(亮度变化量, 颜色)``。"""

    fallback: tuple[float, str] | None = None
    for step in range(1, 251):
        delta = step * (1.0 / 250.0)
        target = lightness + direction * delta
        if target < 0.0 or target > 1.0:
            break
        candidate = hsl_to_hex(hue, saturation, target)
        ratio = contrast_ratio(candidate, background)
        if ratio >= _LABEL_TARGET_CONTRAST:
            return (delta, candidate)
        if ratio >= LABEL_MIN_CONTRAST and fallback is None:
            fallback = (delta, candidate)
    return fallback


def label_color(
    fill: str,
    mode: str = "auto",
    *,
    single: str = DEFAULT_LABEL_COLOR,
    background: str = DEFAULT_BACKGROUND,
) -> str:
    """返回图表标签文字应使用的颜色。

    Args:
        fill: 标签对应的扇区填充色。
        mode: ``"auto"``（默认）/ ``"match"`` / ``"single"``。
        single: ``mode="single"`` 时统一使用的颜色。
        background: 标签实际绘制所在的背景色，默认白底。

    三种模式：

    * ``match``：标签颜色 = 填充色；
    * ``single``：所有标签统一使用 ``single``；
    * ``auto``：填充色相对背景的 WCAG 对比度已 ≥ 3.0 时直接沿用填充色；
      否则保持色相与饱和度，沿变深（浅背景）或变浅（深背景）方向微调到
      对比度达标，得到既清晰又与扇区同色系的标签色。
    """

    fill = normalize_hex(fill)
    normalized_mode = str(mode).strip().lower()

    if normalized_mode == "match":
        return fill
    if normalized_mode == "single":
        return normalize_hex(single)
    if normalized_mode != "auto":
        raise ValueError(
            f"不支持的标签颜色模式：{mode!r}（可选 auto / match / single）"
        )

    background_hex = normalize_hex(background)
    if contrast_ratio(fill, background_hex) >= LABEL_MIN_CONTRAST:
        return fill

    hue, saturation, lightness = rgb_to_hsl(fill)
    darker = _find_label_lightness(hue, saturation, lightness, -1.0, background_hex)
    lighter = _find_label_lightness(hue, saturation, lightness, 1.0, background_hex)

    candidates = [item for item in (darker, lighter) if item is not None]
    if candidates:
        if (
            len(candidates) == 2
            and abs(candidates[0][0] - candidates[1][0]) < 1e-9
            and luminance(background_hex) >= 0.5
        ):
            return candidates[0][1]
        return min(candidates, key=lambda item: item[0])[1]

    # 极端背景兜底：黑白中对比度更高的那个。
    black_ratio = contrast_ratio("#000000", background_hex)
    white_ratio = contrast_ratio("#FFFFFF", background_hex)
    return "#000000" if black_ratio >= white_ratio else "#FFFFFF"


# ---------------------------------------------------------------------------
# 色板推荐
# ---------------------------------------------------------------------------


def _effective_colors(palette: Palette, n_labels: int) -> tuple[str, ...]:
    colors = palette.colors
    return tuple(colors[index % len(colors)] for index in range(n_labels))


def _recommend_score(
    palette: Palette,
    n_labels: int,
    background: str,
) -> float:
    """为「n_labels 个标签绘制的图表」给色板打分（0–1，越高越合适）。"""

    colors = _effective_colors(palette, n_labels)
    unique_count = len(set(colors))

    if n_labels == 1:
        distinct = 0.85
    elif unique_count < n_labels:
        # 颜色不够，循环复用导致撞色：区分度按缺口比例打折。
        distinct = 0.30 * (unique_count / n_labels)
    else:
        pair_distances = [
            delta_e(colors[first], colors[second])
            for first in range(n_labels)
            for second in range(first + 1, n_labels)
        ]
        min_distance = min(pair_distances)
        mean_distance = sum(pair_distances) / len(pair_distances)
        distinct = 0.55 * min(min_distance / 18.0, 1.0) + 0.45 * min(
            mean_distance / 40.0, 1.0
        )

    visibility = sum(
        min(contrast_ratio(color, background) / 3.0, 1.0) for color in colors
    ) / len(colors)

    capacity = len(palette.colors)
    if capacity >= n_labels:
        size_fit = 1.0
    else:
        size_fit = capacity / n_labels

    return 0.42 * distinct + 0.34 * visibility + 0.24 * size_fit


def palette_scores(
    n_labels: int,
    *,
    background: str = DEFAULT_BACKGROUND,
) -> list[tuple[Palette, float]]:
    """返回全部色板按推荐分数降序排列的 ``(Palette, score)`` 列表。

    与 :func:`recommend_palettes` 共用同一套确定性打分规则，便于调试 UI。
    """

    if isinstance(n_labels, bool) or not isinstance(n_labels, int):
        raise TypeError(f"n_labels 必须是整数，收到 {type(n_labels).__name__}")
    if n_labels < 1:
        raise ValueError(f"n_labels 必须 >= 1，收到 {n_labels}")

    background_hex = normalize_hex(background)
    scored = [
        (palette, _recommend_score(palette, n_labels, background_hex))
        for palette in PALETTES
    ]
    scored.sort(key=lambda item: (-round(item[1], 6), item[0].id))
    return scored


def recommend_palettes(
    n_labels: int,
    *,
    limit: int = 4,
    background: str = DEFAULT_BACKGROUND,
) -> list[Palette]:
    """按标签数量推荐最合适的色板（确定性排序）。

    打分综合考虑：

    * **区分度**（42%）：前 ``n_labels`` 个颜色两两之间的 CIELAB ΔE 最小值与均值；
    * **可见度**（34%）：颜色相对 ``background`` 的 WCAG 对比度（封顶 3.0，
      避免一味追求深色而破坏配色）；
    * **容量匹配**（24%）：色板颜色数是否覆盖 ``n_labels``，不足时按比例扣分。

    结果只依赖入参，多次调用结果完全一致。``limit < 1`` 时返回空列表。
    """

    if isinstance(limit, bool) or not isinstance(limit, int):
        raise TypeError(f"limit 必须是整数，收到 {type(limit).__name__}")
    if limit < 1:
        return []
    return [
        palette
        for palette, _score in palette_scores(
            n_labels, background=background
        )[:limit]
    ]

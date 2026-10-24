"""rosechart.palettes 自测脚本（纯 assert，无第三方依赖）。

运行方式（在 rose 目录下，也可在任意目录运行）::

    rose\\.venv\\python.exe rose\\tests\\test_palettes.py

脚本会自动把 ``rose/`` 加入 ``sys.path``，因此无需安装包或设置环境变量。
全部通过时退出码为 0，并在末尾打印汇总；任何断言失败会直接抛出
``AssertionError`` 并以非 0 退出码结束。
"""

from __future__ import annotations

import re
import sys
import traceback
from dataclasses import FrozenInstanceError
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rosechart import palettes as P  # noqa: E402

# ---------------------------------------------------------------------------
# 极简断言框架
# ---------------------------------------------------------------------------

_CHECKS = 0
_SECTIONS: list[tuple[str, int]] = []


def check(condition: object, message: str) -> None:
    """断言条件成立并计数；失败信息包含上下文，便于定位。"""
    global _CHECKS
    assert condition, message
    _CHECKS += 1


def run_section(title: str, func) -> None:
    before = _CHECKS
    func()
    passed = _CHECKS - before
    _SECTIONS.append((title, passed))
    print(f"[ok] {title:<34s} {passed:>4d} checks")


HEX_PATTERN = re.compile(r"^#[0-9A-F]{6}$")

EXPECTED_PROJECT_NAMED = {
    "软件开发": "#6AFFFF",
    "MES改造": "#E0A6E5",
    "视觉改造": "#EBE082",
    "方案review": "#CCCCCC",
    "方案Review": "#CCCCCC",
    "iPhone扫码": "#CCCCCC",
    "运控改造": "#CCCCCC",
}

EXPECTED_STATUS_NAMED = {
    "On-going": "#FFF45C",
    "Done": "#C2B9B7",
    "Pause": "#D54660",
    "Delay": "#DA435C",
}

REQUIRED_GROUPS = {
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
}

LEGACY_IDS = ("legacy_project", "legacy_status")


# ---------------------------------------------------------------------------
# 1. 色板元数据与色号合法性
# ---------------------------------------------------------------------------


def test_metadata() -> None:
    check(isinstance(P.PALETTES, tuple), "PALETTES 必须是 tuple")
    check(len(P.PALETTES) >= 14, f"PALETTES 至少 14 套，当前 {len(P.PALETTES)}")
    check(
        all(isinstance(palette, P.Palette) for palette in P.PALETTES),
        "PALETTES 的元素必须都是 Palette",
    )
    check(
        len({palette.id for palette in P.PALETTES}) == len(P.PALETTES),
        "色板 id 必须唯一",
    )
    check(
        len({palette.name for palette in P.PALETTES}) == len(P.PALETTES),
        "色板 name 必须唯一",
    )
    check(
        tuple(P.GROUP_ORDER) == tuple(dict.fromkeys(P.GROUP_ORDER)),
        "GROUP_ORDER 不能有重复分组",
    )

    groups_present = {palette.group for palette in P.PALETTES}
    check(
        REQUIRED_GROUPS.issubset(groups_present),
        f"缺少必需分组：{REQUIRED_GROUPS - groups_present}",
    )
    check(
        groups_present.issubset(set(P.GROUP_ORDER)),
        f"出现了 GROUP_ORDER 之外的分组：{groups_present - set(P.GROUP_ORDER)}",
    )

    for palette in P.PALETTES:
        label = f"色板 {palette.id}"
        check(bool(re.fullmatch(r"[a-z][a-z0-9_]*", palette.id)), f"{label} 的 id 格式")
        check(isinstance(palette.name, str) and palette.name.strip() != "", f"{label} name")
        check(isinstance(palette.group, str) and palette.group.strip() != "", f"{label} group")
        check(isinstance(palette.description, str), f"{label} description 类型")
        check(isinstance(palette.tags, tuple), f"{label} tags 必须是 tuple")
        check(
            all(isinstance(tag, str) for tag in palette.tags),
            f"{label} tags 必须都是字符串",
        )
        check(len(palette.colors) == len(set(palette.colors)), f"{label} 内不能有重复色号")
        check(
            all(HEX_PATTERN.fullmatch(color) for color in palette.colors),
            f"{label} 的色号必须是 #RRGGBB：{palette.colors}",
        )
        if palette.id in LEGACY_IDS:
            check(len(palette.colors) == 4, f"{label} 原版色板必须保留 4 色")
        else:
            check(
                6 <= len(palette.colors) <= 8,
                f"{label} 应为 6–8 色，当前 {len(palette.colors)}",
            )
        check(
            all(isinstance(color, str) for color in palette.colors),
            f"{label} colors 必须都是字符串",
        )

    check(
        set(P.palettes_by_group()) == groups_present,
        "palettes_by_group 的分组集合应与 PALETTES 一致",
    )
    check(
        list(P.palettes_by_group())
        == [group for group in P.GROUP_ORDER if group in groups_present],
        "palettes_by_group 应按 GROUP_ORDER 排序",
    )
    check(
        sum(len(items) for items in P.palettes_by_group().values()) == len(P.PALETTES),
        "palettes_by_group 不应丢失色板",
    )


# ---------------------------------------------------------------------------
# 2. 原版色板精确性
# ---------------------------------------------------------------------------


def test_legacy_palettes() -> None:
    project = P.palette_by_id("legacy_project")
    check(
        project.colors == ("#6AFFFF", "#E0A6E5", "#EBE082", "#CCCCCC"),
        f"legacy_project 颜色不符：{project.colors}",
    )
    check(
        dict(project.named_colors or {}) == EXPECTED_PROJECT_NAMED,
        f"legacy_project named_colors 不符：{project.named_colors}",
    )

    status = P.palette_by_id("legacy_status")
    check(
        status.colors == ("#FFF45C", "#C2B9B7", "#D54660", "#DA435C"),
        f"legacy_status 颜色不符：{status.colors}",
    )
    check(
        dict(status.named_colors or {}) == EXPECTED_STATUS_NAMED,
        f"legacy_status named_colors 不符：{status.named_colors}",
    )

    for palette in (project, status):
        assigned = P.assign_colors(palette, list(palette.named_colors or {}))
        for label, expected in (palette.named_colors or {}).items():
            check(
                assigned[label] == expected,
                f"{palette.id} 的 {label!r} 应映射到 {expected}，实际 {assigned[label]}",
            )


# ---------------------------------------------------------------------------
# 3. palette_by_id
# ---------------------------------------------------------------------------


def test_palette_lookup() -> None:
    for palette in P.PALETTES:
        found = P.palette_by_id(palette.id)
        check(found is palette, f"palette_by_id({palette.id!r}) 应返回同一对象")
    check(
        P.palette_by_id("  LEGACY_PROJECT  ") is P.palette_by_id("legacy_project"),
        "palette_by_id 应忽略大小写和首尾空白",
    )
    check(
        P.palette_by_id(pid="legacy_project") is P.palette_by_id("legacy_project"),
        "palette_by_id 应支持 pid= 关键字参数（与约定签名一致）",
    )

    for missing in ("no_such_palette", "", "legacy-proj"):
        try:
            P.palette_by_id(missing)
        except KeyError:
            check(True, "missing id should raise")
        else:  # pragma: no cover - 失败路径
            check(False, f"palette_by_id({missing!r}) 应抛出 KeyError")

    try:
        P.palette_by_id(None)  # type: ignore[arg-type]
    except TypeError:
        check(True, "None id should raise")
    else:  # pragma: no cover
        check(False, "palette_by_id(None) 应抛出 TypeError")


# ---------------------------------------------------------------------------
# 4. assign_colors
# ---------------------------------------------------------------------------


def test_assign_colors() -> None:
    palette = P.PALETTES[2]
    labels = [f"类目{index}" for index in range(10)]
    expected = {
        label: palette.colors[index % len(palette.colors)]
        for index, label in enumerate(labels)
    }
    assigned = P.assign_colors(palette, labels)
    check(assigned == expected, "assign_colors 应按 colors 顺序循环")
    check(len(assigned) == len(labels), "assign_colors 返回长度应等于标签数")
    check(list(assigned) == labels, "assign_colors 应保持标签输入顺序")
    check(
        P.assign_colors(palette, labels) == assigned,
        "assign_colors 对相同输入必须稳定",
    )
    assigned_values = set(assigned.values())
    check(bool(assigned_values), "assign_colors 返回值非空")
    check(
        assigned_values.issubset(set(palette.colors)),
        "assign_colors 只能使用色板内颜色",
    )
    check(
        P.assign_colors(palette.id, labels) == assigned,
        "assign_colors 应接受色板 id 字符串",
    )

    # overrides 覆盖循环色
    overrides = {"类目0": "#123456", "类目3": "#aBcDeF"}
    overridden = P.assign_colors(palette, labels, overrides)
    check(overridden["类目0"] == "#123456", "overrides 应覆盖第一个标签")
    check(overridden["类目3"] == "#ABCDEF", "overrides 颜色应被规范化")
    check(
        overridden["类目1"] == palette.colors[0],
        "override 标签不占用循环索引，未命中标签仍从 colors[0] 开始",
    )
    check(
        overridden["类目2"] == palette.colors[1],
        "未命中的标签仍按原循环顺序取色",
    )
    check(
        len(overridden) == len(labels),
        "overrides 不应改变返回字典长度",
    )
    check(
        P.assign_colors(palette, ["A"], {"不在本次": "#000000"})
        == {"A": palette.colors[0]},
        "不在 labels 中的 override 应被忽略",
    )

    # 重复标签：只保留首次出现
    duplicated = P.assign_colors(palette, ["A", "A", "B"])
    check(list(duplicated) == ["A", "B"], "重复标签应被去重")
    check(len(duplicated) == 2, "重复标签不应产生重复键")

    # named_colors 优先且不占用循环索引
    status = P.palette_by_id("legacy_status")
    mixed = P.assign_colors(
        status,
        ["On-going", "X", "Done", "Y", "Pause"],
    )
    check(mixed["On-going"] == "#FFF45C", "named 标签应优先使用原映射")
    check(mixed["X"] == status.colors[0], "未知标签从未命名槽位开始循环")
    check(mixed["Y"] == status.colors[1], "named 标签不应消耗循环索引")
    check(mixed["Pause"] == "#D54660", "named 标签 Pause 映射不变")

    # 空标签
    check(P.assign_colors(palette, []) == {}, "空 labels 应返回空 dict")
    check(P.assign_colors(palette, [], {"A": "#000000"}) == {}, "空 labels 不应注入 override")

    try:
        P.assign_colors(12345, ["A"])  # type: ignore[arg-type]
    except TypeError:
        check(True, "非法 palette 应抛 TypeError")
    else:  # pragma: no cover
        check(False, "assign_colors 应对非法 palette 抛 TypeError")

    try:
        P.assign_colors(palette, ["A"], {"A": "not-a-color"})
    except ValueError:
        check(True, "非法 override 颜色应抛 ValueError")
    else:  # pragma: no cover
        check(False, "assign_colors 应校验 override 颜色")


# ---------------------------------------------------------------------------
# 5. label_color
# ---------------------------------------------------------------------------


def test_label_color() -> None:
    check(P.label_color("#6AFFFF", mode="match") == "#6AFFFF", "match 模式应返回填充色")
    check(
        P.label_color(fill="#6AFFFF", mode="match") == "#6AFFFF",
        "label_color 应支持 fill= 关键字参数（与约定签名一致）",
    )
    check(
        P.label_color("#6affff", mode="match") == "#6AFFFF",
        "match 模式输出应规范化为大写",
    )
    check(
        P.label_color("#123456", mode="single") == "#334155",
        "single 模式应使用默认 single 颜色",
    )
    check(
        P.label_color("#123456", mode="single", single="#000000") == "#000000",
        "single 模式应支持自定义颜色",
    )
    check(
        P.label_color("#6AFFFF", mode="SINGLE", single="#ABCDEF") == "#ABCDEF",
        "mode 应忽略大小写",
    )
    check(
        P.label_color("#1F3A5F") == "#1F3A5F",
        "对比度已达标时 auto 应保留原填充色",
    )
    check(
        P.label_color("#FFF45C") != "#FFF45C",
        "白底上过亮的填充色 auto 应推导出更深标签色",
    )

    try:
        P.label_color("#6AFFFF", mode="neon")
    except ValueError:
        check(True, "非法 mode 应抛 ValueError")
    else:  # pragma: no cover
        check(False, "label_color 应对非法 mode 抛 ValueError")

    # 全部内置色板 × 全部颜色：白底与其它常见背景上的 auto 标签色都必须达标
    backgrounds = ("#FFFFFF", "#F8FAFC", "#E8EEF4", "#0F172A", "#101418")
    for background in backgrounds:
        for palette in P.PALETTES:
            for fill in palette.colors:
                derived = P.label_color(fill, background=background)
                ratio = P.contrast_ratio(derived, background)
                check(
                    ratio >= P.LABEL_MIN_CONTRAST - 1e-9,
                    f"{palette.id} / {fill} 在 {background} 上标签色 {derived} "
                    f"对比度仅 {ratio:.3f}",
                )
                check(
                    HEX_PATTERN.fullmatch(derived) is not None,
                    f"{palette.id} / {fill} 标签色格式非法：{derived}",
                )

    # 推导出的标签色应尽量保留色相（而非变成纯灰）
    for fill in ("#6AFFFF", "#E0A6E5", "#EBE082", "#F49AB0", "#8FD9A8"):
        source_hue, _source_saturation, _source_lightness = P.rgb_to_hsl(fill)
        label_hue, _label_saturation, _label_lightness = P.rgb_to_hsl(
            P.label_color(fill)
        )
        hue_gap = abs(source_hue - label_hue)
        hue_gap = min(hue_gap, 360.0 - hue_gap)
        check(
            hue_gap <= 2.0,
            f"{fill} 的 auto 标签色色相偏移过大：{hue_gap:.2f}°",
        )

    # 深色背景：深色填充应被提亮到可读
    for fill in ("#17324D", "#173B35", "#101A33", "#1C1C1C"):
        derived = P.label_color(fill, background="#0F172A")
        ratio = P.contrast_ratio(derived, "#0F172A")
        check(ratio >= P.LABEL_MIN_CONTRAST, f"{fill} 在深色背景上标签色对比度 {ratio:.2f}")


# ---------------------------------------------------------------------------
# 6. 基础工具函数
# ---------------------------------------------------------------------------


def test_color_utils() -> None:
    # normalize_hex / is_hex_color
    check(P.normalize_hex("abc") == "#AABBCC", "3 位缩写应补全")
    check(P.normalize_hex("#aBcDeF") == "#ABCDEF", "应规范化为大写并保留 #")
    check(P.normalize_hex("  #FFF  ") == "#FFFFFF", "应忽略首尾空白")
    check(P.is_hex_color("#ABC") is True, "is_hex_color 应接受缩写")
    check(P.is_hex_color("red") is False, "is_hex_color 应拒绝颜色名")
    check(P.is_hex_color(None) is False, "is_hex_color 应拒绝非字符串")
    for bad in ("#12345", "#1234567", "#GGGGGG", "0x123456", ""):
        try:
            P.normalize_hex(bad)
        except ValueError:
            check(True, "invalid color should raise")
        else:  # pragma: no cover
            check(False, f"normalize_hex({bad!r}) 应抛出 ValueError")
    try:
        P.normalize_hex(None)  # type: ignore[arg-type]
    except TypeError:
        check(True, "None should raise TypeError")
    else:  # pragma: no cover
        check(False, "normalize_hex(None) 应抛出 TypeError")

    # hex_to_rgb / rgb_to_hex
    check(P.hex_to_rgb("#FFFFFF") == (255, 255, 255), "hex_to_rgb 白色")
    check(P.hex_to_rgb("#000000") == (0, 0, 0), "hex_to_rgb 黑色")
    check(P.hex_to_rgb("#6AFFFF") == (106, 255, 255), "hex_to_rgb 青色")
    check(P.rgb_to_hex((255, 255, 255)) == "#FFFFFF", "rgb_to_hex 白色")
    check(P.rgb_to_hex((0, 0, 0)) == "#000000", "rgb_to_hex 黑色")
    check(P.rgb_to_hex((300, -5, 128)) == "#FF0080", "rgb_to_hex 应裁剪到 0–255")
    try:
        P.rgb_to_hex((1, 2))  # type: ignore[arg-type]
    except ValueError:
        check(True, "rgb_to_hex 长度非法应抛 ValueError")
    else:  # pragma: no cover
        check(False, "rgb_to_hex 应校验通道数量")

    for palette in P.PALETTES:
        for color in palette.colors:
            check(P.hex_to_rgb(color) and True, "hex_to_rgb 非空")
            check(P.rgb_to_hex(P.hex_to_rgb(color)) == color, f"往返转换失败：{color}")

    # luminance / contrast_ratio
    check(abs(P.luminance("#FFFFFF") - 1.0) < 1e-12, "白色相对亮度应为 1")
    check(abs(P.luminance("#000000")) < 1e-12, "黑色相对亮度应为 0")
    check(
        abs(P.contrast_ratio("#000000", "#FFFFFF") - 21.0) < 1e-9,
        "黑白对比度应为 21:1",
    )
    check(
        abs(P.contrast_ratio("#FFFFFF", "#000000") - 21.0) < 1e-9,
        "contrast_ratio 应与顺序无关",
    )
    for palette in P.PALETTES:
        for color in palette.colors:
            ratio = P.contrast_ratio(color, "#FFFFFF")
            check(1.0 <= ratio <= 21.0, f"{color} 对比度越界：{ratio}")
    check(
        abs(P.contrast_ratio("#777777", "#777777") - 1.0) < 1e-12,
        "同色对比度应为 1",
    )

    # mix_colors
    check(P.mix_colors("#123456", "#ABCDEF", 0.0) == "#123456", "mix weight=0")
    check(P.mix_colors("#123456", "#ABCDEF", 1.0) == "#ABCDEF", "mix weight=1")
    check(
        P.mix_colors("#000000", "#FFFFFF", 0.5)
        == P.mix_colors("#FFFFFF", "#000000", 0.5),
        "mix_colors 应满足交换律",
    )
    mixed = P.mix_colors("#000000", "#FFFFFF", 0.5)
    check(HEX_PATTERN.fullmatch(mixed) is not None, "mix_colors 结果格式合法")
    check(
        P.luminance("#000000") < P.luminance(mixed) < P.luminance("#FFFFFF"),
        "黑白混合结果亮度应居中",
    )
    for bad_weight in (-0.1, 1.1):
        try:
            P.mix_colors("#000000", "#FFFFFF", bad_weight)
        except ValueError:
            check(True, "invalid weight should raise")
        else:  # pragma: no cover
            check(False, "mix_colors 应校验 weight 范围")

    # darken / lighten（保持色相，改变亮度）
    for color in ("#4E8CC4", "#E0A6E5", "#7BA05B", "#FF9F1C"):
        darker = P.darken(color, 0.25)
        lighter = P.lighten(color, 0.25)
        check(P.luminance(darker) < P.luminance(color), f"darken 应降低亮度：{color}")
        check(P.luminance(lighter) > P.luminance(color), f"lighten 应提高亮度：{color}")
        for derived in (darker, lighter):
            check(HEX_PATTERN.fullmatch(derived) is not None, "派生色格式合法")
            source_hue = P.rgb_to_hsl(color)[0]
            derived_hue = P.rgb_to_hsl(derived)[0]
            gap = abs(source_hue - derived_hue)
            gap = min(gap, 360.0 - gap)
            check(gap <= 2.0, f"派生色色相偏移过大：{color} -> {derived}")
    check(P.darken("#4E8CC4", 0.0) == "#4E8CC4", "darken amount=0 应为原色")
    check(P.darken("#4E8CC4", 1.0) == "#000000", "darken amount=1 应为黑色")
    check(P.lighten("#4E8CC4", 0.0) == "#4E8CC4", "lighten amount=0 应为原色")
    check(P.lighten("#4E8CC4", 1.0) == "#FFFFFF", "lighten amount=1 应为白色")
    for bad_amount in (-0.2, 1.2):
        try:
            P.darken("#4E8CC4", bad_amount)
        except ValueError:
            check(True, "invalid amount should raise")
        else:  # pragma: no cover
            check(False, "darken 应校验 amount 范围")

    # HSL 往返
    for palette in P.PALETTES:
        for color in palette.colors:
            hue, saturation, lightness = P.rgb_to_hsl(color)
            check(0.0 <= hue < 360.0, f"{color} 色相越界")
            check(0.0 <= saturation <= 1.0, f"{color} 饱和度越界")
            check(0.0 <= lightness <= 1.0, f"{color} 亮度越界")
            rebuilt = P.hsl_to_hex(hue, saturation, lightness)
            source = P.hex_to_rgb(color)
            target = P.hex_to_rgb(rebuilt)
            check(
                max(abs(a - b) for a, b in zip(source, target)) <= 1,
                f"HSL 往返误差过大：{color} -> {rebuilt}",
            )

    # CIELAB ΔE
    check(P.delta_e("#FFFFFF", "#FFFFFF") == 0.0, "同色 ΔE 应为 0")
    check(P.delta_e("#FFFFFF", "#000000") > 90.0, "黑白 ΔE 应接近 100")
    check(
        abs(P.delta_e("#FF0000", "#00FF00") - P.delta_e("#00FF00", "#FF0000")) < 1e-9,
        "ΔE 应满足对称性",
    )
    check(P.delta_e("#FF0000", "#00FF00") > 60.0, "红绿 ΔE 应明显")


# ---------------------------------------------------------------------------
# 7. 推荐算法
# ---------------------------------------------------------------------------


def test_recommendations() -> None:
    for n_labels in (1, 2, 3, 4, 5, 6, 7):
        first = P.recommend_palettes(n_labels)
        second = P.recommend_palettes(n_labels)
        check(len(first) == 4, f"n={n_labels} 应返回 4 套推荐")
        check(
            [palette.id for palette in first] == [palette.id for palette in second],
            f"n={n_labels} 推荐结果必须确定",
        )
        check(
            len({palette.id for palette in first}) == len(first),
            f"n={n_labels} 推荐结果不应重复",
        )
        check(
            all(isinstance(palette, P.Palette) for palette in first),
            f"n={n_labels} 推荐结果必须是 Palette",
        )
        for palette in first:
            effective = [
                palette.colors[index % len(palette.colors)]
                for index in range(n_labels)
            ]
            check(
                len(set(effective)) == n_labels,
                f"n={n_labels} 推荐色板 {palette.id} 的前 {n_labels} 色应互不相同",
            )
            if n_labels >= 5:
                check(
                    len(palette.colors) >= n_labels,
                    f"n={n_labels} 时应推荐容量足够的色板，"
                    f"{palette.id} 只有 {len(palette.colors)} 色",
                )

    for n_labels in (5, 7):
        check(
            "legacy_project"
            not in {palette.id for palette in P.recommend_palettes(n_labels)},
            f"n={n_labels} 时 4 色的原版项目色板不应被推荐",
        )

    check(
        len(P.recommend_palettes(4, limit=2)) == 2,
        "limit 应限制返回数量",
    )
    check(len(P.recommend_palettes(4, limit=1)) == 1, "limit=1 应返回 1 套")
    check(P.recommend_palettes(4, limit=0) == [], "limit=0 应返回空列表")
    check(P.recommend_palettes(4, limit=-3) == [], "limit<0 应返回空列表")
    check(
        len(P.recommend_palettes(4, limit=99)) == len(P.PALETTES),
        "limit 超过色板总数时应返回全部",
    )

    for bad in (0, -1, -100):
        try:
            P.recommend_palettes(bad)
        except ValueError:
            check(True, "invalid n_labels should raise")
        else:  # pragma: no cover
            check(False, f"recommend_palettes({bad}) 应抛出 ValueError")
    for bad in (1.5, "3", None):
        try:
            P.recommend_palettes(bad)  # type: ignore[arg-type]
        except TypeError:
            check(True, "non-int n_labels should raise")
        else:  # pragma: no cover
            check(False, f"recommend_palettes({bad!r}) 应抛出 TypeError")

    # palette_scores 与 recommend_palettes 同源、降序且稳定
    scores = P.palette_scores(4)
    check(len(scores) == len(P.PALETTES), "palette_scores 应覆盖全部色板")
    check(
        [score for _palette, score in scores]
        == sorted((score for _palette, score in scores), reverse=True),
        "palette_scores 应按分数降序",
    )
    check(
        [palette.id for palette in P.recommend_palettes(4)]
        == [palette.id for palette, _score in scores[:4]],
        "recommend_palettes 应与 palette_scores 前 4 名一致",
    )

    # 深色背景推荐仍然确定性且数量正确
    dark_first = P.recommend_palettes(4, background="#0F172A")
    dark_second = P.recommend_palettes(4, background="#0F172A")
    check(len(dark_first) == 4, "深色背景应返回 4 套推荐")
    check(
        [palette.id for palette in dark_first]
        == [palette.id for palette in dark_second],
        "深色背景推荐必须确定",
    )
    check(
        len({palette.id for palette in dark_first}) == 4,
        "深色背景推荐不应重复",
    )
    for palette in dark_first:
        for fill in palette.colors[:4]:
            check(
                P.contrast_ratio(P.label_color(fill, background="#0F172A"), "#0F172A")
                >= P.LABEL_MIN_CONTRAST,
                "深色背景推荐色板的标签色应可读",
            )


# ---------------------------------------------------------------------------
# 8. 数据模型约束
# ---------------------------------------------------------------------------


def test_datamodel() -> None:
    palette = P.PALETTES[0]
    try:
        palette.id = "changed"  # type: ignore[misc]
    except FrozenInstanceError:
        check(True, "Palette 应是 frozen 的")
    else:  # pragma: no cover
        check(False, "Palette 必须禁止属性赋值")

    custom = P.Palette(
        id="custom",
        name="自定义",
        group="自定义",
        colors=("abc", "#123456"),
        tags=("测试",),
        description="测试用色板",
    )
    check(custom.colors == ("#AABBCC", "#123456"), "Palette 应规范化颜色")
    check(custom.tags == ("测试",), "Palette 应保留 tags")
    check(custom.named_colors is None, "默认 named_colors 应为 None")

    for kwargs in (
        {"id": "", "name": "X", "group": "G", "colors": ("#123456",)},
        {"id": "x", "name": "", "group": "G", "colors": ("#123456",)},
        {"id": "x", "name": "X", "group": "", "colors": ("#123456",)},
        {"id": "x", "name": "X", "group": "G", "colors": ()},
        {"id": "x", "name": "X", "group": "G", "colors": ("#12345",)},
    ):
        try:
            P.Palette(**kwargs)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            check(True, "invalid Palette should raise")
        else:  # pragma: no cover
            check(False, f"无效 Palette 参数应报错：{kwargs}")

    with_named = P.Palette(
        id="custom_named",
        name="自定义命名",
        group="自定义",
        colors=("#112233", "#445566"),
        named_colors={"A": "#ABCDEF"},
    )
    check(
        dict(with_named.named_colors or {}) == {"A": "#ABCDEF"},
        "named_colors 应被规范化保存",
    )
    check(
        P.assign_colors(with_named, ["A", "B"])["A"] == "#ABCDEF",
        "自定义 named_colors 应生效",
    )


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------


def main() -> int:
    print("=" * 66)
    print("  RoseChart palettes self-test")
    print(f"  module: {P.__file__}")
    print("=" * 66)
    sections = (
        ("palette metadata & validity", test_metadata),
        ("legacy palettes exactness", test_legacy_palettes),
        ("palette lookup", test_palette_lookup),
        ("assign_colors", test_assign_colors),
        ("label_color", test_label_color),
        ("color utilities", test_color_utils),
        ("recommendations", test_recommendations),
        ("datamodel constraints", test_datamodel),
    )
    failures = 0
    for title, func in sections:
        try:
            run_section(title, func)
        except AssertionError as error:
            failures += 1
            print(f"[FAIL] {title}")
            print(f"       {error}")
            traceback.print_exc()
        except Exception as error:  # pragma: no cover - 暴露意外异常
            failures += 1
            print(f"[ERROR] {title}: {type(error).__name__}: {error}")
            traceback.print_exc()

    print("-" * 66)
    groups = len({palette.group for palette in P.PALETTES})
    if failures:
        print(f"FAILED: {failures} section(s) failed, {_CHECKS} checks passed")
        return 1
    print(
        f"ALL TESTS PASSED — {len(P.PALETTES)} palettes / {groups} groups / "
        f"{_CHECKS} assertions"
    )
    print("=" * 66)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

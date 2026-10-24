"""Edge-case data tests for the chart engine + label auto layout."""
from __future__ import annotations

import itertools
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg", force=True)

import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from PIL import Image

from rosechart.chart import StyleConfig, build_spec, configure_chinese_font, export_chart, RoseChart
from rosechart.palettes import assign_colors, label_color, palette_by_id

QA_DIR = Path(__file__).resolve().parent / "edge"
QA_DIR.mkdir(parents=True, exist_ok=True)
configure_chinese_font()


def make_excel_files() -> dict[str, Path]:
    files: dict[str, Path] = {}

    many_categories = [
        "软件开发平台",
        "MES制造执行系统改造",
        "视觉检测改造",
        "方案评审",
        "iPhone扫码应用",
        "运动控制改造",
        "数据中台建设",
        "供应链看板",
        "质量追溯模块",
        "能源管理平台",
        "设备联网改造",
        "AI质检试点",
    ]
    statuses = ["进行中 On-going", "已完成 Done", "已暂停 Pause", "延期 Delay", "待启动"]
    rows = []
    for index in range(36):
        rows.append(
            {
                "项目编号": f"P{index + 1:03d}",
                "项目名称": f"项目 {index + 1}",
                "开发类别": many_categories[index % len(many_categories)],
                "状态": statuses[(index // 2) % len(statuses)],
            }
        )
    path = QA_DIR / "many_categories.xlsx"
    pd.DataFrame(rows).to_excel(path, index=False, sheet_name="项目数据")
    files["many"] = path

    path = QA_DIR / "single_category.xlsx"
    pd.DataFrame(
        {
            "项目名称": [f"项目 {i}" for i in range(5)],
            "开发类别": ["软件开发"] * 5,
            "状态": ["Done"] * 5,
        }
    ).to_excel(path, index=False)
    files["single"] = path

    path = QA_DIR / "other_columns.xlsx"
    pd.DataFrame(
        {
            "序号": list(range(1, 9)),
            "项目类型": ["平台化", "定制化", "平台化", "运维", "定制化", "运维", "平台化", "运维"],
            "进展": ["启动", "开发中", "开发中", "测试", "启动", "测试", "完成", "完成"],
        }
    ).to_excel(path, index=False)
    files["other"] = path

    path = QA_DIR / "messy.xlsx"
    values = [" 软件开发 ", "软件开发", "", None, "MES改造", "视觉改造", " 视觉改造", "方案Review"]
    df = pd.DataFrame(
        {
            "开发类别": values,
            "状态": ["Done", " done", "Done", "", "On-going", None, "On-going", "Delay"],
        }
    )
    df.to_excel(path, index=False)
    files["messy"] = path
    return files


def label_overlaps(chart: RoseChart) -> list[tuple[str, str]]:
    renderer = chart.figure.canvas.get_renderer()
    boxes = {}
    for label, handle in chart.handles.items():
        boxes[label] = handle.text.get_window_extent(renderer=renderer)
    overlaps: list[tuple[str, str]] = []
    for (name_a, box_a), (name_b, box_b) in itertools.combinations(boxes.items(), 2):
        if box_a.overlaps(box_b):
            overlaps.append((name_a, name_b))
    return overlaps


def render_case(name: str, pairs: list[tuple[str, int]], palette_id: str, title: str) -> dict:
    labels = [label for label, _value in pairs]
    values = [value for _label, value in pairs]
    palette = palette_by_id(palette_id)
    fills = assign_colors(palette, labels)
    label_colors = {label: label_color(fills[label], "auto") for label in labels}
    style = StyleConfig(title=title, background="transparent")
    spec = build_spec(labels, values, style, fill_colors=fills, label_colors=label_colors)
    target = QA_DIR / f"{name}.png"
    export_chart(spec, target)
    # measure overlaps at export resolution
    figure = Figure(figsize=(12, 8), dpi=100)
    FigureCanvasAgg(figure)
    chart = RoseChart(spec, figure, preview=False)
    figure.canvas.draw()
    overlaps = label_overlaps(chart)
    fonts_ok = len(chart.handles) == len(labels)
    return {
        "name": name,
        "target": target,
        "labels": labels,
        "overlaps": overlaps,
        "handles": fonts_ok,
    }


def build_sheet(results: list[dict]) -> Path:
    thumb_width = 640
    padding = 16
    images = []
    for result in results:
        with Image.open(result["target"]) as image:
            ratio = thumb_width / image.width
            thumb = image.convert("RGBA").resize((thumb_width, int(image.height * ratio)), Image.LANCZOS)
            images.append((result["name"], thumb.copy()))
    columns = 2
    rows = (len(images) + columns - 1) // columns
    cell_h = max(image.height for _name, image in images) + 34
    sheet = Image.new("RGBA", (columns * (thumb_width + padding) + padding, rows * (cell_h + padding) + padding), "#F1F5F9")
    from PIL import ImageDraw

    draw = ImageDraw.Draw(sheet)
    for index, (name, image) in enumerate(images):
        column = index % columns
        row = index // columns
        x = padding + column * (thumb_width + padding)
        y = padding + row * (cell_h + padding)
        sheet.paste(image, (x, y + 22), image)
        draw.text((x, y + 2), name, fill="#0F172A")
    target = QA_DIR / "edge_cases_sheet.png"
    sheet.convert("RGB").save(target)
    return target


def main() -> int:
    print("creating excel fixtures…")
    files = make_excel_files()
    from rosechart import data as data_mod

    cases: list[dict] = []
    failures = 0
    specs = [
        ("many_categories", files["many"], "开发类别", "status", "legacy_project"),
        ("many_status", files["many"], "状态", "status", "legacy_status"),
        ("single_category", files["single"], "开发类别", "project", "legacy_project"),
        ("single_status", files["single"], "状态", "status", "legacy_status"),
        ("other_columns", files["other"], "项目类型", "category", "business_steel"),
        ("other_status", files["other"], "进展", "status", "business_forest"),
        ("messy_cleaned", files["messy"], "开发类别", "category", "tech_neon"),
    ]
    for name, path, column, kind, palette_id in specs:
        sheet_data = data_mod.load_sheet(path, 0)
        pairs = data_mod.value_counts(sheet_data.dataframe, column)
        title = {"category": "项目类型统计", "project": "项目统计", "status": "状态统计"}[kind]
        result = render_case(name, pairs, palette_id, f"{title} · {name}")
        cases.append(result)
        print(
            f"{name}: {len(pairs)} categories, overlaps={len(result['overlaps'])}"
            + (f" -> {result['overlaps']}" if result["overlaps"] else "")
        )
        if result["overlaps"]:
            failures += 1

    # legacy title chart from example data
    sheet_data = data_mod.load_sheet(ROOT / "examples" / "project_test_data.xlsx", 0)
    result = render_case(
        "legacy_example",
        data_mod.value_counts(sheet_data.dataframe, "开发类别"),
        "legacy_project",
        "SW项目统计",
    )
    cases.append(result)
    print("legacy_example: overlaps=", result["overlaps"])
    if result["overlaps"]:
        failures += 1

    print("building contact sheet…")
    sheet_path = build_sheet(cases)
    print("contact sheet:", sheet_path)

    # detection checks
    checks = []
    for path, expected_a, expected_b in (
        (files["many"], "开发类别", "状态"),
        (files["other"], "项目类型", "进展"),
        (files["messy"], "开发类别", "状态"),
    ):
        sheet_data = data_mod.load_sheet(path, 0)
        detected = data_mod.detect_columns(sheet_data.columns)
        checks.append((path.name, detected == (expected_a, expected_b), detected))
    for name, ok, detected in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] column detection {name}: {detected}")
        if not ok:
            failures += 1

    # messy data cleaning: duplicates/blank must be merged
    sheet_data = data_mod.load_sheet(files["messy"], 0)
    pairs = data_mod.value_counts(sheet_data.dataframe, "开发类别")
    expected = {"软件开发": 2, "MES改造": 1, "视觉改造": 2, "方案Review": 1}
    actual = dict(pairs)
    ok = actual == expected
    print(f"[{'PASS' if ok else 'FAIL'}] messy cleanup: {actual}")
    if not ok:
        failures += 1

    # export format checks
    labels = ["软件开发", "MES改造"]
    style = StyleConfig(title="格式检查")
    fills = assign_colors(palette_by_id("legacy_project"), labels)
    spec = build_spec(labels, [3, 2], style, fill_colors=fills, label_colors=dict(fills))
    for fmt, size in (("svg", None), ("pdf", None), ("png", (1920, 1280))):
        target = QA_DIR / f"format_check.{fmt}"
        export_chart(spec, target, width=size[0] if size else None, height=size[1] if size else None, fmt=fmt)
        print(f"[{'PASS' if target.exists() and target.stat().st_size > 1000 else 'FAIL'}] export {fmt}: {target.stat().st_size if target.exists() else 'missing'} bytes")
        if not target.exists():
            failures += 1
    from PIL import Image as PILImage

    with PILImage.open(QA_DIR / "format_check.png") as image:
        ok = image.size == (1920, 1280)
        print(f"[{'PASS' if ok else 'FAIL'}] png custom size {image.size}")
        if not ok:
            failures += 1

    print("\nRESULT:", "ALL PASS" if failures == 0 else f"{failures} FAILURES")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)

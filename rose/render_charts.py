"""Headless command line renderer (kept for compatibility with older scripts).

The interactive desktop app lives in ``app.py``; this module only exposes the
same public helpers the previous version had, now implemented on top of the new
``rosechart`` engine so CLI output and GUI output share one drawing pipeline.

Usage::

    .venv\\python.exe render_charts.py --input examples\\project_test_data.xlsx
"""
from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=True)

import pandas as pd

from rosechart import data as data_mod
from rosechart.chart import (
    StyleConfig,
    build_spec,
    configure_chinese_font,
    export_chart,
)
from rosechart.palettes import assign_colors, label_color, palette_by_id

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = BASE_DIR / "output"
DEFAULT_TEST_FILE = BASE_DIR / "examples" / "project_test_data.xlsx"


def resolve_input_file(input_arg: str | None) -> Path:
    if input_arg:
        input_path = Path(input_arg).expanduser()
        if not input_path.is_absolute():
            input_path = (Path.cwd() / input_path).resolve()
        if not input_path.is_file():
            raise FileNotFoundError(f"找不到 Excel 文件：{input_path}")
        return input_path

    if DEFAULT_TEST_FILE.is_file():
        return DEFAULT_TEST_FILE

    candidates: list[Path] = []
    for directory in (Path.cwd(), BASE_DIR):
        candidates.extend(
            path for path in directory.glob("*.xls*") if not path.name.startswith("~$")
        )
    candidates = sorted(set(path.resolve() for path in candidates))
    if not candidates:
        raise FileNotFoundError(
            "没有找到 Excel 文件。请使用 --input 指定文件，或从 GUI 中选择一个文件。"
        )
    return candidates[0]


def list_excel_sheets(input_file: str | Path) -> list[str]:
    return data_mod.list_sheets(resolve_input_file(str(input_file)))


def _legacy_style(title: str) -> StyleConfig:
    style = StyleConfig(title=title)
    style.background = "transparent"
    return style


def _build_legacy_spec(
    pairs: list[tuple[str, int]],
    *,
    title: str,
    palette_id: str,
    label_mode: str,
):
    labels = [label for label, _value in pairs]
    values = [value for _label, value in pairs]
    palette = palette_by_id(palette_id)
    fill_colors = assign_colors(palette, labels)
    label_colors = {
        label: label_color(fill_colors[label], label_mode) for label in labels
    }
    style = _legacy_style(title)
    return build_spec(labels, values, style, fill_colors=fill_colors, label_colors=label_colors)


def generate_charts(
    input_file: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    sheet: str | int = 0,
) -> dict[str, object]:
    configure_chinese_font()
    input_path = resolve_input_file(str(input_file))
    resolved_output = Path(output_dir).expanduser()
    if not resolved_output.is_absolute():
        resolved_output = (BASE_DIR / resolved_output).resolve()
    resolved_output.mkdir(parents=True, exist_ok=True)

    sheet_data = data_mod.load_sheet(input_path, sheet)
    project_pairs = data_mod.value_counts(sheet_data.dataframe, "开发类别")
    status_pairs = data_mod.value_counts(sheet_data.dataframe, "状态")

    project_spec = _build_legacy_spec(
        project_pairs,
        title="SW项目统计",
        palette_id="legacy_project",
        label_mode="auto",
    )
    status_spec = _build_legacy_spec(
        status_pairs,
        title="SW项目状态统计",
        palette_id="legacy_status",
        label_mode="auto",
    )

    project_png = resolved_output / "Chart_Project.png"
    status_png = resolved_output / "Chart_Status.png"
    export_chart(project_spec, project_png)
    export_chart(status_spec, status_png)

    return {
        "input": input_path,
        "output_dir": resolved_output,
        "project_png": project_png,
        "status_png": status_png,
        "project_counts": {label: value for label, value in project_pairs},
        "status_counts": {label: value for label, value in status_pairs},
        "row_count": sheet_data.row_count,
        "project_spec": project_spec,
        "status_spec": status_spec,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="从 Excel 的开发类别和状态列直接生成两张 PNG 玫瑰图。"
    )
    parser.add_argument("--input", help="Excel 文件路径。省略时优先使用随项目生成的测试文件。")
    parser.add_argument("--sheet", default=0, help="工作表名称或从 0 开始的序号，默认读取第一个工作表。")
    parser.add_argument("--output-dir", help="PNG 输出文件夹；默认使用项目中的 output 文件夹。")
    return parser


def parse_sheet(value: str | int) -> str | int:
    if isinstance(value, int):
        return value
    text = str(value).strip()
    return int(text) if text.isdigit() else text


def main() -> int:
    args = build_parser().parse_args()
    input_path = resolve_input_file(args.input)
    result = generate_charts(
        input_file=input_path,
        output_dir=args.output_dir or DEFAULT_OUTPUT_DIR,
        sheet=parse_sheet(args.sheet),
    )
    print(f"Input: {result['input']}")
    print("Project category counts: " + json.dumps(result["project_counts"], ensure_ascii=True))
    print("Status counts: " + json.dumps(result["status_counts"], ensure_ascii=True))
    print(f"Created: {result['project_png']}")
    print(f"Created: {result['status_png']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

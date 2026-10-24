"""Excel loading, sheet/column detection and aggregation helpers."""
from __future__ import annotations

import warnings
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Sequence

import pandas as pd

APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = APP_DIR / "output"
DEFAULT_EXAMPLE_FILE = APP_DIR / "examples" / "project_test_data.xlsx"

CATEGORY_KEYWORDS = (
    "开发类别",
    "项目类别",
    "类别",
    "项目类型",
    "类型",
    "分类",
    "系统",
    "模块",
    "产品",
)
STATUS_KEYWORDS = (
    "状态",
    "项目状态",
    "进展",
    "进度状态",
    "阶段",
    "完成情况",
)

EXCEL_FILE_TYPES = [
    ("Excel 文件", "*.xlsx *.xls *.xlsm"),
    ("所有文件", "*.*"),
]


class DataError(Exception):
    """User-facing data loading error."""


@dataclass
class SheetData:
    path: Path
    sheet: str
    dataframe: pd.DataFrame
    sheets: list[str] = field(default_factory=list)

    @property
    def columns(self) -> list[str]:
        return [str(column) for column in self.dataframe.columns]

    @property
    def row_count(self) -> int:
        return int(len(self.dataframe))


@contextmanager
def _quiet_openpyxl() -> Iterator[None]:
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            category=UserWarning,
            module=r"openpyxl\.worksheet\._reader",
        )
        yield


def list_sheets(path: str | Path) -> list[str]:
    input_path = Path(path).expanduser()
    if not input_path.is_file():
        raise DataError(f"找不到 Excel 文件：\n{input_path}")
    try:
        with _quiet_openpyxl():
            with pd.ExcelFile(input_path) as workbook:
                return list(workbook.sheet_names)
    except Exception as exc:  # pragma: no cover - depends on file contents
        raise DataError(f"无法读取 Excel 工作表列表：\n{exc}") from exc


def load_sheet(path: str | Path, sheet: str | int = 0) -> SheetData:
    input_path = Path(path).expanduser()
    if not input_path.is_file():
        raise DataError(f"找不到 Excel 文件：\n{input_path}")
    try:
        with _quiet_openpyxl():
            with pd.ExcelFile(input_path) as workbook:
                sheets = list(workbook.sheet_names)
                if isinstance(sheet, int):
                    if not sheets:
                        raise DataError("该 Excel 中没有可读取的工作表。")
                    sheet = sheets[min(max(sheet, 0), len(sheets) - 1)]
                if sheet not in sheets:
                    raise DataError(f"工作表“{sheet}”不存在。")
                dataframe = pd.read_excel(workbook, sheet_name=sheet)
    except DataError:
        raise
    except Exception as exc:  # pragma: no cover - depends on file contents
        raise DataError(f"读取工作表失败：\n{exc}") from exc
    if dataframe.empty:
        raise DataError("工作表没有数据。")
    return SheetData(path=input_path, sheet=str(sheet), dataframe=dataframe, sheets=sheets)


def detect_column(columns: Sequence[str], keywords: Sequence[str]) -> str | None:
    names = [str(column) for column in columns]
    for keyword in keywords:
        for name in names:
            if name.strip() == keyword:
                return name
    for keyword in keywords:
        for name in names:
            if keyword in name:
                return name
    return None


def detect_columns(columns: Sequence[str]) -> tuple[str | None, str | None]:
    names = [str(column) for column in columns]
    first = detect_column(names, CATEGORY_KEYWORDS)
    second = detect_column(names, STATUS_KEYWORDS)
    if second == first:
        second = None
    if first is None or second is None:
        remaining = [
            name
            for name in names
            if name not in {first, second} and not _looks_like_id(name)
        ]
        if first is None and remaining:
            first = remaining.pop(0)
        if second is None and remaining:
            second = remaining.pop(0)
    return first, second


def _looks_like_id(name: str) -> bool:
    lowered = str(name).lower()
    return any(token in lowered for token in ("编号", "序号", "id", "index", "no."))


def usable_columns(columns: Sequence[str]) -> list[str]:
    return [str(column) for column in columns]


def value_counts(
    dataframe: pd.DataFrame,
    column: str,
    *,
    drop_empty: bool = True,
    sort: str = "count_desc",
) -> list[tuple[str, int]]:
    """Count distinct values of ``column``, mirroring the legacy cleaning rules."""
    if column not in dataframe.columns:
        available = "、".join(str(name) for name in dataframe.columns)
        raise DataError(f"缺少列“{column}”。当前列为：{available}")
    series = dataframe[column]
    if drop_empty:
        series = series.dropna().astype(str).str.strip()
        series = series[series.ne("")]
    counts = series.value_counts()
    pairs = [(str(label), int(value)) for label, value in counts.items()]
    if sort == "count_asc":
        pairs.sort(key=lambda item: (item[1], item[0]))
    elif sort == "name":
        pairs.sort(key=lambda item: item[0])
    elif sort == "manual":
        pass
    else:
        pairs.sort(key=lambda item: (-item[1], item[0]))
    if not pairs:
        raise DataError(f"列“{column}”没有可统计的数据。")
    return pairs


def sort_pairs(pairs: Iterable[tuple[str, int]], mode: str) -> list[tuple[str, int]]:
    data = [(str(label), int(value)) for label, value in pairs]
    if mode == "count_asc":
        data.sort(key=lambda item: (item[1], item[0]))
    elif mode == "name":
        data.sort(key=lambda item: item[0])
    else:
        data.sort(key=lambda item: (-item[1], item[0]))
    return data


def find_default_example() -> Path | None:
    if DEFAULT_EXAMPLE_FILE.is_file():
        return DEFAULT_EXAMPLE_FILE
    return None

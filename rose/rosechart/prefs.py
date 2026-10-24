"""Persistent application preferences and project files."""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from .chart import StyleConfig

APP_DIR = Path(__file__).resolve().parents[1]
PREFS_PATH = APP_DIR / "rosechart_prefs.json"
PROJECT_SUFFIX = ".roseproj"
PROJECT_KIND = "rosechart-project"
PROJECT_VERSION = 2
MAX_RECENT_FILES = 8


def default_chart_state(kind: str) -> dict[str, Any]:
    if kind == "chart2":
        return {
            "title": "SW项目状态统计",
            "subtitle": "",
            "palette_id": "legacy_status",
            "label_mode": "auto",
            "label_single_color": "#334155",
            "overrides": {},
            "layout": {},
            "sort_mode": "count_desc",
        }
    return {
        "title": "SW项目统计",
        "subtitle": "",
        "palette_id": "legacy_project",
        "label_mode": "auto",
        "label_single_color": "#334155",
        "overrides": {},
        "layout": {},
        "sort_mode": "count_desc",
    }


def default_project_state() -> dict[str, Any]:
    return {
        "file": "",
        "sheet": "",
        "column_a": "",
        "column_b": "",
        "mode": "both",
        "active": "chart1",
        "charts": {
            "chart1": default_chart_state("chart1"),
            "chart2": default_chart_state("chart2"),
        },
        "style": asdict(StyleConfig()),
        "export": {
            "format": "png",
            "preset": "1200x800",
            "width": 1200,
            "height": 800,
            "dpi": 100,
            "transparent": True,
            "output_dir": str(APP_DIR / "output"),
            "filename": "{title}",
        },
    }


def default_preferences() -> dict[str, Any]:
    return {
        "version": PROJECT_VERSION,
        "window": {"geometry": "", "zoomed": False},
        "recent_files": [],
        "project": default_project_state(),
    }


def _deep_merge(base: Any, incoming: Any) -> Any:
    if isinstance(base, dict) and isinstance(incoming, dict):
        merged = deepcopy(base)
        for key, value in incoming.items():
            if key in merged:
                merged[key] = _deep_merge(merged[key], value)
            else:
                merged[key] = deepcopy(value)
        return merged
    return deepcopy(incoming)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _write_json(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    tmp.replace(path)


class Preferences:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else PREFS_PATH
        self.data = default_preferences()

    def load(self) -> dict[str, Any]:
        stored = _read_json(self.path)
        self.data = _deep_merge(default_preferences(), stored or {})
        return self.data

    def save(self) -> None:
        try:
            _write_json(self.path, self.data)
        except OSError:
            pass

    # -- convenience accessors -------------------------------------------

    @property
    def project(self) -> dict[str, Any]:
        return self.data.setdefault("project", default_project_state())

    def add_recent_file(self, file_path: str | Path) -> None:
        text = str(file_path)
        recent = [item for item in self.data.get("recent_files", []) if item != text]
        recent.insert(0, text)
        self.data["recent_files"] = recent[:MAX_RECENT_FILES]

    def recent_files(self) -> list[str]:
        return list(self.data.get("recent_files", []))

    def window_geometry(self) -> str:
        return str(self.data.get("window", {}).get("geometry", ""))

    def set_window_geometry(self, geometry: str, zoomed: bool = False) -> None:
        self.data.setdefault("window", {})
        self.data["window"]["geometry"] = geometry
        self.data["window"]["zoomed"] = bool(zoomed)


def style_from_dict(raw: Mapping[str, Any] | None) -> StyleConfig:
    style = StyleConfig()
    if not raw:
        return style
    valid = {field: getattr(style, field) for field in style.__dataclass_fields__}
    for key, value in raw.items():
        if key in valid:
            try:
                setattr(style, key, value)
            except (TypeError, ValueError):
                pass
    return style


def load_project(path: str | Path) -> dict[str, Any] | None:
    data = _read_json(Path(path))
    if not data or data.get("kind") != PROJECT_KIND:
        return None
    state = data.get("project")
    if not isinstance(state, dict):
        return None
    return state


def save_project(path: str | Path, project: Mapping[str, Any]) -> Path:
    target = Path(path)
    if target.suffix.lower() != PROJECT_SUFFIX:
        target = target.with_suffix(PROJECT_SUFFIX)
    payload = {
        "kind": PROJECT_KIND,
        "version": PROJECT_VERSION,
        "project": project,
    }
    _write_json(target, payload)
    return target

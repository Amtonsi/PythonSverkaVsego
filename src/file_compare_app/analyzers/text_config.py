from __future__ import annotations

import configparser
import json
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from file_compare_app.analyzers.base import Analyzer
from file_compare_app.core.config_profiles import is_risky_change, normalize_lines_for_path, risk_note
from file_compare_app.core.models import Change, ChangeLocation, ComparisonResult
from file_compare_app.core.text_diff import line_changes


CONFIG_SUFFIXES = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env", ".properties", ".xml"}


class TextConfigAnalyzer(Analyzer):
    def compare(self, left_path: Path, right_path: Path) -> ComparisonResult:
        suffix = left_path.suffix.lower()
        if suffix == ".json" and right_path.suffix.lower() == ".json":
            return self._compare_mapping(left_path, right_path, _load_json(left_path), _load_json(right_path), "json")
        if suffix == ".toml" and right_path.suffix.lower() == ".toml":
            return self._compare_mapping(left_path, right_path, _load_toml(left_path), _load_toml(right_path), "toml")
        if suffix in {".yaml", ".yml"} and right_path.suffix.lower() in {".yaml", ".yml"}:
            left_data = _load_yaml(left_path)
            right_data = _load_yaml(right_path)
            if left_data is not None and right_data is not None:
                return self._compare_mapping(left_path, right_path, left_data, right_data, "yaml")
        if suffix in {".ini", ".cfg"} and right_path.suffix.lower() in {".ini", ".cfg"}:
            left_ini = _try_load_ini(left_path)
            right_ini = _try_load_ini(right_path)
            if left_ini is not None and right_ini is not None:
                return self._compare_mapping(left_path, right_path, left_ini, right_ini, "ini")
            return self._compare_lines(left_path, right_path)
        if suffix in {".env", ".properties"} and right_path.suffix.lower() in {".env", ".properties"}:
            return self._compare_mapping(left_path, right_path, _load_key_value(left_path), _load_key_value(right_path), suffix.lstrip("."))
        if suffix == ".xml" and right_path.suffix.lower() == ".xml":
            return self._compare_mapping(left_path, right_path, _load_xml(left_path), _load_xml(right_path), "xml")
        return self._compare_lines(left_path, right_path)

    def _compare_lines(self, left_path: Path, right_path: Path) -> ComparisonResult:
        left_profile_lines = normalize_lines_for_path(left_path, _read_text(left_path).splitlines())
        right_profile_lines = normalize_lines_for_path(right_path, _read_text(right_path).splitlines())
        left_lines = [line.text for line in left_profile_lines]
        right_lines = [line.text for line in right_profile_lines]
        changes: list[Change] = []
        for index, (kind, left_index, right_index, before, after) in enumerate(line_changes(left_lines, right_lines), start=1):
            left_line_number = left_profile_lines[left_index].line_number if left_index is not None else None
            right_line_number = right_profile_lines[right_index].line_number if right_index is not None else None
            risky = is_risky_change(before, after)
            notes = "line diff"
            if risky:
                notes = f"{notes}; {risk_note(before, after)}"
            changes.append(
                Change(
                    change_id=f"text-{index}",
                    change_type=kind,  # type: ignore[arg-type]
                    severity="risk" if risky else "normal",
                    source_location=ChangeLocation(str(left_path), line=left_line_number) if left_line_number is not None else None,
                    target_location=ChangeLocation(str(right_path), line=right_line_number) if right_line_number is not None else None,
                    before=before,
                    after=after,
                    format="text",
                    confidence=1.0,
                    notes=notes,
                )
            )
        file_kind = "config" if left_path.suffix.lower() in CONFIG_SUFFIXES or left_path.name.lower() in {"dockerfile", ".gitignore"} else "text"
        return ComparisonResult(str(left_path), str(right_path), file_kind, changes)

    def _compare_mapping(self, left_path: Path, right_path: Path, left_data: Any, right_data: Any, format_name: str) -> ComparisonResult:
        changes: list[Change] = []
        for index, (key_path, before, after, change_type) in enumerate(_diff_values(left_data, right_data), start=1):
            before_text = "" if before is None else str(before)
            after_text = "" if after is None else str(after)
            risky = is_risky_change(before_text, after_text, key_path)
            changes.append(
                Change(
                    change_id=f"{format_name}-{index}",
                    change_type=change_type,  # type: ignore[arg-type]
                    severity="risk" if risky else "normal",
                    source_location=ChangeLocation(str(left_path)),
                    target_location=ChangeLocation(str(right_path)),
                    before=before_text,
                    after=after_text,
                    format=format_name,
                    confidence=1.0,
                    notes=f"{key_path}; {risk_note(before_text, after_text, key_path)}" if risky else key_path,
                )
            )
        return ComparisonResult(str(left_path), str(right_path), "config", changes)


def _read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1251", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="replace")


def _load_json(path: Path) -> Any:
    return json.loads(_read_text(path))


def _load_toml(path: Path) -> Any:
    return tomllib.loads(_read_text(path))


def _load_yaml(path: Path) -> Any | None:
    try:
        import yaml
    except ModuleNotFoundError:
        return None
    return yaml.safe_load(_read_text(path))


def _load_ini(path: Path) -> dict[str, dict[str, str]]:
    parser = configparser.ConfigParser()
    parser.read_string(_read_text(path))
    return {section: dict(parser.items(section)) for section in parser.sections()}


def _try_load_ini(path: Path) -> dict[str, dict[str, str]] | None:
    try:
        return _load_ini(path)
    except configparser.Error:
        return None


def _load_key_value(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in _read_text(path).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _load_xml(path: Path) -> dict[str, str]:
    root = ET.fromstring(_read_text(path))
    values: dict[str, str] = {}

    def walk(node: ET.Element, prefix: str) -> None:
        current = f"{prefix}.{node.tag}" if prefix else node.tag
        text = (node.text or "").strip()
        if text:
            values[current] = text
        for key, value in sorted(node.attrib.items()):
            values[f"{current}.@{key}"] = value
        for child in node:
            walk(child, current)

    walk(root, "")
    return values


def _diff_values(left: Any, right: Any, prefix: str = "") -> list[tuple[str, Any, Any, str]]:
    if isinstance(left, dict) and isinstance(right, dict):
        changes: list[tuple[str, Any, Any, str]] = []
        for key in sorted(set(left) | set(right), key=str):
            key_path = f"{prefix}.{key}" if prefix else str(key)
            if key not in left:
                changes.append((key_path, None, right[key], "added"))
            elif key not in right:
                changes.append((key_path, left[key], None, "removed"))
            else:
                changes.extend(_diff_values(left[key], right[key], key_path))
        return changes
    if left != right:
        return [(prefix, left, right, "modified")]
    return []

from __future__ import annotations

from html import escape
from pathlib import Path

from file_compare_app.core.models import Change, ChangeLocation, ComparisonResult


TEXTUAL_KINDS = {"text", "config"}
CHANGE_LABELS = {
    "added": "Добавлено",
    "removed": "Удалено",
    "modified": "Изменено",
}


def change_type_label(change_type: str) -> str:
    return CHANGE_LABELS.get(change_type, change_type)


def compact_location(location: ChangeLocation | None) -> str:
    if location is None:
        return ""
    if location.sheet and location.cell:
        return f"{location.sheet}!{location.cell}"
    if location.page is not None and location.ocr_line is not None:
        return f"стр. {location.page}, OCR {location.ocr_line}"
    if location.page is not None:
        return f"стр. {location.page}"
    if location.line is not None and location.column is not None:
        return f"строка {location.line}, колонка {location.column}"
    if location.line is not None:
        return f"строка {location.line}"
    if location.byte_offset is not None and location.byte_length is not None:
        return f"bytes {location.byte_offset}-{location.byte_offset + location.byte_length}"
    if location.x is not None and location.y is not None and location.width is not None and location.height is not None:
        return f"{location.x},{location.y} {location.width}x{location.height}"
    return Path(location.path).name


def render_result_html(result: ComparisonResult) -> tuple[str, str]:
    if result.file_kind in TEXTUAL_KINDS:
        left_lines = _read_display_lines(Path(result.left_path))
        right_lines = _read_display_lines(Path(result.right_path))
        return (
            _render_lines(left_lines, _line_classes(result.changes, "left")),
            _render_lines(right_lines, _line_classes(result.changes, "right")),
        )
    return _render_change_table(result, "left"), _render_change_table(result, "right")


def _read_display_lines(path: Path) -> list[str]:
    for encoding in ("utf-8-sig", "utf-8", "cp1251", "latin-1"):
        try:
            return path.read_text(encoding=encoding).splitlines()
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="replace").splitlines()


def _line_classes(changes: list[Change], side: str) -> dict[int, tuple[str, str]]:
    classes: dict[int, tuple[str, str]] = {}
    for change in changes:
        if side == "left":
            location = change.source_location
            if location is None or location.line is None:
                continue
            if change.change_type == "removed":
                classes[location.line] = ("old", change_type_label(change.change_type))
            elif change.change_type == "modified":
                classes[location.line] = ("old", change_type_label(change.change_type))
        else:
            location = change.target_location
            if location is None or location.line is None:
                continue
            if change.change_type == "added":
                classes[location.line] = ("added", change_type_label(change.change_type))
            elif change.change_type == "modified":
                classes[location.line] = ("new", change_type_label(change.change_type))
    return classes


def _render_lines(lines: list[str], line_classes: dict[int, tuple[str, str]]) -> str:
    rows = []
    for index, line in enumerate(lines, start=1):
        css_class, label = line_classes.get(index, ("", ""))
        badge = f"<span class='badge'>{escape(label)}</span>" if label else ""
        rows.append(
            f"<p class='line {css_class}'><span class='ln'>{index}</span>"
            f"{badge}<span class='txt'>{escape(line)}</span></p>"
        )
    return _wrap_lines("".join(rows))


def _render_change_table(result: ComparisonResult, side: str) -> str:
    rows = []
    for index, change in enumerate(result.changes, start=1):
        value = change.before if side == "left" else change.after
        css_class = "old" if side == "left" else "new"
        if change.change_type == "added" and side == "left":
            value = ""
            css_class = ""
        if change.change_type == "removed" and side == "right":
            value = ""
            css_class = ""
        badge = f"<span class='badge'>{escape(change_type_label(change.change_type))}</span>" if value else ""
        rows.append(
            f"<p class='line {css_class}'><span class='ln'>{index}</span>"
            f"{badge}<span class='txt'>{escape(value)}</span></p>"
        )
    if not rows:
        rows.append("<p class='line'><span class='ln'>1</span><span class='txt'>Изменений не найдено</span></p>")
    return _wrap_lines("".join(rows))


def _wrap_lines(rows: str) -> str:
    return f"""
    <style>
      body {{ margin: 0; font-family: Consolas, 'Courier New'; font-size: 12px; color: #111827; }}
      p.line {{
        margin: 0;
        padding: 4px 8px;
        white-space: pre-wrap;
        word-wrap: break-word;
      }}
      span {{
        padding: 2px 6px;
      }}
      span.ln {{
        display: inline-block;
        min-width: 38px;
        color: #8a95a8;
        background: #f8fafc;
        text-align: right;
        border-right: 1px solid #eef2f7;
      }}
      span.badge {{
        display: inline-block;
        min-width: 72px;
        margin: 0 6px;
        border-radius: 6px;
        text-align: center;
        font-family: Segoe UI, Arial;
        font-size: 11px;
        font-weight: 700;
        color: #344054;
        background: #f2f4f7;
      }}
      span.txt {{
        white-space: pre-wrap;
        word-wrap: break-word;
      }}
      p.old {{ background: #fff1f0; color: #b42318; }}
      p.new {{ background: #ecfdf3; color: #087443; }}
      p.added {{ background: #ecfdf3; color: #087443; }}
      p.warn {{ background: #fffaeb; color: #b54708; }}
      p.focus {{ background: #eff6ff; color: #1d4ed8; }}
    </style>
    {rows}
    """

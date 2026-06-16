from pathlib import Path

from file_compare_app.core.orchestrator import compare_files
from file_compare_app.ui.diff_view import render_result_html


def test_render_result_html_shows_full_text_with_line_numbers_and_highlights(tmp_path: Path) -> None:
    old = tmp_path / "old.txt"
    new = tmp_path / "new.txt"
    old.write_text("host=localhost\ntimeout=30\nenabled=true\n", encoding="utf-8")
    new.write_text("host=localhost\ntimeout=45\nenabled=true\nmode=strict\n", encoding="utf-8")
    result = compare_files(old, new)

    left_html, right_html = render_result_html(result)

    assert "host=localhost" in left_html
    assert "host=localhost" in right_html
    assert "<span class='ln'>2</span>" in left_html
    assert "timeout=30" in left_html
    assert "timeout=45" in right_html
    assert "line old" in left_html
    assert "line new" in right_html
    assert "mode=strict" in right_html
    assert "line added" in right_html


def test_render_result_html_marks_change_type_and_allows_wrapping(tmp_path: Path) -> None:
    old = tmp_path / "old.cfg"
    new = tmp_path / "new.cfg"
    long_line = "access-list acl_inside_in extended permit object-group VERY_LONG_OBJECT_NAME " * 4
    old.write_text(f"same\n{long_line}old\n", encoding="utf-8")
    new.write_text(f"same\n{long_line}new\nadded-value\n", encoding="utf-8")
    result = compare_files(old, new)

    left_html, right_html = render_result_html(result)

    assert "Изменено" in left_html
    assert "Изменено" in right_html
    assert "Добавлено" in right_html
    assert "white-space: pre-wrap" in left_html
    assert "white-space: nowrap" not in left_html
    assert "word-wrap: break-word" in right_html

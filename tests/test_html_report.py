from file_compare_app.core.models import Change, ChangeLocation, ComparisonResult
from file_compare_app.reports.html_report import render_html_report


def test_html_report_escapes_content_and_includes_credit() -> None:
    result = ComparisonResult(
        left_path="old.txt",
        right_path="new.txt",
        file_kind="text",
        changes=[
            Change(
                change_id="c1",
                change_type="modified",
                severity="normal",
                source_location=ChangeLocation(path="old.txt", line=1),
                target_location=ChangeLocation(path="new.txt", line=1),
                before="<old>",
                after="<new>",
                format="text",
                confidence=1.0,
                notes="line diff",
            )
        ],
    )

    html = render_html_report(result)

    assert "&lt;old&gt;" in html
    assert "&lt;new&gt;" in html
    assert "Разработал: Абдрахманов Амаль Даулетович" in html


def test_html_report_uses_modern_summary_and_compact_locations() -> None:
    result = ComparisonResult(
        left_path="old.txt",
        right_path="new.txt",
        file_kind="text",
        changes=[
            Change(
                change_id="c1",
                change_type="modified",
                severity="normal",
                source_location=ChangeLocation(path="old.txt", line=1),
                target_location=ChangeLocation(path="new.txt", line=1),
                before="timeout=30",
                after="timeout=45",
                format="config",
                confidence=1.0,
                notes="line diff",
            ),
            Change(
                change_id="c2",
                change_type="added",
                severity="info",
                source_location=None,
                target_location=ChangeLocation(path="new.txt", line=2),
                before="",
                after="strict=true",
                format="config",
                confidence=1.0,
            ),
        ],
    )

    html = render_html_report(result)

    assert 'class="summary-grid"' in html
    assert "Сравнение файлов" in html
    assert "Найдено изменений: 2" in html
    assert "строка 1" in html
    assert "строка 2" in html


def test_html_report_localizes_change_type_column() -> None:
    result = ComparisonResult(
        left_path="old.txt",
        right_path="new.txt",
        file_kind="text",
        changes=[
            Change(
                change_id="c1",
                change_type="modified",
                severity="normal",
                source_location=ChangeLocation(path="old.txt", line=1),
                target_location=ChangeLocation(path="new.txt", line=1),
                before="a",
                after="b",
                format="text",
                confidence=1.0,
            ),
            Change(
                change_id="c2",
                change_type="added",
                severity="info",
                source_location=None,
                target_location=ChangeLocation(path="new.txt", line=2),
                before="",
                after="c",
                format="text",
                confidence=1.0,
            ),
            Change(
                change_id="c3",
                change_type="removed",
                severity="normal",
                source_location=ChangeLocation(path="old.txt", line=3),
                target_location=None,
                before="d",
                after="",
                format="text",
                confidence=1.0,
            ),
        ],
    )

    html = render_html_report(result)

    assert ">Изменено<" in html
    assert ">Добавлено<" in html
    assert ">Удалено<" in html
    assert ">modified<" not in html
    assert ">added<" not in html
    assert ">removed<" not in html

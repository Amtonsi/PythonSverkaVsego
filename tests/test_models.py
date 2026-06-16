from file_compare_app.core.models import Change, ChangeLocation, ComparisonResult


def test_change_location_display_for_line() -> None:
    location = ChangeLocation(path="old.txt", line=42, column=3)
    assert location.display() == "old.txt:42:3"


def test_change_location_display_for_page_and_cell() -> None:
    page_location = ChangeLocation(path="scan.pdf", page=4, ocr_line=12)
    cell_location = ChangeLocation(path="book.xlsx", sheet="Sheet1", cell="B7")
    assert page_location.display() == "scan.pdf page 4 OCR line 12"
    assert cell_location.display() == "book.xlsx Sheet1!B7"


def test_comparison_result_counts_changes() -> None:
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
                notes="line changed",
            )
        ],
    )
    assert result.change_count == 1
    assert result.has_changes is True

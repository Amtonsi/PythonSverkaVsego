from pathlib import Path

import pytest


def test_xlsx_analyzer_reports_changed_cell(tmp_path: Path) -> None:
    pytest.importorskip("openpyxl")
    from openpyxl import Workbook

    from file_compare_app.analyzers.xlsx import XlsxAnalyzer

    old = tmp_path / "old.xlsx"
    new = tmp_path / "new.xlsx"
    old_wb = Workbook()
    old_wb.active["B7"] = "old"
    old_wb.save(old)
    new_wb = Workbook()
    new_wb.active["B7"] = "new"
    new_wb.save(new)

    result = XlsxAnalyzer().compare(old, new)

    assert result.file_kind == "xlsx"
    assert result.change_count == 1
    assert result.changes[0].target_location.cell == "B7"
    assert result.changes[0].before == "old"
    assert result.changes[0].after == "new"


def test_image_analyzer_reports_changed_region(tmp_path: Path) -> None:
    pytest.importorskip("PIL")
    from PIL import Image

    from file_compare_app.analyzers.image import ImageAnalyzer

    old = tmp_path / "old.png"
    new = tmp_path / "new.png"
    Image.new("RGB", (4, 4), "white").save(old)
    image = Image.new("RGB", (4, 4), "white")
    image.putpixel((2, 1), (0, 0, 0))
    image.save(new)

    result = ImageAnalyzer().compare(old, new)

    assert result.file_kind == "image"
    assert result.change_count == 1
    assert result.changes[0].target_location.x == 2
    assert result.changes[0].target_location.y == 1

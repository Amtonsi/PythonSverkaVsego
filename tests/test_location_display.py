from file_compare_app.core.models import ChangeLocation
from file_compare_app.ui.diff_view import compact_location


def test_compact_location_prefers_human_short_places() -> None:
    assert compact_location(ChangeLocation(path=r"C:\very\long\old.txt", line=2)) == "строка 2"
    assert compact_location(ChangeLocation(path="book.xlsx", sheet="Sheet1", cell="B7")) == "Sheet1!B7"
    assert compact_location(ChangeLocation(path="scan.pdf", page=4, ocr_line=12)) == "стр. 4, OCR 12"
    assert compact_location(ChangeLocation(path="file.bin", byte_offset=3, byte_length=1)) == "bytes 3-4"

from pathlib import Path

from file_compare_app.analyzers.binary import BinaryAnalyzer


def test_binary_analyzer_reports_byte_offset(tmp_path: Path) -> None:
    old = tmp_path / "old.bin"
    new = tmp_path / "new.bin"
    old.write_bytes(b"abc123")
    new.write_bytes(b"abc923")

    result = BinaryAnalyzer().compare(old, new)

    assert result.file_kind == "binary"
    assert result.change_count == 1
    assert result.changes[0].change_type == "binary"
    assert result.changes[0].source_location.byte_offset == 3
    assert result.changes[0].before == "31"
    assert result.changes[0].after == "39"

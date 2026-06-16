from pathlib import Path

from file_compare_app.core.orchestrator import compare_files


def test_orchestrator_uses_text_analyzer(tmp_path: Path) -> None:
    old = tmp_path / "old.txt"
    new = tmp_path / "new.txt"
    old.write_text("a\nb\n", encoding="utf-8")
    new.write_text("a\nc\n", encoding="utf-8")

    result = compare_files(old, new)

    assert result.file_kind == "text"
    assert result.change_count == 1
    assert result.changes[0].before == "b"
    assert result.changes[0].after == "c"


def test_orchestrator_uses_binary_fallback(tmp_path: Path) -> None:
    old = tmp_path / "old.unknown"
    new = tmp_path / "new.unknown"
    old.write_bytes(b"a")
    new.write_bytes(b"b")

    result = compare_files(old, new)

    assert result.file_kind == "binary"

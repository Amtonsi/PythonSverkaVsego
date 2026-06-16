import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from file_compare_app.ui.main_window import DropFileButton, MainWindow


def _app() -> QApplication:
    return QApplication.instance() or QApplication(sys.argv)


def test_main_window_assigns_selected_files(tmp_path: Path) -> None:
    _app()
    left = tmp_path / "old.conf"
    right = tmp_path / "new.conf"
    left.write_text("timeout=30", encoding="utf-8")
    right.write_text("timeout=45", encoding="utf-8")

    window = MainWindow()
    window.assign_left_file(left)
    window.assign_right_file(right)

    assert window.left_path == left
    assert window.right_path == right
    assert window.left_file_name.text() == "old.conf"
    assert window.right_file_name.text() == "new.conf"
    assert "10 B" in window.left_file_note.text()
    assert "10 B" in window.right_file_note.text()


def test_drop_file_button_accepts_existing_file(tmp_path: Path) -> None:
    _app()
    dropped: list[Path] = []
    source = tmp_path / "config.yaml"
    source.write_text("mode: local", encoding="utf-8")

    button = DropFileButton("leftFileChip", "OLD", "Select", "Drop", dropped.append)
    button.handle_file_path(source)

    assert dropped == [source]


def test_drop_file_button_ignores_missing_path(tmp_path: Path) -> None:
    _app()
    dropped: list[Path] = []
    missing = tmp_path / "missing.txt"

    button = DropFileButton("rightFileChip", "NEW", "Select", "Drop", dropped.append)
    button.handle_file_path(missing)

    assert dropped == []

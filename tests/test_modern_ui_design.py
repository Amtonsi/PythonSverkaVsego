import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QMessageBox, QPushButton, QTextEdit

from file_compare_app.core.models import Change, ChangeLocation, ComparisonResult
from file_compare_app.ui.main_window import MainWindow


def test_main_window_uses_approved_modern_layout() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()

    assert window.windowTitle() == "Сравнение файлов"
    assert window.windowFlags() & Qt.FramelessWindowHint
    assert not window.windowIcon().isNull()

    required_objects = [
        "titleBar",
        "brandMark",
        "brandTitle",
        "brandTag",
        "toolbar",
        "leftFileChip",
        "rightFileChip",
        "privacyPill",
        "compareArea",
        "compareTabs",
        "viewerGrid",
        "rightSidebar",
        "statusbarCustom",
        "developerCredit",
    ]
    for object_name in required_objects:
        assert window.findChild(object, object_name) is not None

    assert window.findChild(object, "brandTitle").text() == "Сравнение файлов"
    assert "Абдрахманов Амаль Даулетович" in window.findChild(object, "developerCredit").text()


def test_message_boxes_use_sf_window_icon() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()

    box = window._create_message_box(QMessageBox.Icon.Information, "Диагностика зависимостей", "Текст")

    assert box.windowTitle() == "Диагностика зависимостей"
    assert box.text() == "Текст"
    assert not box.windowIcon().isNull()


def test_main_window_has_background_progress_controls() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()

    assert window.findChild(object, "compareProgress") is not None
    assert window.findChild(object, "cancelCompareButton") is not None
    assert not window.cancel_button.isEnabled()

    window._set_compare_busy(True)

    assert not window.compare_button.isEnabled()
    assert window.cancel_button.isEnabled()
    assert window.progress_bar.value() == 0

    window._set_compare_busy(False)

    assert window.compare_button.isEnabled()
    assert not window.cancel_button.isEnabled()


def test_compare_toolbar_does_not_restore_registry_search_when_windowed() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()

    window._set_mode("compare")
    window._apply_responsive_toolbar(1280)

    assert window.registry_search_box.isHidden()
    assert window.left_file_name.text() == "Исходный файл"
    assert window.right_file_name.text() == "Новая версия"
    assert not window.compare_button.isHidden()
    assert not window.export_button.isHidden()


def test_main_window_formats_dependency_diagnostics() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()

    report = window._dependency_diagnostics_text()

    assert "Диагностика" in report
    assert "DOCX" in report
    assert "PDF" in report
    assert "OCR" in report


def test_compare_view_tabs_are_clickable_controls() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()

    for object_name in ("compareTabText", "compareTabPages", "compareTabOcr", "compareTabHex"):
        button = window.findChild(QPushButton, object_name)
        assert button is not None
        assert button.cursor().shape() == Qt.PointingHandCursor

    window.compare_tab_buttons["ocr"].click()

    assert window.compare_view_mode == "ocr"
    assert window.compare_tab_buttons["ocr"].property("active") is True
    assert window.compare_tab_buttons["text"].property("active") is False


def test_compare_viewers_wrap_long_lines() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()

    assert window.left_view["text"].lineWrapMode() == QTextEdit.WidgetWidth
    assert window.right_view["text"].lineWrapMode() == QTextEdit.WidgetWidth


def test_grouped_klp_changes_update_removed_and_added_counters(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    old_file = tmp_path / "old.klp"
    new_file = tmp_path / "new.klp"
    old_file.write_text("old", encoding="utf-8")
    new_file.write_text("new", encoding="utf-8")
    result = ComparisonResult(
        left_path=str(old_file),
        right_path=str(new_file),
        file_kind="klp",
        changes=[
            Change(
                change_id="sections",
                change_type="modified",
                severity="normal",
                source_location=None,
                target_location=None,
                before="Секции удалены (388): old",
                after="Секции добавлены (16): new",
                format="klp",
                confidence=0.92,
                notes="KLP sections",
            ),
            Change(
                change_id="values",
                change_type="modified",
                severity="normal",
                source_location=None,
                target_location=None,
                before="Значения удалены (805): old",
                after="Значения добавлены (24): new",
                format="klp",
                confidence=0.92,
                notes="KLP values",
            ),
            Change(
                change_id="metadata",
                change_type="modified",
                severity="low",
                source_location=None,
                target_location=None,
                before="size_bytes: 1068993",
                after="size_bytes: 1068974",
                format="klp",
                confidence=0.9,
                notes="KLP technical metadata",
            ),
        ],
    )

    window._render_result(result)

    assert window.removed_stat.number_label.text() == "1193"
    assert window.added_stat.number_label.text() == "40"


def test_change_filter_pills_are_clickable_controls() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()

    for object_name in ("changeFilterAll", "changeFilterText", "changeFilterOcr", "changeFilterRisk"):
        button = window.findChild(QPushButton, object_name)
        assert button is not None
        assert button.cursor().shape() == Qt.PointingHandCursor

    window.change_filter_buttons["ocr"].click()

    assert window.change_filter == "ocr"
    assert window.change_filter_buttons["ocr"].property("active") is True
    assert window.change_filter_buttons["all"].property("active") is False


def test_sync_scroll_control_links_both_document_viewers() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    toggle = window.findChild(QCheckBox, "syncScrollToggle")
    assert toggle is not None
    assert toggle.isChecked()
    assert toggle.cursor().shape() == Qt.PointingHandCursor

    long_text = "\n".join(f"line {index}" for index in range(200))
    window.left_view["text"].setPlainText(long_text)
    window.right_view["text"].setPlainText(long_text)
    window.resize(900, 360)
    window.show()
    app.processEvents()

    left_bar = window.left_view["text"].verticalScrollBar()
    right_bar = window.right_view["text"].verticalScrollBar()
    left_bar.setValue(left_bar.maximum())
    app.processEvents()

    assert right_bar.value() == right_bar.maximum()


def test_change_navigation_buttons_scroll_to_selected_change(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    old_file = tmp_path / "old.txt"
    new_file = tmp_path / "new.txt"
    old_file.write_text("\n".join(f"old line {index}" for index in range(220)), encoding="utf-8")
    new_file.write_text("\n".join(f"new line {index}" for index in range(220)), encoding="utf-8")
    result = ComparisonResult(
        left_path=str(old_file),
        right_path=str(new_file),
        file_kind="text",
        changes=[
            Change(
                change_id="first",
                change_type="modified",
                severity="normal",
                source_location=ChangeLocation(path=str(old_file), line=5),
                target_location=ChangeLocation(path=str(new_file), line=5),
                before="old line 5",
                after="new line 5",
                format="text",
                confidence=1.0,
            ),
            Change(
                change_id="second",
                change_type="modified",
                severity="normal",
                source_location=ChangeLocation(path=str(old_file), line=190),
                target_location=ChangeLocation(path=str(new_file), line=190),
                before="old line 190",
                after="new line 190",
                format="text",
                confidence=1.0,
            ),
        ],
    )

    window.resize(900, 360)
    window.show()
    window._render_result(result)
    app.processEvents()
    start_value = window.left_view["text"].verticalScrollBar().value()

    window.next_button.click()
    app.processEvents()

    assert window.changes_list.currentRow() == 1
    assert window.left_view["text"].verticalScrollBar().value() > start_value

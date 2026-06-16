import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from file_compare_app.core.models import ComparisonResult
from file_compare_app.ui.compare_worker import CompareWorker


def _app() -> QApplication:
    return QApplication.instance() or QApplication(sys.argv)


def test_compare_worker_emits_progress_and_result(tmp_path: Path) -> None:
    _app()
    left = tmp_path / "old.txt"
    right = tmp_path / "new.txt"
    left.write_text("old", encoding="utf-8")
    right.write_text("new", encoding="utf-8")
    result = ComparisonResult(str(left), str(right), "text")

    def fake_compare(left_path: Path, right_path: Path) -> ComparisonResult:
        assert left_path == left
        assert right_path == right
        return result

    worker = CompareWorker(left, right, compare_func=fake_compare)
    progress: list[tuple[int, str]] = []
    finished: list[ComparisonResult] = []
    worker.progress.connect(lambda value, message: progress.append((value, message)))
    worker.finished.connect(finished.append)

    worker.run()

    assert [value for value, _message in progress] == [10, 70, 100]
    assert finished == [result]


def test_compare_worker_can_be_canceled_before_compare(tmp_path: Path) -> None:
    _app()
    left = tmp_path / "old.txt"
    right = tmp_path / "new.txt"
    left.write_text("old", encoding="utf-8")
    right.write_text("new", encoding="utf-8")
    calls: list[str] = []

    def fake_compare(left_path: Path, right_path: Path) -> ComparisonResult:
        calls.append("called")
        return ComparisonResult(str(left_path), str(right_path), "text")

    worker = CompareWorker(left, right, compare_func=fake_compare)
    canceled: list[bool] = []
    worker.canceled.connect(lambda: canceled.append(True))

    worker.cancel()
    worker.run()

    assert calls == []
    assert canceled == [True]

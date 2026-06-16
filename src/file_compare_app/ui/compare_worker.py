from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from file_compare_app.analyzers.base import AnalyzerDependencyError
from file_compare_app.core.models import ComparisonResult
from file_compare_app.core.orchestrator import compare_files


CompareFunc = Callable[[Path, Path], ComparisonResult]


class CompareWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(object)
    failed = Signal(str, str)
    canceled = Signal()

    def __init__(self, left_path: Path | str, right_path: Path | str, compare_func: CompareFunc = compare_files) -> None:
        super().__init__()
        self.left_path = Path(left_path)
        self.right_path = Path(right_path)
        self._compare_func = compare_func
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        if self._cancel_requested:
            self.canceled.emit()
            return

        self.progress.emit(10, "Подготовка файлов")
        if self._cancel_requested:
            self.canceled.emit()
            return

        self.progress.emit(70, "Сравнение содержимого")
        try:
            result = self._compare_func(self.left_path, self.right_path)
        except AnalyzerDependencyError as exc:
            self.failed.emit("Не хватает зависимости", str(exc))
            return
        except Exception as exc:
            self.failed.emit("Ошибка сравнения", f"Не удалось сравнить файлы: {exc.__class__.__name__}")
            return

        if self._cancel_requested:
            self.canceled.emit()
            return

        self.progress.emit(100, "Готово")
        self.finished.emit(result)

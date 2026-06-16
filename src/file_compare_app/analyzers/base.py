from abc import ABC, abstractmethod
from pathlib import Path

from file_compare_app.core.models import ComparisonResult


class AnalyzerDependencyError(RuntimeError):
    pass


class Analyzer(ABC):
    @abstractmethod
    def compare(self, left_path: Path, right_path: Path) -> ComparisonResult:
        raise NotImplementedError

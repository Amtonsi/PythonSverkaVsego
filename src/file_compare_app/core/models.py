from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


ChangeType = Literal["added", "removed", "modified", "moved", "metadata", "binary"]
Severity = Literal["info", "normal", "warning", "risk"]


@dataclass(frozen=True)
class ChangeLocation:
    path: str
    line: int | None = None
    column: int | None = None
    page: int | None = None
    ocr_line: int | None = None
    sheet: str | None = None
    cell: str | None = None
    byte_offset: int | None = None
    byte_length: int | None = None
    x: int | None = None
    y: int | None = None
    width: int | None = None
    height: int | None = None

    def display(self) -> str:
        if self.sheet and self.cell:
            return f"{self.path} {self.sheet}!{self.cell}"
        if self.page is not None and self.ocr_line is not None:
            return f"{self.path} page {self.page} OCR line {self.ocr_line}"
        if self.page is not None:
            return f"{self.path} page {self.page}"
        if self.line is not None and self.column is not None:
            return f"{self.path}:{self.line}:{self.column}"
        if self.line is not None:
            return f"{self.path}:{self.line}"
        if self.byte_offset is not None and self.byte_length is not None:
            end = self.byte_offset + self.byte_length
            return f"{self.path} bytes {self.byte_offset}-{end}"
        if self.x is not None and self.y is not None and self.width is not None and self.height is not None:
            return f"{self.path} region {self.x},{self.y},{self.width}x{self.height}"
        return self.path


@dataclass(frozen=True)
class Change:
    change_id: str
    change_type: ChangeType
    severity: Severity
    source_location: ChangeLocation | None
    target_location: ChangeLocation | None
    before: str
    after: str
    format: str
    confidence: float
    notes: str = ""


@dataclass(frozen=True)
class ComparisonResult:
    left_path: str
    right_path: str
    file_kind: str
    changes: list[Change] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def change_count(self) -> int:
        return len(self.changes)

    @property
    def has_changes(self) -> bool:
        return bool(self.changes)

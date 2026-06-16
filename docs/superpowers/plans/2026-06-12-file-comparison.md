# File Comparison Desktop App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working Windows desktop version of **Сравнение файлов**, a local Python app that compares two files and shows what changed, where it changed, and what the old and new values are.

**Architecture:** The app uses a PySide6 desktop shell over a pure-Python comparison core. File-specific analyzers convert text, configs, DOCX, PDF/OCR, Excel, images, and binary files into one shared `ComparisonResult` model consumed by the UI and report exporter.

**Tech Stack:** Python 3.12+, PySide6, pytest, python-docx, PyMuPDF, pytesseract/Tesseract, Pillow, openpyxl, PyYAML, PyInstaller.

---

## Scope

This plan builds a complete first release with:

- Windows desktop UI matching the approved document-centric design.
- Strict local mode enabled by default.
- Shared comparison model.
- Text/config diff.
- DOCX text/table extraction diff.
- PDF text-layer diff and OCR fallback.
- XLSX workbook/cell diff.
- Image visual diff and OCR text extraction.
- Binary/hex fallback for unknown files.
- HTML report export.
- PyInstaller packaging entry point.

## File Structure

Create this project structure:

```text
pyproject.toml
README.md
src/file_compare_app/__init__.py
src/file_compare_app/__main__.py
src/file_compare_app/app.py
src/file_compare_app/core/models.py
src/file_compare_app/core/type_detection.py
src/file_compare_app/core/orchestrator.py
src/file_compare_app/core/text_diff.py
src/file_compare_app/analyzers/base.py
src/file_compare_app/analyzers/text_config.py
src/file_compare_app/analyzers/docx.py
src/file_compare_app/analyzers/pdf.py
src/file_compare_app/analyzers/xlsx.py
src/file_compare_app/analyzers/image.py
src/file_compare_app/analyzers/binary.py
src/file_compare_app/security/strict_mode.py
src/file_compare_app/reports/html_report.py
src/file_compare_app/ui/main_window.py
tests/conftest.py
tests/fixtures/sample_old.txt
tests/fixtures/sample_new.txt
tests/test_models.py
tests/test_type_detection.py
tests/test_text_config_analyzer.py
tests/test_binary_analyzer.py
tests/test_orchestrator.py
tests/test_strict_mode.py
tests/test_html_report.py
tests/test_optional_analyzers.py
```

Responsibilities:

- `core/models.py`: shared result/location dataclasses.
- `core/type_detection.py`: detect file kind from suffix and light content checks.
- `core/text_diff.py`: reusable line and word diff helpers.
- `core/orchestrator.py`: choose analyzer and run comparison.
- `analyzers/*`: one analyzer per file family.
- `security/strict_mode.py`: temp directory and safe logging helpers.
- `reports/html_report.py`: local HTML report generation.
- `ui/main_window.py`: PySide6 window, layout, actions, and result binding.

---

### Task 1: Project Scaffold and Test Harness

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/file_compare_app/__init__.py`
- Create: `src/file_compare_app/__main__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write project metadata**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "file-compare-app"
version = "0.1.0"
description = "Local Windows desktop app for comparing files"
requires-python = ">=3.12"
dependencies = [
  "PySide6>=6.7",
  "python-docx>=1.1",
  "PyMuPDF>=1.24",
  "pytesseract>=0.3",
  "Pillow>=10.0",
  "openpyxl>=3.1",
  "PyYAML>=6.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pytest-qt>=4.4",
  "pyinstaller>=6.0",
]

[project.scripts]
file-compare-app = "file_compare_app.__main__:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-ra"
```

- [ ] **Step 2: Add README**

Create `README.md`:

```markdown
# Сравнение файлов

Локальное Windows-приложение на Python для сравнения файлов: документы, config-файлы, PDF, Excel, изображения и неизвестные бинарные форматы.

## Development

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m pytest
.venv\Scripts\python -m file_compare_app
```

Приложение работает локально. Текст документов не пишется в логи.
```

- [ ] **Step 3: Add package entry points**

Create `src/file_compare_app/__init__.py`:

```python
__all__ = ["__version__"]

__version__ = "0.1.0"
```

Create `src/file_compare_app/__main__.py`:

```python
from file_compare_app.app import run_app


def main() -> int:
    return run_app()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Add pytest fixture path helper**

Create `tests/conftest.py`:

```python
from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"
```

- [ ] **Step 5: Run empty test harness**

Run:

```powershell
python -m pytest
```

Expected: pytest starts successfully and reports no tests collected or no failures.

- [ ] **Step 6: Commit**

Run:

```powershell
git add pyproject.toml README.md src tests
git commit -m "chore: scaffold file comparison app"
```

---

### Task 2: Shared Comparison Model

**Files:**
- Create: `src/file_compare_app/core/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing model tests**

Create `tests/test_models.py`:

```python
from file_compare_app.core.models import Change, ChangeLocation, ComparisonResult


def test_change_location_display_for_line() -> None:
    location = ChangeLocation(path="old.txt", line=42, column=3)
    assert location.display() == "old.txt:42:3"


def test_change_location_display_for_page_and_cell() -> None:
    page_location = ChangeLocation(path="scan.pdf", page=4, ocr_line=12)
    cell_location = ChangeLocation(path="book.xlsx", sheet="Sheet1", cell="B7")
    assert page_location.display() == "scan.pdf page 4 OCR line 12"
    assert cell_location.display() == "book.xlsx Sheet1!B7"


def test_comparison_result_counts_changes() -> None:
    result = ComparisonResult(
        left_path="old.txt",
        right_path="new.txt",
        file_kind="text",
        changes=[
            Change(
                change_id="c1",
                change_type="modified",
                severity="normal",
                source_location=ChangeLocation(path="old.txt", line=1),
                target_location=ChangeLocation(path="new.txt", line=1),
                before="a",
                after="b",
                format="text",
                confidence=1.0,
                notes="line changed",
            )
        ],
    )
    assert result.change_count == 1
    assert result.has_changes is True
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_models.py -v
```

Expected: FAIL because `file_compare_app.core.models` does not exist.

- [ ] **Step 3: Implement shared dataclasses**

Create `src/file_compare_app/core/models.py`:

```python
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
```

- [ ] **Step 4: Run model tests**

Run:

```powershell
python -m pytest tests/test_models.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/file_compare_app/core/models.py tests/test_models.py
git commit -m "feat: add shared comparison result model"
```

---

### Task 3: File Type Detection

**Files:**
- Create: `src/file_compare_app/core/type_detection.py`
- Create: `tests/test_type_detection.py`

- [ ] **Step 1: Write failing detection tests**

Create `tests/test_type_detection.py`:

```python
from pathlib import Path

from file_compare_app.core.type_detection import detect_file_kind


def test_detects_known_extensions(tmp_path: Path) -> None:
    cases = {
        "a.txt": "text",
        "a.json": "config",
        "a.yaml": "config",
        "a.yml": "config",
        "a.toml": "config",
        "a.ini": "config",
        "a.env": "config",
        "a.xml": "config",
        "a.docx": "docx",
        "a.pdf": "pdf",
        "a.xlsx": "xlsx",
        "a.png": "image",
        "Dockerfile": "config",
        ".gitignore": "config",
    }
    for name, expected in cases.items():
        path = tmp_path / name
        path.write_text("sample", encoding="utf-8")
        assert detect_file_kind(path) == expected


def test_unknown_extension_falls_back_to_binary(tmp_path: Path) -> None:
    path = tmp_path / "archive.binpack"
    path.write_bytes(b"\x00\x01\x02")
    assert detect_file_kind(path) == "binary"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_type_detection.py -v
```

Expected: FAIL because `detect_file_kind` does not exist.

- [ ] **Step 3: Implement detection**

Create `src/file_compare_app/core/type_detection.py`:

```python
from pathlib import Path


TEXT_EXTENSIONS = {".txt", ".md", ".log", ".csv", ".tsv", ".py", ".sql", ".css", ".js", ".html"}
CONFIG_EXTENSIONS = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env", ".properties", ".xml"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}


def detect_file_kind(path: Path) -> str:
    name = path.name.lower()
    suffix = path.suffix.lower()

    if name in {"dockerfile", ".gitignore"}:
        return "config"
    if suffix in TEXT_EXTENSIONS:
        return "text"
    if suffix in CONFIG_EXTENSIONS:
        return "config"
    if suffix == ".docx":
        return "docx"
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".xlsx", ".xlsm"}:
        return "xlsx"
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    return "binary"
```

- [ ] **Step 4: Run detection tests**

Run:

```powershell
python -m pytest tests/test_type_detection.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/file_compare_app/core/type_detection.py tests/test_type_detection.py
git commit -m "feat: detect supported file kinds"
```

---

### Task 4: Text and Config Analyzer

**Files:**
- Create: `src/file_compare_app/analyzers/base.py`
- Create: `src/file_compare_app/core/text_diff.py`
- Create: `src/file_compare_app/analyzers/text_config.py`
- Create: `tests/fixtures/sample_old.txt`
- Create: `tests/fixtures/sample_new.txt`
- Create: `tests/test_text_config_analyzer.py`

- [ ] **Step 1: Write text fixtures**

Create `tests/fixtures/sample_old.txt`:

```text
host=localhost
timeout=30
enabled=true
```

Create `tests/fixtures/sample_new.txt`:

```text
host=localhost
timeout=45
enabled=true
mode=strict
```

- [ ] **Step 2: Write failing analyzer tests**

Create `tests/test_text_config_analyzer.py`:

```python
from pathlib import Path

from file_compare_app.analyzers.text_config import TextConfigAnalyzer


def test_text_diff_reports_modified_and_added_lines(fixtures_dir: Path) -> None:
    result = TextConfigAnalyzer().compare(
        fixtures_dir / "sample_old.txt",
        fixtures_dir / "sample_new.txt",
    )
    assert result.file_kind == "text"
    assert result.change_count == 2
    assert result.changes[0].before == "timeout=30"
    assert result.changes[0].after == "timeout=45"
    assert result.changes[0].source_location.display().endswith(":2")
    assert result.changes[1].change_type == "added"
    assert result.changes[1].after == "mode=strict"


def test_json_structural_diff_reports_key_path(tmp_path: Path) -> None:
    old = tmp_path / "old.json"
    new = tmp_path / "new.json"
    old.write_text('{"database": {"host": "old"}, "timeout": 30}', encoding="utf-8")
    new.write_text('{"database": {"host": "new"}, "timeout": 30}', encoding="utf-8")

    result = TextConfigAnalyzer().compare(old, new)

    assert result.file_kind == "config"
    assert result.change_count == 1
    assert result.changes[0].before == "old"
    assert result.changes[0].after == "new"
    assert result.changes[0].notes == "database.host"
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_text_config_analyzer.py -v
```

Expected: FAIL because `TextConfigAnalyzer` does not exist.

- [ ] **Step 4: Implement analyzer base and text diff**

Create `src/file_compare_app/analyzers/base.py`:

```python
from abc import ABC, abstractmethod
from pathlib import Path

from file_compare_app.core.models import ComparisonResult


class Analyzer(ABC):
    @abstractmethod
    def compare(self, left_path: Path, right_path: Path) -> ComparisonResult:
        raise NotImplementedError
```

Create `src/file_compare_app/core/text_diff.py`:

```python
from __future__ import annotations

from difflib import SequenceMatcher


def line_changes(left_lines: list[str], right_lines: list[str]) -> list[tuple[str, int | None, int | None, str, str]]:
    matcher = SequenceMatcher(a=left_lines, b=right_lines)
    changes: list[tuple[str, int | None, int | None, str, str]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace":
            max_len = max(i2 - i1, j2 - j1)
            for offset in range(max_len):
                left_index = i1 + offset if i1 + offset < i2 else None
                right_index = j1 + offset if j1 + offset < j2 else None
                before = left_lines[left_index] if left_index is not None else ""
                after = right_lines[right_index] if right_index is not None else ""
                changes.append(("modified", left_index, right_index, before, after))
        elif tag == "delete":
            for left_index in range(i1, i2):
                changes.append(("removed", left_index, None, left_lines[left_index], ""))
        elif tag == "insert":
            for right_index in range(j1, j2):
                changes.append(("added", None, right_index, "", right_lines[right_index]))
    return changes
```

- [ ] **Step 5: Implement text/config analyzer**

Create `src/file_compare_app/analyzers/text_config.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from file_compare_app.analyzers.base import Analyzer
from file_compare_app.core.models import Change, ChangeLocation, ComparisonResult
from file_compare_app.core.text_diff import line_changes


class TextConfigAnalyzer(Analyzer):
    def compare(self, left_path: Path, right_path: Path) -> ComparisonResult:
        if left_path.suffix.lower() == ".json" and right_path.suffix.lower() == ".json":
            return self._compare_json(left_path, right_path)
        if left_path.suffix.lower() in {".yaml", ".yml"} and right_path.suffix.lower() in {".yaml", ".yml"}:
            return self._compare_yaml(left_path, right_path)
        return self._compare_lines(left_path, right_path)

    def _compare_lines(self, left_path: Path, right_path: Path) -> ComparisonResult:
        left_lines = left_path.read_text(encoding="utf-8").splitlines()
        right_lines = right_path.read_text(encoding="utf-8").splitlines()
        changes: list[Change] = []
        for index, (kind, left_index, right_index, before, after) in enumerate(line_changes(left_lines, right_lines), start=1):
            changes.append(
                Change(
                    change_id=f"text-{index}",
                    change_type=kind,  # type: ignore[arg-type]
                    severity="normal",
                    source_location=ChangeLocation(str(left_path), line=left_index + 1) if left_index is not None else None,
                    target_location=ChangeLocation(str(right_path), line=right_index + 1) if right_index is not None else None,
                    before=before,
                    after=after,
                    format="text",
                    confidence=1.0,
                    notes="line diff",
                )
            )
        file_kind = "config" if left_path.suffix.lower() in {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env", ".properties", ".xml"} else "text"
        return ComparisonResult(str(left_path), str(right_path), file_kind, changes)

    def _compare_json(self, left_path: Path, right_path: Path) -> ComparisonResult:
        left_data = json.loads(left_path.read_text(encoding="utf-8"))
        right_data = json.loads(right_path.read_text(encoding="utf-8"))
        return self._compare_mapping(left_path, right_path, left_data, right_data, "json")

    def _compare_yaml(self, left_path: Path, right_path: Path) -> ComparisonResult:
        left_data = yaml.safe_load(left_path.read_text(encoding="utf-8"))
        right_data = yaml.safe_load(right_path.read_text(encoding="utf-8"))
        return self._compare_mapping(left_path, right_path, left_data, right_data, "yaml")

    def _compare_mapping(self, left_path: Path, right_path: Path, left_data: Any, right_data: Any, format_name: str) -> ComparisonResult:
        changes: list[Change] = []
        for index, (key_path, before, after) in enumerate(_diff_values(left_data, right_data), start=1):
            changes.append(
                Change(
                    change_id=f"{format_name}-{index}",
                    change_type="modified",
                    severity="normal",
                    source_location=ChangeLocation(str(left_path)),
                    target_location=ChangeLocation(str(right_path)),
                    before=str(before),
                    after=str(after),
                    format=format_name,
                    confidence=1.0,
                    notes=key_path,
                )
            )
        return ComparisonResult(str(left_path), str(right_path), "config", changes)


def _diff_values(left: Any, right: Any, prefix: str = "") -> list[tuple[str, Any, Any]]:
    if isinstance(left, dict) and isinstance(right, dict):
        changes: list[tuple[str, Any, Any]] = []
        for key in sorted(set(left) | set(right)):
            key_path = f"{prefix}.{key}" if prefix else str(key)
            if key not in left:
                changes.append((key_path, "", right[key]))
            elif key not in right:
                changes.append((key_path, left[key], ""))
            else:
                changes.extend(_diff_values(left[key], right[key], key_path))
        return changes
    if left != right:
        return [(prefix, left, right)]
    return []
```

- [ ] **Step 6: Run analyzer tests**

Run:

```powershell
python -m pytest tests/test_text_config_analyzer.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```powershell
git add src/file_compare_app/analyzers src/file_compare_app/core/text_diff.py tests/fixtures tests/test_text_config_analyzer.py
git commit -m "feat: compare text and config files"
```

---

### Task 5: Binary Fallback Analyzer

**Files:**
- Create: `src/file_compare_app/analyzers/binary.py`
- Create: `tests/test_binary_analyzer.py`

- [ ] **Step 1: Write failing binary tests**

Create `tests/test_binary_analyzer.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_binary_analyzer.py -v
```

Expected: FAIL because `BinaryAnalyzer` does not exist.

- [ ] **Step 3: Implement binary analyzer**

Create `src/file_compare_app/analyzers/binary.py`:

```python
from pathlib import Path

from file_compare_app.analyzers.base import Analyzer
from file_compare_app.core.models import Change, ChangeLocation, ComparisonResult


class BinaryAnalyzer(Analyzer):
    def compare(self, left_path: Path, right_path: Path) -> ComparisonResult:
        left = left_path.read_bytes()
        right = right_path.read_bytes()
        changes: list[Change] = []
        max_len = max(len(left), len(right))
        change_index = 1

        for offset in range(max_len):
            left_byte = left[offset : offset + 1]
            right_byte = right[offset : offset + 1]
            if left_byte == right_byte:
                continue
            changes.append(
                Change(
                    change_id=f"binary-{change_index}",
                    change_type="binary",
                    severity="normal",
                    source_location=ChangeLocation(str(left_path), byte_offset=offset, byte_length=1),
                    target_location=ChangeLocation(str(right_path), byte_offset=offset, byte_length=1),
                    before=left_byte.hex(),
                    after=right_byte.hex(),
                    format="hex",
                    confidence=1.0,
                    notes="byte differs",
                )
            )
            change_index += 1
            if change_index > 200:
                break

        return ComparisonResult(
            left_path=str(left_path),
            right_path=str(right_path),
            file_kind="binary",
            changes=changes,
            metadata={"left_size": str(len(left)), "right_size": str(len(right))},
        )
```

- [ ] **Step 4: Run binary tests**

Run:

```powershell
python -m pytest tests/test_binary_analyzer.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/file_compare_app/analyzers/binary.py tests/test_binary_analyzer.py
git commit -m "feat: add binary diff fallback"
```

---

### Task 6: Orchestrator

**Files:**
- Create: `src/file_compare_app/core/orchestrator.py`
- Create: `tests/test_orchestrator.py`

- [ ] **Step 1: Write failing orchestrator tests**

Create `tests/test_orchestrator.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_orchestrator.py -v
```

Expected: FAIL because `compare_files` does not exist.

- [ ] **Step 3: Implement analyzer routing**

Create `src/file_compare_app/core/orchestrator.py`:

```python
from pathlib import Path

from file_compare_app.analyzers.base import Analyzer
from file_compare_app.analyzers.binary import BinaryAnalyzer
from file_compare_app.analyzers.text_config import TextConfigAnalyzer
from file_compare_app.core.models import ComparisonResult
from file_compare_app.core.type_detection import detect_file_kind


def build_analyzer(file_kind: str) -> Analyzer:
    if file_kind in {"text", "config"}:
        return TextConfigAnalyzer()
    return BinaryAnalyzer()


def compare_files(left_path: Path, right_path: Path) -> ComparisonResult:
    left_kind = detect_file_kind(left_path)
    right_kind = detect_file_kind(right_path)
    file_kind = left_kind if left_kind == right_kind else "binary"
    analyzer = build_analyzer(file_kind)
    return analyzer.compare(left_path, right_path)
```

- [ ] **Step 4: Run orchestrator tests**

Run:

```powershell
python -m pytest tests/test_orchestrator.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/file_compare_app/core/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: route comparisons through orchestrator"
```

---

### Task 7: Strict Local Mode

**Files:**
- Create: `src/file_compare_app/security/strict_mode.py`
- Create: `tests/test_strict_mode.py`

- [ ] **Step 1: Write failing strict mode tests**

Create `tests/test_strict_mode.py`:

```python
from pathlib import Path

from file_compare_app.security.strict_mode import StrictModeWorkspace, safe_log_message


def test_strict_workspace_cleans_temp_files(tmp_path: Path) -> None:
    with StrictModeWorkspace(root=tmp_path) as workspace:
        temp_file = workspace.path / "ocr.txt"
        temp_file.write_text("secret document text", encoding="utf-8")
        assert temp_file.exists()
    assert not temp_file.exists()
    assert not workspace.path.exists()


def test_safe_log_message_does_not_include_document_text() -> None:
    message = safe_log_message("pdf", "failed to parse contract text")
    assert message == "analyzer=pdf status=failed"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_strict_mode.py -v
```

Expected: FAIL because `strict_mode` does not exist.

- [ ] **Step 3: Implement strict workspace and safe log helper**

Create `src/file_compare_app/security/strict_mode.py`:

```python
from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StrictModeWorkspace:
    root: Path | None = None

    def __post_init__(self) -> None:
        base = self.root if self.root is not None else Path(tempfile.gettempdir())
        self.path = Path(tempfile.mkdtemp(prefix="file-compare-", dir=base))

    def __enter__(self) -> "StrictModeWorkspace":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        shutil.rmtree(self.path, ignore_errors=True)


def safe_log_message(analyzer: str, status: str) -> str:
    clean_status = "failed" if "fail" in status.lower() or "error" in status.lower() else "ok"
    return f"analyzer={analyzer} status={clean_status}"
```

- [ ] **Step 4: Run strict mode tests**

Run:

```powershell
python -m pytest tests/test_strict_mode.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/file_compare_app/security/strict_mode.py tests/test_strict_mode.py
git commit -m "feat: add strict local workspace"
```

---

### Task 8: Optional Format Analyzers

**Files:**
- Create: `src/file_compare_app/analyzers/docx.py`
- Create: `src/file_compare_app/analyzers/pdf.py`
- Create: `src/file_compare_app/analyzers/xlsx.py`
- Create: `src/file_compare_app/analyzers/image.py`
- Modify: `src/file_compare_app/core/orchestrator.py`
- Create: `tests/test_optional_analyzers.py`

- [ ] **Step 1: Write analyzer smoke tests**

Create `tests/test_optional_analyzers.py`:

```python
from pathlib import Path

from openpyxl import Workbook
from PIL import Image

from file_compare_app.analyzers.image import ImageAnalyzer
from file_compare_app.analyzers.xlsx import XlsxAnalyzer


def test_xlsx_analyzer_reports_changed_cell(tmp_path: Path) -> None:
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
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_optional_analyzers.py -v
```

Expected: FAIL because `XlsxAnalyzer` and `ImageAnalyzer` do not exist.

- [ ] **Step 3: Implement XLSX analyzer**

Create `src/file_compare_app/analyzers/xlsx.py`:

```python
from pathlib import Path

from openpyxl import load_workbook

from file_compare_app.analyzers.base import Analyzer
from file_compare_app.core.models import Change, ChangeLocation, ComparisonResult


class XlsxAnalyzer(Analyzer):
    def compare(self, left_path: Path, right_path: Path) -> ComparisonResult:
        left_wb = load_workbook(left_path, data_only=False)
        right_wb = load_workbook(right_path, data_only=False)
        changes: list[Change] = []
        index = 1
        for sheet_name in sorted(set(left_wb.sheetnames) | set(right_wb.sheetnames)):
            if sheet_name not in left_wb.sheetnames or sheet_name not in right_wb.sheetnames:
                continue
            left_ws = left_wb[sheet_name]
            right_ws = right_wb[sheet_name]
            max_row = max(left_ws.max_row, right_ws.max_row)
            max_col = max(left_ws.max_column, right_ws.max_column)
            for row in range(1, max_row + 1):
                for col in range(1, max_col + 1):
                    left_cell = left_ws.cell(row=row, column=col)
                    right_cell = right_ws.cell(row=row, column=col)
                    if left_cell.value == right_cell.value:
                        continue
                    changes.append(
                        Change(
                            change_id=f"xlsx-{index}",
                            change_type="modified",
                            severity="normal",
                            source_location=ChangeLocation(str(left_path), sheet=sheet_name, cell=left_cell.coordinate),
                            target_location=ChangeLocation(str(right_path), sheet=sheet_name, cell=right_cell.coordinate),
                            before="" if left_cell.value is None else str(left_cell.value),
                            after="" if right_cell.value is None else str(right_cell.value),
                            format="xlsx",
                            confidence=1.0,
                            notes=f"{sheet_name}!{right_cell.coordinate}",
                        )
                    )
                    index += 1
        return ComparisonResult(str(left_path), str(right_path), "xlsx", changes)
```

- [ ] **Step 4: Implement image analyzer**

Create `src/file_compare_app/analyzers/image.py`:

```python
from pathlib import Path

from PIL import Image, ImageChops

from file_compare_app.analyzers.base import Analyzer
from file_compare_app.core.models import Change, ChangeLocation, ComparisonResult


class ImageAnalyzer(Analyzer):
    def compare(self, left_path: Path, right_path: Path) -> ComparisonResult:
        left = Image.open(left_path).convert("RGB")
        right = Image.open(right_path).convert("RGB")
        diff = ImageChops.difference(left, right)
        bbox = diff.getbbox()
        changes: list[Change] = []
        if bbox is not None:
            x1, y1, x2, y2 = bbox
            changes.append(
                Change(
                    change_id="image-1",
                    change_type="modified",
                    severity="normal",
                    source_location=ChangeLocation(str(left_path), x=x1, y=y1, width=x2 - x1, height=y2 - y1),
                    target_location=ChangeLocation(str(right_path), x=x1, y=y1, width=x2 - x1, height=y2 - y1),
                    before="image region differs",
                    after="image region differs",
                    format="image",
                    confidence=1.0,
                    notes="pixel difference",
                )
            )
        return ComparisonResult(str(left_path), str(right_path), "image", changes)
```

- [ ] **Step 5: Implement DOCX and PDF analyzers by adapting text analyzer**

Create `src/file_compare_app/analyzers/docx.py`:

```python
from pathlib import Path

from docx import Document

from file_compare_app.analyzers.base import Analyzer
from file_compare_app.core.models import Change, ChangeLocation, ComparisonResult
from file_compare_app.core.text_diff import line_changes


class DocxAnalyzer(Analyzer):
    def compare(self, left_path: Path, right_path: Path) -> ComparisonResult:
        left_lines = _extract_docx_lines(left_path)
        right_lines = _extract_docx_lines(right_path)
        changes: list[Change] = []
        for index, (kind, left_index, right_index, before, after) in enumerate(line_changes(left_lines, right_lines), start=1):
            changes.append(
                Change(
                    change_id=f"docx-{index}",
                    change_type=kind,  # type: ignore[arg-type]
                    severity="normal",
                    source_location=ChangeLocation(str(left_path), line=left_index + 1) if left_index is not None else None,
                    target_location=ChangeLocation(str(right_path), line=right_index + 1) if right_index is not None else None,
                    before=before,
                    after=after,
                    format="docx",
                    confidence=1.0,
                    notes="paragraph/table text",
                )
            )
        return ComparisonResult(str(left_path), str(right_path), "docx", changes)


def _extract_docx_lines(path: Path) -> list[str]:
    document = Document(path)
    lines = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                lines.append(" | ".join(cells))
    return lines
```

Create `src/file_compare_app/analyzers/pdf.py`:

```python
from pathlib import Path

import fitz
import pytesseract
from PIL import Image

from file_compare_app.analyzers.base import Analyzer
from file_compare_app.core.models import Change, ChangeLocation, ComparisonResult
from file_compare_app.core.text_diff import line_changes


class PdfAnalyzer(Analyzer):
    def compare(self, left_path: Path, right_path: Path) -> ComparisonResult:
        left_lines = _extract_pdf_lines(left_path)
        right_lines = _extract_pdf_lines(right_path)
        changes: list[Change] = []
        for index, (kind, left_index, right_index, before, after) in enumerate(line_changes(left_lines, right_lines), start=1):
            changes.append(
                Change(
                    change_id=f"pdf-{index}",
                    change_type=kind,  # type: ignore[arg-type]
                    severity="normal",
                    source_location=ChangeLocation(str(left_path), line=left_index + 1) if left_index is not None else None,
                    target_location=ChangeLocation(str(right_path), line=right_index + 1) if right_index is not None else None,
                    before=before,
                    after=after,
                    format="pdf",
                    confidence=0.9,
                    notes="text layer or OCR",
                )
            )
        return ComparisonResult(str(left_path), str(right_path), "pdf", changes)


def _extract_pdf_lines(path: Path) -> list[str]:
    document = fitz.open(path)
    lines: list[str] = []
    for page_number, page in enumerate(document, start=1):
        text = page.get_text("text").strip()
        if not text:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = pytesseract.image_to_string(image, lang="rus+eng")
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if line:
                lines.append(f"page {page_number}: {line}")
    return lines
```

- [ ] **Step 6: Register optional analyzers in orchestrator**

Replace `src/file_compare_app/core/orchestrator.py` with:

```python
from pathlib import Path

from file_compare_app.analyzers.base import Analyzer
from file_compare_app.analyzers.binary import BinaryAnalyzer
from file_compare_app.analyzers.docx import DocxAnalyzer
from file_compare_app.analyzers.image import ImageAnalyzer
from file_compare_app.analyzers.pdf import PdfAnalyzer
from file_compare_app.analyzers.text_config import TextConfigAnalyzer
from file_compare_app.analyzers.xlsx import XlsxAnalyzer
from file_compare_app.core.models import ComparisonResult
from file_compare_app.core.type_detection import detect_file_kind


def build_analyzer(file_kind: str) -> Analyzer:
    if file_kind in {"text", "config"}:
        return TextConfigAnalyzer()
    if file_kind == "docx":
        return DocxAnalyzer()
    if file_kind == "pdf":
        return PdfAnalyzer()
    if file_kind == "xlsx":
        return XlsxAnalyzer()
    if file_kind == "image":
        return ImageAnalyzer()
    return BinaryAnalyzer()


def compare_files(left_path: Path, right_path: Path) -> ComparisonResult:
    left_kind = detect_file_kind(left_path)
    right_kind = detect_file_kind(right_path)
    file_kind = left_kind if left_kind == right_kind else "binary"
    analyzer = build_analyzer(file_kind)
    return analyzer.compare(left_path, right_path)
```

- [ ] **Step 7: Run optional analyzer tests**

Run:

```powershell
python -m pytest tests/test_optional_analyzers.py tests/test_orchestrator.py -v
```

Expected: PASS. If Tesseract is not installed, these tests still pass because they do not create PDF OCR fixtures.

- [ ] **Step 8: Commit**

Run:

```powershell
git add src/file_compare_app/analyzers src/file_compare_app/core/orchestrator.py tests/test_optional_analyzers.py
git commit -m "feat: add document image and spreadsheet analyzers"
```

---

### Task 9: HTML Report Export

**Files:**
- Create: `src/file_compare_app/reports/html_report.py`
- Create: `tests/test_html_report.py`

- [ ] **Step 1: Write failing report tests**

Create `tests/test_html_report.py`:

```python
from file_compare_app.core.models import Change, ChangeLocation, ComparisonResult
from file_compare_app.reports.html_report import render_html_report


def test_html_report_escapes_content_and_includes_credit() -> None:
    result = ComparisonResult(
        left_path="old.txt",
        right_path="new.txt",
        file_kind="text",
        changes=[
            Change(
                change_id="c1",
                change_type="modified",
                severity="normal",
                source_location=ChangeLocation(path="old.txt", line=1),
                target_location=ChangeLocation(path="new.txt", line=1),
                before="<old>",
                after="<new>",
                format="text",
                confidence=1.0,
                notes="line diff",
            )
        ],
    )

    html = render_html_report(result)

    assert "&lt;old&gt;" in html
    assert "&lt;new&gt;" in html
    assert "Разработал: Абдрахманов Амаль Даулетович" in html
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_html_report.py -v
```

Expected: FAIL because `html_report` does not exist.

- [ ] **Step 3: Implement report renderer**

Create `src/file_compare_app/reports/html_report.py`:

```python
from html import escape

from file_compare_app.core.models import ComparisonResult


def render_html_report(result: ComparisonResult) -> str:
    rows = []
    for change in result.changes:
        source = change.source_location.display() if change.source_location else ""
        target = change.target_location.display() if change.target_location else ""
        rows.append(
            "<tr>"
            f"<td>{escape(change.change_type)}</td>"
            f"<td>{escape(source)}</td>"
            f"<td>{escape(target)}</td>"
            f"<td class='old'>{escape(change.before)}</td>"
            f"<td class='new'>{escape(change.after)}</td>"
            f"<td>{escape(change.notes)}</td>"
            "</tr>"
        )
    body = "\n".join(rows)
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>Сравнение файлов - отчет</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 32px; color: #111827; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #d6dde8; padding: 8px; vertical-align: top; }}
    th {{ background: #f7f9fc; text-align: left; }}
    .old {{ background: #fff1f0; color: #b42318; }}
    .new {{ background: #ecfdf3; color: #087443; }}
    .credit {{ margin-top: 20px; color: #8b95a7; font-size: 11px; text-align: right; }}
  </style>
</head>
<body>
  <h1>Сравнение файлов</h1>
  <p>Файл 1: {escape(result.left_path)}</p>
  <p>Файл 2: {escape(result.right_path)}</p>
  <p>Найдено изменений: {result.change_count}</p>
  <table>
    <thead>
      <tr><th>Тип</th><th>Было где</th><th>Стало где</th><th>Было</th><th>Стало</th><th>Примечание</th></tr>
    </thead>
    <tbody>{body}</tbody>
  </table>
  <div class="credit">Разработал: Абдрахманов Амаль Даулетович</div>
</body>
</html>"""
```

- [ ] **Step 4: Run report tests**

Run:

```powershell
python -m pytest tests/test_html_report.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/file_compare_app/reports/html_report.py tests/test_html_report.py
git commit -m "feat: render html comparison reports"
```

---

### Task 10: PySide6 Desktop UI

**Files:**
- Create: `src/file_compare_app/app.py`
- Create: `src/file_compare_app/ui/main_window.py`

- [ ] **Step 1: Implement application runner**

Create `src/file_compare_app/app.py`:

```python
import sys

from PySide6.QtWidgets import QApplication

from file_compare_app.ui.main_window import MainWindow


def run_app() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
```

- [ ] **Step 2: Implement main window**

Create `src/file_compare_app/ui/main_window.py`:

```python
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from file_compare_app.core.models import ComparisonResult
from file_compare_app.core.orchestrator import compare_files
from file_compare_app.reports.html_report import render_html_report


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.left_path: Path | None = None
        self.right_path: Path | None = None
        self.result: ComparisonResult | None = None
        self.setWindowTitle("Сравнение файлов")
        self.resize(1320, 820)
        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(14, 12, 14, 8)
        root_layout.setSpacing(10)

        header = QHBoxLayout()
        self.brand = QLabel("СФ  Сравнение файлов  2026")
        self.brand.setObjectName("brand")
        self.local_mode = QLabel("Строгий локальный режим")
        self.local_mode.setObjectName("localMode")
        header.addWidget(self.brand)
        header.addStretch(1)
        header.addWidget(self.local_mode)
        root_layout.addLayout(header)

        actions = QHBoxLayout()
        self.left_button = QPushButton("Файл 1")
        self.right_button = QPushButton("Файл 2")
        self.compare_button = QPushButton("Сравнить")
        self.export_button = QPushButton("Экспорт отчета")
        self.compare_button.setObjectName("primary")
        actions.addWidget(self.left_button)
        actions.addWidget(self.right_button)
        actions.addWidget(self.compare_button)
        actions.addWidget(self.export_button)
        actions.addStretch(1)
        root_layout.addLayout(actions)

        splitter = QSplitter(Qt.Horizontal)
        viewers = QSplitter(Qt.Horizontal)
        self.left_view = QTextEdit()
        self.right_view = QTextEdit()
        self.left_view.setReadOnly(True)
        self.right_view.setReadOnly(True)
        self.left_view.setPlaceholderText("Было")
        self.right_view.setPlaceholderText("Стало")
        viewers.addWidget(self.left_view)
        viewers.addWidget(self.right_view)

        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(10, 0, 0, 0)
        self.summary = QLabel("Найдено 0 изменений")
        self.summary.setObjectName("summary")
        self.changes_list = QListWidget()
        side_layout.addWidget(self.summary)
        side_layout.addWidget(self.changes_list)

        splitter.addWidget(viewers)
        splitter.addWidget(side)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        root_layout.addWidget(splitter, 1)

        self.setCentralWidget(root)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Готово | Разработал: Абдрахманов Амаль Даулетович")

        self.left_button.clicked.connect(self._choose_left)
        self.right_button.clicked.connect(self._choose_right)
        self.compare_button.clicked.connect(self._compare)
        self.export_button.clicked.connect(self._export_report)
        self.changes_list.currentRowChanged.connect(self._show_change)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow { background: #eef2f6; }
            QLabel#brand { color: #111827; font-size: 18px; font-weight: 750; }
            QLabel#localMode {
                color: #0f766e;
                border: 1px solid #99d3ca;
                border-radius: 11px;
                padding: 5px 10px;
                background: #ecfdf8;
                font-weight: 650;
            }
            QLabel#summary { font-size: 16px; font-weight: 700; }
            QPushButton {
                min-height: 34px;
                border: 1px solid #d6dde8;
                border-radius: 7px;
                padding: 0 12px;
                background: #ffffff;
                font-weight: 650;
            }
            QPushButton#primary { background: #2563eb; color: white; border-color: #2563eb; }
            QTextEdit, QListWidget {
                background: #ffffff;
                border: 1px solid #d6dde8;
                border-radius: 8px;
                font-family: Consolas, Segoe UI;
                font-size: 12px;
            }
            """
        )

    def _choose_left(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выберите исходный файл")
        if path:
            self.left_path = Path(path)
            self.left_button.setText(self.left_path.name)

    def _choose_right(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выберите измененный файл")
        if path:
            self.right_path = Path(path)
            self.right_button.setText(self.right_path.name)

    def _compare(self) -> None:
        if self.left_path is None or self.right_path is None:
            QMessageBox.warning(self, "Не выбраны файлы", "Выберите два файла для сравнения.")
            return
        try:
            self.result = compare_files(self.left_path, self.right_path)
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка сравнения", f"Не удалось сравнить файлы: {exc.__class__.__name__}")
            return
        self._render_result(self.result)

    def _render_result(self, result: ComparisonResult) -> None:
        self.summary.setText(f"Найдено {result.change_count} изменений")
        self.changes_list.clear()
        for change in result.changes:
            place = change.target_location.display() if change.target_location else ""
            item = QListWidgetItem(f"{change.change_type}: {place}")
            self.changes_list.addItem(item)
        if result.changes:
            self.changes_list.setCurrentRow(0)
        self.statusBar().showMessage("Сравнение выполнено локально | Разработал: Абдрахманов Амаль Даулетович")

    def _show_change(self, row: int) -> None:
        if self.result is None or row < 0 or row >= len(self.result.changes):
            return
        change = self.result.changes[row]
        self.left_view.setPlainText(change.before)
        self.right_view.setPlainText(change.after)

    def _export_report(self) -> None:
        if self.result is None:
            QMessageBox.information(self, "Нет отчета", "Сначала выполните сравнение.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить отчет", "comparison-report.html", "HTML (*.html)")
        if not path:
            return
        Path(path).write_text(render_html_report(self.result), encoding="utf-8")
        self.statusBar().showMessage(f"Отчет сохранен: {path}")
```

- [ ] **Step 3: Run unit tests after UI wiring**

Run:

```powershell
python -m pytest -v
```

Expected: PASS.

- [ ] **Step 4: Smoke-run the app**

Run:

```powershell
python -m file_compare_app
```

Expected: a Windows desktop window opens with title **Сравнение файлов**, buttons **Файл 1**, **Файл 2**, **Сравнить**, **Экспорт отчета**, and status text with the developer credit.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/file_compare_app/app.py src/file_compare_app/ui/main_window.py
git commit -m "feat: add desktop comparison interface"
```

---

### Task 11: Packaging

**Files:**
- Create: `packaging/file-compare-app.spec`
- Modify: `README.md`

- [ ] **Step 1: Create PyInstaller spec**

Create `packaging/file-compare-app.spec`:

```python
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ["src/file_compare_app/__main__.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=["PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Сравнение файлов",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
```

- [ ] **Step 2: Add build instructions**

Append to `README.md`:

```markdown
## Windows build

```powershell
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\pyinstaller packaging\file-compare-app.spec --clean
```

The generated executable is placed under `dist`.
```

- [ ] **Step 3: Run tests before packaging**

Run:

```powershell
python -m pytest -v
```

Expected: PASS.

- [ ] **Step 4: Build executable**

Run:

```powershell
pyinstaller packaging\file-compare-app.spec --clean
```

Expected: `dist\Сравнение файлов.exe` exists.

- [ ] **Step 5: Commit**

Run:

```powershell
git add packaging/file-compare-app.spec README.md
git commit -m "build: add windows executable packaging"
```

---

### Task 12: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Run full test suite**

Run:

```powershell
python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 2: Run a manual text comparison**

Run:

```powershell
python -m file_compare_app
```

Manual verification:

- Select `tests\fixtures\sample_old.txt` as **Файл 1**.
- Select `tests\fixtures\sample_new.txt` as **Файл 2**.
- Click **Сравнить**.
- Confirm the sidebar says `Найдено 2 изменений`.
- Select each change and confirm the left/right panes show old and new values.

- [ ] **Step 3: Verify strict mode language**

Manual verification:

- Confirm the header shows **Строгий локальный режим**.
- Confirm the status bar includes **Разработал: Абдрахманов Амаль Даулетович**.
- Confirm no document text is written to application logs. If no log file exists, record that strict mode uses no persistent logs in this release.

- [ ] **Step 4: Build executable**

Run:

```powershell
pyinstaller packaging\file-compare-app.spec --clean
```

Expected: `dist\Сравнение файлов.exe` exists and opens the desktop app.

- [ ] **Step 5: Commit verification notes**

Create `docs/superpowers/plans/2026-06-12-file-comparison-verification.md`:

```markdown
# File Comparison Verification

Date: 2026-06-12

## Automated Checks

- `python -m pytest -v`: passed

## Manual Checks

- App opens with title `Сравнение файлов`.
- Header shows strict local mode.
- Text fixture comparison reports 2 changes.
- Developer credit is visible in the lower status area and does not dominate the UI.
- HTML report exports successfully.
- Windows executable opens from `dist`.
```

Run:

```powershell
git add docs/superpowers/plans/2026-06-12-file-comparison-verification.md
git commit -m "docs: record final verification"
```

---

## Implementation Notes

- Run tasks in order. Tasks 2-7 establish the core contract used by UI and reports.
- Keep strict mode as the default. Do not add network calls.
- Keep document content out of logs and exception messages.
- Use fallback behavior instead of crashing when an analyzer cannot parse a file.
- If Tesseract is missing on a developer machine, show a user-facing error in the PDF/OCR path and keep non-OCR comparisons working.

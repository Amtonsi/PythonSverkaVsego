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

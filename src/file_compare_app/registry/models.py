from __future__ import annotations

from dataclasses import dataclass
from collections import Counter


@dataclass(frozen=True)
class RegistryNode:
    id: int
    parent_id: int | None
    name: str
    node_type: str
    code: str
    responsible: str
    description: str
    monitoring_enabled: bool
    monitor_interval_minutes: int
    created_at: str
    updated_at: str
    template_key: str = ""


@dataclass(frozen=True)
class WatchedFile:
    id: int
    node_id: int
    file_path: str
    label: str
    file_kind: str
    baseline_hash: str
    last_hash: str
    last_checked_at: str | None
    status: str
    last_error: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class FileVersion:
    id: int
    watched_file_id: int
    version_number: int
    snapshot_path: str
    sha256: str
    size_bytes: int
    change_count: int
    created_at: str


@dataclass(frozen=True)
class MonitorEvent:
    id: int
    node_id: int
    watched_file_id: int
    event_type: str
    change_count: int
    report_path: str
    message: str
    created_at: str
    risk_count: int = 0
    risk_summary: str = ""


@dataclass(frozen=True)
class ComparisonReview:
    id: int
    watched_file_id: int
    from_version: int
    to_version: int
    status: str
    reviewer: str
    comment: str
    reviewed_at: str
    updated_at: str


@dataclass(frozen=True)
class MonitoringFileInfo:
    node_path: str
    watched_file: WatchedFile
    latest_version: FileVersion | None
    last_event: MonitorEvent | None


@dataclass(frozen=True)
class MonitoringSummary:
    node_id: int
    total_files: int
    status_counts: Counter[str]
    files: list[MonitoringFileInfo]

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
from pathlib import Path


REGISTRY_DB_FILENAME = "registry.sqlite3"
LEGACY_REGISTRY_DIR_NAME = "FileCompareRegistry"


def default_registry_db_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / REGISTRY_DB_FILENAME
    return legacy_registry_db_path()


def legacy_registry_db_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / LEGACY_REGISTRY_DIR_NAME / REGISTRY_DB_FILENAME


def connect_registry_db(path: Path | None = None) -> sqlite3.Connection:
    db_path = Path(path) if path is not None else default_registry_db_path()
    if path is None:
        copy_legacy_registry_db_if_needed(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("pragma foreign_keys = on")
    return connection


def copy_legacy_registry_db_if_needed(target_path: Path) -> None:
    legacy_path = legacy_registry_db_path()
    if target_path == legacy_path or target_path.exists() or not legacy_path.exists():
        return
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(legacy_path, target_path)


def initialize_registry_db(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        create table if not exists registry_nodes (
            id integer primary key autoincrement,
            parent_id integer references registry_nodes(id) on delete cascade,
            name text not null,
            node_type text not null default 'Объект',
            code text not null default '',
            responsible text not null default '',
            description text not null default '',
            template_key text not null default '',
            monitoring_enabled integer not null default 1,
            monitor_interval_minutes integer not null default 30,
            created_at text not null,
            updated_at text not null
        );

        create table if not exists watched_files (
            id integer primary key autoincrement,
            node_id integer not null references registry_nodes(id) on delete cascade,
            file_path text not null,
            label text not null,
            file_kind text not null,
            baseline_hash text not null,
            last_hash text not null,
            last_checked_at text,
            status text not null default 'ok',
            last_error text not null default '',
            created_at text not null,
            updated_at text not null
        );

        create table if not exists file_versions (
            id integer primary key autoincrement,
            watched_file_id integer not null references watched_files(id) on delete cascade,
            version_number integer not null,
            snapshot_path text not null,
            sha256 text not null,
            size_bytes integer not null default 0,
            change_count integer not null default 0,
            created_at text not null,
            unique(watched_file_id, version_number)
        );

        create table if not exists monitor_events (
            id integer primary key autoincrement,
            node_id integer not null references registry_nodes(id) on delete cascade,
            watched_file_id integer not null references watched_files(id) on delete cascade,
            event_type text not null,
            change_count integer not null default 0,
            report_path text not null default '',
            message text not null default '',
            risk_count integer not null default 0,
            risk_summary text not null default '',
            created_at text not null
        );

        create table if not exists comparison_reviews (
            id integer primary key autoincrement,
            watched_file_id integer not null references watched_files(id) on delete cascade,
            from_version integer not null,
            to_version integer not null,
            status text not null default 'new',
            reviewer text not null default '',
            comment text not null default '',
            reviewed_at text not null default '',
            updated_at text not null,
            unique(watched_file_id, from_version, to_version)
        );

        create index if not exists idx_registry_nodes_parent on registry_nodes(parent_id);
        create index if not exists idx_watched_files_node on watched_files(node_id);
        create index if not exists idx_file_versions_watched on file_versions(watched_file_id);
        create index if not exists idx_monitor_events_node on monitor_events(node_id);
        create index if not exists idx_comparison_reviews_watched on comparison_reviews(watched_file_id);
        """
    )
    _ensure_column(connection, "registry_nodes", "template_key", "text not null default ''")
    _ensure_column(connection, "monitor_events", "risk_count", "integer not null default 0")
    _ensure_column(connection, "monitor_events", "risk_summary", "text not null default ''")
    connection.commit()


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row["name"] for row in connection.execute(f"pragma table_info({table})").fetchall()}
    if column not in columns:
        connection.execute(f"alter table {table} add column {column} {definition}")

# Registry Monitoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first database-backed registry mode for `Сравнение файлов`, with unlimited nested objects, watched files, manual monitoring, and a UI matching the approved registry mockup.

**Architecture:** Add a focused `registry` package over SQLite for persistence, plus a small monitoring service that hashes watched files and records events. Extend the existing PySide6 main window with a mode switch: the current one-time comparison remains intact, and the new registry mode uses a left tree plus right detail/tabs layout.

**Tech Stack:** Python stdlib `sqlite3`, `hashlib`, `dataclasses`, existing PySide6 UI, existing file type detection and comparison/report modules, pytest.

---

## File Structure

Create:

```text
src/file_compare_app/registry/__init__.py
src/file_compare_app/registry/models.py
src/file_compare_app/registry/database.py
src/file_compare_app/registry/repository.py
src/file_compare_app/registry/monitor.py
tests/test_registry_repository.py
tests/test_registry_monitor.py
tests/test_registry_ui.py
```

Modify:

```text
src/file_compare_app/ui/main_window.py
README.md
```

Responsibilities:

- `registry/models.py`: immutable dataclasses used by repository, monitor, and UI.
- `registry/database.py`: connection creation, default DB path, schema migration.
- `registry/repository.py`: CRUD for nodes, watched files, and events.
- `registry/monitor.py`: hash files, create baselines, check watched files, record statuses.
- `ui/main_window.py`: add mode switch, registry layout, tree/list rendering, creation actions, manual check actions.

---

### Task 1: Registry Models And SQLite Schema

**Files:**
- Create: `src/file_compare_app/registry/__init__.py`
- Create: `src/file_compare_app/registry/models.py`
- Create: `src/file_compare_app/registry/database.py`
- Test: `tests/test_registry_repository.py`

- [ ] **Step 1: Write failing schema/model tests**

Create `tests/test_registry_repository.py`:

```python
from pathlib import Path

from file_compare_app.registry.database import connect_registry_db, initialize_registry_db
from file_compare_app.registry.repository import RegistryRepository


def test_registry_database_creates_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "registry.sqlite3"

    with connect_registry_db(db_path) as connection:
        initialize_registry_db(connection)
        table_names = {
            row[0]
            for row in connection.execute(
                "select name from sqlite_master where type = 'table'"
            ).fetchall()
        }

    assert {"registry_nodes", "watched_files", "monitor_events"}.issubset(table_names)


def test_repository_creates_root_and_nested_nodes(tmp_path: Path) -> None:
    repository = RegistryRepository.create(tmp_path / "registry.sqlite3")

    root = repository.create_node(name="Завод №1", node_type="Объект", code="OBJ-001")
    child = repository.create_node(name="Цех 1", parent_id=root.id, node_type="Подобъект")
    grandchild = repository.create_node(name="Линия упаковки", parent_id=child.id)

    assert root.parent_id is None
    assert child.parent_id == root.id
    assert grandchild.parent_id == child.id
    assert [node.name for node in repository.list_children(root.id)] == ["Цех 1"]
    assert [node.name for node in repository.list_children(child.id)] == ["Линия упаковки"]
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest tests\test_registry_repository.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'file_compare_app.registry'`.

- [ ] **Step 3: Add dataclasses**

Create `src/file_compare_app/registry/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


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
class MonitorEvent:
    id: int
    node_id: int
    watched_file_id: int
    event_type: str
    change_count: int
    report_path: str
    message: str
    created_at: str
```

Create `src/file_compare_app/registry/__init__.py`:

```python
from file_compare_app.registry.models import MonitorEvent, RegistryNode, WatchedFile

__all__ = ["MonitorEvent", "RegistryNode", "WatchedFile"]
```

- [ ] **Step 4: Add database schema helper**

Create `src/file_compare_app/registry/database.py`:

```python
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def default_registry_db_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "FileCompareRegistry" / "registry.sqlite3"


def connect_registry_db(path: Path | None = None) -> sqlite3.Connection:
    db_path = path or default_registry_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("pragma foreign_keys = on")
    return connection


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

        create table if not exists monitor_events (
            id integer primary key autoincrement,
            node_id integer not null references registry_nodes(id) on delete cascade,
            watched_file_id integer not null references watched_files(id) on delete cascade,
            event_type text not null,
            change_count integer not null default 0,
            report_path text not null default '',
            message text not null default '',
            created_at text not null
        );

        create index if not exists idx_registry_nodes_parent on registry_nodes(parent_id);
        create index if not exists idx_watched_files_node on watched_files(node_id);
        create index if not exists idx_monitor_events_node on monitor_events(node_id);
        """
    )
    connection.commit()
```

- [ ] **Step 5: Add minimal repository node creation/listing**

Create `src/file_compare_app/registry/repository.py`:

```python
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from file_compare_app.registry.database import connect_registry_db, initialize_registry_db
from file_compare_app.registry.models import RegistryNode


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RegistryRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    @classmethod
    def create(cls, path: Path | None = None) -> "RegistryRepository":
        connection = connect_registry_db(path)
        initialize_registry_db(connection)
        return cls(connection)

    def create_node(
        self,
        name: str,
        parent_id: int | None = None,
        node_type: str = "Объект",
        code: str = "",
        responsible: str = "",
        description: str = "",
    ) -> RegistryNode:
        timestamp = _now()
        cursor = self.connection.execute(
            """
            insert into registry_nodes
            (parent_id, name, node_type, code, responsible, description, created_at, updated_at)
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (parent_id, name, node_type, code, responsible, description, timestamp, timestamp),
        )
        self.connection.commit()
        return self.get_node(int(cursor.lastrowid))

    def get_node(self, node_id: int) -> RegistryNode:
        row = self.connection.execute(
            "select * from registry_nodes where id = ?",
            (node_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"registry node {node_id} not found")
        return _node_from_row(row)

    def list_children(self, parent_id: int | None) -> list[RegistryNode]:
        if parent_id is None:
            rows = self.connection.execute(
                "select * from registry_nodes where parent_id is null order by name"
            ).fetchall()
        else:
            rows = self.connection.execute(
                "select * from registry_nodes where parent_id = ? order by name",
                (parent_id,),
            ).fetchall()
        return [_node_from_row(row) for row in rows]


def _node_from_row(row: sqlite3.Row) -> RegistryNode:
    return RegistryNode(
        id=int(row["id"]),
        parent_id=row["parent_id"],
        name=row["name"],
        node_type=row["node_type"],
        code=row["code"],
        responsible=row["responsible"],
        description=row["description"],
        monitoring_enabled=bool(row["monitoring_enabled"]),
        monitor_interval_minutes=int(row["monitor_interval_minutes"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
```

- [ ] **Step 6: Run tests to verify GREEN**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest tests\test_registry_repository.py -q
```

Expected: `2 passed`.

---

### Task 2: Watched Files And Event Repository

**Files:**
- Modify: `src/file_compare_app/registry/repository.py`
- Test: `tests/test_registry_repository.py`

- [ ] **Step 1: Add failing watched-file/event tests**

Append to `tests/test_registry_repository.py`:

```python
def test_repository_creates_watched_file_and_event(tmp_path: Path) -> None:
    repository = RegistryRepository.create(tmp_path / "registry.sqlite3")
    node = repository.create_node(name="Линия упаковки")

    watched = repository.create_watched_file(
        node_id=node.id,
        file_path=r"D:\Objects\Factory-1\controller.yaml",
        label="controller.yaml",
        file_kind="config",
        baseline_hash="abc",
        last_hash="abc",
    )
    event = repository.create_event(
        node_id=node.id,
        watched_file_id=watched.id,
        event_type="baseline",
        message="baseline saved",
    )

    assert watched.node_id == node.id
    assert watched.status == "ok"
    assert repository.list_watched_files(node.id)[0].label == "controller.yaml"
    assert repository.list_events(node.id)[0].id == event.id
```

- [ ] **Step 2: Run test to verify RED**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest tests\test_registry_repository.py::test_repository_creates_watched_file_and_event -q
```

Expected: FAIL with `AttributeError: 'RegistryRepository' object has no attribute 'create_watched_file'`.

- [ ] **Step 3: Add watched file and event methods**

Modify `src/file_compare_app/registry/repository.py` by importing additional models:

```python
from file_compare_app.registry.models import MonitorEvent, RegistryNode, WatchedFile
```

Add these methods inside `RegistryRepository`:

```python
    def create_watched_file(
        self,
        node_id: int,
        file_path: str,
        label: str,
        file_kind: str,
        baseline_hash: str,
        last_hash: str,
        status: str = "ok",
    ) -> WatchedFile:
        timestamp = _now()
        cursor = self.connection.execute(
            """
            insert into watched_files
            (node_id, file_path, label, file_kind, baseline_hash, last_hash, status, created_at, updated_at)
            values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (node_id, file_path, label, file_kind, baseline_hash, last_hash, status, timestamp, timestamp),
        )
        self.connection.commit()
        return self.get_watched_file(int(cursor.lastrowid))

    def get_watched_file(self, watched_file_id: int) -> WatchedFile:
        row = self.connection.execute(
            "select * from watched_files where id = ?",
            (watched_file_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"watched file {watched_file_id} not found")
        return _watched_file_from_row(row)

    def list_watched_files(self, node_id: int) -> list[WatchedFile]:
        rows = self.connection.execute(
            "select * from watched_files where node_id = ? order by label",
            (node_id,),
        ).fetchall()
        return [_watched_file_from_row(row) for row in rows]

    def update_watched_file_status(
        self,
        watched_file_id: int,
        last_hash: str,
        status: str,
        last_error: str = "",
    ) -> WatchedFile:
        timestamp = _now()
        self.connection.execute(
            """
            update watched_files
            set last_hash = ?, status = ?, last_error = ?, last_checked_at = ?, updated_at = ?
            where id = ?
            """,
            (last_hash, status, last_error, timestamp, timestamp, watched_file_id),
        )
        self.connection.commit()
        return self.get_watched_file(watched_file_id)

    def create_event(
        self,
        node_id: int,
        watched_file_id: int,
        event_type: str,
        change_count: int = 0,
        report_path: str = "",
        message: str = "",
    ) -> MonitorEvent:
        timestamp = _now()
        cursor = self.connection.execute(
            """
            insert into monitor_events
            (node_id, watched_file_id, event_type, change_count, report_path, message, created_at)
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            (node_id, watched_file_id, event_type, change_count, report_path, message, timestamp),
        )
        self.connection.commit()
        return self.get_event(int(cursor.lastrowid))

    def get_event(self, event_id: int) -> MonitorEvent:
        row = self.connection.execute(
            "select * from monitor_events where id = ?",
            (event_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"monitor event {event_id} not found")
        return _event_from_row(row)

    def list_events(self, node_id: int) -> list[MonitorEvent]:
        rows = self.connection.execute(
            "select * from monitor_events where node_id = ? order by id desc",
            (node_id,),
        ).fetchall()
        return [_event_from_row(row) for row in rows]
```

Add row mappers:

```python
def _watched_file_from_row(row: sqlite3.Row) -> WatchedFile:
    return WatchedFile(
        id=int(row["id"]),
        node_id=int(row["node_id"]),
        file_path=row["file_path"],
        label=row["label"],
        file_kind=row["file_kind"],
        baseline_hash=row["baseline_hash"],
        last_hash=row["last_hash"],
        last_checked_at=row["last_checked_at"],
        status=row["status"],
        last_error=row["last_error"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _event_from_row(row: sqlite3.Row) -> MonitorEvent:
    return MonitorEvent(
        id=int(row["id"]),
        node_id=int(row["node_id"]),
        watched_file_id=int(row["watched_file_id"]),
        event_type=row["event_type"],
        change_count=int(row["change_count"]),
        report_path=row["report_path"],
        message=row["message"],
        created_at=row["created_at"],
    )
```

- [ ] **Step 4: Run repository tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest tests\test_registry_repository.py -q
```

Expected: all repository tests pass.

---

### Task 3: Manual File Monitoring Service

**Files:**
- Create: `src/file_compare_app/registry/monitor.py`
- Modify: `src/file_compare_app/registry/repository.py`
- Test: `tests/test_registry_monitor.py`

- [ ] **Step 1: Write failing monitor tests**

Create `tests/test_registry_monitor.py`:

```python
from pathlib import Path

from file_compare_app.registry.monitor import RegistryMonitor, file_sha256
from file_compare_app.registry.repository import RegistryRepository


def test_file_sha256_changes_when_file_changes(tmp_path: Path) -> None:
    file_path = tmp_path / "controller.yaml"
    file_path.write_text("timeout: 30", encoding="utf-8")
    first = file_sha256(file_path)

    file_path.write_text("timeout: 45", encoding="utf-8")
    second = file_sha256(file_path)

    assert first != second


def test_monitor_adds_baseline_and_detects_unchanged_file(tmp_path: Path) -> None:
    repository = RegistryRepository.create(tmp_path / "registry.sqlite3")
    node = repository.create_node("Линия упаковки")
    file_path = tmp_path / "controller.yaml"
    file_path.write_text("timeout: 30", encoding="utf-8")
    monitor = RegistryMonitor(repository)

    watched = monitor.add_file(node.id, file_path)
    checked = monitor.check_file(watched.id)

    assert checked.status == "ok"
    assert [event.event_type for event in repository.list_events(node.id)] == ["checked", "baseline"]


def test_monitor_detects_changed_and_missing_files(tmp_path: Path) -> None:
    repository = RegistryRepository.create(tmp_path / "registry.sqlite3")
    node = repository.create_node("Линия упаковки")
    file_path = tmp_path / "controller.yaml"
    file_path.write_text("timeout: 30", encoding="utf-8")
    monitor = RegistryMonitor(repository)
    watched = monitor.add_file(node.id, file_path)

    file_path.write_text("timeout: 45", encoding="utf-8")
    changed = monitor.check_file(watched.id)
    file_path.unlink()
    missing = monitor.check_file(watched.id)

    assert changed.status == "changed"
    assert missing.status == "missing"
    assert [event.event_type for event in repository.list_events(node.id)][:2] == ["missing", "changed"]
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest tests\test_registry_monitor.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'file_compare_app.registry.monitor'`.

- [ ] **Step 3: Add subtree listing to repository**

Add this method to `RegistryRepository`:

```python
    def list_descendant_ids(self, node_id: int) -> list[int]:
        rows = self.connection.execute(
            """
            with recursive tree(id) as (
                select id from registry_nodes where id = ?
                union all
                select registry_nodes.id
                from registry_nodes
                join tree on registry_nodes.parent_id = tree.id
            )
            select id from tree
            """,
            (node_id,),
        ).fetchall()
        return [int(row["id"]) for row in rows]
```

- [ ] **Step 4: Add monitor implementation**

Create `src/file_compare_app/registry/monitor.py`:

```python
from __future__ import annotations

import hashlib
from pathlib import Path

from file_compare_app.core.type_detection import detect_file_kind
from file_compare_app.registry.models import WatchedFile
from file_compare_app.registry.repository import RegistryRepository


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class RegistryMonitor:
    def __init__(self, repository: RegistryRepository) -> None:
        self.repository = repository

    def add_file(self, node_id: int, path: Path | str, label: str | None = None) -> WatchedFile:
        file_path = Path(path)
        digest = file_sha256(file_path)
        watched = self.repository.create_watched_file(
            node_id=node_id,
            file_path=str(file_path),
            label=label or file_path.name,
            file_kind=detect_file_kind(file_path),
            baseline_hash=digest,
            last_hash=digest,
        )
        self.repository.create_event(
            node_id=node_id,
            watched_file_id=watched.id,
            event_type="baseline",
            message="Файл добавлен в мониторинг",
        )
        return watched

    def check_file(self, watched_file_id: int) -> WatchedFile:
        watched = self.repository.get_watched_file(watched_file_id)
        file_path = Path(watched.file_path)
        if not file_path.exists():
            updated = self.repository.update_watched_file_status(
                watched.id,
                watched.last_hash,
                "missing",
                "Файл не найден",
            )
            self.repository.create_event(watched.node_id, watched.id, "missing", message="Файл не найден")
            return updated
        try:
            digest = file_sha256(file_path)
        except OSError as exc:
            updated = self.repository.update_watched_file_status(
                watched.id,
                watched.last_hash,
                "error",
                exc.__class__.__name__,
            )
            self.repository.create_event(watched.node_id, watched.id, "error", message=exc.__class__.__name__)
            return updated
        status = "changed" if digest != watched.last_hash else "ok"
        updated = self.repository.update_watched_file_status(watched.id, digest, status)
        event_type = "changed" if status == "changed" else "checked"
        change_count = 1 if status == "changed" else 0
        self.repository.create_event(watched.node_id, watched.id, event_type, change_count=change_count)
        return updated

    def check_node(self, node_id: int, include_children: bool = True) -> list[WatchedFile]:
        node_ids = self.repository.list_descendant_ids(node_id) if include_children else [node_id]
        checked: list[WatchedFile] = []
        for current_node_id in node_ids:
            for watched in self.repository.list_watched_files(current_node_id):
                checked.append(self.check_file(watched.id))
        return checked
```

- [ ] **Step 5: Run monitor tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest tests\test_registry_monitor.py tests\test_registry_repository.py -q
```

Expected: all registry backend tests pass.

---

### Task 4: Registry Mode UI Skeleton

**Files:**
- Modify: `src/file_compare_app/ui/main_window.py`
- Test: `tests/test_registry_ui.py`

- [ ] **Step 1: Write failing UI structure test**

Create `tests/test_registry_ui.py`:

```python
import sys

from PySide6.QtWidgets import QApplication

from file_compare_app.ui.main_window import MainWindow


def test_main_window_has_registry_mode_layout() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()

    required_objects = [
        "modeCompareButton",
        "modeRegistryButton",
        "registryWorkspace",
        "registryTree",
        "registryObjectTitle",
        "registryFilesTable",
        "registryEventsList",
        "registryMonitoringPanel",
        "registryPropertiesPanel",
    ]

    for object_name in required_objects:
        assert window.findChild(object, object_name) is not None
```

- [ ] **Step 2: Run UI test to verify RED**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest tests\test_registry_ui.py -q
```

Expected: FAIL because registry widgets do not exist.

- [ ] **Step 3: Add imports and repository fields**

Modify `src/file_compare_app/ui/main_window.py` imports:

```python
from PySide6.QtWidgets import QInputDialog, QStackedWidget, QTabWidget, QTreeWidget, QTreeWidgetItem
from file_compare_app.registry.monitor import RegistryMonitor
from file_compare_app.registry.repository import RegistryRepository
```

Add fields in `MainWindow.__init__` before `_build_ui()`:

```python
self.registry_repository = RegistryRepository.create()
self.registry_monitor = RegistryMonitor(self.registry_repository)
self.selected_registry_node_id: int | None = None
```

- [ ] **Step 4: Replace workspace with stacked modes**

In `_build_ui`, replace:

```python
shell_layout.addWidget(self._build_toolbar())
shell_layout.addWidget(self._build_workspace(), 1)
```

with:

```python
shell_layout.addWidget(self._build_toolbar())
self.mode_stack = QStackedWidget()
self.mode_stack.setObjectName("modeStack")
self.mode_stack.addWidget(self._build_workspace())
self.mode_stack.addWidget(self._build_registry_workspace())
shell_layout.addWidget(self.mode_stack, 1)
```

- [ ] **Step 5: Add mode buttons to toolbar**

At the start of `_build_toolbar`, before file chips, add:

```python
modes = QFrame()
modes.setObjectName("modeTabs")
mode_layout = QHBoxLayout(modes)
mode_layout.setContentsMargins(4, 4, 4, 4)
mode_layout.setSpacing(6)
self.mode_compare_button = QPushButton("⇄ Сравнение")
self.mode_compare_button.setObjectName("modeCompareButton")
self.mode_registry_button = QPushButton("▦ Реестр объектов")
self.mode_registry_button.setObjectName("modeRegistryButton")
mode_layout.addWidget(self.mode_compare_button)
mode_layout.addWidget(self.mode_registry_button)
layout.addWidget(modes)
```

In `_build_ui`, connect:

```python
self.mode_compare_button.clicked.connect(lambda: self._set_mode("compare"))
self.mode_registry_button.clicked.connect(lambda: self._set_mode("registry"))
```

Add method:

```python
def _set_mode(self, mode: str) -> None:
    self.mode_stack.setCurrentIndex(1 if mode == "registry" else 0)
    self.mode_compare_button.setProperty("active", mode == "compare")
    self.mode_registry_button.setProperty("active", mode == "registry")
    self.mode_compare_button.style().unpolish(self.mode_compare_button)
    self.mode_compare_button.style().polish(self.mode_compare_button)
    self.mode_registry_button.style().unpolish(self.mode_registry_button)
    self.mode_registry_button.style().polish(self.mode_registry_button)
```

- [ ] **Step 6: Add registry workspace skeleton**

Add to `MainWindow`:

```python
def _build_registry_workspace(self) -> QFrame:
    workspace = QFrame()
    workspace.setObjectName("registryWorkspace")
    layout = QHBoxLayout(workspace)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(14)
    layout.addWidget(self._build_registry_tree_panel())
    layout.addWidget(self._build_registry_detail_panel(), 1)
    return workspace

def _build_registry_tree_panel(self) -> QFrame:
    panel = QFrame()
    panel.setObjectName("registryPanel")
    panel.setFixedWidth(330)
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)
    header = QFrame()
    header.setObjectName("summaryPanel")
    header_layout = QHBoxLayout(header)
    header_layout.setContentsMargins(14, 10, 14, 10)
    title = QLabel("Реестр")
    title.setObjectName("summaryTitle")
    self.add_root_button = QToolButton()
    self.add_root_button.setText("+")
    self.add_root_button.setObjectName("iconButtonSmall")
    header_layout.addWidget(title)
    header_layout.addStretch(1)
    header_layout.addWidget(self.add_root_button)
    self.registry_tree = QTreeWidget()
    self.registry_tree.setObjectName("registryTree")
    self.registry_tree.setHeaderHidden(True)
    layout.addWidget(header)
    layout.addWidget(self.registry_tree, 1)
    return panel

def _build_registry_detail_panel(self) -> QFrame:
    panel = QFrame()
    panel.setObjectName("registryDetail")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(0, 0, 0, 0)
    self.registry_object_title = QLabel("Выберите объект")
    self.registry_object_title.setObjectName("registryObjectTitle")
    self.registry_object_title.setProperty("role", "registryTitle")
    layout.addWidget(self.registry_object_title)
    tabs = QTabWidget()
    tabs.setObjectName("registryTabs")
    self.registry_files_table = QListWidget()
    self.registry_files_table.setObjectName("registryFilesTable")
    self.registry_events_list = QListWidget()
    self.registry_events_list.setObjectName("registryEventsList")
    self.registry_monitoring_panel = QLabel("Мониторинг")
    self.registry_monitoring_panel.setObjectName("registryMonitoringPanel")
    self.registry_properties_panel = QLabel("Свойства")
    self.registry_properties_panel.setObjectName("registryPropertiesPanel")
    tabs.addTab(self.registry_files_table, "Файлы")
    tabs.addTab(self.registry_events_list, "История")
    tabs.addTab(self.registry_monitoring_panel, "Мониторинг")
    tabs.addTab(self.registry_properties_panel, "Свойства")
    layout.addWidget(tabs, 1)
    return panel
```

- [ ] **Step 7: Add stylesheet entries**

Add these rules in `_apply_style`:

```css
QFrame#modeTabs {
    background: #f7f9fc;
    border: 1px solid #d6dde8;
    border-radius: 8px;
}
QPushButton#modeCompareButton, QPushButton#modeRegistryButton {
    min-height: 34px;
    padding: 0 12px;
    border: 1px solid transparent;
    border-radius: 7px;
    background: transparent;
    color: #667085;
    font-size: 13px;
    font-weight: 650;
}
QPushButton#modeCompareButton[active="true"], QPushButton#modeRegistryButton[active="true"] {
    background: #ffffff;
    color: #2563eb;
    border-color: #a7c1ff;
}
QFrame#registryPanel, QFrame#registryDetail {
    background: #ffffff;
    border: 1px solid #d6dde8;
    border-radius: 8px;
}
QLabel#registryObjectTitle {
    padding: 18px;
    color: #111827;
    font-size: 24px;
    font-weight: 800;
}
QTreeWidget#registryTree {
    border: 0;
    padding: 10px;
    font-size: 13px;
}
QTabWidget#registryTabs::pane {
    border-top: 1px solid #d6dde8;
}
```

- [ ] **Step 8: Run UI test**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest tests\test_registry_ui.py tests\test_modern_ui_design.py -q
```

Expected: all UI structure tests pass.

---

### Task 5: Registry Data Binding And Object Creation

**Files:**
- Modify: `src/file_compare_app/ui/main_window.py`
- Test: `tests/test_registry_ui.py`

- [ ] **Step 1: Add failing object creation test**

Append to `tests/test_registry_ui.py`:

```python
def test_main_window_creates_and_selects_registry_nodes(tmp_path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.registry_repository = window.registry_repository.create(tmp_path / "registry.sqlite3")
    window.registry_monitor = window.registry_monitor.__class__(window.registry_repository)

    root = window.create_registry_node("Завод №1")
    child = window.create_registry_node("Цех 1", parent_id=root.id)
    window.refresh_registry_tree()
    window.select_registry_node(child.id)

    assert window.selected_registry_node_id == child.id
    assert window.registry_object_title.text() == "Цех 1"
    assert window.registry_tree.topLevelItemCount() == 1
```

- [ ] **Step 2: Run test to verify RED**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest tests\test_registry_ui.py::test_main_window_creates_and_selects_registry_nodes -q
```

Expected: FAIL with missing `create_registry_node`.

- [ ] **Step 3: Add public UI helpers**

Add to `MainWindow`:

```python
def create_registry_node(self, name: str, parent_id: int | None = None):
    node_type = "Подобъект" if parent_id is not None else "Объект"
    node = self.registry_repository.create_node(name=name, parent_id=parent_id, node_type=node_type)
    self.refresh_registry_tree()
    return node

def refresh_registry_tree(self) -> None:
    self.registry_tree.clear()
    for node in self.registry_repository.list_children(None):
        item = self._registry_tree_item(node)
        self.registry_tree.addTopLevelItem(item)
        self._append_registry_children(item, node.id)
    self.registry_tree.expandAll()

def _append_registry_children(self, parent_item: QTreeWidgetItem, parent_id: int) -> None:
    for child in self.registry_repository.list_children(parent_id):
        child_item = self._registry_tree_item(child)
        parent_item.addChild(child_item)
        self._append_registry_children(child_item, child.id)

def _registry_tree_item(self, node) -> QTreeWidgetItem:
    item = QTreeWidgetItem([node.name])
    item.setData(0, Qt.UserRole, node.id)
    return item

def select_registry_node(self, node_id: int) -> None:
    self.selected_registry_node_id = node_id
    node = self.registry_repository.get_node(node_id)
    self.registry_object_title.setText(node.name)
    self._render_registry_files(node_id)
    self._render_registry_events(node_id)
```

- [ ] **Step 4: Connect tree and buttons**

In `_build_ui`, add:

```python
self.registry_tree.currentItemChanged.connect(self._on_registry_tree_selection)
self.add_root_button.clicked.connect(self._create_root_node_dialog)
```

Add:

```python
def _on_registry_tree_selection(self, current: QTreeWidgetItem | None, previous: QTreeWidgetItem | None) -> None:
    if current is None:
        return
    node_id = current.data(0, Qt.UserRole)
    if isinstance(node_id, int):
        self.select_registry_node(node_id)

def _create_root_node_dialog(self) -> None:
    name, accepted = QInputDialog.getText(self, "Новый объект", "Название объекта:")
    if accepted and name.strip():
        self.create_registry_node(name.strip())
```

- [ ] **Step 5: Add file/event render helpers**

Add:

```python
def _render_registry_files(self, node_id: int) -> None:
    self.registry_files_table.clear()
    for watched in self.registry_repository.list_watched_files(node_id):
        self.registry_files_table.addItem(f"{watched.label}\n{watched.file_path}\n{watched.status}")

def _render_registry_events(self, node_id: int) -> None:
    self.registry_events_list.clear()
    for event in self.registry_repository.list_events(node_id):
        self.registry_events_list.addItem(f"{event.created_at} | {event.event_type}\n{event.message}")
```

- [ ] **Step 6: Run UI data binding tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest tests\test_registry_ui.py -q
```

Expected: registry UI tests pass.

---

### Task 6: Attach Files And Manual Check From UI

**Files:**
- Modify: `src/file_compare_app/ui/main_window.py`
- Test: `tests/test_registry_ui.py`

- [ ] **Step 1: Add failing UI file-monitor test**

Append to `tests/test_registry_ui.py`:

```python
def test_main_window_adds_and_checks_file_for_selected_node(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.registry_repository = window.registry_repository.create(tmp_path / "registry.sqlite3")
    window.registry_monitor = window.registry_monitor.__class__(window.registry_repository)
    node = window.create_registry_node("Линия упаковки")
    file_path = tmp_path / "controller.yaml"
    file_path.write_text("timeout: 30", encoding="utf-8")

    window.select_registry_node(node.id)
    watched = window.add_watched_file_to_selected_node(file_path)
    file_path.write_text("timeout: 45", encoding="utf-8")
    checked = window.check_selected_registry_node()

    assert watched.label == "controller.yaml"
    assert checked[0].status == "changed"
    assert "changed" in window.registry_events_list.item(0).text()
```

- [ ] **Step 2: Run test to verify RED**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest tests\test_registry_ui.py::test_main_window_adds_and_checks_file_for_selected_node -q
```

Expected: FAIL with missing `add_watched_file_to_selected_node`.

- [ ] **Step 3: Add UI methods**

Add to `MainWindow`:

```python
def add_watched_file_to_selected_node(self, path: Path | str):
    if self.selected_registry_node_id is None:
        raise RuntimeError("registry node is not selected")
    watched = self.registry_monitor.add_file(self.selected_registry_node_id, Path(path))
    self._render_registry_files(self.selected_registry_node_id)
    self._render_registry_events(self.selected_registry_node_id)
    return watched

def check_selected_registry_node(self):
    if self.selected_registry_node_id is None:
        return []
    checked = self.registry_monitor.check_node(self.selected_registry_node_id)
    self._render_registry_files(self.selected_registry_node_id)
    self._render_registry_events(self.selected_registry_node_id)
    self.status_text.setText("Реестр проверен локально")
    return checked
```

- [ ] **Step 4: Add toolbar buttons for registry actions**

Add registry-specific toolbar buttons in `_build_toolbar`:

```python
self.add_child_button = QPushButton("+ Подобъект")
self.add_child_button.setObjectName("secondaryButton")
self.add_watched_file_button = QPushButton("+ Файл")
self.add_watched_file_button.setObjectName("secondaryButton")
self.check_registry_button = QPushButton("⟳ Проверить")
self.check_registry_button.setObjectName("secondaryButton")
actions_layout.addWidget(self.add_child_button)
actions_layout.addWidget(self.add_watched_file_button)
actions_layout.addWidget(self.check_registry_button)
```

Connect in `_build_ui`:

```python
self.add_child_button.clicked.connect(self._create_child_node_dialog)
self.add_watched_file_button.clicked.connect(self._add_watched_file_dialog)
self.check_registry_button.clicked.connect(self.check_selected_registry_node)
```

Add dialogs:

```python
def _create_child_node_dialog(self) -> None:
    if self.selected_registry_node_id is None:
        QMessageBox.information(self, "Не выбран объект", "Выберите объект или подобъект в реестре.")
        return
    name, accepted = QInputDialog.getText(self, "Новый подобъект", "Название подобъекта:")
    if accepted and name.strip():
        child = self.create_registry_node(name.strip(), parent_id=self.selected_registry_node_id)
        self.select_registry_node(child.id)

def _add_watched_file_dialog(self) -> None:
    if self.selected_registry_node_id is None:
        QMessageBox.information(self, "Не выбран объект", "Выберите объект или подобъект в реестре.")
        return
    path, _ = QFileDialog.getOpenFileName(self, "Добавить файл в мониторинг")
    if path:
        self.add_watched_file_to_selected_node(Path(path))
```

- [ ] **Step 5: Run UI and backend tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest tests\test_registry_ui.py tests\test_registry_monitor.py tests\test_registry_repository.py -q
```

Expected: all registry tests pass.

---

### Task 7: Polish Registry Visuals And Documentation

**Files:**
- Modify: `src/file_compare_app/ui/main_window.py`
- Modify: `README.md`
- Test: `tests/test_registry_ui.py`

- [ ] **Step 1: Add UI text/style assertions**

Append to `tests/test_registry_ui.py`:

```python
def test_registry_mode_keeps_approved_visual_labels() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()

    assert window.mode_registry_button.text() == "▦ Реестр объектов"
    assert window.add_child_button.text() == "+ Подобъект"
    assert window.add_watched_file_button.text() == "+ Файл"
    assert window.check_registry_button.text() == "⟳ Проверить"
```

- [ ] **Step 2: Run test**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest tests\test_registry_ui.py::test_registry_mode_keeps_approved_visual_labels -q
```

Expected: PASS after Task 6.

- [ ] **Step 3: Update README**

Add this section to `README.md`:

```markdown
## Реестр объектов

В режиме `Реестр объектов` приложение хранит локальную SQLite-базу:

- объекты и подобъекты без ограничения глубины;
- файлы, закрепленные за выбранным объектом;
- baseline-хеш при добавлении файла;
- ручную проверку изменений;
- историю событий мониторинга.

База по умолчанию создается в `%LOCALAPPDATA%\FileCompareRegistry\registry.sqlite3`.
```

- [ ] **Step 4: Run full tests**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest -q
```

Expected: all tests pass.

---

### Task 8: Visual Smoke And Executable Rebuild

**Files:**
- Optional modify: `work/capture_actual_compare.py` or add a temporary smoke script under workspace only
- Generated: `outputs/registry-ui.png`
- Generated: `dist/Сравнение файлов.exe`

- [ ] **Step 1: Create smoke screenshot script in workspace**

Create `work/capture_registry_ui.py` outside the PyCharm project:

```python
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from file_compare_app.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1320, 820)
    node = window.create_registry_node("Линия упаковки")
    sample = Path(r"C:\Users\impal\PycharmProjects\PythonSverkaVsego\tests\fixtures\sample_old.txt")
    window.select_registry_node(node.id)
    window.add_watched_file_to_selected_node(sample)
    window._set_mode("registry")
    window.show()

    def capture() -> None:
        output = Path(r"C:\Users\impal\Documents\Codex\2026-06-12\new-chat\outputs\registry-ui.png")
        output.parent.mkdir(parents=True, exist_ok=True)
        window.grab().save(str(output))
        print(output)
        window.close()
        app.quit()

    QTimer.singleShot(700, capture)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run smoke screenshot**

Run:

```powershell
$env:PYTHONPATH='C:\Users\impal\PycharmProjects\PythonSverkaVsego\src'
.\.venv\Scripts\python C:\Users\impal\Documents\Codex\2026-06-12\new-chat\work\capture_registry_ui.py
```

Expected: `outputs\registry-ui.png` exists and shows registry mode with readable Russian text.

- [ ] **Step 3: Rebuild exe**

Run:

```powershell
.\.venv\Scripts\pyinstaller packaging\file-compare-app.spec --clean --noconfirm
```

Expected: `dist\Сравнение файлов.exe` is rebuilt successfully.

- [ ] **Step 4: Final verification**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest -q
```

Expected: all tests pass after rebuild.

---

## Self-Review

- Spec coverage: the plan covers SQLite schema, unlimited nesting, watched files, monitor events, manual check, registry UI, docs, tests, visual smoke, and exe rebuild.
- Stage boundary: timer-based background monitoring remains intentionally outside this first implementation; manual monitoring is fully covered.
- Completeness scan: passed; every task has concrete files, commands, and expected outcomes.
- Type consistency: repository, monitor, and UI method names match across tests and implementation tasks.

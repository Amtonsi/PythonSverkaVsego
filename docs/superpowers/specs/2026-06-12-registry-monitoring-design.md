# Registry And File Monitoring Design

## Goal

Add a local registry mode to `Сравнение файлов` so the user can maintain objects and nested subobjects, attach files to any registry node, and repeatedly monitor those files for changes.

The approved UI direction must match the visual mockup:

- left side: unlimited-depth object tree;
- top toolbar: mode switch, search, create object, create subobject, add file, check;
- right side: selected object card;
- lower right area: tabs `Файлы`, `История`, `Мониторинг`, `Свойства`;
- bottom-right credit remains subtle: `Разработал: Абдрахманов Амаль Даулетович`.

## Product Model

The app keeps two user workflows:

1. One-time comparison of two manually selected files.
2. Registry monitoring for objects and their files.

The registry workflow is hierarchical. A registry node can represent an object, subobject, equipment, department, document group, or any other user-defined item. Nesting has no fixed depth.

Example:

```text
Завод №1
  Цех 1
    Линия упаковки
      Контроллер PLC
      Документация
```

Files can be attached to any node in the tree. Each file keeps its own baseline hash, last hash, last check time, status, and history.

## Database

Use SQLite because the application is local Windows software and does not require a server.

Default database path:

```text
%LOCALAPPDATA%\FileCompareRegistry\registry.sqlite3
```

The first implementation should also allow tests to create temporary databases by passing an explicit database path.

### Tables

`registry_nodes`

- `id`: integer primary key;
- `parent_id`: nullable foreign key to `registry_nodes.id`;
- `name`: required display name;
- `node_type`: text, default `Объект`;
- `code`: optional object code;
- `responsible`: optional responsible person;
- `description`: optional text;
- `monitoring_enabled`: boolean integer, default `1`;
- `monitor_interval_minutes`: integer, default `30`;
- `created_at`: ISO timestamp;
- `updated_at`: ISO timestamp.

`watched_files`

- `id`: integer primary key;
- `node_id`: required foreign key to `registry_nodes.id`;
- `file_path`: absolute file path;
- `label`: user-facing file name;
- `file_kind`: detected type, such as `text`, `config`, `docx`, `pdf`, `xlsx`, `image`, `binary`;
- `baseline_hash`: file hash saved when the file is added or baseline is reset;
- `last_hash`: hash from the last check;
- `last_checked_at`: nullable ISO timestamp;
- `status`: `ok`, `changed`, `missing`, `error`;
- `last_error`: optional text;
- `created_at`: ISO timestamp;
- `updated_at`: ISO timestamp.

`monitor_events`

- `id`: integer primary key;
- `node_id`: required foreign key;
- `watched_file_id`: required foreign key;
- `event_type`: `baseline`, `checked`, `changed`, `missing`, `error`;
- `change_count`: integer, default `0`;
- `report_path`: optional local HTML report path;
- `message`: optional readable note;
- `created_at`: ISO timestamp.

## Backend Components

`registry/database.py`

- Opens SQLite connection.
- Applies schema migrations.
- Enables foreign keys.
- Provides low-level transaction helpers.

`registry/repository.py`

- Creates, updates, deletes, moves, and lists registry nodes.
- Creates, lists, updates, and deletes watched files.
- Reads event history.
- Keeps database logic out of UI code.

`registry/models.py`

- Dataclasses for `RegistryNode`, `WatchedFile`, `MonitorEvent`.

`registry/monitor.py`

- Computes file hash.
- Checks watched files.
- Uses existing `compare_files` for changed files when a baseline/reference file is available.
- Records events and statuses.
- Does not send any file data to the network.

## Baseline Rules

When a file is added:

1. Compute its current hash.
2. Save that hash as both `baseline_hash` and `last_hash`.
3. Create a `baseline` event.
4. Show status `ok`.

When checking:

1. If file is missing, status becomes `missing` and a `missing` event is created.
2. If hash is the same as `last_hash`, status becomes `ok` and a `checked` event is created.
3. If hash changed, status becomes `changed`.
4. For changed files, create a `changed` event. If a comparison report can be generated, store `report_path`.

Baseline reset is a deliberate user action. It updates `baseline_hash` to the current file hash and creates a new `baseline` event.

## UI Design

The approved design is a new mode inside the existing PySide6 window.

### Top Mode Switch

Add two modes:

- `Сравнение`
- `Реестр объектов`

The registry mode uses the current visual language: dark titlebar, white toolbar, light gray workspace, compact 8px-radius panels, restrained blue/green/red/amber statuses.

### Left Panel

The left panel is a tree:

- search field;
- unlimited nested nodes;
- status dot for each node;
- badge with count of changed or problematic files in that subtree;
- selected node highlight.

Actions:

- `+ Объект`: creates a root node;
- `+ Подобъект`: creates a child under the selected node;
- delete node only after confirmation;
- move node later, not required in first implementation.

### Right Panel

The right panel displays the selected node:

- name;
- status pill;
- description;
- type;
- code;
- responsible;
- path in registry;
- monitoring interval;
- last check time;
- KPI cards: file count, changed count, check count.

Tabs:

- `Файлы`: watched files attached to the selected node;
- `История`: events for the selected node and optionally children;
- `Мониторинг`: enable/disable, interval, check on startup;
- `Свойства`: edit name, type, code, responsible, description.

## Monitoring Scope

First implementation:

- manual check for selected node;
- check all files under selected node including nested children;
- save status and events;
- UI reflects changed/missing/error states.

Second implementation:

- timer-based background monitoring;
- check on app startup;
- notification badges while user works.

This staged approach keeps the first database-backed version usable and stable without making background scheduling risky.

## Error Handling

- Missing file: mark `missing`; do not crash.
- Permission error: mark `error`; store short error class/message.
- Unsupported file: use existing binary fallback where possible.
- Database error: show a clear dialog and keep UI responsive.
- Delete object with children/files: require confirmation.

## Testing

Add tests for:

- schema creation;
- create root node;
- create nested nodes with unlimited-depth parent references;
- list children;
- list tree;
- create watched file and baseline hash;
- detect unchanged file;
- detect changed file;
- detect missing file;
- record monitor events;
- UI presence of registry mode controls.

Full verification remains:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python -m pytest -q
```

## Out Of Scope For First Implementation

- multi-user network database;
- cloud sync;
- permissions by user role;
- automatic Windows service;
- advanced drag-and-drop tree reordering;
- report cleanup policy;
- email or messenger notifications.

## Open Decisions

The approved first implementation will create manual monitoring. Background timer monitoring is designed as the next step after the database-backed registry is stable.

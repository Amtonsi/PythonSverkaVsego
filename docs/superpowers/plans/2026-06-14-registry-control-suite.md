# Registry Control Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add smart config comparison, review statuses, risk summaries, object templates, and scheduled monitoring settings to the local file comparison registry.

**Architecture:** Keep the existing SQLite repository and PySide6 UI, adding small focused modules for config profiles and risk detection. Store review/schedule/template metadata in SQLite tables/columns, then surface it in existing registry tabs and Excel export.

**Tech Stack:** Python 3.14, PySide6, SQLite, openpyxl, pytest, PyInstaller.

---

### Task 1: Smart Config Profiles

**Files:**
- Create: `src/file_compare_app/core/config_profiles.py`
- Modify: `src/file_compare_app/analyzers/text_config.py`
- Modify: `src/file_compare_app/analyzers/klp.py`
- Test: `tests/test_config_profiles.py`

- [ ] Write failing tests for ignoring service lines such as `Cryptochecksum`, `Saved`, `Written by`, `size_bytes`, `klparbin_offset`, and generated timestamps.
- [ ] Add profile detection by extension/name for `cfg`, `klp`, `json`, `yaml`, `ini`, `env`, and generic text.
- [ ] Normalize line comparisons through the selected profile while preserving original line numbers.
- [ ] Mark risky config changes with `severity="risk"` when ACL/firewall/interface/route/password/protection keywords change.
- [ ] Run targeted config/KLP tests, then the full suite.

### Task 2: Review Statuses for Version Pairs

**Files:**
- Modify: `src/file_compare_app/registry/database.py`
- Modify: `src/file_compare_app/registry/models.py`
- Modify: `src/file_compare_app/registry/repository.py`
- Modify: `src/file_compare_app/ui/main_window.py`
- Test: `tests/test_registry_repository.py`
- Test: `tests/test_registry_ui.py`

- [ ] Add `comparison_reviews` table keyed by `watched_file_id`, `from_version`, and `to_version`.
- [ ] Add repository methods to read and update status, reviewer, comment, and timestamp.
- [ ] Show review status in the files table and selected pair card.
- [ ] Add UI controls for `Новое`, `Проверено`, `Согласовано`, `Отклонено`, reviewer, and comment.
- [ ] Include review fields in Excel export.

### Task 3: Risk Panel

**Files:**
- Create: `src/file_compare_app/core/risk_rules.py`
- Modify: `src/file_compare_app/registry/monitor.py`
- Modify: `src/file_compare_app/ui/main_window.py`
- Test: `tests/test_risk_rules.py`
- Test: `tests/test_registry_ui.py`

- [ ] Add reusable risk keyword/rule analysis for comparison changes and monitored file metadata.
- [ ] Store risk count and risk summary in monitor events.
- [ ] Add a `Риски` registry tab with total risky files and latest risky changes.
- [ ] Add risk counters to monitoring dashboard.

### Task 4: Object Templates and Monitoring Schedule

**Files:**
- Modify: `src/file_compare_app/registry/database.py`
- Modify: `src/file_compare_app/registry/repository.py`
- Modify: `src/file_compare_app/ui/main_window.py`
- Test: `tests/test_registry_repository.py`
- Test: `tests/test_registry_ui.py`

- [ ] Add built-in object templates: `АРМ`, `Сервер`, `Kaspersky`, `Cisco/ASA`, `Контроллер`.
- [ ] Store selected template and monitoring interval on each registry node.
- [ ] Add template/interval controls to the object card.
- [ ] Show next check text and monitoring enabled state in the object summary.

### Task 5: Packaging and Listing

**Files:**
- Modify: `docs/Листинг_программы_с_комментариями.txt`
- Build: `dist/Сравнение файлов.exe`

- [ ] Run all tests with a workspace basetemp.
- [ ] Copy verified files to the main PyCharm project.
- [ ] Rebuild the exe with PyInstaller.
- [ ] Regenerate the full listing.
- [ ] Verify exe and listing exist.

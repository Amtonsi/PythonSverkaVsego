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


def test_monitor_adds_baseline_version_and_detects_unchanged_file(tmp_path: Path) -> None:
    repository = RegistryRepository.create(tmp_path / "registry.sqlite3")
    node = repository.create_node("Линия упаковки")
    file_path = tmp_path / "controller.yaml"
    file_path.write_text("timeout: 30", encoding="utf-8")
    monitor = RegistryMonitor(repository)

    watched = monitor.add_file(node.id, file_path)
    checked = monitor.check_file(watched.id)

    assert checked.status == "ok"
    assert repository.get_latest_file_version(watched.id).version_number == 1
    assert [event.event_type for event in repository.list_events(node.id)] == ["checked", "baseline"]


def test_monitor_detects_changed_file_by_comparing_previous_version(tmp_path: Path) -> None:
    repository = RegistryRepository.create(tmp_path / "registry.sqlite3")
    node = repository.create_node("Линия упаковки")
    file_path = tmp_path / "controller.yaml"
    file_path.write_text("timeout: 30", encoding="utf-8")
    monitor = RegistryMonitor(repository)
    watched = monitor.add_file(node.id, file_path)

    file_path.write_text("timeout: 45", encoding="utf-8")
    changed = monitor.check_file(watched.id)
    versions = repository.list_file_versions(watched.id)
    event = repository.list_events(node.id)[0]

    assert changed.status == "changed"
    assert [version.version_number for version in versions] == [1, 2]
    assert versions[0].sha256 != versions[1].sha256
    assert event.event_type == "changed"
    assert event.change_count > 0
    assert "v1 -> v2" in event.message
    assert "timeout: 30" in event.message
    assert "timeout: 45" in event.message


def test_monitor_adds_before_after_pair_as_single_logical_file(tmp_path: Path) -> None:
    repository = RegistryRepository.create(tmp_path / "registry.sqlite3")
    node = repository.create_node("Object")
    before = tmp_path / "UPN1 ARM DeltaV.klp"
    after = tmp_path / "UPN1 ARM DeltaV - after.klp"
    before.write_text("hash=old", encoding="utf-8")
    after.write_text("hash=new", encoding="utf-8")
    monitor = RegistryMonitor(repository)

    watched = monitor.add_file_pair(node.id, before, after, label="UPN1 ARM DeltaV.klp")

    watched_files = repository.list_watched_files(node.id)
    versions = repository.list_file_versions(watched.id)
    event = repository.list_events(node.id)[0]
    assert len(watched_files) == 1
    assert watched_files[0].id == watched.id
    assert watched_files[0].file_path == str(after)
    assert watched_files[0].status == "changed"
    assert [version.version_number for version in versions] == [1, 2]
    assert "v1 -> v2" in event.message
    assert "hash=old" in event.message
    assert "hash=new" in event.message


def test_monitor_adds_next_after_version_from_previous_after(tmp_path: Path) -> None:
    repository = RegistryRepository.create(tmp_path / "registry.sqlite3")
    node = repository.create_node("Object")
    before = tmp_path / "policy.klp"
    after = tmp_path / "policy-after.klp"
    next_after = tmp_path / "policy-after-2.klp"
    before.write_text("hash=old", encoding="utf-8")
    after.write_text("hash=new", encoding="utf-8")
    next_after.write_text("hash=latest", encoding="utf-8")
    monitor = RegistryMonitor(repository)
    watched = monitor.add_file_pair(node.id, before, after)

    updated = monitor.add_next_version(watched.id, next_after)

    versions = repository.list_file_versions(watched.id)
    event = repository.list_events(node.id)[0]
    assert updated.file_path == str(next_after)
    assert [version.version_number for version in versions] == [1, 2, 3]
    assert "v2 -> v3" in event.message
    assert "hash=new" in event.message
    assert "hash=latest" in event.message


def test_monitor_detects_missing_file_without_losing_previous_version(tmp_path: Path) -> None:
    repository = RegistryRepository.create(tmp_path / "registry.sqlite3")
    node = repository.create_node("Линия упаковки")
    file_path = tmp_path / "controller.yaml"
    file_path.write_text("timeout: 30", encoding="utf-8")
    monitor = RegistryMonitor(repository)
    watched = monitor.add_file(node.id, file_path)

    file_path.unlink()
    missing = monitor.check_file(watched.id)

    assert missing.status == "missing"
    assert repository.get_latest_file_version(watched.id).version_number == 1
    assert repository.list_events(node.id)[0].event_type == "missing"


def test_monitoring_summary_includes_child_nodes_and_latest_version_info(tmp_path: Path) -> None:
    repository = RegistryRepository.create(tmp_path / "registry.sqlite3")
    root = repository.create_node("Объект")
    child = repository.create_node("Подобъект", parent_id=root.id)
    file_path = tmp_path / "policy.klp"
    file_path.write_text("hash=old", encoding="utf-8")
    monitor = RegistryMonitor(repository)
    watched = monitor.add_file(child.id, file_path)

    file_path.write_text("hash=new", encoding="utf-8")
    monitor.check_file(watched.id)
    summary = monitor.build_node_summary(root.id)

    assert summary.total_files == 1
    assert summary.status_counts["changed"] == 1
    assert summary.files[0].node_path == "Объект / Подобъект"
    assert summary.files[0].latest_version.version_number == 2
    assert "hash=old" in summary.files[0].last_event.message
    assert "hash=new" in summary.files[0].last_event.message


def test_registry_monitor_records_risk_count_for_dangerous_config_change(tmp_path: Path) -> None:
    repository = RegistryRepository.create(tmp_path / "registry.sqlite3")
    monitor = RegistryMonitor(repository)
    node = repository.create_node("Firewall")
    config = tmp_path / "running.cfg"
    config.write_text("access-list outside_in extended permit ip any any\n", encoding="utf-8")
    watched = monitor.add_file(node.id, config)

    config.write_text("access-list outside_in extended deny ip any any\n", encoding="utf-8")
    monitor.check_file(watched.id)

    event = repository.get_last_event_for_watched_file(watched.id)
    assert event is not None
    assert event.risk_count == 1
    assert "access-list" in event.risk_summary

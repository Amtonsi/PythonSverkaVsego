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


def test_cfg_without_ini_sections_falls_back_to_line_diff(tmp_path: Path) -> None:
    old = tmp_path / "running-config_before.cfg"
    new = tmp_path / "running-config_after.cfg"
    old.write_text(
        "Cryptochecksum: old\n"
        "interface GigabitEthernet0/1\n"
        " description old uplink\n"
        "!\n",
        encoding="utf-8",
    )
    new.write_text(
        "Cryptochecksum: new\n"
        "interface GigabitEthernet0/1\n"
        " description new uplink\n"
        "!\n",
        encoding="utf-8",
    )

    result = TextConfigAnalyzer().compare(old, new)

    assert result.file_kind == "config"
    assert result.changes
    assert result.changes[0].format == "text"
    assert result.changes[0].source_location.display().endswith(":3")
    assert "description old uplink" in result.changes[0].before


def test_cfg_inserted_lines_do_not_turn_shared_config_lines_into_removals(tmp_path: Path) -> None:
    old = tmp_path / "old.cfg"
    new = tmp_path / "new.cfg"
    old.write_text(
        "object-group service OPC_PORTS_PERMIT\n"
        " service-object tcp-udp gt 1024 \n"
        " service-object tcp-udp range 135 139 \n"
        " service-object tcp-udp eq 445 \n"
        " service-object tcp-udp eq 12345 \n"
        "access-list acl_outside_in extended permit object-group OPC_PORTS_PERMIT object-group Server\n"
        "pager lines 24\n",
        encoding="utf-8",
    )
    new.write_text(
        "object-group service OPC_PORTS_PERMIT\n"
        " description added letters\n"
        " service-object tcp-udp range 135 139 \n"
        " service-object tcp-udp eq 445 \n"
        " service-object tcp range 1024 4999 \n"
        "access-list acl_outside_in extended permit object-group OPC_PORTS_PERMIT object-group Server log\n"
        "pager lines 24\n",
        encoding="utf-8",
    )

    result = TextConfigAnalyzer().compare(old, new)
    changed_text = "\n".join(f"{change.change_type}: {change.before} -> {change.after}" for change in result.changes)

    assert "service-object tcp-udp eq 445" not in changed_text
    assert any(change.change_type == "added" and "description added letters" in change.after for change in result.changes)
    assert any(change.change_type == "modified" and " log" in change.after for change in result.changes)

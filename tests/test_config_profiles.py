from pathlib import Path

from file_compare_app.analyzers.klp import KasperskyKlpAnalyzer
from file_compare_app.analyzers.text_config import TextConfigAnalyzer


def test_cfg_profile_ignores_generated_service_lines(tmp_path: Path) -> None:
    before = tmp_path / "running-config_before.cfg"
    after = tmp_path / "running-config_after.cfg"
    before.write_text(
        "\n".join(
            [
                "Cryptochecksum: old",
                ": Saved",
                ": Written by admin at 10:00",
                "hostname oil-gs-operator-mes-fw01",
                "interface Ethernet0/0",
            ]
        ),
        encoding="utf-8",
    )
    after.write_text(
        "\n".join(
            [
                "Cryptochecksum: new",
                ": Saved",
                ": Written by engineer at 11:00",
                "hostname oil-gs-operator-mes-fw01",
                "interface Ethernet0/0",
            ]
        ),
        encoding="utf-8",
    )

    result = TextConfigAnalyzer().compare(before, after)

    assert result.change_count == 0


def test_cfg_profile_marks_firewall_acl_changes_as_risk(tmp_path: Path) -> None:
    before = tmp_path / "running-config_before.cfg"
    after = tmp_path / "running-config_after.cfg"
    before.write_text("access-list outside_in extended permit ip any any\n", encoding="utf-8")
    after.write_text("access-list outside_in extended deny ip any any\n", encoding="utf-8")

    result = TextConfigAnalyzer().compare(before, after)

    assert result.change_count == 1
    assert result.changes[0].severity == "risk"
    assert "risk rule" in result.changes[0].notes


def test_klp_profile_ignores_extracted_binary_metadata_noise(tmp_path: Path) -> None:
    before = tmp_path / "policy_before.klp"
    after = tmp_path / "policy_after.klp"
    before.write_text("size_bytes: 100\nklparbin_offset: 10\nvalue=CyberSecurity for Nodes AR\n", encoding="utf-8")
    after.write_text("size_bytes: 200\nklparbin_offset: 20\nvalue=CyberSecurity for Nodes AR\n", encoding="utf-8")

    result = KasperskyKlpAnalyzer().compare(before, after)

    assert result.change_count == 0

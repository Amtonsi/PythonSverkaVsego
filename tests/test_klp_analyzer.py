from pathlib import Path
import zlib

from file_compare_app.analyzers.klp import KasperskyKlpAnalyzer, extract_klp_profile_lines
from file_compare_app.core.orchestrator import compare_files


def _raw_deflate(payload: bytes) -> bytes:
    compressor = zlib.compressobj(level=9, wbits=-zlib.MAX_WBITS)
    return compressor.compress(payload) + compressor.flush()


def _write_klp(path: Path, section_hash: str) -> None:
    visible = (
        ".core\0"
        "AntiCryptor\0"
        "hash\0"
        f"{section_hash}\0"
        "2.5.0.0\0"
    ).encode("utf-16le")
    compressed = "KLPOL_ACCEPT_PARENT\0KLPRSS_Mnd\0".encode("utf-16le")
    path.write_bytes(
        b"\x08\x00\x00\x00kscpolfmn\x01\x00\x00"
        + b"ZLIB"
        + _raw_deflate(b"<!--KLPARBIN -->" + compressed)
        + b"<!--KLPARBIN -->"
        + visible
    )


def test_kaspersky_klp_profile_lines_extract_policy_metadata(tmp_path: Path) -> None:
    policy = tmp_path / "policy.klp"
    _write_klp(policy, "hash-old")

    lines = extract_klp_profile_lines(policy)

    assert "format: Kaspersky KLP policy" in lines
    assert "magic: kscpolfmn" in lines
    assert "klparbin_marker: yes" in lines
    assert "zlib_blocks: 1" in lines
    assert "section: AntiCryptor" in lines
    assert "value: hash-old" in lines
    assert "value: KLPOL_ACCEPT_PARENT" in lines


def test_klp_analyzer_reports_changed_kaspersky_section_hash(tmp_path: Path) -> None:
    old = tmp_path / "old.klp"
    new = tmp_path / "new.klp"
    _write_klp(old, "hash-old")
    _write_klp(new, "hash-new")

    result = KasperskyKlpAnalyzer().compare(old, new)

    assert result.file_kind == "klp"
    assert any("hash-old" in change.before and "hash-new" in change.after for change in result.changes)
    assert any(change.notes == "KLP values" for change in result.changes)


def test_klp_analyzer_groups_large_profile_differences(tmp_path: Path) -> None:
    old = tmp_path / "old.klp"
    new = tmp_path / "new.klp"
    old.write_text("\n".join(f"section: OldSection{i}" for i in range(80)), encoding="utf-8")
    new.write_text("\n".join(f"section: NewSection{i}" for i in range(25)), encoding="utf-8")

    result = KasperskyKlpAnalyzer().compare(old, new)

    assert result.file_kind == "klp"
    assert len(result.changes) <= 3
    assert any(change.notes == "KLP values" for change in result.changes)
    assert "еще" in result.changes[0].before


def test_klp_analyzer_keeps_group_summary_short(tmp_path: Path) -> None:
    old = tmp_path / "old.klp"
    new = tmp_path / "new.klp"
    old.write_text(
        "\n".join(f"section: OldVeryLongSectionNameWithManyPartsAndSuffix{i}" for i in range(40)),
        encoding="utf-8",
    )
    new.write_text(
        "\n".join(f"section: NewVeryLongSectionNameWithManyPartsAndSuffix{i}" for i in range(40)),
        encoding="utf-8",
    )

    result = KasperskyKlpAnalyzer().compare(old, new)

    assert result.changes
    assert all(len(change.before) <= 180 for change in result.changes if change.before)
    assert all(len(change.after) <= 180 for change in result.changes if change.after)


def test_orchestrator_uses_klp_analyzer_for_kaspersky_policy(tmp_path: Path) -> None:
    old = tmp_path / "old.klp"
    new = tmp_path / "new.klp"
    _write_klp(old, "hash-old")
    _write_klp(new, "hash-new")

    result = compare_files(old, new)

    assert result.file_kind == "klp"
    assert result.changes

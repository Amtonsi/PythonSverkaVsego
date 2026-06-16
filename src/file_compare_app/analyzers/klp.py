from __future__ import annotations

import re
import zlib
from pathlib import Path

from file_compare_app.analyzers.base import Analyzer
from file_compare_app.core.config_profiles import is_risky_change, normalize_lines_for_path, risk_note
from file_compare_app.core.models import Change, ChangeLocation, ComparisonResult


KLP_MAGIC = b"kscpolfmn"
KLPARBIN_MARKER = b"<!--KLPARBIN -->"
TEXT_RE = re.compile(r"[A-Za-zА-Яа-я0-9_./+ :;=,()\\\-\[\]{}]{4,}")


class KasperskyKlpAnalyzer(Analyzer):
    def compare(self, left_path: Path, right_path: Path) -> ComparisonResult:
        left_lines = [line.text for line in normalize_lines_for_path(left_path, extract_klp_profile_lines(left_path))]
        right_lines = [line.text for line in normalize_lines_for_path(right_path, extract_klp_profile_lines(right_path))]
        changes = _profile_changes(
            _parse_profile_lines(left_lines),
            _parse_profile_lines(right_lines),
            left_path,
            right_path,
        )
        return ComparisonResult(str(left_path), str(right_path), "klp", changes)


def extract_klp_profile_lines(path: Path) -> list[str]:
    data = path.read_bytes()
    zlib_positions = _find_all(data, b"ZLIB")
    if KLP_MAGIC not in data[:32] and KLPARBIN_MARKER not in data and not zlib_positions:
        return _extract_text_klp_lines(path, data)
    strings = set(_extract_readable_strings(data))
    for payload in _extract_raw_deflate_payloads(data, zlib_positions):
        strings.update(_extract_readable_strings(payload))

    clean_values = sorted(_clean_string(value) for value in strings if _clean_string(value))
    sections = sorted(value for value in clean_values if _looks_like_section(value))
    marker_position = data.find(KLPARBIN_MARKER)

    lines = [
        "format: Kaspersky KLP policy",
        f"magic: {_detect_magic(data)}",
        f"size_bytes: {len(data)}",
        f"klparbin_marker: {'yes' if marker_position >= 0 else 'no'}",
        f"zlib_blocks: {len(zlib_positions)}",
    ]
    if marker_position >= 0:
        lines.append(f"klparbin_offset: {marker_position}")

    lines.append("[sections]")
    lines.extend(f"section: {section}" for section in sections)
    lines.append("[values]")
    lines.extend(f"value: {value}" for value in clean_values)
    return lines


def _extract_text_klp_lines(path: Path, data: bytes) -> list[str]:
    for encoding in ("utf-8-sig", "utf-8", "cp1251", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = data.decode(errors="replace")
    lines = [
        "format: Kaspersky KLP policy text",
        "magic: text",
        f"size_bytes: {len(data)}",
        "[values]",
    ]
    lines.extend(line.strip() for line in text.splitlines() if line.strip())
    if len(lines) == 4:
        lines.append(f"value: {path.name}")
    return lines


def _detect_magic(data: bytes) -> str:
    if KLP_MAGIC in data[:32]:
        return KLP_MAGIC.decode("ascii")
    return "unknown"


def _find_all(data: bytes, needle: bytes) -> list[int]:
    positions: list[int] = []
    start = 0
    while True:
        position = data.find(needle, start)
        if position < 0:
            return positions
        positions.append(position)
        start = position + len(needle)


def _extract_raw_deflate_payloads(data: bytes, zlib_positions: list[int]) -> list[bytes]:
    payloads: list[bytes] = []
    for position in zlib_positions:
        compressed = data[position + 4 :]
        try:
            decompressor = zlib.decompressobj(-zlib.MAX_WBITS)
            payload = decompressor.decompress(compressed, 2_000_000)
        except zlib.error:
            continue
        if payload:
            payloads.append(payload)
    return payloads


def _extract_readable_strings(data: bytes) -> list[str]:
    strings: set[str] = set()
    for offset in (0, 1):
        text = data[offset:].decode("utf-16le", errors="ignore")
        strings.update(_split_and_match(text))
    text = data.decode("ascii", errors="ignore")
    strings.update(value for value in _split_and_match(text) if value.startswith(("KL", "KLP")))
    return sorted(value for value in strings if _is_profile_value(value))


def _split_and_match(text: str) -> set[str]:
    found: set[str] = set()
    for part in re.split(r"[\x00\r\n\t]+", text):
        found.update(TEXT_RE.findall(part))
    return found


def _is_profile_value(value: str) -> bool:
    value = _clean_string(value)
    if len(value) < 3 or len(value) > 120:
        return False
    lowered = value.lower()
    if lowered == "hash":
        return True
    if value.startswith("."):
        return True
    if "section" in lowered:
        return True
    if re.fullmatch(r"\d+(?:\.\d+)+", value):
        return True
    if re.fullmatch(r"[A-Za-z0-9_./+\-=]{4,}", value):
        return True
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_./+\-= ]{3,}", value):
        return True
    return False


def _clean_string(value: str) -> str:
    return " ".join(value.replace("\x00", " ").split())


def _looks_like_section(value: str) -> bool:
    lowered = value.lower()
    if lowered in {"hash", "zlib", "format"}:
        return False
    if re.fullmatch(r"[A-Za-z0-9+/]{12,}={0,2}", value):
        return False
    if re.fullmatch(r"\d+(?:\.\d+)+", value):
        return False
    if len(value) > 90:
        return False
    return any(character.isalpha() for character in value) and (
        value.startswith(".") or value[:1].isupper() or "section" in lowered
    )


def _parse_profile_lines(lines: list[str]) -> dict[str, object]:
    metadata: dict[str, str] = {}
    sections: set[str] = set()
    values: set[str] = set()
    mode = "metadata"
    for line in lines:
        if line == "[sections]":
            mode = "sections"
            continue
        if line == "[values]":
            mode = "values"
            continue
        if mode == "sections" and line.startswith("section: "):
            sections.add(line.removeprefix("section: "))
            continue
        if mode == "values":
            values.add(line.removeprefix("value: ") if line.startswith("value: ") else line)
            continue
        if ": " in line:
            key, value = line.split(": ", 1)
            metadata[key] = value
    return {"metadata": metadata, "sections": sections, "values": values}


def _profile_changes(
    left_profile: dict[str, object],
    right_profile: dict[str, object],
    left_path: Path,
    right_path: Path,
) -> list[Change]:
    changes: list[Change] = []
    _append_set_change(
        changes,
        left_profile["sections"],  # type: ignore[arg-type]
        right_profile["sections"],  # type: ignore[arg-type]
        left_path,
        right_path,
        "Секции",
        "KLP sections",
    )
    _append_set_change(
        changes,
        left_profile["values"],  # type: ignore[arg-type]
        right_profile["values"],  # type: ignore[arg-type]
        left_path,
        right_path,
        "Значения",
        "KLP values",
    )
    _append_metadata_change(
        changes,
        left_profile["metadata"],  # type: ignore[arg-type]
        right_profile["metadata"],  # type: ignore[arg-type]
        left_path,
        right_path,
    )
    return changes


def _append_set_change(
    changes: list[Change],
    left_values: set[str],
    right_values: set[str],
    left_path: Path,
    right_path: Path,
    title: str,
    notes: str,
) -> None:
    removed = sorted(left_values - right_values)
    added = sorted(right_values - left_values)
    if not removed and not added:
        return
    change_type = "modified" if removed and added else "removed" if removed else "added"
    before_text = f"{title} удалены ({len(removed)}): {_sample_values(removed)}" if removed else ""
    after_text = f"{title} добавлены ({len(added)}): {_sample_values(added)}" if added else ""
    risky = is_risky_change(before_text, after_text, notes)
    changes.append(
        Change(
            change_id=f"klp-{len(changes) + 1}",
            change_type=change_type,  # type: ignore[arg-type]
            severity="risk" if risky else "normal",
            source_location=ChangeLocation(str(left_path), line=1) if removed else None,
            target_location=ChangeLocation(str(right_path), line=1) if added else None,
            before=before_text,
            after=after_text,
            format="klp",
            confidence=0.92,
            notes=f"{notes}; {risk_note(before_text, after_text, notes)}" if risky else notes,
        )
    )


def _append_metadata_change(
    changes: list[Change],
    left_metadata: dict[str, str],
    right_metadata: dict[str, str],
    left_path: Path,
    right_path: Path,
) -> None:
    changed_keys = sorted(key for key in set(left_metadata) | set(right_metadata) if left_metadata.get(key) != right_metadata.get(key))
    if not changed_keys:
        return
    changes.append(
        Change(
            change_id=f"klp-{len(changes) + 1}",
            change_type="modified",
            severity="low",
            source_location=ChangeLocation(str(left_path), line=1),
            target_location=ChangeLocation(str(right_path), line=1),
            before="; ".join(f"{key}: {left_metadata.get(key, '-')}" for key in changed_keys),
            after="; ".join(f"{key}: {right_metadata.get(key, '-')}" for key in changed_keys),
            format="klp",
            confidence=0.9,
            notes="KLP technical metadata",
        )
    )


def _sample_values(values: list[str], limit: int = 3, max_length: int = 96) -> str:
    if not values:
        return "-"
    sample = values[:limit]
    suffix = f"; еще {len(values) - limit}" if len(values) > limit else ""
    text = "; ".join(sample) + suffix
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"

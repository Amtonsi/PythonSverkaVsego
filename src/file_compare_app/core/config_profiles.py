from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NormalizedLine:
    text: str
    original: str
    line_number: int


SERVICE_LINE_PATTERNS = [
    re.compile(r"^\s*cryptochecksum\s*:", re.IGNORECASE),
    re.compile(r"^\s*:?\s*saved\s*$", re.IGNORECASE),
    re.compile(r"^\s*:?\s*written by .+ at .+", re.IGNORECASE),
    re.compile(r"^\s*(generated|created|exported)\s+(at|on|by)\b", re.IGNORECASE),
    re.compile(r"^\s*(last[-_ ]?modified|timestamp|date|time)\s*[:=]", re.IGNORECASE),
    re.compile(r"^\s*(size_bytes|klparbin_offset|zlib_blocks|magic|format)\s*:", re.IGNORECASE),
    re.compile(r"^\s*#\s*(generated|saved|written)\b", re.IGNORECASE),
]

RISK_PATTERNS = [
    re.compile(r"\baccess-list\b|\bacl\b|\bfirewall\b", re.IGNORECASE),
    re.compile(r"\bpermit\b|\bdeny\b|\boutside_in\b|\binside_in\b", re.IGNORECASE),
    re.compile(r"\binterface\b|\broute\b|\bgateway\b|\bnat\b", re.IGNORECASE),
    re.compile(r"\bpassword\b|\bpasswd\b|\bsecret\b|\bencrypt", re.IGNORECASE),
    re.compile(r"\bdisable(?:d)?\b|\boff\b|\bprotection\b|\bkaspersky\b|\bklprss\b", re.IGNORECASE),
]


def normalize_lines_for_path(path: Path, lines: list[str]) -> list[NormalizedLine]:
    return [
        normalized
        for line_number, line in enumerate(lines, start=1)
        if (normalized := normalize_line(path, line, line_number)) is not None
    ]


def normalize_line(path: Path, line: str, line_number: int) -> NormalizedLine | None:
    stripped = " ".join(line.strip().split())
    if not stripped:
        return None
    if _is_service_line(path, stripped):
        return None
    return NormalizedLine(text=stripped, original=line, line_number=line_number)


def is_risky_change(before: str, after: str, notes: str = "") -> bool:
    haystack = f"{before}\n{after}\n{notes}"
    return any(pattern.search(haystack) for pattern in RISK_PATTERNS)


def risk_note(before: str, after: str, notes: str = "") -> str:
    return "risk rule: critical config keyword" if is_risky_change(before, after, notes) else ""


def _is_service_line(path: Path, stripped: str) -> bool:
    suffix = path.suffix.lower()
    if any(pattern.search(stripped) for pattern in SERVICE_LINE_PATTERNS):
        return True
    if suffix in {".klp", ".cfg", ".conf"} and re.match(r"^\s*!?\s*$", stripped):
        return True
    return False

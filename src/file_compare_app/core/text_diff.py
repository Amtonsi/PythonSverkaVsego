from __future__ import annotations

from collections import Counter
from difflib import SequenceMatcher


LineChange = tuple[str, int | None, int | None, str, str]
MIN_MODIFIED_SIMILARITY = 0.35


def line_changes(left_lines: list[str], right_lines: list[str]) -> list[LineChange]:
    return _patience_line_changes(left_lines, right_lines, 0, 0)


def _patience_line_changes(
    left_lines: list[str],
    right_lines: list[str],
    left_offset: int,
    right_offset: int,
) -> list[LineChange]:
    anchors = _unique_lcs_anchors(left_lines, right_lines)
    if not anchors:
        return _sequence_line_changes(left_lines, right_lines, left_offset, right_offset)

    changes: list[LineChange] = []
    previous_left = 0
    previous_right = 0
    for left_index, right_index in anchors:
        changes.extend(
            _patience_line_changes(
                left_lines[previous_left:left_index],
                right_lines[previous_right:right_index],
                left_offset + previous_left,
                right_offset + previous_right,
            )
        )
        previous_left = left_index + 1
        previous_right = right_index + 1
    changes.extend(
        _patience_line_changes(
            left_lines[previous_left:],
            right_lines[previous_right:],
            left_offset + previous_left,
            right_offset + previous_right,
        )
    )
    return changes


def _sequence_line_changes(
    left_lines: list[str],
    right_lines: list[str],
    left_offset: int,
    right_offset: int,
) -> list[LineChange]:
    matcher = SequenceMatcher(a=left_lines, b=right_lines, autojunk=False)
    changes: list[LineChange] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace":
            max_len = max(i2 - i1, j2 - j1)
            for offset in range(max_len):
                local_left_index = i1 + offset if i1 + offset < i2 else None
                local_right_index = j1 + offset if j1 + offset < j2 else None
                before = left_lines[local_left_index] if local_left_index is not None else ""
                after = right_lines[local_right_index] if local_right_index is not None else ""
                left_index = left_offset + local_left_index if local_left_index is not None else None
                right_index = right_offset + local_right_index if local_right_index is not None else None
                if before and after and _should_split_replace(before, after):
                    changes.append(("removed", left_index, None, before, ""))
                    changes.append(("added", None, right_index, "", after))
                else:
                    kind = "modified" if before and after else "added" if after else "removed"
                    changes.append((kind, left_index, right_index, before, after))
        elif tag == "delete":
            for local_left_index in range(i1, i2):
                changes.append(("removed", left_offset + local_left_index, None, left_lines[local_left_index], ""))
        elif tag == "insert":
            for local_right_index in range(j1, j2):
                changes.append(("added", None, right_offset + local_right_index, "", right_lines[local_right_index]))
    return changes


def _unique_lcs_anchors(left_lines: list[str], right_lines: list[str]) -> list[tuple[int, int]]:
    left_counts = Counter(left_lines)
    right_counts = Counter(right_lines)
    right_positions = {line: index for index, line in enumerate(right_lines) if right_counts[line] == 1}
    pairs = [
        (left_index, right_positions[line])
        for left_index, line in enumerate(left_lines)
        if left_counts[line] == 1 and right_counts[line] == 1
    ]
    return _longest_increasing_pairs(pairs)


def _longest_increasing_pairs(pairs: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not pairs:
        return []
    best: list[tuple[int, int]] = []
    for pair in pairs:
        left_index, right_index = pair
        candidates = [sequence + [pair] for sequence in best if sequence[-1][1] < right_index]
        candidate = max(candidates, key=len, default=[pair])
        best.append(candidate)
    return max(best, key=len, default=[])


def _line_similarity(left: str, right: str) -> float:
    return SequenceMatcher(a=left.strip().lower(), b=right.strip().lower(), autojunk=False).ratio()


def _should_split_replace(left: str, right: str) -> bool:
    if min(len(left.strip()), len(right.strip())) < 8:
        return False
    return _line_similarity(left, right) < MIN_MODIFIED_SIMILARITY

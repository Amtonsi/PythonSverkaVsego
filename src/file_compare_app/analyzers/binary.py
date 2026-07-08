from pathlib import Path

from file_compare_app.analyzers.base import Analyzer
from file_compare_app.core.models import Change, ChangeLocation, ComparisonResult


class BinaryAnalyzer(Analyzer):
    def compare(self, left_path: Path, right_path: Path) -> ComparisonResult:
        left = left_path.read_bytes()
        right = right_path.read_bytes()
        changes: list[Change] = []
        max_len = max(len(left), len(right))
        change_index = 1
        offset = 0
        max_reported_changes = 200

        while offset < max_len:
            if len(changes) >= max_reported_changes:
                break
            left_byte = left[offset : offset + 1]
            right_byte = right[offset : offset + 1]
            if left_byte == right_byte:
                offset += 1
                continue

            start = offset
            before = bytearray()
            after = bytearray()
            while offset < max_len and left[offset : offset + 1] != right[offset : offset + 1]:
                before.extend(left[offset : offset + 1])
                after.extend(right[offset : offset + 1])
                offset += 1

            length = max(len(before), len(after))
            changes.append(
                Change(
                    change_id=f"binary-{change_index}",
                    change_type="binary",
                    severity="normal",
                    source_location=ChangeLocation(str(left_path), byte_offset=start, byte_length=length),
                    target_location=ChangeLocation(str(right_path), byte_offset=start, byte_length=length),
                    before=bytes(before).hex(),
                    after=bytes(after).hex(),
                    format="hex",
                    confidence=1.0,
                    notes="byte range differs",
                )
            )
            change_index += 1

        if len(changes) >= max_reported_changes and offset < max_len:
            changes.append(
                Change(
                    change_id=f"binary-{len(changes) + 1}",
                    change_type="modified",
                    severity="warning",
                    source_location=ChangeLocation(str(left_path)),
                    target_location=ChangeLocation(str(right_path)),
                    before="binary diff truncated",
                    after=f"only first {max_reported_changes} byte-diff regions are shown",
                    format="hex",
                    confidence=1.0,
                    notes="Exceeded binary diff truncation limit",
                )
            )
        metadata = {
            "left_size": str(len(left)),
            "right_size": str(len(right)),
            "truncated": "true" if len(changes) > max_reported_changes else "false",
        }
        return ComparisonResult(
            left_path=str(left_path),
            right_path=str(right_path),
            file_kind="binary",
            changes=changes,
            metadata=metadata,
        )

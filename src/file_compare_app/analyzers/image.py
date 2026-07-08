from pathlib import Path

from file_compare_app.analyzers.base import Analyzer, AnalyzerDependencyError
from file_compare_app.core.models import Change, ChangeLocation, ComparisonResult


class ImageAnalyzer(Analyzer):
    def compare(self, left_path: Path, right_path: Path) -> ComparisonResult:
        try:
            from PIL import Image, ImageChops
        except ModuleNotFoundError as exc:
            raise AnalyzerDependencyError("Для сравнения изображений установите Pillow.") from exc

        changes: list[Change] = []
        with Image.open(left_path) as left_image, Image.open(right_path) as right_image:
            left = left_image.convert("RGB")
            right = right_image.convert("RGB")

        if left.size != right.size:
            width = max(left.width, right.width)
            height = max(left.height, right.height)
            changes.append(
                Change(
                    change_id="image-size-1",
                    change_type="modified",
                    severity="warning",
                    source_location=ChangeLocation(str(left_path), x=0, y=0, width=width, height=height),
                    target_location=ChangeLocation(str(right_path), x=0, y=0, width=width, height=height),
                    before=f"{left.width}x{left.height}",
                    after=f"{right.width}x{right.height}",
                    format="image",
                    confidence=1.0,
                    notes="Image dimensions differ",
                )
            )
        else:
            diff = ImageChops.difference(left, right)
            bbox = diff.getbbox()
            if bbox is not None:
                x1, y1, x2, y2 = bbox
                changes.append(
                    Change(
                        change_id="image-1",
                        change_type="modified",
                        severity="normal",
                        source_location=ChangeLocation(str(left_path), x=x1, y=y1, width=x2 - x1, height=y2 - y1),
                        target_location=ChangeLocation(str(right_path), x=x1, y=y1, width=x2 - x1, height=y2 - y1),
                        before="image region differs",
                        after="image region differs",
                        format="image",
                        confidence=1.0,
                        notes="pixel difference",
                    )
                )
        ocr_changes = _ocr_text_change(left_path, right_path)
        changes.extend(ocr_changes)
        return ComparisonResult(str(left_path), str(right_path), "image", changes)


def _ocr_text_change(left_path: Path, right_path: Path) -> list[Change]:
    try:
        import pytesseract
        from PIL import Image
    except ModuleNotFoundError:
        return []

    try:
        with Image.open(left_path) as left_image, Image.open(right_path) as right_image:
            left_text = pytesseract.image_to_string(left_image, lang="rus+eng").strip()
            right_text = pytesseract.image_to_string(right_image, lang="rus+eng").strip()
    except Exception:
        return []
    if left_text == right_text:
        return []
    return [
        Change(
            change_id="image-ocr-1",
            change_type="modified",
            severity="warning",
            source_location=ChangeLocation(str(left_path)),
            target_location=ChangeLocation(str(right_path)),
            before=left_text,
            after=right_text,
            format="ocr",
            confidence=0.8,
            notes="OCR text differs",
        )
    ]

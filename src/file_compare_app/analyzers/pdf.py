from pathlib import Path

from file_compare_app.analyzers.base import Analyzer, AnalyzerDependencyError
from file_compare_app.core.models import Change, ChangeLocation, ComparisonResult
from file_compare_app.core.text_diff import line_changes


class PdfAnalyzer(Analyzer):
    def compare(self, left_path: Path, right_path: Path) -> ComparisonResult:
        left_lines = _extract_pdf_lines(left_path)
        right_lines = _extract_pdf_lines(right_path)
        changes: list[Change] = []
        for index, (kind, left_index, right_index, before, after) in enumerate(line_changes(left_lines, right_lines), start=1):
            changes.append(
                Change(
                    change_id=f"pdf-{index}",
                    change_type=kind,  # type: ignore[arg-type]
                    severity="normal",
                    source_location=ChangeLocation(str(left_path), line=left_index + 1) if left_index is not None else None,
                    target_location=ChangeLocation(str(right_path), line=right_index + 1) if right_index is not None else None,
                    before=before,
                    after=after,
                    format="pdf",
                    confidence=0.9,
                    notes="text layer or OCR",
                )
            )
        return ComparisonResult(str(left_path), str(right_path), "pdf", changes)


def _extract_pdf_lines(path: Path) -> list[str]:
    try:
        import fitz
    except ModuleNotFoundError as exc:
        raise AnalyzerDependencyError("Для сравнения PDF установите PyMuPDF.") from exc

    lines: list[str] = []
    with fitz.open(path) as document:
        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            if not text:
                try:
                    text = _ocr_page(page)
                except AnalyzerDependencyError:
                    continue
                except Exception:
                    continue
            for raw_line in text.splitlines():
                line = raw_line.strip()
                if line:
                    lines.append(f"page {page_number}: {line}")
    return lines


def _ocr_page(page: object) -> str:
    try:
        import fitz
        import pytesseract
        from PIL import Image
    except ModuleNotFoundError as exc:
        raise AnalyzerDependencyError("Для OCR установите pytesseract, Pillow и Tesseract OCR rus+eng.") from exc

    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return pytesseract.image_to_string(image, lang="rus+eng")

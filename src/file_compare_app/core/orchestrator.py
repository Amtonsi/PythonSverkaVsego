from pathlib import Path

from file_compare_app.analyzers.base import Analyzer
from file_compare_app.analyzers.binary import BinaryAnalyzer
from file_compare_app.analyzers.docx import DocxAnalyzer
from file_compare_app.analyzers.image import ImageAnalyzer
from file_compare_app.analyzers.klp import KasperskyKlpAnalyzer
from file_compare_app.analyzers.pdf import PdfAnalyzer
from file_compare_app.analyzers.text_config import TextConfigAnalyzer
from file_compare_app.analyzers.xlsx import XlsxAnalyzer
from file_compare_app.core.models import ComparisonResult
from file_compare_app.core.type_detection import detect_file_kind


def build_analyzer(file_kind: str) -> Analyzer:
    if file_kind in {"text", "config"}:
        return TextConfigAnalyzer()
    if file_kind == "docx":
        return DocxAnalyzer()
    if file_kind == "pdf":
        return PdfAnalyzer()
    if file_kind == "xlsx":
        return XlsxAnalyzer()
    if file_kind == "image":
        return ImageAnalyzer()
    if file_kind == "klp":
        return KasperskyKlpAnalyzer()
    return BinaryAnalyzer()


def compare_files(left_path: Path, right_path: Path) -> ComparisonResult:
    left_kind = detect_file_kind(left_path)
    right_kind = detect_file_kind(right_path)
    file_kind = left_kind if left_kind == right_kind else "binary"
    analyzer = build_analyzer(file_kind)
    return analyzer.compare(left_path, right_path)

from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec
from shutil import which


@dataclass(frozen=True)
class DependencyStatus:
    key: str
    label: str
    required_for: str
    available: bool
    detail: str


def collect_dependency_statuses() -> list[DependencyStatus]:
    return [
        _python_module("ui", "PySide6", "Интерфейс приложения", "PySide6"),
        _python_module("docx", "DOCX", "Word-документы", "docx"),
        _python_module("pdf", "PDF", "PDF с текстовым слоем", "fitz"),
        _python_module("ocr_python", "OCR Python", "OCR-обвязка для PDF и изображений", "pytesseract"),
        _external_program("ocr_engine", "OCR Tesseract", "Распознавание сканов", "tesseract"),
        _python_module("excel", "Excel", "XLSX-книги и ячейки", "openpyxl"),
        _python_module("image", "Images", "PNG/JPG/WebP и визуальное сравнение", "PIL"),
        _python_module("yaml", "YAML", "Config-файлы .yaml/.yml", "yaml"),
    ]


def format_dependency_report(statuses: list[DependencyStatus]) -> str:
    lines = ["Диагностика локальных возможностей", ""]
    for status in statuses:
        state = "доступно" if status.available else "не найдено"
        lines.append(f"{status.label}: {state}")
        lines.append(f"  Для: {status.required_for}")
        lines.append(f"  Детали: {status.detail}")
    return "\n".join(lines)


def _python_module(key: str, label: str, required_for: str, module_name: str) -> DependencyStatus:
    available = find_spec(module_name) is not None
    detail = f"Python-модуль `{module_name}` установлен" if available else f"Python-модуль `{module_name}` не найден"
    return DependencyStatus(key, label, required_for, available, detail)


def _external_program(key: str, label: str, required_for: str, executable: str) -> DependencyStatus:
    path = which(executable)
    available = path is not None
    detail = f"Найден: {path}" if path else f"`{executable}` не найден в PATH"
    return DependencyStatus(key, label, required_for, available, detail)

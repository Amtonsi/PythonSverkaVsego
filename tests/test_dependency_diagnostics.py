from file_compare_app.diagnostics.dependencies import collect_dependency_statuses, format_dependency_report


def test_dependency_statuses_cover_supported_features() -> None:
    statuses = collect_dependency_statuses()
    keys = {status.key for status in statuses}

    assert {
        "ui",
        "docx",
        "pdf",
        "ocr_python",
        "ocr_engine",
        "excel",
        "image",
        "yaml",
    }.issubset(keys)
    assert all(isinstance(status.available, bool) for status in statuses)


def test_dependency_report_is_human_readable() -> None:
    report = format_dependency_report(collect_dependency_statuses())

    assert "DOCX" in report
    assert "PDF" in report
    assert "OCR" in report
    assert "Excel" in report

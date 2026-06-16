from pathlib import Path

from file_compare_app.security.strict_mode import StrictModeWorkspace, safe_log_message


def test_strict_workspace_cleans_temp_files(tmp_path: Path) -> None:
    with StrictModeWorkspace(root=tmp_path) as workspace:
        temp_file = workspace.path / "ocr.txt"
        temp_file.write_text("secret document text", encoding="utf-8")
        assert temp_file.exists()
    assert not temp_file.exists()
    assert not workspace.path.exists()


def test_safe_log_message_does_not_include_document_text() -> None:
    message = safe_log_message("pdf", "failed to parse contract text")
    assert message == "analyzer=pdf status=failed"

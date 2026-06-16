from pathlib import Path

from file_compare_app.core.type_detection import detect_file_kind


def test_detects_known_extensions(tmp_path: Path) -> None:
    cases = {
        "a.txt": "text",
        "a.json": "config",
        "a.yaml": "config",
        "a.yml": "config",
        "a.toml": "config",
        "a.ini": "config",
        "a.env": "config",
        "a.xml": "config",
        "a.docx": "docx",
        "a.pdf": "pdf",
        "a.xlsx": "xlsx",
        "a.png": "image",
        "policy.klp": "klp",
        "Dockerfile": "config",
        ".gitignore": "config",
    }
    for name, expected in cases.items():
        path = tmp_path / name
        path.write_text("sample", encoding="utf-8")
        assert detect_file_kind(path) == expected


def test_unknown_extension_falls_back_to_binary(tmp_path: Path) -> None:
    path = tmp_path / "archive.binpack"
    path.write_bytes(b"\x00\x01\x02")
    assert detect_file_kind(path) == "binary"

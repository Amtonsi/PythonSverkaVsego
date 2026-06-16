from pathlib import Path
import tomllib


def test_project_metadata_is_ready_for_gui_packaging() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]
    dev_dependencies = pyproject["project"]["optional-dependencies"]["dev"]

    assert any(item.startswith("PySide6") for item in dependencies)
    assert any(item.startswith("pyinstaller") for item in dev_dependencies)
    assert pyproject["project"]["scripts"]["python-sverka-vsego"] == "file_compare_app.__main__:main"


def test_pyinstaller_spec_includes_src_package_path() -> None:
    spec = Path("packaging/file-compare-app.spec").read_text(encoding="utf-8")

    assert 'SRC = ROOT / "src"' in spec
    assert "pathex=[str(ROOT), str(SRC)]" in spec


def test_pyinstaller_spec_uses_sf_executable_icon() -> None:
    spec = Path("packaging/file-compare-app.spec").read_text(encoding="utf-8")

    assert 'ICON = ROOT / "packaging" / "sf.ico"' in spec
    assert "icon=str(ICON)" in spec
    assert Path("packaging/sf.ico").is_file()

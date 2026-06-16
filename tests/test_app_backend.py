from file_compare_app.app import select_ui_backend


def test_select_ui_backend_returns_available_backend() -> None:
    assert select_ui_backend() in {"pyside6", "tkinter"}

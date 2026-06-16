from __future__ import annotations

import importlib.util
import sys


def select_ui_backend() -> str:
    if importlib.util.find_spec("PySide6") is not None:
        return "pyside6"
    return "tkinter"


def run_app() -> int:
    if select_ui_backend() == "pyside6":
        from PySide6.QtWidgets import QApplication

        from file_compare_app.ui.branding import app_icon
        from file_compare_app.ui.main_window import MainWindow

        app = QApplication(sys.argv)
        app.setWindowIcon(app_icon())
        window = MainWindow()
        window.show()
        return app.exec()

    from file_compare_app.ui.tk_main_window import run_tk_app

    return run_tk_app()

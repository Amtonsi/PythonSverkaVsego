from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime
from html import escape
from pathlib import Path

from PySide6.QtCore import QPoint, QThread, Qt
from PySide6.QtGui import QBrush, QColor, QDragEnterEvent, QDropEvent, QFont, QTextOption
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QCheckBox,
    QComboBox,
    QFrame,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QMenu,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from file_compare_app.core.models import Change, ComparisonResult
from file_compare_app.core.orchestrator import compare_files
from file_compare_app.diagnostics.dependencies import collect_dependency_statuses, format_dependency_report
from file_compare_app.registry.monitor import RegistryMonitor
from file_compare_app.registry.repository import RegistryRepository
from file_compare_app.ui.branding import app_icon
from file_compare_app.ui.compare_worker import CompareWorker
from file_compare_app.ui.diff_view import change_type_label, compact_location, render_result_html
from file_compare_app.reports.html_report import render_html_report


OBJECT_TEMPLATES = [
    ("", "Без шаблона"),
    ("arm", "АРМ"),
    ("server", "Сервер"),
    ("kaspersky", "Kaspersky"),
    ("cisco_asa", "Cisco/ASA"),
    ("controller", "Контроллер"),
]

REVIEW_STATUSES = [
    ("new", "Новое"),
    ("checked", "Проверено"),
    ("approved", "Согласовано"),
    ("rejected", "Отклонено"),
]


class DropFileButton(QPushButton):
    def __init__(
        self,
        object_name: str,
        icon: str,
        name: str,
        note: str,
        on_file: Callable[[Path], None],
    ) -> None:
        super().__init__()
        self._on_file = on_file
        self.setObjectName(object_name)
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(250)
        self.setMaximumWidth(340)
        self.setFixedHeight(42)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(9)

        icon_label = QLabel(icon)
        icon_label.setObjectName("fileIconNew" if icon == "NEW" else "fileIcon")
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setFixedSize(28, 28)

        meta = QFrame()
        meta_layout = QVBoxLayout(meta)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(2)
        self.name_label = QLabel(name)
        self.name_label.setObjectName("fileName")
        self.name_label.setWordWrap(False)
        self.note_label = QLabel(note)
        self.note_label.setObjectName("fileNote")
        meta_layout.addWidget(self.name_label)
        meta_layout.addWidget(self.note_label)

        layout.addWidget(icon_label)
        layout.addWidget(meta, 1)

    def handle_file_path(self, path: Path | str) -> None:
        file_path = Path(path)
        if file_path.is_file():
            self._on_file(file_path)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # type: ignore[override]
        if self._first_local_path(event) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # type: ignore[override]
        path = self._first_local_path(event)
        if path is None:
            event.ignore()
            return
        self.handle_file_path(path)
        event.acceptProposedAction()

    @staticmethod
    def _first_local_path(event: QDragEnterEvent | QDropEvent) -> Path | None:
        mime_data = event.mimeData()
        if not mime_data.hasUrls():
            return None
        for url in mime_data.urls():
            if url.isLocalFile():
                return Path(url.toLocalFile())
        return None


class TitleBar(QFrame):
    def __init__(self, window: QMainWindow) -> None:
        super().__init__()
        self.window = window
        self.drag_position: QPoint | None = None
        self.setObjectName("titleBar")
        self.setFixedHeight(48)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 10, 0)
        layout.setSpacing(10)

        brand = QFrame()
        brand.setObjectName("brand")
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(10)

        self.mark = QLabel("СФ")
        self.mark.setObjectName("brandMark")
        self.mark.setAlignment(Qt.AlignCenter)

        self.title = QLabel("Сравнение файлов")
        self.title.setObjectName("brandTitle")

        self.tag = QLabel("2026")
        self.tag.setObjectName("brandTag")
        self.tag.setAlignment(Qt.AlignCenter)

        brand_layout.addWidget(self.mark)
        brand_layout.addWidget(self.title)
        brand_layout.addWidget(self.tag)

        layout.addWidget(brand)
        layout.addStretch(1)

        self.min_button = self._window_button("-")
        self.max_button = self._window_button("□")
        self.close_button = self._window_button("×")
        self.close_button.setObjectName("windowCloseButton")

        self.min_button.clicked.connect(window.showMinimized)
        self.max_button.clicked.connect(self._toggle_max_restore)
        self.close_button.clicked.connect(window.close)

        layout.addWidget(self.min_button)
        layout.addWidget(self.max_button)
        layout.addWidget(self.close_button)

    def _window_button(self, text: str) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setObjectName("windowButton")
        button.setFixedSize(34, 28)
        return button

    def _toggle_max_restore(self) -> None:
        if self.window.isMaximized():
            self.window.showNormal()
        else:
            self.window.showMaximized()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self.drag_position is not None and event.buttons() & Qt.LeftButton and not self.window.isMaximized():
            self.window.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self.drag_position = None
        event.accept()


class MainWindow(QMainWindow):
    def __init__(self, registry_repository: RegistryRepository | None = None) -> None:
        super().__init__()
        self.left_path: Path | None = None
        self.right_path: Path | None = None
        self.result: ComparisonResult | None = None
        self.compare_view_mode = "text"
        self.change_filter = "all"
        self.visible_changes: list[Change] = []
        self.preview_left_html = ""
        self.preview_right_html = ""
        self.sync_scroll_enabled = True
        self._syncing_scrollbars = False
        self.compare_thread: QThread | None = None
        self.compare_worker: CompareWorker | None = None
        self.registry_repository = registry_repository or RegistryRepository.create()
        self.registry_monitor = RegistryMonitor(self.registry_repository)
        self.selected_registry_node_id: int | None = None
        self.registry_search_query = ""
        self.registry_status_filter_key = "all"
        self.current_mode = "compare"
        self.setWindowTitle("Сравнение файлов")
        self.setWindowIcon(app_icon())
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.resize(1320, 820)
        self.setMinimumSize(940, 620)
        self._build_ui()
        self._apply_style()
        self._apply_responsive_toolbar(self.width())
        self.refresh_registry_tree()
        self._render_empty_preview()

    def _build_ui(self) -> None:
        shell = QWidget()
        shell.setObjectName("appShell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        shell_layout.addWidget(TitleBar(self))
        shell_layout.addWidget(self._build_toolbar())
        self.mode_stack = QStackedWidget()
        self.mode_stack.setObjectName("modeStack")
        self.mode_stack.addWidget(self._build_workspace())
        self.mode_stack.addWidget(self._build_registry_workspace())
        shell_layout.addWidget(self.mode_stack, 1)
        shell_layout.addWidget(self._build_statusbar())

        self.setCentralWidget(shell)

        self.left_file_button.clicked.connect(self._choose_left)
        self.right_file_button.clicked.connect(self._choose_right)
        self.compare_button.clicked.connect(self._compare)
        self.cancel_button.clicked.connect(self._cancel_compare)
        self.export_button.clicked.connect(self._export_report)
        self.settings_button.clicked.connect(self._show_diagnostics)
        self.mode_compare_button.clicked.connect(lambda: self._set_mode("compare"))
        self.mode_registry_button.clicked.connect(lambda: self._set_mode("registry"))
        self.registry_search_box.textChanged.connect(self.set_registry_search_query)
        self.registry_status_filter.currentIndexChanged.connect(self._on_registry_status_filter_changed)
        self.registry_tree.currentItemChanged.connect(self._on_registry_tree_selection)
        self.add_root_button.clicked.connect(self._create_root_node_dialog)
        self.add_root_toolbar_button.clicked.connect(self._create_root_node_dialog)
        self.add_child_button.clicked.connect(self._create_child_node_dialog)
        self.add_file_button.clicked.connect(self._add_registry_file_dialog)
        self.compare_registry_button.clicked.connect(self.compare_selected_registry_file)
        self.check_registry_button.clicked.connect(self.check_selected_registry_node)
        self.backup_registry_button.clicked.connect(self._backup_registry_database_dialog)
        self.export_registry_excel_button.clicked.connect(self._export_registry_excel_dialog)
        self.delete_node_button.clicked.connect(self._confirm_delete_selected_registry_node)
        self.registry_files_table.currentItemChanged.connect(
            lambda current, previous: self._on_registry_file_selection_changed()
        )
        self.registry_files_table.itemDoubleClicked.connect(lambda item: self.compare_selected_registry_file())
        self.registry_files_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.registry_files_table.customContextMenuRequested.connect(self._show_registry_file_context_menu)
        self.prev_button.clicked.connect(lambda: self._move_selection(-1))
        self.next_button.clicked.connect(lambda: self._move_selection(1))
        self.sync_scroll_toggle.toggled.connect(self._set_sync_scroll_enabled)
        self.changes_list.currentRowChanged.connect(self._show_change)
        self._connect_sync_scrollbars()
        self._set_mode("compare")
        self._refresh_registry_compare_action()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if all(hasattr(self, name) for name in ("privacy_pill", "status_temp", "tech_label", "registry_search_box")):
            self._apply_responsive_toolbar(event.size().width())

    def _apply_responsive_toolbar(self, width: int) -> None:
        compact = width < 1320
        very_compact = width < 960
        mode = getattr(self, "current_mode", "compare")

        file_min = 180 if compact else 250
        file_max = 240 if compact else 340
        for button in (self.left_file_button, self.right_file_button):
            button.setMinimumWidth(file_min)
            button.setMaximumWidth(file_max)

        self.progress_bar.setFixedWidth(90 if compact else 120)
        self.privacy_pill.setVisible(not compact)
        self.status_temp.setVisible(not compact)
        self.tech_label.setVisible(not very_compact)
        self.registry_search_box.setVisible(mode == "registry" and not very_compact)
        self.registry_search_box.setMinimumWidth(210 if compact else 280)
        self.registry_search_box.setMaximumWidth(260 if compact else 16777215)
        self.registry_status_filter.setVisible(mode == "registry" and not very_compact)
        self.registry_status_filter.setMinimumWidth(120 if compact else 150)
        self.registry_status_filter.setMaximumWidth(150 if compact else 180)

        self.mode_compare_button.setText("↔ Сравнение" if not very_compact else "↔")
        self.mode_compare_button.setToolTip("Сравнение файлов")
        self.mode_registry_button.setText("▦ Реестр объектов" if not very_compact else "▦ Реестр")
        self.mode_registry_button.setToolTip("Реестр объектов")

        self.add_root_toolbar_button.setText("+ Объект")
        self.add_child_button.setText("+ Подобъект" if not very_compact else "+ Под")
        self.add_file_button.setText("+ Файл")
        self.compare_registry_button.setText("Сравнить")
        self.check_registry_button.setText("Проверить" if compact else "⟳ Проверить")
        self.backup_registry_button.setText("Бэкап" if compact else "Бэкап БД")
        self.export_registry_excel_button.setText("Excel")
        self.delete_node_button.setText("Удалить")
        self._refresh_file_chip_labels(compact, very_compact)

    def _refresh_file_chip_labels(self, compact: bool, very_compact: bool) -> None:
        if self.left_path is None:
            self.left_file_name.setText("До" if very_compact else "Исходный файл" if compact else "Выберите исходный файл")
        if self.right_path is None:
            self.right_file_name.setText("После" if very_compact else "Новая версия" if compact else "Выберите новую версию")

    def _create_message_box(
        self,
        icon: QMessageBox.Icon,
        title: str,
        message: str,
        buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
        default_button: QMessageBox.StandardButton = QMessageBox.StandardButton.NoButton,
    ) -> QMessageBox:
        box = QMessageBox(self)
        box.setWindowIcon(app_icon())
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(message)
        box.setStandardButtons(buttons)
        if default_button != QMessageBox.StandardButton.NoButton:
            box.setDefaultButton(default_button)
        return box

    def _show_message(self, icon: QMessageBox.Icon, title: str, message: str) -> QMessageBox.StandardButton:
        return QMessageBox.StandardButton(self._create_message_box(icon, title, message).exec())

    def _ask_question(
        self,
        title: str,
        message: str,
        buttons: QMessageBox.StandardButton,
        default_button: QMessageBox.StandardButton,
    ) -> QMessageBox.StandardButton:
        return QMessageBox.StandardButton(
            self._create_message_box(QMessageBox.Icon.Question, title, message, buttons, default_button).exec()
        )

    def _build_toolbar(self) -> QFrame:
        toolbar = QFrame()
        toolbar.setObjectName("toolbar")
        toolbar.setFixedHeight(64)
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(16)

        modes = QFrame()
        modes.setObjectName("modeTabs")
        mode_layout = QHBoxLayout(modes)
        mode_layout.setContentsMargins(4, 4, 4, 4)
        mode_layout.setSpacing(6)
        self.mode_compare_button = QPushButton("⇄ Сравнение")
        self.mode_compare_button.setObjectName("modeCompareButton")
        self.mode_registry_button = QPushButton("▦ Реестр объектов")
        self.mode_registry_button.setObjectName("modeRegistryButton")
        mode_layout.addWidget(self.mode_compare_button)
        mode_layout.addWidget(self.mode_registry_button)
        layout.addWidget(modes)

        self.file_pair_panel = QFrame()
        self.file_pair_panel.setObjectName("filePair")
        file_layout = QHBoxLayout(self.file_pair_panel)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(10)
        self.left_file_button, self.left_file_name, self.left_file_note = self._file_chip("leftFileChip", "OLD", "Выберите исходный файл", "Файл 1")
        self.right_file_button, self.right_file_name, self.right_file_note = self._file_chip("rightFileChip", "NEW", "Выберите новую версию", "Файл 2")
        file_layout.addWidget(self.left_file_button)
        file_layout.addWidget(self.right_file_button)
        layout.addWidget(self.file_pair_panel, 2)

        self.registry_search_box = QLineEdit()
        self.registry_search_box.setObjectName("registrySearchBox")
        self.registry_search_box.setPlaceholderText("Поиск объекта, файла, ответственного...")
        self.registry_search_box.setClearButtonEnabled(True)
        self.registry_search_box.setFixedHeight(36)
        self.registry_search_box.setMinimumWidth(280)
        layout.addWidget(self.registry_search_box, 2)

        self.registry_status_filter = QComboBox()
        self.registry_status_filter.setObjectName("registryStatusFilter")
        self.registry_status_filter.setFixedHeight(36)
        self.registry_status_filter.setMinimumWidth(150)
        for text, value in (
            ("Все статусы", "all"),
            ("OK", "ok"),
            ("Изменен", "changed"),
            ("Нет файла", "missing"),
            ("Ошибка", "error"),
        ):
            self.registry_status_filter.addItem(text, value)
        self.registry_status_filter.setMaxVisibleItems(5)
        status_popup = self.registry_status_filter.view()
        status_popup.setObjectName("registryStatusFilterPopup")
        status_popup.setMinimumWidth(150)
        status_popup.setStyleSheet(
            """
            QAbstractItemView#registryStatusFilterPopup {
                background: #ffffff;
                color: #111827;
                border: 1px solid #d6dde8;
                border-radius: 8px;
                padding: 4px;
                outline: 0;
                selection-background-color: #eff6ff;
                selection-color: #2563eb;
            }
            QAbstractItemView#registryStatusFilterPopup::item {
                min-height: 30px;
                padding: 6px 10px;
                color: #111827;
            }
            QAbstractItemView#registryStatusFilterPopup::item:selected {
                background: #eff6ff;
                color: #2563eb;
            }
            """
        )
        layout.addWidget(self.registry_status_filter)

        actions = QFrame()
        actions.setObjectName("actions")
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        self.compare_button = QPushButton("Сравнить")
        self.compare_button.setObjectName("primaryButton")
        self.export_button = QPushButton("Экспорт отчета")
        self.export_button.setObjectName("secondaryButton")
        self.add_root_toolbar_button = QPushButton("+ Объект")
        self.add_root_toolbar_button.setObjectName("primaryButton")
        self.add_child_button = QPushButton("+ Подобъект")
        self.add_child_button.setObjectName("secondaryButton")
        self.add_file_button = QPushButton("+ Файл")
        self.add_file_button.setObjectName("addRegistryFileButton")
        self.add_file_button.setToolTip("Добавить первый файл или новую версию выбранного файла")
        self.add_before_file_button = self.add_file_button
        self.add_watched_file_button = self.add_file_button
        self.compare_registry_button = QPushButton("Сравнить")
        self.compare_registry_button.setObjectName("compareRegistryFileButton")
        self.compare_registry_button.setToolTip("Сравнить две последние версии выбранного файла из реестра")
        self.check_registry_button = QPushButton("⟳ Проверить")
        self.check_registry_button.setObjectName("secondaryButton")
        self.backup_registry_button = QPushButton("Бэкап БД")
        self.backup_registry_button.setObjectName("backupRegistryButton")
        self.backup_registry_button.setToolTip("Создать резервную копию базы данных рядом с реестром")
        self.export_registry_excel_button = QPushButton("Excel")
        self.export_registry_excel_button.setObjectName("exportRegistryExcelButton")
        self.export_registry_excel_button.setToolTip("Выгрузить реестр объектов, файлов, сверок и истории в Excel")
        self.delete_node_button = QPushButton("Удалить")
        self.delete_node_button.setObjectName("deleteNodeButton")
        self.settings_button = QToolButton()
        self.settings_button.setText("⚙")
        self.settings_button.setObjectName("iconButton")
        self.cancel_button = QToolButton()
        self.cancel_button.setText("×")
        self.cancel_button.setToolTip("Отменить сравнение")
        self.cancel_button.setObjectName("cancelCompareButton")
        self.cancel_button.setEnabled(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("compareProgress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedWidth(120)
        self.progress_bar.setTextVisible(False)
        actions_layout.addWidget(self.compare_button)
        actions_layout.addWidget(self.export_button)
        actions_layout.addWidget(self.add_root_toolbar_button)
        actions_layout.addWidget(self.add_child_button)
        actions_layout.addWidget(self.add_file_button)
        actions_layout.addWidget(self.compare_registry_button)
        actions_layout.addWidget(self.check_registry_button)
        actions_layout.addWidget(self.backup_registry_button)
        actions_layout.addWidget(self.export_registry_excel_button)
        actions_layout.addWidget(self.delete_node_button)
        actions_layout.addWidget(self.cancel_button)
        actions_layout.addWidget(self.progress_bar)
        actions_layout.addWidget(self.settings_button)
        layout.addWidget(actions, 1)
        self.compare_toolbar_widgets = [
            self.file_pair_panel,
            self.compare_button,
            self.export_button,
            self.cancel_button,
            self.progress_bar,
        ]
        self.registry_toolbar_widgets = [
            self.registry_search_box,
            self.registry_status_filter,
            self.add_root_toolbar_button,
            self.add_child_button,
            self.add_file_button,
            self.compare_registry_button,
            self.check_registry_button,
            self.backup_registry_button,
            self.export_registry_excel_button,
            self.delete_node_button,
        ]

        privacy = QFrame()
        privacy.setObjectName("privacy")
        privacy_layout = QHBoxLayout(privacy)
        privacy_layout.setContentsMargins(0, 0, 0, 0)
        self.privacy_pill = QLabel("Строгий локальный режим")
        self.privacy_pill.setObjectName("privacyPill")
        privacy_layout.addStretch(1)
        privacy_layout.addWidget(self.privacy_pill)
        layout.addWidget(privacy, 1)

        return toolbar

    def _file_chip(self, object_name: str, icon: str, name: str, note: str) -> tuple[DropFileButton, QLabel, QLabel]:
        callback = self.assign_right_file if icon == "NEW" else self.assign_left_file
        button = DropFileButton(object_name, icon, name, note, callback)
        return button, button.name_label, button.note_label

    def _build_workspace(self) -> QFrame:
        workspace = QFrame()
        workspace.setObjectName("workspace")
        layout = QHBoxLayout(workspace)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)
        layout.addWidget(self._build_compare_area(), 1)
        layout.addWidget(self._build_sidebar())
        return workspace

    def _build_registry_workspace(self) -> QFrame:
        workspace = QFrame()
        workspace.setObjectName("registryWorkspace")
        layout = QHBoxLayout(workspace)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)
        layout.addWidget(self._build_registry_tree_panel())
        layout.addWidget(self._build_registry_detail_panel(), 1)
        return workspace

    def _build_registry_tree_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("registryPanel")
        panel.setFixedWidth(330)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("summaryPanel")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 10, 14, 10)
        title = QLabel("Реестр")
        title.setObjectName("summaryTitle")
        self.add_root_button = QToolButton()
        self.add_root_button.setText("+")
        self.add_root_button.setObjectName("iconButtonSmall")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(self.add_root_button)

        self.registry_tree = QTreeWidget()
        self.registry_tree.setObjectName("registryTree")
        self.registry_tree.setHeaderHidden(True)

        layout.addWidget(header)
        layout.addWidget(self.registry_tree, 1)
        return panel

    def _build_registry_detail_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("registryDetail")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.registry_object_title = QLabel("Выберите объект")
        self.registry_object_title.setObjectName("registryObjectTitle")
        self.registry_object_title.setProperty("role", "registryTitle")
        layout.addWidget(self.registry_object_title)

        tabs = QTabWidget()
        tabs.setObjectName("registryTabs")

        files_page = QWidget()
        files_page.setObjectName("registryFilesPage")
        files_layout = QVBoxLayout(files_page)
        files_layout.setContentsMargins(0, 0, 0, 0)
        files_layout.setSpacing(0)
        self.registry_files_stack = QStackedWidget()
        self.registry_files_stack.setObjectName("registryFilesStack")
        self.registry_files_table = QTableWidget(0, 6)
        self.registry_files_table.setObjectName("registryFilesTable")
        self.registry_files_table.setHorizontalHeaderLabels(["ID", "Файл до", "Файл после", "Версии", "Статус", "Загружено"])
        self.registry_files_table.verticalHeader().setVisible(False)
        self.registry_files_table.setShowGrid(False)
        self.registry_files_table.setAlternatingRowColors(True)
        self.registry_files_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.registry_files_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.registry_files_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.registry_files_table.setWordWrap(False)
        self.registry_files_table.setColumnWidth(0, 54)
        self.registry_files_table.setColumnWidth(1, 260)
        self.registry_files_table.setColumnWidth(2, 260)
        self.registry_files_table.setColumnWidth(3, 110)
        self.registry_files_table.setColumnWidth(4, 110)
        self.registry_files_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.registry_files_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.registry_files_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.registry_files_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.registry_files_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.registry_files_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.registry_files_empty_state = QTextEdit()
        self.registry_files_empty_state.setObjectName("registryFilesEmptyState")
        self.registry_files_empty_state.setReadOnly(True)
        self.registry_files_empty_state.setLineWrapMode(QTextEdit.WidgetWidth)
        self.registry_files_stack.addWidget(self.registry_files_table)
        self.registry_files_stack.addWidget(self.registry_files_empty_state)
        files_layout.addWidget(self.registry_files_stack, 1)
        self.registry_selected_pair_panel = QTextEdit()
        self.registry_selected_pair_panel.setObjectName("registrySelectedPairPanel")
        self.registry_selected_pair_panel.setReadOnly(True)
        self.registry_selected_pair_panel.setLineWrapMode(QTextEdit.WidgetWidth)
        self.registry_selected_pair_panel.setFixedHeight(150)
        files_layout.addWidget(self.registry_selected_pair_panel)
        review_panel = QFrame()
        review_panel.setObjectName("registryReviewPanel")
        review_layout = QHBoxLayout(review_panel)
        review_layout.setContentsMargins(12, 8, 12, 8)
        review_layout.setSpacing(8)
        self.registry_review_status_input = QComboBox()
        self.registry_review_status_input.setObjectName("registryReviewStatusInput")
        for value, label in REVIEW_STATUSES:
            self.registry_review_status_input.addItem(label, value)
        self.registry_review_reviewer_input = QLineEdit()
        self.registry_review_reviewer_input.setObjectName("registryReviewReviewerInput")
        self.registry_review_reviewer_input.setPlaceholderText("Проверил")
        self.registry_review_comment_input = QTextEdit()
        self.registry_review_comment_input.setObjectName("registryReviewCommentInput")
        self.registry_review_comment_input.setPlaceholderText("Комментарий")
        self.registry_review_comment_input.setFixedHeight(44)
        self.save_registry_review_button = QPushButton("Сохранить статус")
        self.save_registry_review_button.setObjectName("saveRegistryReviewButton")
        self.save_registry_review_button.clicked.connect(self.save_selected_registry_review)
        review_layout.addWidget(self.registry_review_status_input)
        review_layout.addWidget(self.registry_review_reviewer_input)
        review_layout.addWidget(self.registry_review_comment_input, 1)
        review_layout.addWidget(self.save_registry_review_button)
        files_layout.addWidget(review_panel)

        object_page = QWidget()
        object_page.setObjectName("registryNodeCardPanel")
        object_layout = QVBoxLayout(object_page)
        object_layout.setContentsMargins(16, 14, 16, 16)
        object_layout.setSpacing(12)

        object_form = QFrame()
        object_form.setObjectName("registryNodeFormCard")
        form_layout = QFormLayout(object_form)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setHorizontalSpacing(14)
        form_layout.setVerticalSpacing(10)

        self.registry_node_name_input = QLineEdit()
        self.registry_node_name_input.setObjectName("registryNodeNameInput")
        self.registry_node_name_input.setPlaceholderText("Название объекта")
        self.registry_node_code_input = QLineEdit()
        self.registry_node_code_input.setObjectName("registryNodeCodeInput")
        self.registry_node_code_input.setPlaceholderText("Код, инвентарный номер или тег")
        self.registry_node_responsible_input = QLineEdit()
        self.registry_node_responsible_input.setObjectName("registryNodeResponsibleInput")
        self.registry_node_responsible_input.setPlaceholderText("Ответственный")
        self.registry_node_description_input = QTextEdit()
        self.registry_node_description_input.setObjectName("registryNodeDescriptionInput")
        self.registry_node_description_input.setPlaceholderText("Краткое описание объекта")
        self.registry_node_description_input.setLineWrapMode(QTextEdit.WidgetWidth)
        self.registry_node_description_input.setFixedHeight(88)
        self.registry_node_template_input = QComboBox()
        self.registry_node_template_input.setObjectName("registryNodeTemplateInput")
        for value, label in OBJECT_TEMPLATES:
            self.registry_node_template_input.addItem(label, value)
        self.registry_monitor_interval_input = QSpinBox()
        self.registry_monitor_interval_input.setObjectName("registryMonitorIntervalInput")
        self.registry_monitor_interval_input.setRange(1, 10080)
        self.registry_monitor_interval_input.setSuffix(" мин")

        form_layout.addRow("Название", self.registry_node_name_input)
        form_layout.addRow("Код", self.registry_node_code_input)
        form_layout.addRow("Ответственный", self.registry_node_responsible_input)
        form_layout.addRow("Шаблон", self.registry_node_template_input)
        form_layout.addRow("Интервал", self.registry_monitor_interval_input)
        form_layout.addRow("Описание", self.registry_node_description_input)
        object_layout.addWidget(object_form)

        self.save_registry_node_button = QPushButton("Сохранить карточку")
        self.save_registry_node_button.setObjectName("saveRegistryNodeButton")
        self.save_registry_node_button.clicked.connect(self.save_selected_registry_node_card)
        object_layout.addWidget(self.save_registry_node_button, 0, Qt.AlignLeft)

        self.registry_node_card_summary = QTextEdit()
        self.registry_node_card_summary.setObjectName("registryNodeCardSummary")
        self.registry_node_card_summary.setReadOnly(True)
        self.registry_node_card_summary.setLineWrapMode(QTextEdit.WidgetWidth)
        object_layout.addWidget(self.registry_node_card_summary, 1)

        self.registry_events_list = QListWidget()
        self.registry_events_list.setObjectName("registryEventsList")
        self.registry_monitoring_panel = QTextEdit()
        self.registry_monitoring_panel.setObjectName("registryMonitoringPanel")
        self.registry_monitoring_panel.setReadOnly(True)
        self.registry_monitoring_panel.setLineWrapMode(QTextEdit.WidgetWidth)
        self.registry_versions_panel = QTextEdit()
        self.registry_versions_panel.setObjectName("registryVersionsPanel")
        self.registry_versions_panel.setReadOnly(True)
        self.registry_versions_panel.setLineWrapMode(QTextEdit.WidgetWidth)
        self.registry_risks_panel = QTextEdit()
        self.registry_risks_panel.setObjectName("registryRisksPanel")
        self.registry_risks_panel.setReadOnly(True)
        self.registry_risks_panel.setLineWrapMode(QTextEdit.WidgetWidth)
        tabs.addTab(files_page, "Файлы")
        tabs.addTab(object_page, "Объект")
        tabs.addTab(self.registry_events_list, "История")
        tabs.addTab(self.registry_monitoring_panel, "Мониторинг")
        tabs.addTab(self.registry_risks_panel, "Риски")
        tabs.addTab(self.registry_versions_panel, "Версии")
        layout.addWidget(tabs, 1)
        return panel

    def _build_compare_area(self) -> QFrame:
        compare_area = QFrame()
        compare_area.setObjectName("compareArea")
        layout = QVBoxLayout(compare_area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_compare_tabs())

        viewer_grid = QFrame()
        viewer_grid.setObjectName("viewerGrid")
        viewer_layout = QHBoxLayout(viewer_grid)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        viewer_layout.setSpacing(0)
        self.left_view = self._build_viewer("Было", "Ожидание файла")
        self.right_view = self._build_viewer("Стало", "Ожидание файла")
        viewer_layout.addWidget(self.left_view["panel"])
        viewer_layout.addWidget(self.right_view["panel"])
        layout.addWidget(viewer_grid, 1)
        return compare_area

    def _build_compare_tabs(self) -> QFrame:
        tabs = QFrame()
        tabs.setObjectName("compareTabs")
        tabs.setFixedHeight(38)
        layout = QHBoxLayout(tabs)
        layout.setContentsMargins(12, 0, 10, 0)
        layout.setSpacing(4)
        self.compare_tab_buttons: dict[str, QPushButton] = {}
        for mode, text, object_name in (
            ("text", "Текст", "compareTabText"),
            ("pages", "Страницы", "compareTabPages"),
            ("ocr", "OCR", "compareTabOcr"),
            ("hex", "Hex", "compareTabHex"),
        ):
            button = QPushButton(text)
            button.setObjectName(object_name)
            button.setProperty("role", "compareTab")
            button.setCursor(Qt.PointingHandCursor)
            button.setFixedHeight(30)
            button.setMinimumWidth(64)
            button.clicked.connect(lambda checked=False, selected_mode=mode: self.set_compare_view_mode(selected_mode))
            self.compare_tab_buttons[mode] = button
            layout.addWidget(button)
        self._refresh_button_group(self.compare_tab_buttons, self.compare_view_mode)
        layout.addStretch(1)
        self.sync_scroll_toggle = QCheckBox("Синхронная прокрутка")
        self.sync_scroll_toggle.setObjectName("syncScrollToggle")
        self.sync_scroll_toggle.setCursor(Qt.PointingHandCursor)
        self.sync_scroll_toggle.setChecked(True)
        layout.addWidget(self.sync_scroll_toggle)
        self.prev_button = QToolButton()
        self.prev_button.setText("‹")
        self.prev_button.setObjectName("iconButtonSmall")
        self.prev_button.setCursor(Qt.PointingHandCursor)
        self.prev_button.setToolTip("Предыдущее изменение")
        self.next_button = QToolButton()
        self.next_button.setText("›")
        self.next_button.setObjectName("iconButtonSmall")
        self.next_button.setCursor(Qt.PointingHandCursor)
        self.next_button.setToolTip("Следующее изменение")
        layout.addWidget(self.prev_button)
        layout.addWidget(self.next_button)
        return tabs

    def _build_viewer(self, title: str, place: str) -> dict[str, QWidget]:
        panel = QFrame()
        panel.setObjectName("viewer")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        head = QFrame()
        head.setObjectName("viewerHead")
        head.setFixedHeight(34)
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(12, 0, 12, 0)
        title_label = QLabel(title)
        title_label.setObjectName("viewerTitle")
        place_label = QLabel(place)
        place_label.setObjectName("viewerPlace")
        head_layout.addWidget(title_label)
        head_layout.addStretch(1)
        head_layout.addWidget(place_label)

        text = QTextEdit()
        text.setObjectName("viewerBody")
        text.setReadOnly(True)
        text.setLineWrapMode(QTextEdit.WidgetWidth)
        text.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        text.setFont(QFont("Consolas", 10))

        panel_layout.addWidget(head)
        panel_layout.addWidget(text, 1)
        return {"panel": panel, "text": text, "place": place_label}

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("rightSidebar")
        sidebar.setFixedWidth(352)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        summary = QFrame()
        summary.setObjectName("summaryPanel")
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(14, 14, 14, 14)
        summary_layout.setSpacing(10)
        self.summary = QLabel("Найдено 0 изменений")
        self.summary.setObjectName("summaryTitle")
        stats = QFrame()
        stats.setObjectName("stats")
        stats_layout = QGridLayout(stats)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setHorizontalSpacing(8)
        self.removed_stat = self._stat_card("0", "удалено", "statRed")
        self.added_stat = self._stat_card("0", "добавлено", "statGreen")
        self.ocr_stat = self._stat_card("0", "OCR", "statAmber")
        stats_layout.addWidget(self.removed_stat, 0, 0)
        stats_layout.addWidget(self.added_stat, 0, 1)
        stats_layout.addWidget(self.ocr_stat, 0, 2)
        summary_layout.addWidget(self.summary)
        summary_layout.addWidget(stats)

        filters = QFrame()
        filters.setObjectName("filters")
        filters_layout = QHBoxLayout(filters)
        filters_layout.setContentsMargins(12, 10, 12, 10)
        filters_layout.setSpacing(7)
        self.change_filter_buttons: dict[str, QPushButton] = {}
        for filter_key, text, object_name in (
            ("all", "Все", "changeFilterAll"),
            ("text", "Текст", "changeFilterText"),
            ("ocr", "OCR", "changeFilterOcr"),
            ("risk", "Риски", "changeFilterRisk"),
        ):
            button = QPushButton(text)
            button.setObjectName(object_name)
            button.setProperty("role", "changeFilter")
            button.setCursor(Qt.PointingHandCursor)
            button.setFixedHeight(28)
            button.clicked.connect(
                lambda checked=False, selected_filter=filter_key: self.set_change_filter(selected_filter)
            )
            self.change_filter_buttons[filter_key] = button
            filters_layout.addWidget(button)
        self._refresh_button_group(self.change_filter_buttons, self.change_filter)
        filters_layout.addStretch(1)

        self.changes_list = QListWidget()
        self.changes_list.setObjectName("changesList")

        layout.addWidget(summary)
        layout.addWidget(filters)
        layout.addWidget(self.changes_list, 1)
        return sidebar

    def _stat_card(self, value: str, label: str, object_name: str) -> QFrame:
        card = QFrame()
        card.setObjectName("stat")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(4)
        number = QLabel(value)
        number.setObjectName(object_name)
        caption = QLabel(label)
        caption.setObjectName("statCaption")
        card_layout.addWidget(number)
        card_layout.addWidget(caption)
        card.number_label = number  # type: ignore[attr-defined]
        return card

    def _build_statusbar(self) -> QFrame:
        statusbar = QFrame()
        statusbar.setObjectName("statusbarCustom")
        statusbar.setFixedHeight(42)
        layout = QHBoxLayout(statusbar)
        layout.setContentsMargins(18, 0, 18, 0)
        layout.setSpacing(16)
        self.status_ready = QLabel("Готово")
        self.status_ready.setObjectName("statusOk")
        self.status_text = QLabel("Сравнение выполнено локально")
        self.status_text.setObjectName("statusText")
        self.status_temp = QLabel("Временные данные будут удалены при закрытии")
        self.status_temp.setObjectName("statusText")
        self.tech_label = QLabel("UTF-8 | OCR rus+eng | PySide6")
        self.tech_label.setObjectName("techLabel")
        self.credit_label = QLabel("Разработал: Абдрахманов Амаль Даулетович")
        self.credit_label.setObjectName("developerCredit")
        self.credit_label.setAlignment(Qt.AlignRight)

        layout.addWidget(self.status_ready)
        layout.addWidget(self.status_text)
        layout.addWidget(self.status_temp)
        layout.addStretch(1)
        right = QFrame()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(2)
        right_layout.addWidget(self.tech_label)
        right_layout.addWidget(self.credit_label)
        layout.addWidget(right)
        return statusbar

    def _set_mode(self, mode: str) -> None:
        self.current_mode = mode
        self.mode_stack.setCurrentIndex(1 if mode == "registry" else 0)
        self.mode_compare_button.setProperty("active", mode == "compare")
        self.mode_registry_button.setProperty("active", mode == "registry")
        for widget in self.compare_toolbar_widgets:
            widget.setVisible(mode == "compare")
        for widget in self.registry_toolbar_widgets:
            widget.setVisible(mode == "registry")
        self.mode_compare_button.style().unpolish(self.mode_compare_button)
        self.mode_compare_button.style().polish(self.mode_compare_button)
        self.mode_registry_button.style().unpolish(self.mode_registry_button)
        self.mode_registry_button.style().polish(self.mode_registry_button)
        if hasattr(self, "privacy_pill"):
            self._apply_responsive_toolbar(self.width())

    def _on_registry_tree_selection(self, current: QTreeWidgetItem | None, previous: QTreeWidgetItem | None) -> None:
        if current is None:
            return
        node_id = current.data(0, Qt.UserRole)
        if isinstance(node_id, int) and hasattr(self, "select_registry_node"):
            self.select_registry_node(node_id)

    def _create_root_node_dialog(self) -> None:
        name, accepted = QInputDialog.getText(self, "Новый объект", "Название объекта:")
        if accepted and name.strip() and hasattr(self, "create_registry_node"):
            self.create_registry_node(name.strip())

    def _create_child_node_dialog(self) -> None:
        if self.selected_registry_node_id is None:
            self._show_message(QMessageBox.Icon.Information, "Не выбран объект", "Выберите объект или подобъект в реестре.")
            return
        name, accepted = QInputDialog.getText(self, "Новый подобъект", "Название подобъекта:")
        if accepted and name.strip():
            child = self.create_registry_node(name.strip(), parent_id=self.selected_registry_node_id)
            self.select_registry_node(child.id)

    def _add_watched_file_dialog(self) -> None:
        self._add_registry_file_dialog()

    def _add_registry_file_dialog(self) -> None:
        if self.selected_registry_node_id is None:
            self._show_message(QMessageBox.Icon.Information, "Не выбран объект", "Выберите объект или подобъект в реестре.")
            return
        title = "Выберите файл"
        if self._selected_watched_file_id() is not None:
            title = "Выберите новую версию файла"
        path, _ = QFileDialog.getOpenFileName(self, title)
        if path:
            self.add_registry_file_to_selected_context(Path(path))

    def _add_before_file_dialog(self) -> None:
        self._add_registry_file_dialog()

    def _add_after_version_dialog(self) -> None:
        self._add_registry_file_dialog()

    def _confirm_delete_selected_registry_node(self) -> None:
        if self.selected_registry_node_id is None:
            self._show_message(QMessageBox.Icon.Information, "Не выбран объект", "Выберите объект или подобъект в реестре.")
            return
        node = self.registry_repository.get_node(self.selected_registry_node_id)
        descendants = self.registry_repository.list_descendant_ids(node.id)
        answer = self._ask_question(
            "Удалить объект",
            f"Удалить «{node.name}» и все подобъекты ниже?\nБудет удалено записей: {len(descendants)}.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.delete_selected_registry_node()

    def create_registry_node(self, name: str, parent_id: int | None = None):
        node_type = "Подобъект" if parent_id is not None else "Объект"
        node = self.registry_repository.create_node(name=name, parent_id=parent_id, node_type=node_type)
        self.refresh_registry_tree()
        return node

    def refresh_registry_tree(self) -> None:
        self.registry_tree.clear()
        for node in self.registry_repository.list_children(None):
            if not self._node_matches_registry_search(node):
                continue
            item = self._registry_tree_item(node)
            self.registry_tree.addTopLevelItem(item)
            self._append_registry_children(item, node.id)
        self.registry_tree.expandAll()

    def _append_registry_children(self, parent_item: QTreeWidgetItem, parent_id: int) -> None:
        for child in self.registry_repository.list_children(parent_id):
            if not self._node_matches_registry_search(child):
                continue
            child_item = self._registry_tree_item(child)
            parent_item.addChild(child_item)
            self._append_registry_children(child_item, child.id)

    def _registry_tree_item(self, node) -> QTreeWidgetItem:
        item = QTreeWidgetItem([node.name])
        item.setData(0, Qt.UserRole, node.id)
        return item

    def set_registry_search_query(self, text: str) -> None:
        self.registry_search_query = text.strip().casefold()
        self.refresh_registry_tree()
        if self.selected_registry_node_id is not None:
            self._render_registry_files(self.selected_registry_node_id)
            self._render_registry_versions_for_current_file()

    def set_registry_status_filter(self, status: str) -> None:
        allowed = {"all", "ok", "changed", "missing", "error"}
        self.registry_status_filter_key = status if status in allowed else "all"
        if hasattr(self, "registry_status_filter"):
            index = self.registry_status_filter_combo_index(self.registry_status_filter_key)
            if index >= 0 and self.registry_status_filter.currentIndex() != index:
                self.registry_status_filter.blockSignals(True)
                self.registry_status_filter.setCurrentIndex(index)
                self.registry_status_filter.blockSignals(False)
        if self.selected_registry_node_id is not None:
            self._render_registry_files(self.selected_registry_node_id)
            self._render_registry_versions_for_current_file()

    def registry_status_filter_combo_index(self, status: str) -> int:
        for index in range(self.registry_status_filter.count()):
            if self.registry_status_filter.itemData(index) == status:
                return index
        return -1

    def _on_registry_status_filter_changed(self) -> None:
        status = self.registry_status_filter.currentData()
        self.set_registry_status_filter(status if isinstance(status, str) else "all")

    def _node_matches_registry_search(self, node) -> bool:
        query = self.registry_search_query
        if not query:
            return True
        node_text = " ".join(
            [
                node.name,
                node.node_type,
                node.code,
                node.responsible,
                node.description,
            ]
        ).casefold()
        if query in node_text:
            return True
        for watched in self.registry_repository.list_watched_files(node.id):
            if query in f"{watched.label} {watched.file_path} {watched.file_kind} {watched.status}".casefold():
                return True
        return any(self._node_matches_registry_search(child) for child in self.registry_repository.list_children(node.id))

    def select_registry_node(self, node_id: int) -> None:
        self.selected_registry_node_id = node_id
        node = self.registry_repository.get_node(node_id)
        self.registry_object_title.setText(node.name)
        self._render_registry_node_card(node_id)
        self._render_registry_files(node_id)
        self._render_registry_events(node_id)
        self._render_registry_monitoring(node_id)
        self._render_registry_risks(node_id)
        self._render_registry_versions_for_current_file()

    def save_selected_registry_node_card(self) -> bool:
        if self.selected_registry_node_id is None:
            return False
        name = self.registry_node_name_input.text().strip()
        if not name:
            self._show_message(QMessageBox.Icon.Warning, "Название не заполнено", "Укажите название объекта.")
            return False
        updated = self.registry_repository.update_node(
            self.selected_registry_node_id,
            name=name,
            code=self.registry_node_code_input.text().strip(),
            responsible=self.registry_node_responsible_input.text().strip(),
            description=self.registry_node_description_input.toPlainText().strip(),
            template_key=str(self.registry_node_template_input.currentData() or ""),
            monitor_interval_minutes=self.registry_monitor_interval_input.value(),
        )
        self.registry_object_title.setText(updated.name)
        self.refresh_registry_tree()
        self._render_registry_node_card(updated.id)
        self._render_registry_files(updated.id)
        self._render_registry_events(updated.id)
        self._render_registry_monitoring(updated.id)
        self._render_registry_risks(updated.id)
        self._render_registry_versions_for_current_file()
        self.status_text.setText(f"Карточка объекта сохранена: {updated.name}")
        return True

    def _render_registry_node_card(self, node_id: int | None) -> None:
        if node_id is None:
            self.registry_node_name_input.clear()
            self.registry_node_code_input.clear()
            self.registry_node_responsible_input.clear()
            self.registry_node_description_input.clear()
            self.registry_node_template_input.setCurrentIndex(0)
            self.registry_monitor_interval_input.setValue(30)
            self.registry_node_card_summary.setHtml(
                _html_page("<div class='empty-state'><h2>Выберите объект</h2><p>Карточка появится после выбора объекта в реестре.</p></div>")
            )
            return

        node = self.registry_repository.get_node(node_id)
        self.registry_node_name_input.setText(node.name)
        self.registry_node_code_input.setText(node.code)
        self.registry_node_responsible_input.setText(node.responsible)
        self.registry_node_description_input.setPlainText(node.description)
        template_index = self.registry_node_template_input.findData(node.template_key)
        self.registry_node_template_input.setCurrentIndex(template_index if template_index >= 0 else 0)
        self.registry_monitor_interval_input.setValue(node.monitor_interval_minutes)

        descendants = self.registry_repository.list_descendant_ids(node_id)
        watched_files = self.registry_repository.list_watched_files_for_tree(node_id)
        events = self.registry_repository.list_events_for_tree(node_id)
        status_counts = {"ok": 0, "changed": 0, "missing": 0, "error": 0}
        version_count = 0
        for watched in watched_files:
            status_counts[watched.status] = status_counts.get(watched.status, 0) + 1
            version_count += len(self.registry_repository.list_file_versions(watched.id))

        self.registry_node_card_summary.setHtml(
            _html_page(
                f"""
                <h2>Карточка объекта</h2>
                <div class='summary-grid'>
                    <div><b>Код</b><br>{escape(node.code or '-')}</div>
                    <div><b>Ответственный</b><br>{escape(node.responsible or '-')}</div>
                    <div><b>Подобъектов</b><br>{max(len(descendants) - 1, 0)}</div>
                    <div><b>Файлов</b><br>{len(watched_files)}</div>
                    <div><b>Версий</b><br>{version_count}</div>
                    <div><b>Событий</b><br>{len(events)}</div>
                </div>
                <div class='monitor-card'>
                    <div class='card-title'>{escape(node.name)}</div>
                    <div><b>Тип:</b> {escape(node.node_type)}</div>
                    <div><b>Шаблон:</b> {escape(_template_label(node.template_key))} | <b>Интервал:</b> {node.monitor_interval_minutes} мин</div>
                    <div><b>Описание:</b> {escape(node.description or 'не заполнено')}</div>
                    <div><b>Создан:</b> {escape(_format_registry_datetime(node.created_at))} | <b>Обновлен:</b> {escape(_format_registry_datetime(node.updated_at))}</div>
                </div>
                <div class='summary-grid'>
                    <div><b>OK</b><br>{status_counts.get('ok', 0)}</div>
                    <div><b>Изменено</b><br>{status_counts.get('changed', 0)}</div>
                    <div><b>Нет файла</b><br>{status_counts.get('missing', 0)}</div>
                    <div><b>Ошибки</b><br>{status_counts.get('error', 0)}</div>
                </div>
                """
            )
        )

    def delete_selected_registry_node(self) -> bool:
        if self.selected_registry_node_id is None:
            return False
        node = self.registry_repository.get_node(self.selected_registry_node_id)
        parent_id = node.parent_id
        deleted_ids = self.registry_repository.delete_node(node.id)
        self.refresh_registry_tree()
        if parent_id is not None:
            try:
                self.select_registry_node(parent_id)
            except KeyError:
                self._clear_registry_selection()
        else:
            self._clear_registry_selection()
        self.status_text.setText(f"Удалено объектов: {len(deleted_ids)}")
        return True

    def _confirm_delete_selected_registry_file(self) -> None:
        watched_file_id = self._selected_watched_file_id()
        if watched_file_id is None:
            self._show_message(QMessageBox.Icon.Information, "Не выбран файл", "Выберите файл в списке.")
            return
        watched = self.registry_repository.get_watched_file(watched_file_id)
        answer = self._ask_question(
            "Удалить файл",
            f"Удалить «{watched.label}» из реестра вместе с историей версий?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.delete_selected_registry_file()

    def delete_selected_registry_file(self) -> bool:
        watched_file_id = self._selected_watched_file_id()
        if watched_file_id is None:
            return False
        deleted = self.registry_repository.delete_watched_file(watched_file_id)
        if self.selected_registry_node_id is not None:
            self._render_registry_files(self.selected_registry_node_id)
            self._render_registry_events(self.selected_registry_node_id)
            self._render_registry_monitoring(self.selected_registry_node_id)
            self._render_registry_versions_for_current_file()
        self.status_text.setText(f"Файл удален из реестра: {deleted.label}")
        return True

    def _clear_registry_selection(self) -> None:
        self.selected_registry_node_id = None
        self.registry_object_title.setText("Выберите объект")
        self.registry_files_table.setRowCount(0)
        self.registry_files_stack.setCurrentWidget(self.registry_files_empty_state)
        self._render_registry_files_empty_state("Выберите объект", "Выберите объект или подобъект слева, чтобы увидеть его файлы.")
        self._render_selected_registry_pair_panel()
        self._render_registry_node_card(None)
        self.registry_events_list.clear()
        self.registry_monitoring_panel.clear()
        self.registry_risks_panel.clear()
        self.registry_versions_panel.clear()
        self.registry_tree.clearSelection()
        self._refresh_registry_compare_action()

    def add_watched_file_to_selected_node(self, path: Path | str):
        if self.selected_registry_node_id is None:
            raise RuntimeError("registry node is not selected")
        watched = self.registry_monitor.add_file(self.selected_registry_node_id, Path(path))
        self._render_registry_files(self.selected_registry_node_id)
        self._render_registry_events(self.selected_registry_node_id)
        self._render_registry_monitoring(self.selected_registry_node_id)
        self._render_registry_versions_for_current_file()
        self.status_text.setText("Файл добавлен в мониторинг")
        return watched

    def add_registry_file_to_selected_context(self, path: Path | str):
        if self.selected_registry_node_id is None:
            raise RuntimeError("registry node is not selected")
        watched_file_id = self._selected_watched_file_id()
        if watched_file_id is None:
            watched = self.add_watched_file_to_selected_node(path)
            self._select_watched_file(watched.id)
            return watched
        return self.add_after_version_to_selected_registry_file(path)

    def add_watched_file_pair_to_selected_node(self, before_path: Path | str, after_path: Path | str):
        if self.selected_registry_node_id is None:
            raise RuntimeError("registry node is not selected")
        before_file = Path(before_path)
        after_file = Path(after_path)
        watched = self.registry_monitor.add_file_pair(self.selected_registry_node_id, before_file, after_file)
        self._render_registry_files(self.selected_registry_node_id)
        self._render_registry_events(self.selected_registry_node_id)
        self._render_registry_monitoring(self.selected_registry_node_id)
        self._select_watched_file(watched.id)
        self._render_registry_versions_for_current_file()
        self.status_text.setText("Добавлена пара версий: файл до и файл после")
        return watched

    def add_after_version_to_selected_registry_file(self, path: Path | str):
        watched_file_id = self._selected_watched_file_id()
        if watched_file_id is None:
            raise RuntimeError("registry watched file is not selected")
        updated = self.registry_monitor.add_next_version(watched_file_id, Path(path))
        if self.selected_registry_node_id is not None:
            self._render_registry_files(self.selected_registry_node_id)
            self._render_registry_events(self.selected_registry_node_id)
            self._render_registry_monitoring(self.selected_registry_node_id)
            self._select_watched_file(updated.id)
            self._render_registry_versions_for_current_file()
        self.status_text.setText("Добавлена новая версия файла после")
        return updated

    def check_selected_registry_node(self):
        if self.selected_registry_node_id is None:
            return []
        checked = self.registry_monitor.check_node(self.selected_registry_node_id)
        self._render_registry_files(self.selected_registry_node_id)
        self._render_registry_events(self.selected_registry_node_id)
        self._render_registry_monitoring(self.selected_registry_node_id)
        self._render_registry_versions_for_current_file()
        self.status_text.setText("Реестр проверен локально")
        return checked

    def check_selected_registry_file(self):
        watched_file_id = self._selected_watched_file_id()
        if watched_file_id is None:
            return None
        checked = self.registry_monitor.check_file(watched_file_id)
        if self.selected_registry_node_id is not None:
            self._render_registry_files(self.selected_registry_node_id)
            self._render_registry_events(self.selected_registry_node_id)
            self._render_registry_monitoring(self.selected_registry_node_id)
            self._select_watched_file(checked.id)
            self._render_registry_versions_for_current_file()
        self.status_text.setText("Файл проверен локально")
        return checked

    def _show_registry_file_context_menu(self, position: QPoint) -> None:
        row = self.registry_files_table.rowAt(position.y())
        if row >= 0:
            self.registry_files_table.setCurrentCell(row, 0)
            self.registry_files_table.selectRow(row)
        menu = self._build_registry_file_context_menu()
        menu.exec(self.registry_files_table.viewport().mapToGlobal(position))

    def _build_registry_file_context_menu(self) -> QMenu:
        menu = QMenu(self)
        compare_action = menu.addAction("Сравнить")
        compare_action.setEnabled(self._selected_registry_compare_pair() is not None)
        compare_action.triggered.connect(self.compare_selected_registry_file)

        export_action = menu.addAction("Экспорт отчета")
        export_action.setEnabled(self._selected_registry_compare_pair() is not None)
        export_action.triggered.connect(lambda checked=False: self.export_selected_registry_report())

        add_version_action = menu.addAction("Добавить новую версию")
        add_version_action.setEnabled(self.selected_registry_node_id is not None)
        add_version_action.triggered.connect(self._add_registry_file_dialog)

        check_action = menu.addAction("Проверить файл")
        check_action.setEnabled(self._selected_watched_file_id() is not None)
        check_action.triggered.connect(self.check_selected_registry_file)

        delete_action = menu.addAction("Удалить файл")
        delete_action.setEnabled(self._selected_watched_file_id() is not None)
        delete_action.triggered.connect(self._confirm_delete_selected_registry_file)
        return menu

    def compare_selected_registry_file(self) -> bool:
        pair = self._selected_registry_compare_pair()
        if pair is None:
            self._show_message(
                QMessageBox.Icon.Information,
                "Недостаточно версий",
                "Выберите файл реестра, у которого есть минимум две версии: файл ДО и файл ПОСЛЕ.",
            )
            return False
        left_path, right_path = pair
        missing = [str(path) for path in (left_path, right_path) if not path.is_file()]
        if missing:
            self._show_message(
                QMessageBox.Icon.Warning,
                "Снимок версии не найден",
                "Не найден сохраненный файл версии:\n" + "\n".join(missing),
            )
            return False
        self.assign_left_file(left_path)
        self.assign_right_file(right_path)
        self._set_mode("compare")
        self.status_text.setText("Сравнение запущено из реестра")
        self._compare()
        return True

    def export_selected_registry_report(self, path: Path | str | None = None) -> Path | None:
        pair = self._selected_registry_compare_pair()
        if pair is None:
            self._show_message(
                QMessageBox.Icon.Information,
                "Недостаточно версий",
                "Выберите файл реестра, у которого есть минимум две версии.",
            )
            return None
        left_path, right_path = pair
        missing = [str(file_path) for file_path in (left_path, right_path) if not file_path.is_file()]
        if missing:
            self._show_message(
                QMessageBox.Icon.Warning,
                "Снимок версии не найден",
                "Не найден сохраненный файл версии:\n" + "\n".join(missing),
            )
            return None
        if path is None:
            selected_path, _ = QFileDialog.getSaveFileName(
                self,
                "Сохранить отчет реестра",
                "registry-comparison-report.html",
                "HTML (*.html)",
            )
            if not selected_path:
                return None
            path = selected_path
        output_path = Path(path)
        result = compare_files(left_path, right_path)
        output_path.write_text(render_html_report(result), encoding="utf-8")
        self.status_text.setText(f"Отчет реестра сохранен: {output_path}")
        return output_path

    def _backup_registry_database_dialog(self) -> None:
        default_dir = self.registry_repository.db_path.parent if self.registry_repository.db_path is not None else Path.cwd()
        selected_dir = QFileDialog.getExistingDirectory(self, "Папка для резервной копии БД", str(default_dir))
        if selected_dir:
            self.backup_registry_database(Path(selected_dir))

    def backup_registry_database(self, target_dir: Path | str | None = None) -> Path | None:
        try:
            backup_path = self.registry_repository.backup_database(target_dir)
        except Exception as exc:
            self._show_message(QMessageBox.Icon.Warning, "Ошибка резервной копии", f"Не удалось создать резервную копию: {exc}")
            return None
        self.status_text.setText(f"Резервная копия БД создана: {backup_path}")
        return backup_path

    def _export_registry_excel_dialog(self) -> None:
        default_dir = self.registry_repository.db_path.parent if self.registry_repository.db_path is not None else Path.cwd()
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            "Выгрузить реестр в Excel",
            str(default_dir / "registry-export.xlsx"),
            "Excel (*.xlsx)",
        )
        if selected_path:
            self.export_registry_excel(Path(selected_path))

    def export_registry_excel(self, path: Path | str | None = None) -> Path | None:
        if path is None:
            self._export_registry_excel_dialog()
            return None
        try:
            export_path = self.registry_repository.export_registry_excel(path)
        except Exception as exc:
            self._show_message(QMessageBox.Icon.Warning, "Ошибка выгрузки", f"Не удалось выгрузить реестр: {exc}")
            return None
        self.status_text.setText(f"Реестр выгружен в Excel: {export_path}")
        return export_path

    def _selected_registry_compare_pair(self) -> tuple[Path, Path] | None:
        row_meta = self._selected_registry_row_meta()
        if row_meta is not None:
            left_path = row_meta.get("left_path")
            right_path = row_meta.get("right_path")
            if isinstance(left_path, str) and isinstance(right_path, str):
                return Path(left_path), Path(right_path)
        watched_file_id = self._selected_watched_file_id()
        if watched_file_id is None:
            return None
        versions = self.registry_repository.list_file_versions(watched_file_id)
        if len(versions) < 2:
            return None
        previous, latest = versions[-2], versions[-1]
        return Path(previous.snapshot_path), Path(latest.snapshot_path)

    def _refresh_registry_compare_action(self) -> None:
        self.compare_registry_button.setEnabled(self._selected_registry_compare_pair() is not None)

    def _render_registry_files(self, node_id: int) -> None:
        selected_meta = self._selected_registry_row_meta()
        selected_id = selected_meta.get("watched_id") if selected_meta is not None else None
        selected_to_version = selected_meta.get("to_version") if selected_meta is not None else None
        self.registry_files_table.setRowCount(0)
        row_to_select = 0
        for watched in self.registry_repository.list_watched_files(node_id):
            versions = self.registry_repository.list_file_versions(watched.id)
            if len(versions) >= 2:
                version_pairs = list(zip(versions, versions[1:]))
            elif versions:
                version_pairs = [(versions[0], None)]
            else:
                version_pairs = [(None, None)]

            for before_version, after_version in version_pairs:
                if before_version is not None:
                    before_text = _snapshot_display_name(before_version.snapshot_path)
                else:
                    before_text = "Добавьте файл до"
                if after_version is not None:
                    after_text = _snapshot_display_name(after_version.snapshot_path)
                    route_text = f"v{before_version.version_number} -> v{after_version.version_number}" if before_version else "-"
                    loaded_text = _format_registry_datetime(after_version.created_at)
                elif before_version is not None:
                    after_text = "Добавьте файл после"
                    route_text = f"v{before_version.version_number}"
                    loaded_text = _format_registry_datetime(before_version.created_at)
                else:
                    after_text = "Добавьте файл после"
                    route_text = "-"
                    loaded_text = "-"

                if not self._watched_file_matches_registry_filters(watched, before_text, after_text, route_text, loaded_text):
                    continue

                row = self.registry_files_table.rowCount()
                row_meta = {
                    "watched_id": watched.id,
                    "from_version": before_version.version_number if before_version is not None else None,
                    "to_version": after_version.version_number if after_version is not None else None,
                    "left_path": before_version.snapshot_path if before_version is not None and after_version is not None else None,
                    "right_path": after_version.snapshot_path if after_version is not None else None,
                }
                self.registry_files_table.insertRow(row)
                values = [
                    str(row + 1),
                    before_text,
                    after_text,
                    route_text,
                    _registry_status_text(watched.status),
                    loaded_text,
                ]
                for column, value in enumerate(values):
                    cell = QTableWidgetItem(value)
                    cell.setToolTip(
                        "\n".join(
                            [
                                f"ID: {row + 1}",
                                f"Файл: {watched.label}",
                                f"Текущий путь: {watched.file_path}",
                                f"Строка сверки: {route_text}",
                                f"Версий: {len(versions)}",
                            ]
                        )
                    )
                    if column == 0:
                        cell.setData(Qt.UserRole, row_meta)
                    if column in {0, 3, 4}:
                        cell.setTextAlignment(Qt.AlignCenter)
                    elif column == 5:
                        cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    if column == 4:
                        _apply_registry_status_style(cell, watched.status)
                    self.registry_files_table.setItem(row, column, cell)
                self.registry_files_table.setRowHeight(row, 38)
                if watched.id == selected_id and (
                    selected_to_version is None or selected_to_version == row_meta["to_version"]
                ):
                    row_to_select = row
        if self.registry_files_table.rowCount():
            self.registry_files_stack.setCurrentWidget(self.registry_files_table)
            self.registry_files_table.setCurrentCell(row_to_select, 0)
            self.registry_files_table.selectRow(row_to_select)
        else:
            self.registry_files_stack.setCurrentWidget(self.registry_files_empty_state)
            if self.registry_repository.list_watched_files(node_id):
                self._render_registry_files_empty_state(
                    "Ничего не найдено",
                    "Измените поиск или фильтр статуса, чтобы снова увидеть строки сверок.",
                )
            else:
                self._render_registry_files_empty_state(
                    "Загрузите первый файл",
                    "Нажмите '+ Файл'. Первая загрузка станет базовая версия v1. Следующая загрузка создаст строку сверки v1 -> v2.",
                )
            self.registry_versions_panel.setPlainText("Добавьте файл до и файл после, чтобы начать историю версий.")
        self._render_selected_registry_pair_panel()
        self._refresh_registry_compare_action()

    def _render_registry_files_empty_state(self, title: str, message: str) -> None:
        self.registry_files_empty_state.setHtml(
            _html_page(
                f"""
                <div class='empty-state'>
                    <h2>{escape(title)}</h2>
                    <p>{escape(message)}</p>
                    <p class='hint'>Реестр хранит цепочку сверок: v1 -> v2, v2 -> v3 и дальше по порядку.</p>
                </div>
                """
            )
        )

    def _watched_file_matches_registry_filters(
        self,
        watched,
        before_text: str,
        after_text: str,
        route_text: str,
        loaded_text: str,
    ) -> bool:
        if self.registry_status_filter_key != "all" and watched.status != self.registry_status_filter_key:
            return False
        query = self.registry_search_query
        if not query:
            return True
        haystack = " ".join(
            [
                watched.label,
                watched.file_path,
                watched.file_kind,
                _registry_status_text(watched.status),
                before_text,
                after_text,
                route_text,
                loaded_text,
            ]
        ).casefold()
        return query in haystack

    def _selected_watched_file_id(self) -> int | None:
        row_meta = self._selected_registry_row_meta()
        if row_meta is not None:
            watched_file_id = row_meta.get("watched_id")
            return watched_file_id if isinstance(watched_file_id, int) else None

        return None

    def _selected_registry_row_meta(self) -> dict[str, object] | None:
        row = self.registry_files_table.currentRow()
        if row < 0:
            return None
        item = self.registry_files_table.item(row, 0)
        if item is None:
            return None
        row_data = item.data(Qt.UserRole)
        if isinstance(row_data, dict):
            return row_data
        if isinstance(row_data, int):
            return {"watched_id": row_data}
        return None

    def _select_watched_file(self, watched_file_id: int) -> None:
        row_to_select = -1
        for row in range(self.registry_files_table.rowCount()):
            item = self.registry_files_table.item(row, 0)
            if item is None:
                continue
            row_data = item.data(Qt.UserRole)
            if isinstance(row_data, dict) and row_data.get("watched_id") == watched_file_id:
                row_to_select = row
            elif row_data == watched_file_id:
                row_to_select = row
        if row_to_select >= 0:
            self.registry_files_table.setCurrentCell(row_to_select, 0)
            self.registry_files_table.selectRow(row_to_select)

    def _render_registry_events(self, node_id: int) -> None:
        self.registry_events_list.clear()
        for event in self.registry_repository.list_events(node_id):
            self.registry_events_list.addItem(f"{event.created_at} | {event.event_type}\n{event.message}")

    def _on_registry_file_selection_changed(self) -> None:
        self._render_registry_versions_for_current_file()
        self._render_selected_registry_pair_panel()

    def _render_selected_registry_pair_panel(self) -> None:
        row = self.registry_files_table.currentRow()
        if row < 0 or self.registry_files_table.rowCount() == 0:
            self.registry_selected_pair_panel.setHtml(
                _html_page(
                    """
                    <div class='selected-pair'>
                        <h2>Выбранная сверка</h2>
                        <p class='hint'>Выберите строку в таблице, чтобы увидеть файл до, файл после, версию, статус и действия.</p>
                    </div>
                    """
                )
            )
            self._render_registry_review_controls()
            return

        def cell_text(column: int) -> str:
            item = self.registry_files_table.item(row, column)
            return item.text() if item is not None else "-"

        row_id = cell_text(0)
        before_text = cell_text(1)
        after_text = cell_text(2)
        route_text = cell_text(3)
        status_text = cell_text(4)
        loaded_text = cell_text(5)
        row_meta = self._selected_registry_row_meta()
        review_text = "Новое"
        if row_meta is not None and isinstance(row_meta.get("watched_id"), int) and isinstance(row_meta.get("from_version"), int) and isinstance(row_meta.get("to_version"), int):
            review = self.registry_repository.get_comparison_review(
                row_meta["watched_id"],  # type: ignore[arg-type]
                row_meta["from_version"],  # type: ignore[arg-type]
                row_meta["to_version"],  # type: ignore[arg-type]
            )
            review_text = _review_status_text(review.status)
        self.registry_selected_pair_panel.setHtml(
            _html_page(
                f"""
                <div class='selected-pair'>
                    <h2>Выбранная сверка</h2>
                    <div class='summary-grid'>
                        <div><b>ID {escape(row_id)}</b><br>{escape(route_text)}</div>
                        <div><b>Статус</b><br>{escape(status_text)}</div>
                        <div><b>Согласование</b><br>{escape(review_text)}</div>
                        <div><b>Загружено</b><br>{escape(loaded_text)}</div>
                    </div>
                    <div class='monitor-card'>
                        <div><b>Файл до:</b> {escape(before_text)}</div>
                        <div><b>Файл после:</b> {escape(after_text)}</div>
                        <div class='hint'>Действия: Сравнить | Экспорт отчета | Добавить новую версию</div>
                    </div>
                </div>
                """
            )
        )
        self._render_registry_review_controls()

    def _render_registry_review_controls(self) -> None:
        row_meta = self._selected_registry_row_meta()
        watched_id = row_meta.get("watched_id") if row_meta else None
        from_version = row_meta.get("from_version") if row_meta else None
        to_version = row_meta.get("to_version") if row_meta else None
        enabled = isinstance(watched_id, int) and isinstance(from_version, int) and isinstance(to_version, int)
        for widget in (
            self.registry_review_status_input,
            self.registry_review_reviewer_input,
            self.registry_review_comment_input,
            self.save_registry_review_button,
        ):
            widget.setEnabled(enabled)
        if not enabled:
            self.registry_review_status_input.setCurrentIndex(0)
            self.registry_review_reviewer_input.clear()
            self.registry_review_comment_input.clear()
            return
        review = self.registry_repository.get_comparison_review(watched_id, from_version, to_version)
        status_index = self.registry_review_status_input.findData(review.status)
        self.registry_review_status_input.setCurrentIndex(status_index if status_index >= 0 else 0)
        self.registry_review_reviewer_input.setText(review.reviewer)
        self.registry_review_comment_input.setPlainText(review.comment)

    def save_selected_registry_review(self) -> bool:
        row_meta = self._selected_registry_row_meta()
        if row_meta is None:
            return False
        watched_id = row_meta.get("watched_id")
        from_version = row_meta.get("from_version")
        to_version = row_meta.get("to_version")
        if not isinstance(watched_id, int) or not isinstance(from_version, int) or not isinstance(to_version, int):
            return False
        self.registry_repository.upsert_comparison_review(
            watched_id,
            from_version,
            to_version,
            status=str(self.registry_review_status_input.currentData() or "new"),
            reviewer=self.registry_review_reviewer_input.text().strip(),
            comment=self.registry_review_comment_input.toPlainText().strip(),
        )
        self._render_selected_registry_pair_panel()
        if self.selected_registry_node_id is not None:
            self._render_registry_files(self.selected_registry_node_id)
        self.status_text.setText("Статус сверки сохранен")
        return True

    def _render_registry_versions_for_current_file(self) -> None:
        self._refresh_registry_compare_action()
        watched_file_id = self._selected_watched_file_id()
        if watched_file_id is None:
            self.registry_versions_panel.setPlainText("Выберите файл в списке, чтобы увидеть его версии.")
            return
        watched = self.registry_repository.get_watched_file(watched_file_id)
        versions = self.registry_repository.list_file_versions(watched_file_id)
        version_cards: list[str] = []
        transition_cards: list[str] = []
        if not versions:
            version_cards.append("<div class='version-card'>Версии пока не сохранены.</div>")
        if len(versions) < 2:
            transition_cards.append("<div class='version-card'>Загрузите файл после, чтобы появилась первая сверка.</div>")
        for previous, current in zip(versions, versions[1:]):
            transition_cards.append(
                "<div class='version-card'>"
                f"<div class='card-title'>Сверка v{previous.version_number} -> v{current.version_number}</div>"
                f"<div><b>Файл до:</b> {escape(_snapshot_display_name(previous.snapshot_path))}</div>"
                f"<div><b>Файл после:</b> {escape(_snapshot_display_name(current.snapshot_path))}</div>"
                f"<div><b>Изменений:</b> {current.change_count}</div>"
                f"<div><b>Загружено:</b> {escape(_format_registry_datetime(current.created_at))}</div>"
                "</div>"
            )
        for version in versions:
            version_cards.append(
                "<div class='version-card'>"
                f"<div class='card-title'>v{version.version_number}</div>"
                f"<div>Размер: {version.size_bytes} байт</div>"
                f"<div>Изменений: {version.change_count}</div>"
                f"<div>Сохранено: {escape(version.created_at)}</div>"
                f"<div class='path'>Снимок: {escape(version.snapshot_path)}</div>"
                "</div>"
            )
        self.registry_versions_panel.setHtml(
            _html_page(
                f"""
                <h2>Файл: {escape(watched.label)}</h2>
                <div class='summary-grid'>
                    <div><b>Статус</b><br>{escape(_registry_status_text(watched.status))}</div>
                    <div><b>Версий: {len(versions)}</b><br>цепочка v1 -> vN</div>
                </div>
                <p><b>Текущий путь:</b><br><span class='path'>{escape(watched.file_path)}</span></p>
                <p class='hint'>v1 остается базовым файлом ДО. Каждая следующая версия хранит новый файл ПОСЛЕ и сравнивается с предыдущей версией.</p>
                <h2>Цепочка сверок</h2>
                {''.join(transition_cards)}
                <h2>Снимки версий</h2>
                {''.join(version_cards)}
                """
            )
        )

    def _render_registry_monitoring(self, node_id: int) -> None:
        summary = self.registry_monitor.build_node_summary(node_id)
        cards: list[str] = []
        problem_cards: list[str] = []
        if not summary.files:
            cards.append(
                "<div class='monitor-card'>Файлы для мониторинга пока не добавлены.<br>"
                "Начните с кнопки '+ Файл': первая загрузка станет базовой версией v1.</div>"
            )
        for item in summary.files:
            watched = item.watched_file
            version = item.latest_version
            event = item.last_event
            version_text = f"v{version.version_number}" if version is not None else "версий нет"
            hash_text = version.sha256[:12] if version is not None else "-"
            changes_text = str(version.change_count) if version is not None else "0"
            checked_at = watched.last_checked_at or "еще не проверялся"
            last_event = f"{event.event_type}; {event.message}" if event is not None else "событий пока нет"
            card = (
                "<div class='monitor-card'>"
                f"<div class='card-title'>{escape(watched.label)}</div>"
                f"<div><span class='badge'>{escape(_registry_status_text(watched.status))}</span>"
                f" <b>Объект:</b> {escape(item.node_path)}</div>"
                f"<div><b>Текущая версия:</b> {escape(version_text)} | "
                f"<b>Изменений:</b> {escape(changes_text)} | <b>hash:</b> {escape(hash_text)}</div>"
                f"<div><b>Последняя проверка:</b> {escape(checked_at)}</div>"
                f"<div class='path'><b>Текущий файл после:</b> {escape(watched.file_path)}</div>"
                f"<div><b>Последнее событие:</b> {escape(last_event)}</div>"
                "</div>"
            )
            cards.append(card)
            if watched.status != "ok":
                problem_cards.append(card)
        if not problem_cards:
            problem_cards.append("<div class='monitor-card'>Проблемных файлов нет.</div>")
        self.registry_monitoring_panel.setHtml(
            _html_page(
                f"""
                <h2>Панель мониторинга</h2>
                <p class='hint'>Проверяется выбранный объект и все его подобъекты. Файлов под контролем: {summary.total_files}</p>
                <div class='summary-grid'>
                    <div><b>Всего файлов</b><br>{summary.total_files}</div>
                    <div><b>OK</b><br>{summary.status_counts['ok']}</div>
                    <div><b>Изменено</b><br>{summary.status_counts['changed']}</div>
                    <div><b>Нет файла</b><br>{summary.status_counts['missing']}</div>
                    <div><b>Ошибка</b><br>{summary.status_counts['error']}</div>
                </div>
                <h2>Проблемные файлы</h2>
                {''.join(problem_cards)}
                <h2>Все файлы</h2>
                {''.join(cards)}
                """
            )
        )

    def _render_registry_risks(self, node_id: int) -> None:
        risk_events = [event for event in self.registry_repository.list_events_for_tree(node_id) if event.risk_count > 0]
        total_risks = sum(event.risk_count for event in risk_events)
        if not risk_events:
            self.registry_risks_panel.setHtml(
                _html_page(
                    """
                    <h2>Риски</h2>
                    <div class='monitor-card'>Критичных изменений по выбранному объекту пока нет.</div>
                    """
                )
            )
            return
        cards = []
        for event in risk_events[:30]:
            cards.append(
                "<div class='monitor-card'>"
                f"<div class='card-title'>{escape(event.event_type)} | рисков: {event.risk_count}</div>"
                f"<div><b>Событие:</b> {escape(event.message)}</div>"
                f"<div><b>Риск:</b> {escape(event.risk_summary)}</div>"
                f"<div><b>Дата:</b> {escape(_format_registry_datetime(event.created_at))}</div>"
                "</div>"
            )
        self.registry_risks_panel.setHtml(
            _html_page(
                f"""
                <h2>Риски</h2>
                <div class='summary-grid'>
                    <div><b>Всего рисков</b><br>{total_risks}</div>
                    <div><b>Событий с риском</b><br>{len(risk_events)}</div>
                </div>
                {''.join(cards)}
                """
            )
        )

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QWidget#appShell { background: #eef2f6; color: #111827; font-family: Segoe UI, Arial; }
            QFrame#titleBar { background: #111827; color: #f9fafb; }
            QLabel#brandMark {
                min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px;
                border-radius: 7px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2563eb, stop:1 #0f766e);
                color: #ffffff;
                font-size: 13px;
                font-weight: 800;
            }
            QLabel#brandTitle { color: #f9fafb; font-size: 15px; font-weight: 750; }
            QLabel#brandTag {
                color: #99f6e4;
                background: rgba(15, 118, 110, 42);
                border: 1px solid rgba(153, 246, 228, 86);
                border-radius: 11px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 700;
            }
            QToolButton#windowButton, QToolButton#windowCloseButton {
                border: 0;
                border-radius: 5px;
                color: #cbd5e1;
                background: transparent;
                font-size: 13px;
            }
            QToolButton#windowButton:hover { background: #1f2937; color: #ffffff; }
            QToolButton#windowCloseButton:hover { background: #b42318; color: #ffffff; }
            QFrame#modeTabs {
                background: #f7f9fc;
                border: 1px solid #d6dde8;
                border-radius: 8px;
            }
            QPushButton#modeCompareButton, QPushButton#modeRegistryButton {
                min-height: 34px;
                padding: 0 12px;
                border: 1px solid transparent;
                border-radius: 7px;
                background: transparent;
                color: #667085;
                font-size: 13px;
                font-weight: 650;
            }
            QPushButton#modeCompareButton[active="true"], QPushButton#modeRegistryButton[active="true"] {
                background: #ffffff;
                color: #2563eb;
                border-color: #a7c1ff;
            }
            QLineEdit#registrySearchBox, QComboBox#registryStatusFilter {
                border: 1px solid #d6dde8;
                border-radius: 8px;
                background: #ffffff;
                color: #344054;
                padding: 0 12px;
                font-size: 13px;
                font-weight: 600;
            }
            QLineEdit#registrySearchBox {
                selection-background-color: #c7d7fe;
            }
            QLineEdit#registrySearchBox::placeholder {
                color: #8a95a8;
                font-weight: 500;
            }
            QComboBox#registryStatusFilter::drop-down {
                width: 24px;
                border: 0;
            }
            QComboBox#registryStatusFilter QAbstractItemView {
                background: #ffffff;
                color: #111827;
                border: 1px solid #d6dde8;
                selection-background-color: #eff6ff;
                selection-color: #111827;
                outline: 0;
            }
            QFrame#registryNodeFormCard QLabel {
                color: #344054;
                background: transparent;
                font-size: 12px;
                font-weight: 650;
            }
            QLineEdit#registryNodeNameInput, QLineEdit#registryNodeCodeInput, QLineEdit#registryNodeResponsibleInput,
            QLineEdit#registryReviewReviewerInput, QComboBox#registryNodeTemplateInput,
            QComboBox#registryReviewStatusInput, QSpinBox#registryMonitorIntervalInput,
            QTextEdit#registryNodeDescriptionInput, QTextEdit#registryReviewCommentInput {
                border: 1px solid #d6dde8;
                border-radius: 7px;
                background: #ffffff;
                color: #111827;
                padding: 7px 9px;
                font-size: 13px;
                selection-background-color: #c7d7fe;
            }
            QComboBox#registryNodeTemplateInput::drop-down, QComboBox#registryReviewStatusInput::drop-down,
            QSpinBox#registryMonitorIntervalInput::up-button, QSpinBox#registryMonitorIntervalInput::down-button {
                border: 0;
                width: 22px;
            }
            QComboBox#registryNodeTemplateInput QAbstractItemView, QComboBox#registryReviewStatusInput QAbstractItemView {
                background: #ffffff;
                color: #111827;
                border: 1px solid #d6dde8;
                selection-background-color: #eff6ff;
                selection-color: #111827;
                outline: 0;
            }
            QTextEdit#registryNodeDescriptionInput::placeholder, QTextEdit#registryReviewCommentInput::placeholder,
            QLineEdit#registryReviewReviewerInput::placeholder {
                color: #8a95a8;
            }
            QFrame#registryReviewPanel {
                background: #f8fafc;
                border-top: 1px solid #d6dde8;
            }
            QFrame#registryNodeFormCard {
                background: #f8fafc;
                border: 1px solid #e5ebf3;
                border-radius: 8px;
                padding: 12px;
            }
            QFrame#toolbar {
                background: #ffffff;
                border-bottom: 1px solid #d6dde8;
            }
            QPushButton#leftFileChip, QPushButton#rightFileChip {
                text-align: left;
                border: 1px solid #d6dde8;
                border-radius: 7px;
                background: #f7f9fc;
            }
            QPushButton#leftFileChip:hover, QPushButton#rightFileChip:hover {
                border-color: #8fb3ff;
                background: #ffffff;
            }
            QLabel#fileIcon, QLabel#fileIconNew {
                border-radius: 6px;
                color: #ffffff;
                font-size: 11px;
                font-weight: 800;
                background: #2563eb;
            }
            QLabel#fileIconNew { background: #0f766e; }
            QLabel#fileName { color: #111827; font-size: 13px; font-weight: 650; }
            QLabel#fileNote { color: #667085; font-size: 11px; }
            QPushButton#primaryButton, QPushButton#compareRegistryFileButton {
                min-height: 34px;
                padding: 0 12px;
                border: 1px solid #2563eb;
                border-radius: 7px;
                background: #2563eb;
                color: #ffffff;
                font-size: 13px;
                font-weight: 650;
            }
            QPushButton#secondaryButton, QPushButton#addRegistryFileButton, QPushButton#addBeforeFileButton, QPushButton#addAfterVersionButton,
            QPushButton#backupRegistryButton, QPushButton#exportRegistryExcelButton, QPushButton#saveRegistryNodeButton,
            QPushButton#saveRegistryReviewButton,
            QToolButton#iconButton, QToolButton#iconButtonSmall {
                min-height: 34px;
                padding: 0 12px;
                border: 1px solid #d6dde8;
                border-radius: 7px;
                background: #ffffff;
                color: #111827;
                font-size: 13px;
                font-weight: 650;
            }
            QPushButton#deleteNodeButton {
                min-height: 34px;
                padding: 0 12px;
                border: 1px solid #f2b8b5;
                border-radius: 7px;
                background: #fff8f7;
                color: #b42318;
                font-size: 13px;
                font-weight: 650;
            }
            QPushButton#deleteNodeButton:hover {
                background: #fff1f0;
                border-color: #f04438;
            }
            QPushButton#addRegistryFileButton, QPushButton#addBeforeFileButton {
                color: #111827;
                background: #ffffff;
            }
            QPushButton#addAfterVersionButton {
                color: #0f766e;
                background: #ecfdf8;
                border-color: #99d3ca;
            }
            QPushButton#backupRegistryButton, QPushButton#exportRegistryExcelButton {
                color: #1f3a5f;
                background: #f8fafc;
            }
            QPushButton#saveRegistryNodeButton, QPushButton#saveRegistryReviewButton {
                color: #ffffff;
                background: #2563eb;
                border-color: #2563eb;
            }
            QToolButton#iconButton { min-width: 34px; max-width: 34px; padding: 0; font-size: 16px; }
            QToolButton#iconButtonSmall { min-width: 30px; max-width: 30px; min-height: 28px; padding: 0; font-size: 16px; }
            QToolButton#cancelCompareButton {
                min-width: 34px;
                max-width: 34px;
                min-height: 34px;
                padding: 0;
                border: 1px solid #d6dde8;
                border-radius: 7px;
                background: #ffffff;
                color: #b42318;
                font-size: 17px;
                font-weight: 750;
            }
            QToolButton#cancelCompareButton:disabled {
                color: #b8c0cc;
                background: #f7f9fc;
            }
            QProgressBar#compareProgress {
                min-height: 8px;
                max-height: 8px;
                border: 0;
                border-radius: 4px;
                background: #edf1f7;
            }
            QProgressBar#compareProgress::chunk {
                border-radius: 4px;
                background: #2563eb;
            }
            QLabel#privacyPill {
                color: #0f766e;
                background: #ecfdf8;
                border: 1px solid #99d3ca;
                border-radius: 13px;
                padding: 6px 9px;
                font-size: 12px;
                font-weight: 650;
            }
            QFrame#workspace { background: #eef2f6; }
            QFrame#registryWorkspace { background: #eef2f6; }
            QFrame#compareArea, QFrame#rightSidebar {
                background: #ffffff;
                border: 1px solid #d6dde8;
                border-radius: 8px;
            }
            QFrame#registryPanel, QFrame#registryDetail {
                background: #ffffff;
                border: 1px solid #d6dde8;
                border-radius: 8px;
            }
            QLabel#registryObjectTitle {
                padding: 18px;
                color: #111827;
                font-size: 24px;
                font-weight: 800;
            }
            QTreeWidget#registryTree {
                background: #ffffff;
                color: #111827;
                border: 0;
                padding: 10px;
                font-size: 13px;
                outline: 0;
            }
            QTreeWidget#registryTree::item {
                min-height: 30px;
                border-radius: 6px;
                padding: 3px 6px;
            }
            QTreeWidget#registryTree::item:selected {
                background: #eff6ff;
                color: #111827;
                border: 1px solid #a7c1ff;
            }
            QTabWidget#registryTabs::pane {
                border: 0;
                border-top: 1px solid #d6dde8;
            }
            QTabBar::tab {
                min-height: 30px;
                min-width: 82px;
                padding: 0 10px;
                margin: 6px 4px 6px 0;
                border-radius: 7px;
                color: #667085;
                font-size: 12px;
                font-weight: 650;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                color: #2563eb;
                border: 1px solid #d6dde8;
            }
            QTableWidget#registryFilesTable, QListWidget#registryEventsList {
                background: #ffffff;
                color: #111827;
                border: 0;
                padding: 10px;
                font-size: 12px;
                outline: 0;
            }
            QTableWidget#registryFilesTable {
                gridline-color: transparent;
                alternate-background-color: #f8fafc;
                selection-background-color: #eff6ff;
                selection-color: #111827;
            }
            QTableWidget#registryFilesTable::item {
                padding: 8px;
                border-bottom: 1px solid #e5ebf3;
                color: #111827;
            }
            QTableWidget#registryFilesTable::item:selected {
                background: #eff6ff;
                color: #111827;
            }
            QHeaderView::section {
                background: #f7f9fc;
                color: #667085;
                border: 0;
                border-bottom: 1px solid #d6dde8;
                padding: 8px;
                font-size: 11px;
                font-weight: 750;
            }
            QTextEdit#registryMonitoringPanel, QTextEdit#registryVersionsPanel,
            QTextEdit#registryFilesEmptyState, QTextEdit#registrySelectedPairPanel,
            QTextEdit#registryNodeCardSummary, QTextEdit#registryRisksPanel {
                background: #ffffff;
                color: #111827;
                border: 0;
                padding: 14px;
                font-family: Segoe UI, Arial;
                font-size: 12px;
                line-height: 1.35;
            }
            QTextEdit#registrySelectedPairPanel {
                border-top: 1px solid #d6dde8;
                background: #f8fafc;
            }
            QTextEdit#registryFilesEmptyState {
                background: #ffffff;
            }
            QListWidget#registryEventsList::item {
                min-height: 52px;
                border: 1px solid #d6dde8;
                border-radius: 7px;
                padding: 8px;
                margin-bottom: 8px;
                background: #ffffff;
                color: #111827;
            }
            QListWidget#registryEventsList::item:selected {
                border-color: #8fb3ff;
                background: #f5f8ff;
                color: #111827;
            }
            QFrame#compareTabs {
                background: #f7f9fc;
                border-bottom: 1px solid #d6dde8;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QPushButton[role="compareTab"] {
                color: #667085;
                border-radius: 6px;
                padding: 0 10px;
                border: 1px solid transparent;
                background: transparent;
                font-size: 12px;
                font-weight: 650;
            }
            QPushButton[role="compareTab"]:hover {
                background: #ffffff;
                color: #2563eb;
                border-color: #d6dde8;
            }
            QPushButton[role="compareTab"][active="true"] {
                background: #ffffff;
                color: #2563eb;
                border: 1px solid #d6dde8;
            }
            QCheckBox#syncScrollToggle {
                color: #667085;
                font-size: 12px;
                spacing: 7px;
            }
            QCheckBox#syncScrollToggle::indicator {
                width: 14px;
                height: 14px;
                border-radius: 4px;
                border: 1px solid #c7d2e2;
                background: #ffffff;
            }
            QCheckBox#syncScrollToggle::indicator:checked {
                background: #2563eb;
                border-color: #2563eb;
            }
            QFrame#viewer { background: #ffffff; border-right: 1px solid #d6dde8; }
            QFrame#viewerHead {
                background: #ffffff;
                border-bottom: 1px solid #d6dde8;
            }
            QLabel#viewerTitle, QLabel#viewerPlace {
                color: #667085;
                font-size: 12px;
                font-weight: 650;
            }
            QTextEdit#viewerBody {
                background: #ffffff;
                border: 0;
                color: #111827;
                selection-background-color: #eff6ff;
                font-family: Consolas, Courier New;
                font-size: 12px;
            }
            QFrame#summaryPanel {
                background: #ffffff;
                border-bottom: 1px solid #d6dde8;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QLabel#summaryTitle { color: #111827; font-size: 16px; font-weight: 750; }
            QFrame#stat {
                background: #f7f9fc;
                border: 1px solid #d6dde8;
                border-radius: 7px;
            }
            QLabel#statRed, QLabel#statGreen, QLabel#statAmber { font-size: 18px; font-weight: 800; }
            QLabel#statRed { color: #b42318; }
            QLabel#statGreen { color: #087443; }
            QLabel#statAmber { color: #b54708; }
            QLabel#statCaption { color: #667085; font-size: 11px; }
            QFrame#filters {
                background: #f7f9fc;
                border-bottom: 1px solid #d6dde8;
            }
            QPushButton[role="changeFilter"] {
                min-height: 28px;
                border: 1px solid #d6dde8;
                border-radius: 14px;
                padding: 0 9px;
                background: #ffffff;
                color: #667085;
                font-size: 12px;
                font-weight: 650;
            }
            QPushButton[role="changeFilter"]:hover {
                background: #f5f8ff;
                color: #2563eb;
                border-color: #a7c1ff;
            }
            QPushButton[role="changeFilter"][active="true"] {
                background: #eff6ff;
                color: #2563eb;
                border-color: #a7c1ff;
            }
            QListWidget#changesList {
                background: #ffffff;
                border: 0;
                padding: 10px;
                font-size: 12px;
                outline: 0;
            }
            QListWidget#changesList::item {
                min-height: 58px;
                border: 1px solid #d6dde8;
                border-radius: 7px;
                padding: 8px;
                margin-bottom: 8px;
                color: #111827;
                background: #ffffff;
            }
            QListWidget#changesList::item:selected {
                border-color: #8fb3ff;
                background: #f5f8ff;
                color: #111827;
            }
            QFrame#statusbarCustom {
                background: #ffffff;
                border-top: 1px solid #d6dde8;
            }
            QLabel#statusOk { color: #0f766e; font-size: 12px; font-weight: 700; }
            QLabel#statusText { color: #667085; font-size: 12px; }
            QLabel#techLabel { color: #6b7280; font-size: 11px; font-weight: 600; }
            QLabel#developerCredit { color: #8b95a7; font-size: 10px; font-weight: 650; }
            """
        )

    def _render_empty_preview(self) -> None:
        left_html = self._lines_html(
            [
                ("38", "4.1. Исполнитель обязуется выполнить работы в срок.", ""),
                ("39", "4.2. Заказчик предоставляет исходные данные.", ""),
                ("40", "4.3. Срок оплаты составляет 10 банковских дней.", "old"),
                ("41", "4.4. Штраф за просрочку составляет 0,05% за каждый день.", "focus"),
                ("42", "4.5. Все приложения являются частью договора.", ""),
                ("43", "OCR confidence: 91%", "warn"),
            ]
        )
        right_html = self._lines_html(
            [
                ("38", "4.1. Исполнитель обязуется выполнить работы в срок.", ""),
                ("39", "4.2. Заказчик предоставляет исходные данные.", ""),
                ("40", "4.3. Срок оплаты составляет 7 банковских дней.", "new"),
                ("41", "4.4. Штраф за просрочку составляет 0,1% за каждый день.", "focus"),
                ("42", "4.5. Все приложения являются частью договора.", ""),
                ("43", "OCR confidence: 88%", "warn"),
            ]
        )
        self.preview_left_html = left_html
        self.preview_right_html = right_html
        self.left_view["text"].setHtml(left_html)
        self.right_view["text"].setHtml(right_html)
        self._populate_demo_changes()

    def _refresh_button_group(self, buttons: dict[str, QPushButton], active_key: str) -> None:
        for key, button in buttons.items():
            button.setProperty("active", key == active_key)
            button.style().unpolish(button)
            button.style().polish(button)

    def _set_sync_scroll_enabled(self, enabled: bool) -> None:
        self.sync_scroll_enabled = enabled

    def _connect_sync_scrollbars(self) -> None:
        self.left_view["text"].verticalScrollBar().valueChanged.connect(
            lambda value: self._sync_scrollbar("left", "vertical", value)
        )
        self.right_view["text"].verticalScrollBar().valueChanged.connect(
            lambda value: self._sync_scrollbar("right", "vertical", value)
        )
        self.left_view["text"].horizontalScrollBar().valueChanged.connect(
            lambda value: self._sync_scrollbar("left", "horizontal", value)
        )
        self.right_view["text"].horizontalScrollBar().valueChanged.connect(
            lambda value: self._sync_scrollbar("right", "horizontal", value)
        )

    def _sync_scrollbar(self, source: str, orientation: str, value: int) -> None:
        if not self.sync_scroll_enabled or self._syncing_scrollbars:
            return
        source_text = self.left_view["text"] if source == "left" else self.right_view["text"]
        target_text = self.right_view["text"] if source == "left" else self.left_view["text"]
        source_bar = source_text.verticalScrollBar() if orientation == "vertical" else source_text.horizontalScrollBar()
        target_bar = target_text.verticalScrollBar() if orientation == "vertical" else target_text.horizontalScrollBar()
        if source_bar.maximum() <= 0:
            target_value = 0
        else:
            target_value = round((value / source_bar.maximum()) * target_bar.maximum())
        self._syncing_scrollbars = True
        try:
            target_bar.setValue(max(0, min(target_bar.maximum(), target_value)))
        finally:
            self._syncing_scrollbars = False

    def set_compare_view_mode(self, mode: str) -> None:
        if mode not in self.compare_tab_buttons:
            return
        self.compare_view_mode = mode
        self._refresh_button_group(self.compare_tab_buttons, mode)
        self._render_compare_view_mode()

    def set_change_filter(self, filter_key: str) -> None:
        if filter_key not in self.change_filter_buttons:
            return
        self.change_filter = filter_key
        self._refresh_button_group(self.change_filter_buttons, filter_key)
        self._render_change_list()

    def _render_compare_view_mode(self) -> None:
        if self.result is None:
            if self.compare_view_mode == "text":
                self.left_view["text"].setHtml(self.preview_left_html)
                self.right_view["text"].setHtml(self.preview_right_html)
            else:
                message = {
                    "pages": "Нет постраничных данных",
                    "ocr": "Нет OCR-данных",
                    "hex": "Нет hex-данных",
                }.get(self.compare_view_mode, "Нет данных")
                self.left_view["text"].setPlainText(message)
                self.right_view["text"].setPlainText(message)
            return

        if self.compare_view_mode == "text":
            left_html, right_html = render_result_html(self.result)
        else:
            left_html, right_html = self._render_mode_changes(self._changes_for_compare_mode(self.compare_view_mode))
        self.left_view["text"].setHtml(left_html)
        self.right_view["text"].setHtml(right_html)

    def _changes_for_compare_mode(self, mode: str) -> list[Change]:
        if self.result is None:
            return []
        if mode == "text":
            return self.result.changes
        if mode == "pages":
            return [change for change in self.result.changes if self._change_has_page_location(change)]
        if mode == "ocr":
            return [
                change
                for change in self.result.changes
                if change.format.lower() == "ocr"
                or "ocr" in change.notes.lower()
                or any(location and location.ocr_line is not None for location in (change.source_location, change.target_location))
            ]
        if mode == "hex":
            return [
                change
                for change in self.result.changes
                if change.format.lower() in {"hex", "binary"}
                or any(location and location.byte_offset is not None for location in (change.source_location, change.target_location))
            ]
        return self.result.changes

    @staticmethod
    def _change_has_page_location(change: Change) -> bool:
        return any(location and location.page is not None for location in (change.source_location, change.target_location))

    def _render_mode_changes(self, changes: list[Change]) -> tuple[str, str]:
        if not changes:
            empty = self._lines_html([("1", "Данных для этого вида не найдено", "warn")])
            return empty, empty
        left_rows: list[tuple[str, str, str]] = []
        right_rows: list[tuple[str, str, str]] = []
        for index, change in enumerate(changes, start=1):
            left_place = compact_location(change.source_location)
            right_place = compact_location(change.target_location)
            left_text = f"{left_place} {change.before}".strip()
            right_text = f"{right_place} {change.after}".strip()
            left_rows.append((str(index), left_text, "old" if change.before else ""))
            right_rows.append((str(index), right_text, "new" if change.after else ""))
        return self._lines_html(left_rows), self._lines_html(right_rows)

    def _render_change_list(self) -> None:
        if self.result is None:
            return
        self.changes_list.clear()
        self.visible_changes = [change for change in self.result.changes if self._change_matches_filter(change)]
        for change in self.visible_changes:
            place = compact_location(change.target_location or change.source_location)
            self.changes_list.addItem(
                QListWidgetItem(f"{change_type_label(change.change_type)}\n{place}\n- {change.before}\n+ {change.after}")
            )
        if self.visible_changes:
            self.changes_list.setCurrentRow(0)

    def _change_matches_filter(self, change: Change) -> bool:
        if self.change_filter == "all":
            return True
        if self.change_filter == "text":
            return (
                change.format.lower() in {"text", "config", "docx", "pdf", "xlsx"}
                or any(location and location.line is not None for location in (change.source_location, change.target_location))
            )
        if self.change_filter == "ocr":
            return change in self._changes_for_compare_mode("ocr")
        if self.change_filter == "risk":
            return change.severity == "risk" or "risk" in change.notes.lower() or "риск" in change.notes.lower()
        return True

    def _lines_html(self, rows: list[tuple[str, str, str]]) -> str:
        style = """
        <style>
          body { margin: 0; font-family: Consolas, 'Courier New'; font-size: 12px; color: #111827; }
          table { border-collapse: collapse; width: 100%; }
          td { padding: 4px 8px; white-space: pre-wrap; word-wrap: break-word; }
          td.ln { width: 38px; color: #8a95a8; background: #f8fafc; text-align: right; border-right: 1px solid #eef2f7; }
          tr.old td.txt { background: #fff1f0; color: #b42318; }
          tr.new td.txt { background: #ecfdf3; color: #087443; }
          tr.warn td.txt { background: #fffaeb; color: #b54708; }
          tr.focus td.txt { background: #eff6ff; color: #1d4ed8; outline: 2px solid rgba(37,99,235,.45); }
        </style>
        """
        body = "".join(f"<tr class='{cls}'><td class='ln'>{line}</td><td class='txt'>{text}</td></tr>" for line, text, cls in rows)
        return f"{style}<table>{body}</table>"

    def _populate_demo_changes(self) -> None:
        self.changes_list.clear()
        for text in (
            "Срок оплаты\nстр. 4, строка 40\n- 10 банковских дней\n+ 7 банковских дней",
            "Штраф\nстр. 4, строка 41\n- 0,05% за каждый день\n+ 0,1% за каждый день",
            "Новый пункт\nстр. 7, строка 82\n+ электронный документооборот",
            "Config key\napp.yaml:18\n- timeout: 30\n+ timeout: 45",
        ):
            self.changes_list.addItem(QListWidgetItem(text))
        self.changes_list.setCurrentRow(0)

    def _choose_left(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выберите исходный файл")
        if path:
            self.assign_left_file(Path(path))

    def _choose_right(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выберите измененный файл")
        if path:
            self.assign_right_file(Path(path))

    def assign_left_file(self, path: Path | str) -> None:
        self.left_path = Path(path)
        self.left_file_name.setText(self.left_path.name)
        self.left_file_note.setText(self._file_note(self.left_path))
        self.status_text.setText("Исходный файл выбран")

    def assign_right_file(self, path: Path | str) -> None:
        self.right_path = Path(path)
        self.right_file_name.setText(self.right_path.name)
        self.right_file_note.setText(self._file_note(self.right_path))
        self.status_text.setText("Новая версия файла выбрана")

    @staticmethod
    def _file_note(path: Path) -> str:
        suffix = path.suffix.upper().lstrip(".") or "FILE"
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        return f"{suffix} | {MainWindow._format_size(size)}"

    @staticmethod
    def _format_size(size: int) -> str:
        units = ("B", "KB", "MB", "GB")
        value = float(size)
        for unit in units:
            if value < 1024 or unit == units[-1]:
                return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
            value /= 1024
        return f"{size} B"

    def _compare(self) -> None:
        if self.left_path is None or self.right_path is None:
            self._show_message(QMessageBox.Icon.Warning, "Не выбраны файлы", "Выберите два файла для сравнения.")
            return
        if self.compare_thread is not None:
            return

        self._set_compare_busy(True)
        self.compare_thread = QThread(self)
        self.compare_worker = CompareWorker(self.left_path, self.right_path)
        self.compare_worker.moveToThread(self.compare_thread)

        self.compare_thread.started.connect(self.compare_worker.run)
        self.compare_worker.progress.connect(self._on_compare_progress)
        self.compare_worker.finished.connect(self._on_compare_finished)
        self.compare_worker.failed.connect(self._on_compare_failed)
        self.compare_worker.canceled.connect(self._on_compare_canceled)
        self.compare_worker.finished.connect(self.compare_thread.quit)
        self.compare_worker.failed.connect(self.compare_thread.quit)
        self.compare_worker.canceled.connect(self.compare_thread.quit)
        self.compare_thread.finished.connect(self.compare_worker.deleteLater)
        self.compare_thread.finished.connect(self._clear_compare_worker)
        self.compare_thread.start()

    def _set_compare_busy(self, busy: bool) -> None:
        self.compare_button.setEnabled(not busy)
        self.export_button.setEnabled(not busy)
        self.left_file_button.setEnabled(not busy)
        self.right_file_button.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        if busy:
            self.progress_bar.setValue(0)
            self.status_ready.setText("Работа")
            self.status_text.setText("Сравнение запущено")

    def _cancel_compare(self) -> None:
        if self.compare_worker is None:
            return
        self.compare_worker.cancel()
        self.cancel_button.setEnabled(False)
        self.status_text.setText("Отмена запрошена")

    def _on_compare_progress(self, value: int, message: str) -> None:
        self.progress_bar.setValue(value)
        self.status_text.setText(message)

    def _on_compare_finished(self, result: object) -> None:
        if not isinstance(result, ComparisonResult):
            self._on_compare_failed("Ошибка сравнения", "Воркер вернул неизвестный результат")
            return
        self.result = result
        self._render_result(result)
        self._set_compare_busy(False)

    def _on_compare_failed(self, title: str, message: str) -> None:
        self._set_compare_busy(False)
        self.status_ready.setText("Ошибка")
        self.status_text.setText(message)
        if title == "Не хватает зависимости":
            self._show_message(QMessageBox.Icon.Warning, title, message)
        else:
            self._show_message(QMessageBox.Icon.Critical, title, message)

    def _on_compare_canceled(self) -> None:
        self._set_compare_busy(False)
        self.status_ready.setText("Готово")
        self.status_text.setText("Сравнение отменено")

    def _clear_compare_worker(self) -> None:
        self.compare_thread = None
        self.compare_worker = None

    def _dependency_diagnostics_text(self) -> str:
        return format_dependency_report(collect_dependency_statuses())

    def _show_diagnostics(self) -> None:
        self._show_message(QMessageBox.Icon.Information, "Диагностика зависимостей", self._dependency_diagnostics_text())

    def _render_result(self, result: ComparisonResult) -> None:
        self.result = result
        self.summary.setText(f"Найдено {result.change_count} изменений")
        removed = sum(_removed_metric_count(change) for change in result.changes)
        added = sum(_added_metric_count(change) for change in result.changes)
        ocr = sum(1 for change in result.changes if change.format == "ocr" or "OCR" in change.notes)
        self.removed_stat.number_label.setText(str(removed))  # type: ignore[attr-defined]
        self.added_stat.number_label.setText(str(added))  # type: ignore[attr-defined]
        self.ocr_stat.number_label.setText(str(ocr))  # type: ignore[attr-defined]
        self._render_change_list()
        self._render_compare_view_mode()
        if result.changes:
            self.changes_list.setCurrentRow(0)
        else:
            self.left_view["text"].setPlainText("Изменений не найдено")
            self.right_view["text"].setPlainText("Изменений не найдено")
        self.status_ready.setText("Готово")
        self.status_text.setText("Сравнение выполнено локально")

    def _show_change(self, row: int) -> None:
        if self.result is None or row < 0 or row >= len(self.visible_changes):
            return
        change = self.visible_changes[row]
        if change.source_location:
            self.left_view["place"].setText(compact_location(change.source_location))
        if change.target_location:
            self.right_view["place"].setText(compact_location(change.target_location))
        self._scroll_to_change(change)

    def _scroll_to_change(self, change: Change) -> None:
        if self.result is None:
            return
        if change.source_location and change.source_location.line is not None:
            self._scroll_view_to_line(
                self.left_view["text"],
                change.source_location.line,
                self._line_count(Path(self.result.left_path)),
            )
        if change.target_location and change.target_location.line is not None:
            self._scroll_view_to_line(
                self.right_view["text"],
                change.target_location.line,
                self._line_count(Path(self.result.right_path)),
            )

    @staticmethod
    def _scroll_view_to_line(view: QTextEdit, line: int, total_lines: int) -> None:
        bar = view.verticalScrollBar()
        if bar.maximum() <= 0:
            return
        ratio = max(0, min(total_lines - 1, line - 1)) / max(total_lines - 1, 1)
        bar.setValue(round(bar.maximum() * ratio))

    @staticmethod
    def _line_count(path: Path) -> int:
        for encoding in ("utf-8-sig", "utf-8", "cp1251", "latin-1"):
            try:
                return max(1, len(path.read_text(encoding=encoding).splitlines()))
            except UnicodeDecodeError:
                continue
            except OSError:
                return 1
        try:
            return max(1, len(path.read_text(errors="replace").splitlines()))
        except OSError:
            return 1

    def _move_selection(self, delta: int) -> None:
        count = self.changes_list.count()
        if count == 0:
            return
        row = self.changes_list.currentRow()
        self.changes_list.setCurrentRow(max(0, min(count - 1, row + delta)))

    def _export_report(self) -> None:
        if self.result is None:
            self._show_message(QMessageBox.Icon.Information, "Нет отчета", "Сначала выполните сравнение.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить отчет", "comparison-report.html", "HTML (*.html)")
        if not path:
            return
        Path(path).write_text(render_html_report(self.result), encoding="utf-8")
        self.status_text.setText(f"Отчет сохранен: {path}")


def _registry_status_text(status: str) -> str:
    return {
        "ok": "OK",
        "changed": "Изменен",
        "missing": "Файл отсутствует",
        "error": "Ошибка",
    }.get(status, status)


def _template_label(template_key: str) -> str:
    for value, label in OBJECT_TEMPLATES:
        if value == template_key:
            return label
    return "Без шаблона"


def _review_status_text(status: str) -> str:
    for value, label in REVIEW_STATUSES:
        if value == status:
            return label
    return status


def _apply_registry_status_style(item: QTableWidgetItem, status: str) -> None:
    colors = {
        "ok": ("#087443", "#ecfdf3"),
        "changed": ("#b54708", "#fffaeb"),
        "missing": ("#b42318", "#fff1f0"),
        "error": ("#b42318", "#fff1f0"),
    }
    foreground, background = colors.get(status, ("#667085", "#f7f9fc"))
    item.setForeground(QBrush(QColor(foreground)))
    item.setBackground(QBrush(QColor(background)))


def _snapshot_display_name(snapshot_path: str) -> str:
    name = Path(snapshot_path).name
    match = re.match(r"^v\d{4}_(.+)$", name)
    return match.group(1) if match else name


def _format_registry_datetime(value: str) -> str:
    if not value:
        return "-"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone()
    return parsed.strftime("%d.%m.%Y %H:%M")


_GROUPED_REMOVED_RE = re.compile(r"\bудал\w*\s*\((\d+)\)", re.IGNORECASE)
_GROUPED_ADDED_RE = re.compile(r"\bдобав\w*\s*\((\d+)\)", re.IGNORECASE)


def _removed_metric_count(change: Change) -> int:
    grouped_count = _grouped_metric_count(_GROUPED_REMOVED_RE, change.before)
    if grouped_count:
        return grouped_count
    return 1 if change.change_type == "removed" else 0


def _added_metric_count(change: Change) -> int:
    grouped_count = _grouped_metric_count(_GROUPED_ADDED_RE, change.after)
    if grouped_count:
        return grouped_count
    return 1 if change.change_type == "added" else 0


def _grouped_metric_count(pattern: re.Pattern[str], value: str) -> int:
    match = pattern.search(value)
    return int(match.group(1)) if match else 0


def _html_page(body: str) -> str:
    return f"""
    <html>
    <head>
    <style>
        body {{
            font-family: Segoe UI, Arial;
            color: #111827;
            background: #ffffff;
            font-size: 12px;
        }}
        h2 {{
            margin: 0 0 10px 0;
            font-size: 18px;
            font-weight: 800;
            color: #111827;
        }}
        .hint {{
            color: #667085;
            margin: 4px 0 12px 0;
        }}
        .summary-grid {{
            margin: 8px 0 12px 0;
        }}
        .summary-grid div {{
            display: inline-block;
            min-width: 118px;
            margin: 0 8px 8px 0;
            padding: 10px;
            border: 1px solid #d6dde8;
            border-radius: 8px;
            background: #f7f9fc;
        }}
        .monitor-card, .version-card {{
            margin: 0 0 10px 0;
            padding: 12px;
            border: 1px solid #d6dde8;
            border-radius: 8px;
            background: #ffffff;
        }}
        .card-title {{
            font-weight: 800;
            font-size: 13px;
            margin-bottom: 6px;
            color: #111827;
        }}
        .badge {{
            color: #0f766e;
            background: #ecfdf8;
            border: 1px solid #99d3ca;
            border-radius: 7px;
            padding: 2px 6px;
            font-weight: 700;
        }}
        .path {{
            color: #344054;
            font-family: Consolas, monospace;
            white-space: normal;
            word-wrap: break-word;
        }}
    </style>
    </head>
    <body>{body}</body>
    </html>
    """

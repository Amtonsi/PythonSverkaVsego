import re
import sys

import pytest
from PySide6.QtWidgets import QApplication, QTableWidget

from file_compare_app.registry.repository import RegistryRepository
from file_compare_app.ui.main_window import MainWindow


def test_main_window_has_registry_mode_layout(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(registry_repository=RegistryRepository.create(tmp_path / "registry.sqlite3"))

    required_objects = [
        "modeCompareButton",
        "modeRegistryButton",
        "registryWorkspace",
        "registryTree",
        "registryObjectTitle",
        "registryFilesTable",
        "registryEventsList",
        "registryMonitoringPanel",
        "registryVersionsPanel",
        "registryNodeCardPanel",
        "registryRisksPanel",
        "registryNodeNameInput",
        "registryNodeCodeInput",
        "registryNodeResponsibleInput",
        "registryNodeDescriptionInput",
        "registryNodeTemplateInput",
        "registryMonitorIntervalInput",
        "registryReviewStatusInput",
        "registryReviewReviewerInput",
        "registryReviewCommentInput",
        "saveRegistryReviewButton",
        "saveRegistryNodeButton",
        "addRegistryFileButton",
        "compareRegistryFileButton",
        "backupRegistryButton",
        "exportRegistryExcelButton",
        "deleteNodeButton",
    ]

    for object_name in required_objects:
        assert window.findChild(object, object_name) is not None

    assert isinstance(window.registry_files_table, QTableWidget)


def test_registry_review_and_risk_widgets_have_light_styles(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow(registry_repository=RegistryRepository.create(tmp_path / "registry.sqlite3"))
    style = window.styleSheet()

    required_selectors = [
        "QFrame#registryNodeFormCard QLabel",
        "QTextEdit#registryRisksPanel",
        "QTextEdit#registryReviewCommentInput",
        "QTextEdit#registryNodeDescriptionInput::placeholder",
        "QLineEdit#registryReviewReviewerInput",
        "QComboBox#registryReviewStatusInput",
        "QComboBox#registryNodeTemplateInput QAbstractItemView",
        "QPushButton#saveRegistryReviewButton",
        "QComboBox#registryNodeTemplateInput",
        "QSpinBox#registryMonitorIntervalInput",
    ]

    for selector in required_selectors:
        assert selector in style


def test_main_window_loads_existing_registry_database_on_startup(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    repository = RegistryRepository.create(tmp_path / "registry.sqlite3")
    root = repository.create_node("Завод")
    repository.create_node("Цех 1", parent_id=root.id)

    window = MainWindow(registry_repository=repository)

    assert window.registry_tree.topLevelItemCount() == 1
    root_item = window.registry_tree.topLevelItem(0)
    assert root_item.text(0) == "Завод"
    assert root_item.childCount() == 1
    assert root_item.child(0).text(0) == "Цех 1"


def test_registry_object_card_can_save_node_fields(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    repository = RegistryRepository.create(tmp_path / "registry.sqlite3")
    node = repository.create_node("Old object", code="OLD")
    window = MainWindow(registry_repository=repository)

    window.select_registry_node(node.id)
    window.registry_node_name_input.setText("Main object")
    window.registry_node_code_input.setText("OBJ-2026")
    window.registry_node_responsible_input.setText("Engineer")
    window.registry_node_description_input.setPlainText("Critical controller")

    assert window.save_selected_registry_node_card() is True

    updated = repository.get_node(node.id)
    assert updated.name == "Main object"
    assert updated.code == "OBJ-2026"
    assert updated.responsible == "Engineer"
    assert updated.description == "Critical controller"
    assert window.registry_object_title.text() == "Main object"
    assert "OBJ-2026" in window.registry_node_card_summary.toPlainText()


def test_registry_object_card_saves_template_and_monitoring_interval(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    repository = RegistryRepository.create(tmp_path / "registry.sqlite3")
    node = repository.create_node("Object")
    window = MainWindow(registry_repository=repository)

    window.select_registry_node(node.id)
    window.registry_node_template_input.setCurrentText("Kaspersky")
    window.registry_monitor_interval_input.setValue(120)

    assert window.save_selected_registry_node_card() is True

    updated = repository.get_node(node.id)
    assert updated.template_key == "kaspersky"
    assert updated.monitor_interval_minutes == 120
    assert "Kaspersky" in window.registry_node_card_summary.toPlainText()


def test_registry_selected_pair_review_can_be_saved(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    repository = RegistryRepository.create(tmp_path / "registry.sqlite3")
    window = MainWindow(registry_repository=repository)
    node = window.create_registry_node("Object")
    before = tmp_path / "running-before.cfg"
    after = tmp_path / "running-after.cfg"
    before.write_text("hostname old", encoding="utf-8")
    after.write_text("hostname new", encoding="utf-8")

    window.select_registry_node(node.id)
    watched = window.add_registry_file_to_selected_context(before)
    window.add_registry_file_to_selected_context(after)
    window.registry_files_table.setCurrentCell(0, 0)
    window.registry_review_status_input.setCurrentText("Согласовано")
    window.registry_review_reviewer_input.setText("Amal")
    window.registry_review_comment_input.setPlainText("Проверено")

    assert window.save_selected_registry_review() is True

    review = repository.get_comparison_review(watched.id, 1, 2)
    assert review.status == "approved"
    assert review.reviewer == "Amal"
    assert review.comment == "Проверено"
    assert "Согласовано" in window.registry_selected_pair_panel.toPlainText()


def test_registry_risks_panel_shows_latest_risky_events(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    repository = RegistryRepository.create(tmp_path / "registry.sqlite3")
    node = repository.create_node("Object")
    watched = repository.create_watched_file(
        node_id=node.id,
        file_path=str(tmp_path / "running.cfg"),
        label="running.cfg",
        file_kind="cfg",
        baseline_hash="old",
        last_hash="new",
        status="changed",
    )
    repository.create_event(
        node_id=node.id,
        watched_file_id=watched.id,
        event_type="changed",
        change_count=3,
        message="changed",
        risk_count=2,
        risk_summary="ACL/firewall rule changed",
    )
    window = MainWindow(registry_repository=repository)

    window.select_registry_node(node.id)

    risk_text = window.registry_risks_panel.toPlainText()
    assert "Риски" in risk_text
    assert "ACL/firewall rule changed" in risk_text


def test_main_window_can_backup_database_and_export_registry_excel(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    repository = RegistryRepository.create(tmp_path / "registry.sqlite3")
    repository.create_node("Object")
    window = MainWindow(registry_repository=repository)

    backup_path = window.backup_registry_database(tmp_path / "manual-backups")
    export_path = window.export_registry_excel(tmp_path / "registry.xlsx")

    assert backup_path is not None
    assert backup_path.parent == tmp_path / "manual-backups"
    assert backup_path.exists()
    assert export_path == tmp_path / "registry.xlsx"
    assert export_path.exists()


def test_registry_selected_file_can_start_compare_with_latest_versions(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    repository = RegistryRepository.create(tmp_path / "registry.sqlite3")
    window = MainWindow(registry_repository=repository)
    node = window.create_registry_node("Object")
    before = tmp_path / "policy.klp"
    after = tmp_path / "policy-new.klp"
    before.write_text("hash=old", encoding="utf-8")
    after.write_text("hash=new", encoding="utf-8")
    window.select_registry_node(node.id)
    window.add_watched_file_pair_to_selected_node(before, after)
    started: list[tuple[str, str]] = []
    window._compare = lambda: started.append((str(window.left_path), str(window.right_path)))  # type: ignore[method-assign]

    assert window.compare_selected_registry_file() is True

    assert window.mode_stack.currentIndex() == 0
    assert started
    left_path, right_path = started[0]
    assert "v0001_policy.klp" in left_path
    assert "v0002_policy-new.klp" in right_path
    assert window.left_file_name.text() == "v0001_policy.klp"
    assert window.right_file_name.text() == "v0002_policy-new.klp"


def test_toolbar_switches_to_compact_layout_for_narrow_window() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()

    window.resize(980, 680)
    window._apply_responsive_toolbar(980)

    assert window.minimumWidth() <= 980
    assert window.privacy_pill.isHidden()
    assert window.add_child_button.text() == "+ Подобъект"
    assert window.add_file_button.text() == "+ Файл"


def test_main_window_creates_and_selects_registry_nodes(tmp_path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.registry_repository = window.registry_repository.create(tmp_path / "registry.sqlite3")
    window.registry_monitor = window.registry_monitor.__class__(window.registry_repository)

    root = window.create_registry_node("Завод №1")
    child = window.create_registry_node("Цех 1", parent_id=root.id)
    window.refresh_registry_tree()
    window.select_registry_node(child.id)

    assert window.selected_registry_node_id == child.id
    assert window.registry_object_title.text() == "Цех 1"
    assert window.registry_tree.topLevelItemCount() == 1


def test_main_window_adds_and_checks_file_for_selected_node(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.registry_repository = window.registry_repository.create(tmp_path / "registry.sqlite3")
    window.registry_monitor = window.registry_monitor.__class__(window.registry_repository)
    node = window.create_registry_node("Линия упаковки")
    file_path = tmp_path / "controller.yaml"
    file_path.write_text("timeout: 30", encoding="utf-8")

    window.select_registry_node(node.id)
    watched = window.add_watched_file_to_selected_node(file_path)
    file_path.write_text("timeout: 45", encoding="utf-8")
    checked = window.check_selected_registry_node()

    assert watched.label == "controller.yaml"
    assert checked[0].status == "changed"
    assert "changed" in window.registry_events_list.item(0).text()


def test_main_window_adds_before_after_as_one_registry_file(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.registry_repository = window.registry_repository.create(tmp_path / "registry.sqlite3")
    window.registry_monitor = window.registry_monitor.__class__(window.registry_repository)
    node = window.create_registry_node("Object")
    before = tmp_path / "policy.klp"
    after = tmp_path / "policy-new.klp"
    before.write_text("hash=old", encoding="utf-8")
    after.write_text("hash=new", encoding="utf-8")

    window.select_registry_node(node.id)
    watched = window.add_watched_file_pair_to_selected_node(before, after)

    versions = window.registry_repository.list_file_versions(watched.id)
    assert len(window.registry_repository.list_watched_files(node.id)) == 1
    assert [version.version_number for version in versions] == [1, 2]
    assert window.registry_files_table.rowCount() == 1
    headers = [
        window.registry_files_table.horizontalHeaderItem(column).text()
        for column in range(window.registry_files_table.columnCount())
    ]
    assert headers == ["ID", "Файл до", "Файл после", "Версии", "Статус", "Загружено"]
    assert window.registry_files_table.item(0, 0).text() == "1"
    assert window.registry_files_table.item(0, 1).text() == "policy.klp"
    assert window.registry_files_table.item(0, 2).text() == "policy-new.klp"
    assert window.registry_files_table.item(0, 3).text() == "v1 -> v2"
    assert re.fullmatch(r"\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}", window.registry_files_table.item(0, 5).text())
    assert "Версий: 2" in window.registry_versions_panel.toPlainText()
    assert "Файлов под контролем" in window.registry_monitoring_panel.toPlainText()
    assert "Текущая версия" in window.registry_monitoring_panel.toPlainText()
    assert "Сверка v1 -> v2" in window.registry_versions_panel.toPlainText()
    assert "Снимок" in window.registry_versions_panel.toPlainText()


def test_main_window_single_file_button_adds_baseline_then_after_versions(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.registry_repository = window.registry_repository.create(tmp_path / "registry.sqlite3")
    window.registry_monitor = window.registry_monitor.__class__(window.registry_repository)
    node = window.create_registry_node("Object")
    before = tmp_path / "policy.klp"
    after = tmp_path / "policy-new.klp"
    next_after = tmp_path / "policy-new-2.klp"
    before.write_text("hash=old", encoding="utf-8")
    after.write_text("hash=new", encoding="utf-8")
    next_after.write_text("hash=latest", encoding="utf-8")

    window.select_registry_node(node.id)
    watched = window.add_registry_file_to_selected_context(before)
    window.registry_files_table.setCurrentCell(0, 0)
    window.add_registry_file_to_selected_context(after)
    window.registry_files_table.setCurrentCell(0, 0)
    updated = window.add_registry_file_to_selected_context(next_after)

    versions = window.registry_repository.list_file_versions(watched.id)
    assert updated.id == watched.id
    assert [version.version_number for version in versions] == [1, 2, 3]
    assert window.registry_files_table.rowCount() == 2
    assert window.registry_files_table.item(0, 0).text() == "1"
    assert window.registry_files_table.item(0, 1).text() == "policy.klp"
    assert window.registry_files_table.item(0, 2).text() == "policy-new.klp"
    assert window.registry_files_table.item(0, 3).text() == "v1 -> v2"
    assert window.registry_files_table.item(1, 0).text() == "2"
    assert window.registry_files_table.item(1, 1).text() == "policy-new.klp"
    assert window.registry_files_table.item(1, 2).text() == "policy-new-2.klp"
    assert window.registry_files_table.item(1, 3).text() == "v2 -> v3"
    assert re.fullmatch(r"\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}", window.registry_files_table.item(1, 5).text())
    assert "v2 -> v3" in window.registry_events_list.item(0).text()
    assert "Версий: 3" in window.registry_versions_panel.toPlainText()
    assert "Сверка v1 -> v2" in window.registry_versions_panel.toPlainText()
    assert "Сверка v2 -> v3" in window.registry_versions_panel.toPlainText()


def test_registry_compare_uses_selected_version_pair_row(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.registry_repository = window.registry_repository.create(tmp_path / "registry.sqlite3")
    window.registry_monitor = window.registry_monitor.__class__(window.registry_repository)
    node = window.create_registry_node("Object")
    before = tmp_path / "policy.klp"
    after = tmp_path / "policy-new.klp"
    next_after = tmp_path / "policy-new-2.klp"
    before.write_text("hash=old", encoding="utf-8")
    after.write_text("hash=new", encoding="utf-8")
    next_after.write_text("hash=latest", encoding="utf-8")
    started: list[tuple[str, str]] = []
    window._compare = lambda: started.append((str(window.left_path), str(window.right_path)))  # type: ignore[method-assign]

    window.select_registry_node(node.id)
    window.add_registry_file_to_selected_context(before)
    window.add_registry_file_to_selected_context(after)
    window.add_registry_file_to_selected_context(next_after)

    window.registry_files_table.setCurrentCell(0, 0)
    assert window.compare_selected_registry_file() is True
    first_left, first_right = started[-1]
    assert "v0001_policy.klp" in first_left
    assert "v0002_policy-new.klp" in first_right

    window._set_mode("registry")
    window.registry_files_table.setCurrentCell(1, 0)
    assert window.compare_selected_registry_file() is True
    second_left, second_right = started[-1]
    assert "v0002_policy-new.klp" in second_left
    assert "v0003_policy-new-2.klp" in second_right


def test_registry_status_cell_uses_color_marking(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.registry_repository = window.registry_repository.create(tmp_path / "registry.sqlite3")
    window.registry_monitor = window.registry_monitor.__class__(window.registry_repository)
    node = window.create_registry_node("Object")
    before = tmp_path / "running-config.cfg"
    after = tmp_path / "running-config-new.cfg"
    before.write_text("hostname old", encoding="utf-8")
    after.write_text("hostname new", encoding="utf-8")

    window.select_registry_node(node.id)
    window.add_registry_file_to_selected_context(before)
    window.add_registry_file_to_selected_context(after)

    status_item = window.registry_files_table.item(0, 4)
    assert status_item.text() == "Изменен"
    assert status_item.foreground().color().name().lower() == "#b54708"
    assert status_item.background().color().name().lower() == "#fffaeb"


def test_registry_search_and_status_filter_file_rows(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.registry_repository = window.registry_repository.create(tmp_path / "registry.sqlite3")
    window.registry_monitor = window.registry_monitor.__class__(window.registry_repository)
    node = window.create_registry_node("Object")
    policy = tmp_path / "policy.klp"
    running = tmp_path / "running-config.cfg"
    running_next = tmp_path / "running-config-new.cfg"
    policy.write_text("hash=old", encoding="utf-8")
    running.write_text("hostname old", encoding="utf-8")
    running_next.write_text("hostname new", encoding="utf-8")

    window.select_registry_node(node.id)
    window.add_watched_file_to_selected_node(policy)
    window.add_watched_file_pair_to_selected_node(running, running_next)

    window.set_registry_search_query("running")
    assert window.registry_files_table.rowCount() == 1
    assert window.registry_files_table.item(0, 1).text() == "running-config.cfg"

    window.set_registry_search_query("")
    window.set_registry_status_filter("changed")
    assert window.registry_files_table.rowCount() == 1
    assert window.registry_files_table.item(0, 4).text() == "Изменен"


def test_registry_empty_files_state_guides_first_upload(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.registry_repository = window.registry_repository.create(tmp_path / "registry.sqlite3")
    window.registry_monitor = window.registry_monitor.__class__(window.registry_repository)
    node = window.create_registry_node("Object")

    window.select_registry_node(node.id)

    assert window.registry_files_stack.currentWidget() == window.registry_files_empty_state
    empty_text = window.registry_files_empty_state.toPlainText()
    assert "Загрузите первый файл" in empty_text
    assert "+ Файл" in empty_text
    assert "базовая версия" in empty_text


def test_registry_selected_pair_card_updates_for_current_row(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.registry_repository = window.registry_repository.create(tmp_path / "registry.sqlite3")
    window.registry_monitor = window.registry_monitor.__class__(window.registry_repository)
    node = window.create_registry_node("Object")
    before = tmp_path / "policy.klp"
    after = tmp_path / "policy-new.klp"
    next_after = tmp_path / "policy-new-2.klp"
    before.write_text("hash=old", encoding="utf-8")
    after.write_text("hash=new", encoding="utf-8")
    next_after.write_text("hash=latest", encoding="utf-8")

    window.select_registry_node(node.id)
    window.add_registry_file_to_selected_context(before)
    window.add_registry_file_to_selected_context(after)
    window.add_registry_file_to_selected_context(next_after)
    window.registry_files_table.setCurrentCell(0, 0)
    first_card = window.registry_selected_pair_panel.toPlainText()

    assert "Выбранная сверка" in first_card
    assert "ID 1" in first_card
    assert "policy.klp" in first_card
    assert "policy-new.klp" in first_card
    assert "v1 -> v2" in first_card
    assert "Изменен" in first_card

    window.registry_files_table.setCurrentCell(1, 0)
    second_card = window.registry_selected_pair_panel.toPlainText()
    assert "ID 2" in second_card
    assert "policy-new.klp" in second_card
    assert "policy-new-2.klp" in second_card
    assert "v2 -> v3" in second_card


def test_registry_monitoring_dashboard_has_status_cards(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.registry_repository = window.registry_repository.create(tmp_path / "registry.sqlite3")
    window.registry_monitor = window.registry_monitor.__class__(window.registry_repository)
    node = window.create_registry_node("Object")
    before = tmp_path / "running-config.cfg"
    after = tmp_path / "running-config-new.cfg"
    before.write_text("hostname old", encoding="utf-8")
    after.write_text("hostname new", encoding="utf-8")

    window.select_registry_node(node.id)
    window.add_registry_file_to_selected_context(before)
    window.add_registry_file_to_selected_context(after)

    monitoring_text = window.registry_monitoring_panel.toPlainText()
    assert "Панель мониторинга" in monitoring_text
    assert "Всего файлов" in monitoring_text
    assert "Изменено" in monitoring_text
    assert "Проблемные файлы" in monitoring_text
    assert "running-config.cfg" in monitoring_text


def test_registry_status_filter_popup_has_visible_items_style() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()

    assert [window.registry_status_filter.itemText(index) for index in range(window.registry_status_filter.count())] == [
        "Все статусы",
        "OK",
        "Изменен",
        "Нет файла",
        "Ошибка",
    ]
    popup = window.registry_status_filter.view()
    assert popup.objectName() == "registryStatusFilterPopup"
    assert "color: #111827" in popup.styleSheet()
    assert "min-height: 30px" in popup.styleSheet()


def test_registry_search_filters_tree_nodes(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    repository = RegistryRepository.create(tmp_path / "registry.sqlite3")
    repository.create_node("Alpha plant")
    repository.create_node("Beta plant")
    window = MainWindow(registry_repository=repository)

    window.set_registry_search_query("beta")

    assert window.registry_tree.topLevelItemCount() == 1
    assert window.registry_tree.topLevelItem(0).text(0) == "Beta plant"


def test_registry_export_selected_file_report(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.registry_repository = window.registry_repository.create(tmp_path / "registry.sqlite3")
    window.registry_monitor = window.registry_monitor.__class__(window.registry_repository)
    node = window.create_registry_node("Object")
    before = tmp_path / "policy.klp"
    after = tmp_path / "policy-new.klp"
    before.write_text("hash=old", encoding="utf-8")
    after.write_text("hash=new", encoding="utf-8")

    window.select_registry_node(node.id)
    window.add_registry_file_to_selected_context(before)
    window.add_registry_file_to_selected_context(after)
    report_path = window.export_selected_registry_report(tmp_path / "registry-report.html")

    assert report_path == tmp_path / "registry-report.html"
    assert report_path.is_file()
    assert "Сравнение файлов - отчет" in report_path.read_text(encoding="utf-8")


def test_registry_file_context_menu_contains_row_actions(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.registry_repository = window.registry_repository.create(tmp_path / "registry.sqlite3")
    window.registry_monitor = window.registry_monitor.__class__(window.registry_repository)
    node = window.create_registry_node("Object")
    before = tmp_path / "policy.klp"
    after = tmp_path / "policy-new.klp"
    before.write_text("hash=old", encoding="utf-8")
    after.write_text("hash=new", encoding="utf-8")

    window.select_registry_node(node.id)
    window.add_registry_file_to_selected_context(before)
    window.add_registry_file_to_selected_context(after)

    menu = window._build_registry_file_context_menu()
    labels = [action.text() for action in menu.actions() if not action.isSeparator()]

    assert labels == ["Сравнить", "Экспорт отчета", "Добавить новую версию", "Проверить файл", "Удалить файл"]
    assert menu.actions()[0].isEnabled()


def test_main_window_deletes_selected_registry_file_from_context(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.registry_repository = window.registry_repository.create(tmp_path / "registry.sqlite3")
    window.registry_monitor = window.registry_monitor.__class__(window.registry_repository)
    node = window.create_registry_node("Object")
    file_path = tmp_path / "policy.klp"
    file_path.write_text("hash=old", encoding="utf-8")

    window.select_registry_node(node.id)
    watched = window.add_registry_file_to_selected_context(file_path)
    deleted = window.delete_selected_registry_file()

    assert deleted is True
    assert window.registry_files_table.rowCount() == 0
    assert window.registry_repository.list_watched_files(node.id) == []
    with pytest.raises(KeyError):
        window.registry_repository.get_watched_file(watched.id)


def test_main_window_deletes_selected_registry_node_with_children(tmp_path) -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.registry_repository = window.registry_repository.create(tmp_path / "registry.sqlite3")
    window.registry_monitor = window.registry_monitor.__class__(window.registry_repository)
    root = window.create_registry_node("Root")
    child = window.create_registry_node("Child", parent_id=root.id)
    grandchild = window.create_registry_node("Grandchild", parent_id=child.id)

    window.select_registry_node(child.id)
    deleted = window.delete_selected_registry_node()

    assert deleted is True
    assert window.selected_registry_node_id == root.id
    assert window.registry_tree.topLevelItemCount() == 1
    assert window.registry_tree.topLevelItem(0).childCount() == 0
    with pytest.raises(KeyError):
        window.registry_repository.get_node(child.id)
    with pytest.raises(KeyError):
        window.registry_repository.get_node(grandchild.id)


def test_registry_mode_keeps_approved_visual_labels() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()

    assert window.mode_registry_button.text() == "▦ Реестр объектов"
    assert window.add_child_button.text() == "+ Подобъект"
    assert window.add_file_button.text() == "+ Файл"
    assert window.check_registry_button.text() == "⟳ Проверить"
    assert window.delete_node_button.text() == "Удалить"

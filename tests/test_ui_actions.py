import asyncio
import json
import os
import sys
from pathlib import Path

import flet as ft
import pytest

import rpa_control_center.ui as ui_module
from rpa_control_center.models import Base
from rpa_control_center.scheduler import list_schedules
from rpa_control_center.service import list_robots, list_runs
from rpa_control_center.store import make_engine
from rpa_control_center.ui import ControlCenterUI


class FakePage:
    def __init__(self):
        self.services = []
        self.theme_mode = ft.ThemeMode.DARK
        self.dialog = None
        self.updated = 0
        self.popped = 0

    def update(self):
        self.updated += 1

    def show_dialog(self, dialog):
        self.dialog = dialog

    def pop_dialog(self):
        self.popped += 1
        self.dialog = None


@pytest.fixture
def ui(tmp_path, monkeypatch):
    monkeypatch.setenv("RCC_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(ui_module, "windows_task_installed", lambda: False)
    engine = make_engine("sqlite:///" + (tmp_path / "ui.db").as_posix())
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.exec_driver_sql("INSERT INTO alembic_version VALUES ('0005_schedules')")
    app = ControlCenterUI(FakePage(), engine)
    app.refresh(update_page=False)
    yield app
    engine.dispose()


def run(awaitable):
    return asyncio.run(awaitable)


def dialog_action(app, label):
    for action in app.page.dialog.actions:
        if action.content == label:
            return action.on_click
    raise AssertionError(f"Ação não encontrada: {label}")


def walk_controls(control):
    yield control
    for attr in ("content", "label"):
        child = getattr(control, attr, None)
        if isinstance(child, ft.BaseControl):
            yield from walk_controls(child)
    for attr in ("controls", "actions", "rows", "cells"):
        for child in getattr(control, attr, None) or []:
            if isinstance(child, ft.BaseControl):
                yield from walk_controls(child)


def test_all_static_buttons_are_wired(ui):
    controls = list(walk_controls(ui.build()))
    labels = {
        control.content
        for control in controls
        if isinstance(control, (ft.Button, ft.TextButton)) and isinstance(control.content, str)
    }
    tooltips = {
        control.tooltip
        for control in controls
        if isinstance(control, ft.IconButton) and control.tooltip
    }
    expected_labels = {
        "Executar fila", "Atualizar", "Cadastrar", "Cancelar edição",
        "Abrir pasta de logs", "Limpar antigos", "Exportar cadastros",
        "Importar cadastros", "Backup SQLite", "Restaurar SQLite", "Agendar",
        "Instalar gatilho global", "Abrir Agendador", "Remover gatilho global",
    }
    expected_tooltips = {
        "Usar tema claro", "Selecionar arquivo principal", "Selecionar executável",
        "Selecionar pasta", "Remover todos os robôs", "Limpar histórico",
        "Limpar Filtros", "Página Anterior", "Próxima Página",
    }

    assert expected_labels <= labels
    assert expected_tooltips <= tooltips
    for control in controls:
        if isinstance(control, (ft.Button, ft.TextButton, ft.IconButton)):
            assert control.on_click is not None


def test_header_filters_pagination_and_form_buttons(ui):
    ui.toggle_theme()
    assert ui.page.theme_mode == ft.ThemeMode.LIGHT
    ui.toggle_theme()
    assert ui.page.theme_mode == ft.ThemeMode.DARK

    ui.executor_type.value = "executable"
    ui.change_executor()
    assert ui.launcher.disabled
    ui.executor_type.value = "python"
    ui.change_executor()
    assert not ui.launcher.disabled

    ui.schedule_frequency.value = "weekly"
    ui.change_schedule_frequency()
    assert not ui.schedule_weekday.disabled
    ui.schedule_frequency.value = "custom"
    ui.change_schedule_frequency()
    assert ui.schedule_custom_days.visible

    ui.robot_search.value = "abc"
    ui.run_search.value = "def"
    ui.run_state_filter.value = "failed"
    ui.run_business_filter.value = "business_error"
    run(ui.clear_filters())
    assert (ui.robot_search.value, ui.run_search.value) == ("", "")

    ui.history_page = 2
    run(ui.prev_page())
    assert ui.history_page == 1
    ui.history_total = 60
    original_refresh = ui.refresh
    ui.refresh = lambda *_args, **_kwargs: None
    run(ui.next_page())
    assert ui.history_page == 2
    ui.refresh = original_refresh
    run(ui.refresh_click())
    assert ui.status.value == "Dados atualizados"

    ui.editing_robot_id = "x"
    run(ui.cancel_edit())
    assert ui.editing_robot_id is None
    assert ui.status.value == "Edição cancelada"


def test_robot_queue_play_stop_logs_edit_and_removal_buttons(ui, tmp_path):
    script = tmp_path / "robot.py"
    script.write_text('print(\'{"status":"success"}\')', encoding="utf-8")
    ui.name.value = "Robô teste"
    ui.target.value = str(script)
    ui.launcher.value = sys.executable
    ui.cwd.value = str(tmp_path)
    run(ui.save_robot())

    robot = list_robots(ui.engine)[0]
    assert ui.status.value.startswith("Automação cadastrada:")

    run(ui.edit_handler(robot)())
    assert ui.editing_robot_id == robot.id
    assert ui.save_button.content == "Salvar alterações"
    run(ui.cancel_edit())

    run(ui.enqueue_handler(robot.id, robot.name)())
    queued, _ = list_runs(ui.engine, state="queued")
    assert len(queued) == 1
    run(ui.execute_queue())
    completed, _ = list_runs(ui.engine, state="completed")
    assert len(completed) == 1

    run(ui.logs_handler(completed[0])())
    assert ui.selected_run_id == completed[0].id
    assert "STDOUT" in ui.log_content.value

    run(ui.execute_now_handler(robot.id, robot.name)())
    completed, _ = list_runs(ui.engine, state="completed")
    assert len(completed) == 2

    run(ui.toggle_robot_handler(robot.id, robot.name, False)())
    assert not list_robots(ui.engine)[0].active
    run(ui.toggle_robot_handler(robot.id, robot.name, True)())
    assert list_robots(ui.engine)[0].active

    run(ui.enqueue_handler(robot.id, robot.name)())
    queued, _ = list_runs(ui.engine, state="queued")
    run(ui.cancel_handler(queued[0].id)())
    cancelled, _ = list_runs(ui.engine, state="cancelled")
    assert cancelled

    run(ui.confirm_remove_run(completed[0].id)())
    run(dialog_action(ui, "Remover")())
    assert all(item.id != completed[0].id for item in list_runs(ui.engine)[0])

    robot = list_robots(ui.engine)[0]
    run(ui.confirm_remove_robot(robot.id, robot.name)())
    run(dialog_action(ui, "Remover")())
    assert list_robots(ui.engine) == []


def test_schedule_and_windows_trigger_buttons(ui, tmp_path, monkeypatch):
    script = tmp_path / "robot.py"
    script.write_text("print('ok')", encoding="utf-8")
    ui.name.value = "Agendado"
    ui.target.value = str(script)
    ui.launcher.value = sys.executable
    ui.cwd.value = str(tmp_path)
    run(ui.save_robot())
    robot = list_robots(ui.engine)[0]

    ui.schedule_robot.value = robot.id
    ui.schedule_frequency.value = "daily"
    ui.schedule_time.value = "08:30"
    run(ui.save_schedule())
    schedule = list_schedules(ui.engine)[0][0]
    run(ui.toggle_schedule_handler(schedule.id, False)())
    assert not list_schedules(ui.engine)[0][0].active
    run(ui.toggle_schedule_handler(schedule.id, True)())
    run(ui.remove_schedule_handler(schedule.id)())
    assert list_schedules(ui.engine) == []

    calls = []
    monkeypatch.setattr(ui_module, "install_windows_task", lambda root: calls.append(("install", root)))
    monkeypatch.setattr(ui_module, "remove_windows_task", lambda: calls.append(("remove", None)))
    monkeypatch.setattr(ui_module, "open_windows_task_scheduler", lambda: calls.append(("open", None)))

    run(ui.install_windows_task_click())
    assert ui.install_task_button.disabled
    run(ui.open_windows_task_scheduler_click())
    run(ui.confirm_remove_windows_task())
    run(dialog_action(ui, "Remover gatilho")())
    assert [call[0] for call in calls] == ["install", "open", "remove"]
    assert ui.remove_task_button.disabled
    assert not ui.install_task_button.disabled


def test_maintenance_and_bulk_action_buttons(ui, tmp_path, monkeypatch):
    script = tmp_path / "robot.py"
    script.write_text("print('ok')", encoding="utf-8")
    ui.name.value = "Portável"
    ui.target.value = str(script)
    ui.launcher.value = sys.executable
    ui.cwd.value = str(tmp_path)
    run(ui.save_robot())

    save_targets = iter([tmp_path / "robots.json", tmp_path / "backup.db"])

    async def pick_save(*_args, **_kwargs):
        return next(save_targets)

    async def pick_open_json(*_args, **_kwargs):
        return tmp_path / "robots.json"

    monkeypatch.setattr(ui, "_pick_save_file", pick_save)
    monkeypatch.setattr(ui, "_pick_open_file", pick_open_json)
    run(ui.export_robots_click())
    assert (tmp_path / "robots.json").exists()
    run(ui.backup_sqlite_click())
    assert (tmp_path / "backup.db").exists()

    run(ui.import_robots_click())
    dialog_action(ui, "Importar")()
    assert ui.status.value.startswith("Importação concluída:")

    async def pick_open_db(*_args, **_kwargs):
        return tmp_path / "backup.db"

    monkeypatch.setattr(ui, "_pick_open_file", pick_open_db)
    run(ui.restore_sqlite_click())
    dialog_action(ui, "Restaurar")()
    assert ui.status.value == "Banco SQLite restaurado com sucesso."

    ui.retention_days.value = "60"
    run(ui.confirm_purge_old_runs())
    dialog_action(ui, "Limpar antigos")()
    assert ui.status.value.startswith("Retenção aplicada:")

    monkeypatch.setattr(os, "startfile", lambda path: setattr(ui, "opened_logs", path))
    ui.open_logs_folder()
    assert Path(ui.opened_logs).exists()

    run(ui.confirm_clear_history())
    dialog_action(ui, "Limpar Histórico")()
    assert list_runs(ui.engine)[1] == 0
    run(ui.confirm_clear_robots())
    dialog_action(ui, "Limpar Tudo")()
    assert list_robots(ui.engine) == []

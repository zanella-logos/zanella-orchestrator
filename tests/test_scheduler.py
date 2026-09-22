from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from rpa_control_center.models import Base, Run, Schedule
from rpa_control_center.scheduler import (
    add_schedule, enqueue_due_schedules, list_schedules, next_occurrence,
    remove_schedule, set_schedule_active, weekday_mask, weekdays_from_mask,
)
from rpa_control_center.service import add_robot
from rpa_control_center.store import make_engine
import rpa_control_center.scheduler as scheduler_module


def create_database(tmp_path: Path):
    engine = make_engine("sqlite:///" + (tmp_path / "scheduler.db").as_posix())
    Base.metadata.create_all(engine)
    robot_id = add_robot(
        engine, "Scheduled Robot", "robot.py", "python.exe", str(tmp_path), [], 30, "python"
    )
    return engine, robot_id


def test_next_occurrence_daily_and_weekly():
    monday = datetime(2026, 9, 21, 9, 0).timestamp()
    assert datetime.fromtimestamp(next_occurrence("daily", "08:00", None, monday)) == datetime(2026, 9, 22, 8, 0)
    assert datetime.fromtimestamp(next_occurrence("weekly", "10:30", 2, monday)) == datetime(2026, 9, 23, 10, 30)


def test_custom_weekdays_and_business_days():
    business_days = weekday_mask([0, 1, 2, 3, 4])
    assert weekdays_from_mask(business_days) == [0, 1, 2, 3, 4]
    friday = datetime(2026, 9, 25, 18, 0).timestamp()
    next_run = next_occurrence("custom", "08:00", business_days, friday)
    assert datetime.fromtimestamp(next_run) == datetime(2026, 9, 28, 8, 0)


def test_custom_requires_at_least_one_weekday():
    after = datetime(2026, 9, 21, 9, 0).timestamp()
    with pytest.raises(ValueError, match="ao menos um dia"):
        next_occurrence("custom", "08:00", 0, after)


def test_schedule_lifecycle(tmp_path):
    engine, robot_id = create_database(tmp_path)
    schedule_id = add_schedule(engine, robot_id, "weekly", "08:15", 4)
    rows = list_schedules(engine)
    assert len(rows) == 1
    assert rows[0][0].id == schedule_id
    assert rows[0][1] == "Scheduled Robot"

    set_schedule_active(engine, schedule_id, False)
    assert list_schedules(engine)[0][0].active is False
    set_schedule_active(engine, schedule_id, True)
    assert list_schedules(engine)[0][0].active is True
    remove_schedule(engine, schedule_id)
    assert list_schedules(engine) == []
    engine.dispose()


def test_due_schedule_creates_only_one_run(tmp_path):
    engine, robot_id = create_database(tmp_path)
    schedule_id = add_schedule(engine, robot_id, "daily", "08:00", None)
    due_at = datetime(2026, 9, 18, 8, 0).timestamp()
    tick_at = datetime(2026, 9, 18, 8, 1).timestamp()
    with Session(engine) as session, session.begin():
        schedule = session.get(Schedule, schedule_id)
        schedule.next_run_at = due_at

    assert enqueue_due_schedules(engine, tick_at) == 1
    assert enqueue_due_schedules(engine, tick_at) == 0
    with Session(engine) as session:
        runs = list(session.scalars(select(Run)))
        schedule = session.get(Schedule, schedule_id)
        assert len(runs) == 1
        assert runs[0].robot_id == robot_id
        assert schedule.last_run_at == due_at
        assert schedule.next_run_at > tick_at
    engine.dispose()


def test_windows_task_installer_uses_hidden_five_minute_trigger(tmp_path, monkeypatch):
    rcc_path = tmp_path / "Scripts" / "rcc.exe"
    rcc_path.parent.mkdir()
    rcc_path.touch()
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(scheduler_module, "scheduler_cli_path", lambda: rcc_path)
    monkeypatch.setattr(scheduler_module, "application_data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(scheduler_module.subprocess, "run", fake_run)
    (tmp_path / "data").mkdir()

    scheduler_module.install_windows_task(tmp_path / "project")

    command = captured["command"]
    assert command[:2] == ["schtasks.exe", "/Create"]
    assert ["/SC", "MINUTE", "/MO", "5"] == command[4:8]
    assert "/IT" in command and "/RU" not in command
    assert "wscript.exe //B //NoLogo" in command[command.index("/TR") + 1]
    runner = (tmp_path / "data" / "run-scheduler.vbs").read_text(encoding="utf-8")
    assert str(rcc_path) in runner
    assert "scheduler" in runner
    assert "shell.Run" in runner and ", 0, True" in runner


def test_packaged_task_runs_app_in_scheduler_mode(tmp_path, monkeypatch):
    install_root = tmp_path / "Zanella Orchestrator"
    package_dir = install_root / "app" / "src" / "rpa_control_center"
    package_dir.mkdir(parents=True)
    packaged_exe = install_root / "Zanella-Orchestrator.exe"
    packaged_exe.touch()
    monkeypatch.setenv("FLET_APP_STORAGE_DATA", str(tmp_path / "data"))
    monkeypatch.setattr(scheduler_module, "__file__", str(package_dir / "scheduler.py"))
    monkeypatch.setattr(scheduler_module, "application_data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(
        scheduler_module.subprocess, "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    (tmp_path / "data").mkdir()

    scheduler_module.install_windows_task(tmp_path / "project")

    runner = (tmp_path / "data" / "run-scheduler.vbs").read_text(encoding="utf-8")
    assert str(packaged_exe) in runner
    assert 'shell.Environment("PROCESS")("RCC_SCHEDULER_MODE") = "1"' in runner
    assert '" scheduler' not in runner


def test_remove_windows_task_deletes_task_and_runner(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    hidden_runner = data_dir / "run-scheduler.vbs"
    hidden_runner.write_text("test", encoding="utf-8")
    legacy_runner = data_dir / "run-scheduler.cmd"
    legacy_runner.write_text("test", encoding="utf-8")
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(scheduler_module, "application_data_dir", lambda: data_dir)
    monkeypatch.setattr(scheduler_module.subprocess, "run", fake_run)

    scheduler_module.remove_windows_task()

    assert captured["command"] == [
        "schtasks.exe", "/Delete", "/TN", scheduler_module.TASK_NAME, "/F"
    ]
    assert not hidden_runner.exists()
    assert not legacy_runner.exists()


def test_open_windows_task_scheduler(monkeypatch):
    captured = []
    monkeypatch.setattr(scheduler_module.os, "startfile", captured.append)

    scheduler_module.open_windows_task_scheduler()

    assert captured == ["taskschd.msc"]

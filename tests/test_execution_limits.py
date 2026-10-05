import json
import sys
import threading
import time

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from rpa_control_center.database import upgrade_database
from rpa_control_center.engine import execute_run
from rpa_control_center.maintenance import export_robots, import_robots, remove_execution_limits, restore_sqlite
from rpa_control_center.models import Robot, Run, Schedule
from rpa_control_center.service import add_robot, cancel, enqueue, validate_execution_limit
from rpa_control_center.store import claim_next, make_engine
from rpa_control_center.cli import parser


def database(tmp_path):
    url = "sqlite:///" + (tmp_path / "control_center.db").as_posix()
    upgrade_database(url)
    return make_engine(url)


def test_rc5_migration_preserves_limits_history_and_schedules(tmp_path):
    url = "sqlite:///" + (tmp_path / "control_center.db").as_posix()
    config = Config("alembic.ini")
    config.attributes["database_url"] = url
    command.upgrade(config, "0005")
    engine = make_engine(url)
    robot_id = add_robot(engine, "Legacy", "main.py", sys.executable, str(tmp_path), [], 300)
    run_id = enqueue(engine, robot_id)
    with Session(engine) as session, session.begin():
        session.add(Schedule(robot_id=robot_id, frequency="daily", time_of_day="08:00", next_run_at=10))
    engine.dispose()
    upgrade_database(url)
    engine = make_engine(url)
    with Session(engine) as session:
        assert session.get(Robot, robot_id).timeout == 300
        assert session.get(Run, run_id).configuration["timeout"] == 300
        assert session.scalar(select(Schedule.robot_id)) == robot_id
    assert next(column for column in inspect(engine).get_columns("robots") if column["name"] == "timeout")["nullable"]
    backups = list(tmp_path.glob("*.before-rc6-*.bak"))
    assert len(backups) == 1
    upgrade_database(url)
    assert list(tmp_path.glob("*.before-rc6-*.bak")) == backups
    add_robot(engine, "Unlimited", "main.py", sys.executable, str(tmp_path), [])
    engine.dispose()


def test_explicit_removal_backs_up_updates_queue_preserves_history(tmp_path):
    engine = database(tmp_path)
    robot_id = add_robot(engine, "Legacy", "main.py", sys.executable, str(tmp_path), [], 300)
    queued_id = enqueue(engine, robot_id)
    with Session(engine) as session, session.begin():
        past = Run(robot_id=robot_id, configuration={"timeout": 300}, state="timed_out")
        session.add(past)
        session.flush()
        past_id = past.id
    backup = tmp_path / "backup"
    assert remove_execution_limits(engine, backup)[:2] == (1, 1)
    assert json.loads((backup / "cadastros.json").read_text())["robots"][0]["timeout"] == 300
    assert (backup / "control_center.db").is_file()
    assert json.loads((backup / "fila.json").read_text())[0]["configuration"]["timeout"] == 300
    with Session(engine) as session:
        assert session.get(Robot, robot_id).timeout is None
        assert session.get(Run, queued_id).configuration["timeout"] is None
        assert session.get(Run, past_id).configuration["timeout"] == 300
        assert session.get(Run, past_id).state == "timed_out"
    assert remove_execution_limits(engine, tmp_path / "backup2")[:2] == (0, 0)
    exported = tmp_path / "export.json"
    export_robots(engine, exported)
    cancel(engine, queued_id)
    assert import_robots(engine, exported) == (0, 1)
    with Session(engine) as session:
        assert session.get(Robot, robot_id).timeout is None
    engine.dispose()


def test_remove_limits_refuses_active_run(tmp_path):
    engine = database(tmp_path)
    robot_id = add_robot(engine, "Busy", "main.py", sys.executable, str(tmp_path), [], 300)
    run_id = enqueue(engine, robot_id)
    claim_next(engine)
    with pytest.raises(ValueError, match="Aguarde"):
        remove_execution_limits(engine, tmp_path / "backup")
    with Session(engine) as session:
        assert session.get(Robot, robot_id).timeout == 300
        assert session.get(Run, run_id).configuration["timeout"] == 300
    engine.dispose()


def test_unlimited_execution_completes_and_can_be_cancelled(tmp_path):
    engine = database(tmp_path)
    script = tmp_path / "robot.py"
    script.write_text("import time; time.sleep(0.5); print('done')")
    robot_id = add_robot(engine, "Unlimited", str(script), sys.executable, str(tmp_path), [])
    run_id = enqueue(engine, robot_id)
    claim_next(engine)
    assert execute_run(engine, run_id, tmp_path / "logs") == "completed"
    script.write_text("import time; time.sleep(60)")
    run_id = enqueue(engine, robot_id)
    claim_next(engine)
    thread = threading.Thread(target=execute_run, args=(engine, run_id, tmp_path / "logs"))
    thread.start()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with Session(engine) as session:
            if session.get(Run, run_id).state == "running":
                break
        time.sleep(0.05)
    cancel(engine, run_id)
    thread.join(10)
    assert not thread.is_alive()
    with Session(engine) as session:
        assert session.get(Run, run_id).state == "cancelled"
    engine.dispose()


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan"), True, "300"])
def test_invalid_execution_limit_rejected(value):
    with pytest.raises(ValueError):
        validate_execution_limit(value)


def test_cli_defaults_to_unlimited_and_keeps_legacy_option():
    assert parser().parse_args(["robot-add", "A", "a.py"]).timeout is None
    assert parser().parse_args(["robot-add", "A", "a.py", "--max-execution-seconds", "300"]).timeout == 300
    assert parser().parse_args(["robot-add", "A", "a.py", "--timeout", "300"]).timeout == 300


def test_backup_failure_does_not_remove_limits(tmp_path, monkeypatch):
    import rpa_control_center.maintenance as maintenance
    engine = database(tmp_path)
    robot_id = add_robot(engine, "Legacy", "main.py", sys.executable, str(tmp_path), [], 300)
    run_id = enqueue(engine, robot_id)
    def fail_backup(*_):
        raise OSError("Backup failed")
    monkeypatch.setattr(maintenance, "backup_sqlite", fail_backup)
    with pytest.raises(OSError, match="Backup failed"):
        remove_execution_limits(engine, tmp_path / "backup")
    with Session(engine) as session:
        assert session.get(Robot, robot_id).timeout == 300
        assert session.get(Run, run_id).configuration["timeout"] == 300
    engine.dispose()


def test_restoring_rc5_backup_upgrades_schema_without_removing_limits(tmp_path):
    legacy = tmp_path / "legacy.db"
    url = "sqlite:///" + legacy.as_posix()
    config = Config("alembic.ini")
    config.attributes["database_url"] = url
    command.upgrade(config, "0005")
    old_engine = make_engine(url)
    robot_id = add_robot(old_engine, "Legacy", "main.py", sys.executable, str(tmp_path), [], 300)
    old_engine.dispose()
    engine = database(tmp_path)
    restore_sqlite(engine, legacy)
    with Session(engine) as session:
        assert session.get(Robot, robot_id).timeout == 300
    assert remove_execution_limits(engine, tmp_path / "backup")[:2] == (1, 0)
    engine.dispose()

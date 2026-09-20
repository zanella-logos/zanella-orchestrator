import json
from pathlib import Path
import time

import pytest
from sqlalchemy.orm import Session

from rpa_control_center.maintenance import (
    backup_sqlite, export_robots, import_robots, purge_old_runs, restore_sqlite,
)
from rpa_control_center.models import Base, Robot, Run
from rpa_control_center.service import add_robot, list_robots
from rpa_control_center.store import make_engine


def create_database(tmp_path: Path):
    engine = make_engine("sqlite:///" + (tmp_path / "control-center.db").as_posix())
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        connection.exec_driver_sql("INSERT INTO alembic_version VALUES ('0004_robot_active')")
    robot_id = add_robot(
        engine, "Robot A", "robot.py", "python.exe", str(tmp_path), ["--demo"], 30, "python"
    )
    return engine, robot_id


def test_export_and_import_robot_configurations(tmp_path):
    engine, _ = create_database(tmp_path)
    export_path = tmp_path / "robots.json"

    assert export_robots(engine, export_path) == 1
    payload = json.loads(export_path.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert "password" not in export_path.read_text(encoding="utf-8").lower()

    payload["robots"][0]["timeout"] = 90
    payload["robots"].append({**payload["robots"][0], "name": "Robot B"})
    export_path.write_text(json.dumps(payload), encoding="utf-8")
    assert import_robots(engine, export_path) == (1, 1)

    robots = list_robots(engine)
    assert [robot.name for robot in robots] == ["Robot A", "Robot B"]
    assert robots[0].timeout == 90
    engine.dispose()


def test_retention_removes_only_old_final_runs_and_logs(tmp_path):
    engine, robot_id = create_database(tmp_path)
    old_id, recent_id = "old-run", "recent-run"
    with Session(engine) as session, session.begin():
        session.add_all([
            Run(
                id=old_id, robot_id=robot_id, configuration={}, state="completed",
                created_at=time.time() - 100 * 86_400, ended_at=time.time() - 100 * 86_400,
            ),
            Run(id=recent_id, robot_id=robot_id, configuration={}, state="completed"),
        ])
    logs_root = tmp_path / "logs"
    (logs_root / old_id).mkdir(parents=True)
    (logs_root / old_id / "stdout.log").write_text("old", encoding="utf-8")

    assert purge_old_runs(engine, logs_root, 60) == (1, 0)
    with Session(engine) as session:
        assert session.get(Run, old_id) is None
        assert session.get(Run, recent_id) is not None
    assert not (logs_root / old_id).exists()
    engine.dispose()


def test_destructive_maintenance_rejects_active_runs(tmp_path):
    engine, robot_id = create_database(tmp_path)
    with Session(engine) as session, session.begin():
        session.add(Run(robot_id=robot_id, configuration={}, state="queued"))

    with pytest.raises(ValueError, match="ativas ou na fila"):
        purge_old_runs(engine, tmp_path / "logs", 60)
    with pytest.raises(ValueError, match="ativas ou na fila"):
        import_robots(engine, tmp_path / "missing.json")
    engine.dispose()


def test_sqlite_backup_and_restore(tmp_path):
    engine, _ = create_database(tmp_path)
    backup_path = tmp_path / "backup.db"
    assert backup_sqlite(engine, backup_path) == backup_path.resolve()

    add_robot(engine, "Robot B", "b.py", "python.exe", str(tmp_path), [], 30, "python")
    assert len(list_robots(engine)) == 2
    restore_sqlite(engine, backup_path)

    assert [robot.name for robot in list_robots(engine)] == ["Robot A"]
    engine.dispose()

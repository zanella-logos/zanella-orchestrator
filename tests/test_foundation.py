import multiprocessing
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

from alembic import command
from alembic.config import Config
import psutil
import pytest
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from rpa_control_center.database import application_data_dir, database_url
from rpa_control_center.models import Robot, Run
from rpa_control_center.store import claim_next, make_engine
from rpa_control_center.windows import InstallationLock, ProcessTree


def test_scheduler_uses_explicit_data_dir_for_database_config(tmp_path, monkeypatch):
    data_dir = tmp_path / "scheduler-data"
    data_dir.mkdir()
    (data_dir / "config.toml").write_text(
        f'[database]\nbackend = "sqlite"\nsqlite_path = "{(data_dir / "configured.db").as_posix()}"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("RCC_DATA_DIR", str(data_dir))
    monkeypatch.setenv("FLET_APP_STORAGE_DATA", str(tmp_path / "other-flet-data"))

    assert database_url() == "sqlite:///" + (data_dir / "configured.db").as_posix()


def test_packaged_data_migrates_from_legacy_company(tmp_path, monkeypatch):
    legacy = tmp_path / "roaming" / "Victor César Zanella" / "Zanella Orchestrator" / "data"
    legacy.mkdir(parents=True)
    old_db = legacy / "control_center.db"
    import sqlite3
    with sqlite3.connect(old_db) as connection:
        connection.execute("CREATE TABLE marker (value TEXT)")
        connection.execute("INSERT INTO marker VALUES ('preserved')")
    (legacy / "config.toml").write_text('[database]\nbackend = "sqlite"\n', encoding="utf-8")
    (legacy / "logs").mkdir()
    (legacy / "logs" / "run.log").write_text("old log", encoding="utf-8")
    new_data = tmp_path / "roaming" / "Zanella" / "Zanella Orchestrator" / "data"
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("FLET_APP_STORAGE_DATA", str(new_data))
    monkeypatch.delenv("RCC_DATA_DIR", raising=False)

    assert application_data_dir() == new_data
    with sqlite3.connect(new_data / "control_center.db") as connection:
        assert connection.execute("SELECT value FROM marker").fetchone() == ("preserved",)
    assert (new_data / "logs" / "run.log").read_text(encoding="utf-8") == "old log"
    assert (new_data / "config.toml").exists()
    assert old_db.exists()


def claim_worker(url, barrier, output):
    engine = make_engine(url)
    barrier.wait(timeout=20)
    output.put(claim_next(engine))
    engine.dispose()


def lock_worker(key, output):
    try:
        with InstallationLock(key):
            output.put(True)
    except RuntimeError:
        output.put(False)


def test_mutex_excludes_other_process():
    key = str(uuid.uuid4())
    context = multiprocessing.get_context("spawn")
    output = context.Queue()
    with InstallationLock(key):
        child = context.Process(target=lock_worker, args=(key, output))
        child.start()
        assert output.get(timeout=20) is False
        child.join(20)
        assert child.exitcode == 0
    with InstallationLock(key):
        pass


@pytest.mark.parametrize("backend", ["sqlite", "postgresql"])
def test_migration_and_concurrent_claim(tmp_path, monkeypatch, backend):
    url = "sqlite:///" + (tmp_path / "queue.db").as_posix()
    config = Config("alembic.ini")
    if backend == "postgresql":
        url = os.environ.get("RCC_TEST_POSTGRES_URL")
        if not url:
            pytest.skip("Requires an empty disposable PostgreSQL test database")
        check_engine = make_engine(url)
        try:
            assert check_engine.dialect.name == "postgresql"
            with check_engine.connect() as connection:
                database, owner = connection.exec_driver_sql(
                    "SELECT current_database(), pg_get_userbyid(datdba) "
                    "FROM pg_database WHERE datname = current_database()"
                ).one()
            assert database == "rpa_control_center_test"
            assert owner == "rcc_app"
        finally:
            check_engine.dispose()
    monkeypatch.setenv("RCC_DATABASE_URL", url)
    if backend == "postgresql":
        # This database is provisioned exclusively for destructive migration tests.
        command.downgrade(config, "base")
        reset_engine = make_engine(url)
        try:
            remaining = set(inspect(reset_engine).get_table_names())
            assert not ({"robots", "runs"} & remaining)
        finally:
            reset_engine.dispose()
    command.upgrade(config, "head")
    engine = make_engine(url)
    with Session(engine) as session, session.begin():
        robot = Robot(name="Fictício", script="demo.py", interpreter=sys.executable, cwd=str(tmp_path))
        session.add(robot)
        session.flush()
        run = Run(robot_id=robot.id, configuration={"name": robot.name})
        session.add(run)
        session.flush()
        run_id = run.id
    context = multiprocessing.get_context("spawn")
    barrier, output = context.Barrier(2), context.Queue()
    children = [context.Process(target=claim_worker, args=(url, barrier, output)) for _ in range(2)]
    for child in children:
        child.start()
    results = [output.get(timeout=30) for _ in children]
    for child in children:
        child.join(20)
        assert child.exitcode == 0
    assert results.count(run_id) == 1
    assert results.count(None) == 1
    with Session(engine) as session:
        assert session.scalar(select(Run.state)) == "starting"
    engine.dispose()
    command.downgrade(config, "base")
    command.upgrade(config, "head")


def wait_until(predicate):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("Condition not reached before deadline")


def test_job_terminates_descendants(tmp_path):
    child_code = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); time.sleep(60)"
    code = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child_code!r}]); time.sleep(60)"
    with ProcessTree([sys.executable, "-c", code], str(tmp_path)) as tree:
        wait_until(lambda: len(psutil.Process(tree.pid).children(recursive=True)) >= 3)
        children = psutil.Process(tree.pid).children(recursive=True)
        tree.stop()
        wait_until(lambda: tree.active_count() == 0)
        wait_until(lambda: all(not child.is_running() for child in children))


def test_motor_crash_closes_job(tmp_path):
    marker = tmp_path / "pid.txt"
    fixture = Path(__file__).parent / "fixtures" / "crash_owner.py"
    owner = subprocess.Popen([sys.executable, str(fixture), str(marker)])
    try:
        wait_until(lambda: marker.exists() and marker.read_text().strip())
        pid = int(marker.read_text())
        owned = psutil.Process(pid)
        owner.kill()
        owner.wait(timeout=10)
        wait_until(lambda: not owned.is_running())
    finally:
        if owner.poll() is None:
            owner.kill()
            owner.wait(timeout=10)

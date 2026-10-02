import time
import threading

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

import rpa_control_center.engine as engine_module
from rpa_control_center.models import Base, Run, Schedule
from rpa_control_center.scheduler import add_schedule, parse_task_interval, run_scheduler
from rpa_control_center.service import add_robot, enqueue
from rpa_control_center.store import make_engine


@pytest.mark.parametrize("value", ["", "0", "00", "60", "100", "-7", "+7", "7.0", "7,0", " 7", "7 ", "a7", "٧", "０７"])
def test_interval_rejects_invalid_input(value):
    with pytest.raises(ValueError, match="1 a 59"):
        parse_task_interval(value)


def test_running_queue_collects_new_manual_and_due_work_without_next_trigger(tmp_path, monkeypatch):
    engine = make_engine("sqlite:///" + (tmp_path / "continuous.db").as_posix())
    Base.metadata.create_all(engine)
    robots = [add_robot(engine, name, "test.py", "python.exe", str(tmp_path), [], 30, "python")
              for name in ["X", "Y", "Manual", "Scheduled"]]
    first, second = [enqueue(engine, robot) for robot in robots[:2]]
    schedule_id = add_schedule(engine, robots[3], "daily", "08:00", None)
    order = []

    def execute(database, run_id, logs):
        with Session(database) as session, session.begin():
            run = session.get(Run, run_id)
            order.append(run.robot_id)
            run.state = "completed"
            if run_id == first:
                session.get(Schedule, schedule_id).next_run_at = time.time() - 1
        if run_id == first:
            enqueue(database, robots[2])
            # A second worker cannot claim runs while this worker owns the installation.
            results = []

            def competing_worker():
                results.append(run_scheduler(database, logs, "continuous-test"))

            worker = threading.Thread(target=competing_worker)
            worker.start()
            worker.join(timeout=5)
            assert not worker.is_alive()
            assert results == [(0, 0)]
        return "completed"

    monkeypatch.setattr(engine_module, "execute_run", execute)
    assert run_scheduler(engine, tmp_path / "logs", "continuous-test") == (1, 4)
    assert order == robots
    assert run_scheduler(engine, tmp_path / "logs", "continuous-test") == (0, 0)
    with Session(engine) as session:
        assert len(list(session.scalars(select(Run)))) == 4
    engine.dispose()

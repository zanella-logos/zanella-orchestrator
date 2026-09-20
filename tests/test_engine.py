import json
from pathlib import Path
import sys
import threading
import time

import pytest
from sqlalchemy.orm import Session

from rpa_control_center.engine import execute_run, run_engine
from rpa_control_center.executors import build_command
from rpa_control_center.models import Base, Robot, Run
from rpa_control_center.service import (
    cancel, enqueue, list_robots, remove_robot, remove_run, set_robot_active, update_robot,
)
from rpa_control_center.store import claim_next, make_engine


def create_run(tmp_path: Path, source: str, timeout: float = 10, executor_type: str = "python"):
    script = tmp_path / "robot.py"
    script.write_text(source, encoding="utf-8")
    engine = make_engine("sqlite:///" + (tmp_path / "engine.db").as_posix())
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        robot = Robot(
            name="Test robot", executor_type=executor_type, script=str(script), interpreter=sys.executable,
            cwd=str(tmp_path), arguments=[], timeout=timeout,
        )
        session.add(robot)
        session.flush()
        robot_id = robot.id
    run_id = enqueue(engine, robot_id)
    assert claim_next(engine) == run_id
    return engine, run_id


def get_run(engine, run_id):
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if run is not None:
            session.expunge(run)
        return run


def test_success_logs_and_business_result(tmp_path):
    source = """
import json, os
print('linha de saída', flush=True)
path = os.environ['RCC_RESULT_PATH']
payload = {'version': 1, 'run_id': os.environ['RCC_RUN_ID'], 'status': 'success', 'summary': 'Concluído'}
with open(path + '.tmp', 'w', encoding='utf-8') as stream: json.dump(payload, stream)
os.replace(path + '.tmp', path)
"""
    engine, run_id = create_run(tmp_path, source)
    assert execute_run(engine, run_id, tmp_path / "logs") == "completed"
    run = get_run(engine, run_id)
    assert run.exit_code == 0
    assert run.business_result == "success"
    assert run.business_summary == "Concluído"
    assert "linha de saída" in Path(run.stdout_path).read_text(encoding="utf-8")
    engine.dispose()


def test_business_error_is_distinct_from_technical_success(tmp_path):
    source = """
import json, os
path = os.environ['RCC_RESULT_PATH']
payload = {'version': 1, 'run_id': os.environ['RCC_RUN_ID'], 'status': 'business_error', 'summary': 'Recusado'}
with open(path + '.tmp', 'w', encoding='utf-8') as stream: json.dump(payload, stream)
os.replace(path + '.tmp', path)
"""
    engine, run_id = create_run(tmp_path, source)
    assert execute_run(engine, run_id, tmp_path / "logs") == "completed"
    run = get_run(engine, run_id)
    assert run.exit_code == 0
    assert run.business_result == "business_error"
    assert run.business_summary == "Recusado"
    engine.dispose()


def test_nonzero_exit_is_failed(tmp_path):
    engine, run_id = create_run(tmp_path, "import sys; print('erro', file=sys.stderr); raise SystemExit(7)")
    assert execute_run(engine, run_id, tmp_path / "logs") == "failed"
    run = get_run(engine, run_id)
    assert run.exit_code == 7
    assert run.business_result == "not_reported"
    assert "erro" in Path(run.stderr_path).read_text(encoding="utf-8")
    engine.dispose()


def test_timeout(tmp_path):
    engine, run_id = create_run(tmp_path, "import time; time.sleep(60)", timeout=0.2)
    assert execute_run(engine, run_id, tmp_path / "logs") == "timed_out"
    assert get_run(engine, run_id).state == "timed_out"
    engine.dispose()


def test_cancel_running(tmp_path):
    engine, run_id = create_run(tmp_path, "import time; time.sleep(60)")
    thread = threading.Thread(target=execute_run, args=(engine, run_id, tmp_path / "logs"))
    thread.start()
    deadline = time.monotonic() + 10
    while get_run(engine, run_id).state != "running" and time.monotonic() < deadline:
        time.sleep(0.05)
    assert cancel(engine, run_id) == "cancelling"
    thread.join(10)
    assert not thread.is_alive()
    assert get_run(engine, run_id).state == "cancelled"
    engine.dispose()


def test_invalid_paths_fail_without_process(tmp_path):
    engine, run_id = create_run(tmp_path, "print('unused')")
    with Session(engine) as session, session.begin():
        run = session.get(Run, run_id)
        run.configuration = {**run.configuration, "script": str(tmp_path / "missing.py")}
    assert execute_run(engine, run_id, tmp_path / "logs") == "failed"
    assert "Invalid target" in get_run(engine, run_id).reason
    engine.dispose()


def test_supported_command_shapes():
    args = ["um", "dois"]
    assert build_command("python", "python.exe", "robot.py", args) == [
        "python.exe", "-u", "robot.py", *args,
    ]
    assert build_command("powershell", "powershell.exe", "robot.ps1", args) == [
        "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-File", "robot.ps1", *args,
    ]
    assert build_command("batch", "cmd.exe", "robot.bat", args) == [
        "cmd.exe", "/D", "/S", "/C", "robot.bat", *args,
    ]
    assert build_command("node", "node.exe", "robot.js", args) == ["node.exe", "robot.js", *args]
    assert build_command("java", "java.exe", "robot.jar", args) == ["java.exe", "-jar", "robot.jar", *args]
    assert build_command("executable", "ignored.exe", "robot.exe", args) == ["robot.exe", *args]


def test_generic_executable_runs_without_python_adapter(tmp_path):
    engine = make_engine("sqlite:///" + (tmp_path / "executable.db").as_posix())
    Base.metadata.create_all(engine)
    with Session(engine) as session, session.begin():
        robot = Robot(
            name="Native process",
            executor_type="executable",
            script=sys.executable,
            interpreter=sys.executable,
            cwd=str(tmp_path),
            arguments=["-c", "print('generic process')"],
            timeout=10,
        )
        session.add(robot)
        session.flush()
        robot_id = robot.id
    run_id = enqueue(engine, robot_id)
    assert claim_next(engine) == run_id
    assert execute_run(engine, run_id, tmp_path / "logs") == "completed"
    run = get_run(engine, run_id)
    assert run.exit_code == 0
    assert "generic process" in Path(run.stdout_path).read_text(encoding="utf-8")
    engine.dispose()


def create_validation_runs(tmp_path: Path, modes: list[str], timeout: float = 10):
    engine = make_engine("sqlite:///" + (tmp_path / "validation.db").as_posix())
    Base.metadata.create_all(engine)
    script = Path(__file__).parents[1] / "demo" / "validation_robot.py"
    robot_ids = []
    with Session(engine) as session, session.begin():
        for index, mode in enumerate(modes, start=1):
            robot = Robot(
                name=f"Validation {mode} {index}", executor_type="python", script=str(script),
                interpreter=sys.executable, cwd=str(script.parent.parent), arguments=[mode], timeout=timeout,
            )
            session.add(robot)
            session.flush()
            robot_ids.append(robot.id)
    run_ids = [enqueue(engine, robot_id) for robot_id in robot_ids]
    return engine, run_ids


def test_validation_robot_business_error(tmp_path):
    engine, run_ids = create_validation_runs(tmp_path, ["business_error"])
    assert run_engine(engine, tmp_path / "logs", f"test-{time.time_ns()}") == 1
    run = get_run(engine, run_ids[0])
    assert run.state == "completed"
    assert run.exit_code == 0
    assert run.business_result == "business_error"
    engine.dispose()


def test_validation_robot_technical_error(tmp_path):
    engine, run_ids = create_validation_runs(tmp_path, ["technical_error"])
    assert run_engine(engine, tmp_path / "logs", f"test-{time.time_ns()}") == 1
    run = get_run(engine, run_ids[0])
    assert run.state == "failed"
    assert run.exit_code == 7
    assert run.business_result == "not_reported"
    engine.dispose()


def test_validation_robot_timeout_with_child_process(tmp_path):
    engine, run_ids = create_validation_runs(tmp_path, ["hang"], timeout=0.5)
    assert run_engine(engine, tmp_path / "logs", f"test-{time.time_ns()}") == 1
    assert get_run(engine, run_ids[0]).state == "timed_out"
    engine.dispose()


def test_validation_queue_is_sequential(tmp_path):
    engine, run_ids = create_validation_runs(tmp_path, ["success", "success"])
    assert run_engine(engine, tmp_path / "logs", f"test-{time.time_ns()}") == 2
    first, second = (get_run(engine, run_id) for run_id in run_ids)
    assert first.state == second.state == "completed"
    assert first.ended_at <= second.started_at
    engine.dispose()


def test_remove_robot_deletes_only_its_history_and_logs(tmp_path):
    engine, run_id = create_run(tmp_path, "print('done')")
    logs_root = tmp_path / "logs"
    assert execute_run(engine, run_id, logs_root) == "completed"
    with Session(engine) as session:
        robot_id = session.get(Run, run_id).robot_id
    removed, failures = remove_robot(engine, robot_id, logs_root)
    assert (removed, failures) == (1, 0)
    assert list_robots(engine) == []
    assert get_run(engine, run_id) is None
    assert not (logs_root / run_id).exists()
    with pytest.raises(ValueError, match="not found"):
        enqueue(engine, robot_id)
    engine.dispose()


def test_remove_robot_rejects_queued_execution(tmp_path):
    engine, run_id = create_run(tmp_path, "print('pending')")
    with Session(engine) as session:
        robot_id = session.get(Run, run_id).robot_id
    with pytest.raises(ValueError, match="active or queued"):
        remove_robot(engine, robot_id, tmp_path / "logs")
    engine.dispose()


def test_remove_single_history_preserves_other_runs(tmp_path):
    engine, completed_id = create_run(tmp_path, "print('done')")
    logs_root = tmp_path / "logs"
    assert execute_run(engine, completed_id, logs_root) == "completed"
    with Session(engine) as session:
        robot_id = session.get(Run, completed_id).robot_id
    queued_id = enqueue(engine, robot_id)
    assert remove_run(engine, completed_id, logs_root) is True
    assert not (logs_root / completed_id).exists()
    assert get_run(engine, queued_id).state == "queued"
    with pytest.raises(ValueError, match="cannot be removed"):
        remove_run(engine, queued_id, logs_root)
    engine.dispose()


def test_edit_robot_changes_only_future_run_snapshots(tmp_path):
    engine, old_run_id = create_run(tmp_path, "print('old')")
    with Session(engine) as session:
        robot_id = session.get(Run, old_run_id).robot_id
    assert execute_run(engine, old_run_id, tmp_path / "logs") == "completed"
    updated_script = tmp_path / "updated.py"
    updated_script.write_text("print('updated')", encoding="utf-8")
    update_robot(
        engine, robot_id, "Updated robot", str(updated_script), sys.executable,
        str(tmp_path), ["new"], 20, "python",
    )
    new_run_id = enqueue(engine, robot_id)
    assert get_run(engine, old_run_id).configuration["name"] == "Test robot"
    assert get_run(engine, new_run_id).configuration["name"] == "Updated robot"
    engine.dispose()


def test_deactivated_robot_remains_visible_but_cannot_enqueue(tmp_path):
    engine, run_id = create_run(tmp_path, "print('done')")
    with Session(engine) as session:
        robot_id = session.get(Run, run_id).robot_id
    assert execute_run(engine, run_id, tmp_path / "logs") == "completed"
    set_robot_active(engine, robot_id, False)
    robots = list_robots(engine)
    assert len(robots) == 1 and robots[0].active is False
    with pytest.raises(ValueError, match="removed"):
        enqueue(engine, robot_id)
    set_robot_active(engine, robot_id, True)
    assert enqueue(engine, robot_id)
    engine.dispose()

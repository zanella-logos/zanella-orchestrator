"""Robot registration, queueing, cancellation, and queries."""

from pathlib import Path
import shutil
import time

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from .models import Robot, Run


def robot_snapshot(robot: Robot) -> dict:
    return {
        "name": robot.name,
        "executor_type": robot.executor_type,
        "script": robot.script,
        "interpreter": robot.interpreter,
        "cwd": robot.cwd,
        "arguments": list(robot.arguments),
        "timeout": robot.timeout,
    }


def add_robot(engine, name, script, interpreter, cwd, arguments, timeout, executor_type="python") -> str:
    with Session(engine) as session, session.begin():
        robot = Robot(
            name=name, executor_type=executor_type, script=script, interpreter=interpreter, cwd=cwd,
            arguments=arguments, timeout=timeout,
        )
        session.add(robot)
        session.flush()
        return robot.id


def update_robot(
    engine, robot_id, name, script, interpreter, cwd, arguments, timeout, executor_type="python"
) -> None:
    active_states = {"queued", "starting", "running", "cancelling"}
    with Session(engine) as session, session.begin():
        robot = session.get(Robot, robot_id)
        if robot is None:
            raise ValueError("Automation not found")
        has_active_run = session.scalar(
            select(Run.id).where(Run.robot_id == robot_id, Run.state.in_(active_states)).limit(1)
        )
        if has_active_run:
            raise ValueError("Automation has an active or queued execution")
        robot.name = name
        robot.executor_type = executor_type
        robot.script = script
        robot.interpreter = interpreter
        robot.cwd = cwd
        robot.arguments = arguments
        robot.timeout = timeout


def set_robot_active(engine, robot_id: str, active: bool) -> None:
    active_states = {"queued", "starting", "running", "cancelling"}
    with Session(engine) as session, session.begin():
        robot = session.get(Robot, robot_id)
        if robot is None:
            raise ValueError("Automation not found")
        if not active:
            has_active_run = session.scalar(
                select(Run.id).where(Run.robot_id == robot_id, Run.state.in_(active_states)).limit(1)
            )
            if has_active_run:
                raise ValueError("Automation has an active or queued execution")
        robot.active = active


def enqueue(engine, robot_id: str) -> str:
    with Session(engine) as session, session.begin():
        robot = session.get(Robot, robot_id)
        if robot is None:
            raise ValueError("Robot not found")
        if not robot.active:
            raise ValueError("Automation was removed")
        run = Run(robot_id=robot.id, configuration=robot_snapshot(robot))
        session.add(run)
        session.flush()
        return run.id


def cancel(engine, run_id: str) -> str:
    with Session(engine) as session, session.begin():
        run = session.get(Run, run_id)
        if run is None:
            raise ValueError("Run not found")
        if run.state == "queued":
            run.state = "cancelled"
            run.ended_at = time.time()
            run.reason = "Cancelled before execution"
        elif run.state in {"starting", "running"}:
            run.state = "cancelling"
        return run.state


def list_runs(
    engine, limit: int = 25, offset: int = 0, state: str = None,
    business_result: str = None, search: str = None
) -> tuple[list[Run], int]:
    from sqlalchemy import func
    with Session(engine) as session:
        query = select(Run).join(Robot, Run.robot_id == Robot.id)

        if state:
            query = query.where(Run.state == state)
        if business_result:
            query = query.where(Run.business_result == business_result)
        if search:
            query = query.where(Robot.name.ilike(f"%{search}%"))

        count_query = select(func.count()).select_from(query.subquery())
        total = session.scalar(count_query)

        runs = session.scalars(query.order_by(Run.created_at.desc()).limit(limit).offset(offset))
        return list(runs), total


def list_robots(engine, search: str = None) -> list[Robot]:
    with Session(engine) as session:
        query = select(Robot)
        if search:
            term = f"%{search}%"
            query = query.where(or_(Robot.name.ilike(term), Robot.executor_type.ilike(term)))
        return list(session.scalars(query.order_by(Robot.name)))

def _remove_log_directory(logs_root: Path, run_id: str) -> bool:
    root = logs_root.resolve()
    run_directory = (root / run_id).resolve()
    try:
        if run_directory.parent == root and run_directory.exists():
            shutil.rmtree(run_directory)
        return True
    except OSError:
        return False


def remove_robot(engine, robot_id: str, logs_root: Path) -> tuple[int, int]:
    active_states = {"queued", "starting", "running", "cancelling"}
    with Session(engine) as session, session.begin():
        robot = session.get(Robot, robot_id)
        if robot is None or not robot.active:
            raise ValueError("Automation not found")
        has_active_run = session.scalar(
            select(Run.id).where(Run.robot_id == robot_id, Run.state.in_(active_states)).limit(1)
        )
        if has_active_run:
            raise ValueError("Automation has an active or queued execution")
        run_ids = list(session.scalars(select(Run.id).where(Run.robot_id == robot_id)))
        if run_ids:
            session.execute(delete(Run).where(Run.id.in_(run_ids)))
        session.delete(robot)

    cleanup_failures = sum(not _remove_log_directory(logs_root, run_id) for run_id in run_ids)
    return len(run_ids), cleanup_failures


def clear_all_robots(engine, logs_root: Path) -> tuple[int, int]:
    active_states = {"queued", "starting", "running", "cancelling"}
    with Session(engine) as session, session.begin():
        has_active_run = session.scalar(
            select(Run.id).where(Run.state.in_(active_states)).limit(1)
        )
        if has_active_run:
            raise ValueError("Existem execuções ativas ou na fila. Cancele-as primeiro.")

        runs = list(session.scalars(select(Run.id)))
        if runs:
            session.execute(delete(Run))
        session.execute(delete(Robot))

    cleanup_failures = sum(not _remove_log_directory(logs_root, run_id) for run_id in runs)
    return len(runs), cleanup_failures


def clear_all_runs(engine, logs_root: Path) -> tuple[int, int]:
    active_states = {"queued", "starting", "running", "cancelling"}
    with Session(engine) as session, session.begin():
        has_active_run = session.scalar(
            select(Run.id).where(Run.state.in_(active_states)).limit(1)
        )
        if has_active_run:
            raise ValueError("Existem execuções ativas ou na fila. Cancele-as primeiro.")

        runs = list(session.scalars(select(Run.id)))
        if runs:
            session.execute(delete(Run))

    cleanup_failures = sum(not _remove_log_directory(logs_root, run_id) for run_id in runs)
    return len(runs), cleanup_failures


def remove_run(engine, run_id: str, logs_root: Path) -> bool:
    final_states = {"completed", "failed", "cancelled", "timed_out", "interrupted"}
    with Session(engine) as session, session.begin():
        run = session.get(Run, run_id)
        if run is None:
            raise ValueError("Execution not found")
        if run.state not in final_states:
            raise ValueError("Active or queued execution cannot be removed")
        session.delete(run)
    return _remove_log_directory(logs_root, run_id)

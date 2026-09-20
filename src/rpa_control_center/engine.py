"""Sequential Windows execution engine."""

import json
import os
from pathlib import Path
import time

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .models import Run
from .executors import build_command, validate_command_paths
from .store import claim_next, claim_specific
from .windows import InstallationLock, ProcessTree


FINAL_STATES = {"completed", "failed", "cancelled", "timed_out", "interrupted"}
BUSINESS_STATES = {"success", "business_error", "technical_error", "partial"}


def reconcile(engine) -> int:
    with Session(engine) as session, session.begin():
        result = session.execute(
            update(Run)
            .where(Run.state.in_(["starting", "running", "cancelling"]))
            .values(state="interrupted", ended_at=time.time(), reason="Engine supervision was interrupted")
        )
        return result.rowcount


def read_business_result(path: Path, run_id: str) -> tuple[str, str | None]:
    if not path.exists():
        return "not_reported", None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("version") != 1 or payload.get("run_id") != run_id:
            raise ValueError("Result identity does not match")
        status = payload.get("status")
        if status not in BUSINESS_STATES:
            raise ValueError("Unknown business status")
        summary = payload.get("summary")
        return status, str(summary)[:2000] if summary is not None else None
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return "invalid_report", None


def _finish(engine, run_id: str, **values) -> None:
    with Session(engine) as session, session.begin():
        session.execute(update(Run).where(Run.id == run_id).values(**values))


def execute_run(engine, run_id: str, logs_root: Path) -> str:
    with Session(engine) as session:
        run = session.get(Run, run_id)
        config = dict(run.configuration)
    executor_type = config.get("executor_type", "python")
    target = config["script"]
    launcher = config["interpreter"]
    cwd = config["cwd"]
    if error := validate_command_paths(executor_type, launcher, target, cwd):
        _finish(engine, run_id, state="failed", ended_at=time.time(), reason=error)
        return "failed"

    run_dir = logs_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    stdout_path, stderr_path = run_dir / "stdout.log", run_dir / "stderr.log"
    result_path = run_dir / "result.json"
    command = build_command(executor_type, launcher, target, list(map(str, config.get("arguments", []))))
    environment = os.environ.copy()
    environment["PYTHONUNBUFFERED"] = "1"
    environment["PYTHONUTF8"] = "1"
    environment["RCC_RUN_ID"] = run_id
    environment["RCC_RESULT_PATH"] = str(result_path)
    started = time.time()
    try:
        with ProcessTree(
            command, cwd, str(stdout_path), str(stderr_path), environment
        ) as process:
            _finish(
                engine, run_id, state="running", started_at=started,
                stdout_path=str(stdout_path), stderr_path=str(stderr_path),
                result_path=str(result_path), process_id=process.pid,
            )
            deadline = time.monotonic() + float(config["timeout"])
            final_state = None
            reason = None
            while not process.wait(0.1):
                with Session(engine) as session:
                    state = session.scalar(select(Run.state).where(Run.id == run_id))
                if state == "cancelling":
                    process.stop()
                    final_state, reason = "cancelled", "Cancelled by operator"
                    break
                if time.monotonic() >= deadline:
                    process.stop()
                    final_state, reason = "timed_out", "Execution timeout exceeded"
                    break
            process.wait(10)
            exit_code = process.exit_code()
            if final_state is None:
                final_state = "completed" if exit_code == 0 else "failed"
                if exit_code != 0:
                    reason = f"Process exited with code {exit_code}"
    except Exception as error:
        _finish(engine, run_id, state="failed", ended_at=time.time(), reason=f"Could not start process: {error}")
        return "failed"
    business, summary = read_business_result(result_path, run_id)
    _finish(
        engine, run_id, state=final_state, ended_at=time.time(), exit_code=exit_code,
        reason=reason, business_result=business, business_summary=summary,
    )
    return final_state


def run_engine(engine, logs_root: Path, installation_id: str = "default") -> int:
    """Process the full queue sequentially (used by 'Executar fila')."""
    completed = 0
    with InstallationLock(installation_id):
        reconcile(engine)
        while run_id := claim_next(engine):
            execute_run(engine, run_id, logs_root)
            completed += 1
    return completed


def run_engine_direct(engine, run_id: str, logs_root: Path, installation_id: str = "default") -> str:
    """Execute a specific run immediately, bypassing FIFO queue order.

    Used by the per-robot Play button.  Other queued items are left untouched.
    Returns the final state of the run, or 'skipped' if the run could not be
    claimed (e.g. already cancelled or claimed by another process).
    """
    with InstallationLock(installation_id):
        reconcile(engine)
        if not claim_specific(engine, run_id):
            return "skipped"
        return execute_run(engine, run_id, logs_root)

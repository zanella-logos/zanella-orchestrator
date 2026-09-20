"""Persistent local schedules and Windows Task Scheduler adapter."""

from __future__ import annotations

from datetime import datetime, timedelta
import os
from pathlib import Path
import subprocess
import sys
import time

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from .database import application_data_dir
from .engine import run_engine
from .models import Robot, Run, Schedule
from .service import robot_snapshot
from .windows import InstallationLock


TASK_NAME = "RPA Control Center Scheduler"
TASK_INTERVAL_MINUTES = 5
WEEKDAYS = ("Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo")


def weekday_mask(days: list[int]) -> int:
    if not days or any(day not in range(7) for day in days):
        raise ValueError("Selecione ao menos um dia da semana.")
    return sum(1 << day for day in set(days))


def weekdays_from_mask(mask: int | None) -> list[int]:
    return [day for day in range(7) if mask is not None and mask & (1 << day)]


def next_occurrence(frequency: str, time_of_day: str, weekday: int | None, after: float) -> float:
    try:
        hour, minute = map(int, time_of_day.split(":"))
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        raise ValueError("Horário inválido. Use HH:MM.") from None
    if frequency not in {"daily", "weekly", "custom"}:
        raise ValueError("Frequência inválida.")
    if frequency == "weekly" and weekday not in range(7):
        raise ValueError("Informe o dia da semana.")
    if frequency == "custom" and not weekdays_from_mask(weekday):
        raise ValueError("Selecione ao menos um dia da semana.")

    base = datetime.fromtimestamp(after)
    for offset in range(8):
        day = base.date() + timedelta(days=offset)
        candidate = datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=minute)
        if candidate.timestamp() <= after:
            continue
        allowed_days = weekdays_from_mask(weekday) if frequency == "custom" else []
        if (
            frequency == "daily"
            or frequency == "weekly" and candidate.weekday() == weekday
            or frequency == "custom" and candidate.weekday() in allowed_days
        ):
            return candidate.timestamp()
    raise ValueError("Não foi possível calcular o próximo disparo.")


def add_schedule(engine, robot_id: str, frequency: str, time_of_day: str, weekday: int | None) -> str:
    now = time.time()
    next_run_at = next_occurrence(frequency, time_of_day, weekday, now)
    with Session(engine) as session, session.begin():
        robot = session.get(Robot, robot_id)
        if robot is None or not robot.active:
            raise ValueError("Automação não encontrada ou desativada.")
        schedule = Schedule(
            robot_id=robot_id, frequency=frequency, time_of_day=time_of_day,
            weekday=weekday if frequency in {"weekly", "custom"} else None,
            next_run_at=next_run_at,
        )
        session.add(schedule)
        session.flush()
        return schedule.id


def list_schedules(engine) -> list[tuple[Schedule, str]]:
    with Session(engine) as session:
        rows = session.execute(
            select(Schedule, Robot.name).join(Robot).order_by(Schedule.next_run_at, Robot.name)
        )
        return [(schedule, name) for schedule, name in rows]


def set_schedule_active(engine, schedule_id: str, active: bool) -> None:
    with Session(engine) as session, session.begin():
        schedule = session.get(Schedule, schedule_id)
        if schedule is None:
            raise ValueError("Agendamento não encontrado.")
        schedule.active = active
        if active:
            schedule.next_run_at = next_occurrence(
                schedule.frequency, schedule.time_of_day, schedule.weekday, time.time()
            )


def remove_schedule(engine, schedule_id: str) -> None:
    with Session(engine) as session, session.begin():
        result = session.execute(delete(Schedule).where(Schedule.id == schedule_id))
        if result.rowcount != 1:
            raise ValueError("Agendamento não encontrado.")


def enqueue_due_schedules(engine, now: float | None = None) -> int:
    now = time.time() if now is None else now
    created = 0
    with Session(engine) as session, session.begin():
        due = list(session.execute(
            select(Schedule.id, Schedule.next_run_at)
            .join(Robot)
            .where(Schedule.active.is_(True), Robot.active.is_(True), Schedule.next_run_at <= now)
            .order_by(Schedule.next_run_at, Schedule.id)
        ))
        for schedule_id, expected_run_at in due:
            schedule = session.get(Schedule, schedule_id)
            following = next_occurrence(
                schedule.frequency, schedule.time_of_day, schedule.weekday, now
            )
            claimed = session.scalar(
                update(Schedule)
                .where(
                    Schedule.id == schedule_id,
                    Schedule.active.is_(True),
                    Schedule.next_run_at == expected_run_at,
                )
                .values(last_run_at=expected_run_at, next_run_at=following)
                .returning(Schedule.id)
            )
            if claimed:
                robot = session.get(Robot, schedule.robot_id)
                session.add(Run(robot_id=robot.id, configuration=robot_snapshot(robot)))
                created += 1
    return created


def run_scheduler(engine, logs_root: Path, installation_id: str = "default") -> tuple[int, int]:
    with InstallationLock(f"{installation_id}-scheduler"):
        scheduled = enqueue_due_schedules(engine)
    processed = run_engine(engine, logs_root)
    return scheduled, processed


def scheduler_cli_path() -> Path:
    candidate = Path(sys.executable).with_name("rcc.exe")
    if not candidate.exists():
        raise ValueError("Executável rcc.exe não encontrado ao lado do Python do projeto.")
    return candidate


def install_windows_task(project_root: Path) -> None:
    rcc_path = scheduler_cli_path()
    runner_path = application_data_dir() / "run-scheduler.vbs"
    vbs_project_root = str(project_root).replace('"', '""')
    vbs_rcc_path = str(rcc_path).replace('"', '""')
    runner_path.write_text(
        'Set shell = CreateObject("WScript.Shell")\n'
        f'shell.CurrentDirectory = "{vbs_project_root}"\n'
        f'exitCode = shell.Run("""{vbs_rcc_path}"" scheduler", 0, True)\n'
        'WScript.Quit exitCode\n',
        encoding="utf-8",
    )
    command = f'wscript.exe //B //NoLogo "{runner_path}"'
    result = subprocess.run(
        [
            "schtasks.exe", "/Create", "/TN", TASK_NAME, "/SC", "MINUTE",
            "/MO", str(TASK_INTERVAL_MINUTES),
            "/TR", command, "/IT", "/F",
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode:
        raise ValueError((result.stderr or result.stdout).strip() or "Falha ao criar tarefa do Windows.")


def remove_windows_task() -> None:
    result = subprocess.run(
        ["schtasks.exe", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode:
        raise ValueError((result.stderr or result.stdout).strip() or "Falha ao remover tarefa do Windows.")
    data_dir = application_data_dir()
    (data_dir / "run-scheduler.vbs").unlink(missing_ok=True)
    (data_dir / "run-scheduler.cmd").unlink(missing_ok=True)


def open_windows_task_scheduler() -> None:
    os.startfile("taskschd.msc")


def windows_task_installed() -> bool:
    result = subprocess.run(
        ["schtasks.exe", "/Query", "/TN", TASK_NAME],
        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return result.returncode == 0

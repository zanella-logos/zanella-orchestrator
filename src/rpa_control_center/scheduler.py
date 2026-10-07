"""Persistent local schedules and Windows Task Scheduler adapter."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
import os
import re
from pathlib import Path
import subprocess
import sys
import time

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from .database import application_data_dir
from .models import Robot, Run, Schedule
from .service import robot_snapshot
from .windows import InstallationBusy


TASK_NAME = "Zanella Orchestrator"
LEGACY_TASK_NAME = "RPA Control Center Scheduler"
TASK_INTERVAL_MINUTES = 1
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
    from .engine import run_engine

    scheduled = 0

    def record_scheduled(count: int) -> None:
        nonlocal scheduled
        scheduled += count

    try:
        processed = run_engine(engine, logs_root, installation_id, on_scheduled=record_scheduled)
    except InstallationBusy:
        return 0, 0
    return scheduled, processed


def scheduler_cli_path() -> Path:
    if os.environ.get("FLET_APP_STORAGE_DATA"):
        candidate = Path(__file__).resolve().parents[3] / "Zanella-Orchestrator.exe"
    else:
        candidate = Path(sys.executable).with_name("rcc.exe")
    if not candidate.exists():
        raise ValueError(f"Executável do agendador não encontrado: {candidate}")
    return candidate


def parse_task_interval(value: str | int) -> int:
    text = str(value)
    if not re.fullmatch(r"[0-9]{1,2}", text) or not 1 <= int(text) <= 59:
        raise ValueError("Informe um intervalo inteiro de 1 a 59 minutos, usando somente dígitos.")
    return int(text)


def saved_task_interval(installed: bool = False) -> int:
    path = application_data_dir() / "scheduler-interval.txt"
    if path.exists():
        return parse_task_interval(path.read_text(encoding="utf-8"))
    return 5 if installed else TASK_INTERVAL_MINUTES


def _migrate_legacy_windows_task() -> None:
    script = f"""
$ErrorActionPreference = 'Stop'
$oldName = '{LEGACY_TASK_NAME}'
$newName = '{TASK_NAME}'
$oldTask = Get-ScheduledTask -TaskName $oldName -ErrorAction SilentlyContinue
if ($null -eq $oldTask) {{ exit 0 }}
$newTask = Get-ScheduledTask -TaskName $newName -ErrorAction SilentlyContinue
if ($null -ne $newTask) {{
    Disable-ScheduledTask -TaskName $oldName | Out-Null
    try {{
        Unregister-ScheduledTask -TaskName $oldName -Confirm:$false -ErrorAction Stop
    }} catch {{
        Write-Output 'LEGACY_TASK_REMAINS_DISABLED'
    }}
    exit 0
}}
[xml]$definition = Export-ScheduledTask -TaskName $oldName
Disable-ScheduledTask -TaskName $oldName | Out-Null
try {{
    if ($definition.Task.RegistrationInfo.URI) {{
        $definition.Task.RegistrationInfo.URI = "\\$newName"
    }}
    Register-ScheduledTask -TaskName $newName -Xml $definition.OuterXml -ErrorAction Stop | Out-Null
    Get-ScheduledTask -TaskName $newName -ErrorAction Stop | Out-Null
    try {{
        Unregister-ScheduledTask -TaskName $oldName -Confirm:$false -ErrorAction Stop
    }} catch {{
        Write-Output 'LEGACY_TASK_REMAINS_DISABLED'
    }}
}} catch {{
    $newTask = Get-ScheduledTask -TaskName $newName -ErrorAction SilentlyContinue
    if ($null -ne $newTask) {{
        Disable-ScheduledTask -TaskName $newName -ErrorAction SilentlyContinue | Out-Null
        Unregister-ScheduledTask -TaskName $newName -Confirm:$false -ErrorAction SilentlyContinue
    }}
    Enable-ScheduledTask -TaskName $oldName -ErrorAction SilentlyContinue | Out-Null
    throw
}}
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode:
        raise ValueError((result.stderr or result.stdout).strip() or "Falha ao migrar a tarefa do Agendador do Windows.")
    if "LEGACY_TASK_REMAINS_DISABLED" in (result.stdout or ""):
        logging.warning("A tarefa antiga do Zanella permaneceu desativada após a migração.")


def install_windows_task(project_root: Path, interval_minutes: str | int = TASK_INTERVAL_MINUTES) -> None:
    interval_minutes = parse_task_interval(interval_minutes)
    _migrate_legacy_windows_task()
    rcc_path = scheduler_cli_path()
    data_dir = application_data_dir()
    runner_path = data_dir / "run-scheduler.vbs"
    vbs_project_root = str(project_root).replace('"', '""')
    vbs_rcc_path = str(rcc_path).replace('"', '""')
    vbs_data_dir = str(data_dir).replace('"', '""')
    packaged = rcc_path.name == "Zanella-Orchestrator.exe"
    command_suffix = "" if packaged else " scheduler"
    runner_path.write_text(
        'Set shell = CreateObject("WScript.Shell")\n'
        f'shell.CurrentDirectory = "{vbs_project_root}"\n'
        + f'shell.Environment("PROCESS")("RCC_DATA_DIR") = "{vbs_data_dir}"\n'
        + ('shell.Environment("PROCESS")("RCC_SCHEDULER_MODE") = "1"\n' if packaged else '')
        + f'exitCode = shell.Run("""{vbs_rcc_path}"""{command_suffix}, 0, True)\n'
        'WScript.Quit exitCode\n',
        encoding="utf-16",
    )
    command = f'wscript.exe //B //NoLogo "{runner_path}"'
    result = subprocess.run(
        [
            "schtasks.exe", "/Create", "/TN", TASK_NAME, "/SC", "MINUTE",
            "/MO", str(interval_minutes),
            "/TR", command, "/IT", "/F",
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode:
        raise ValueError((result.stderr or result.stdout).strip() or "Falha ao criar tarefa do Windows.")
    (data_dir / "scheduler-interval.txt").write_text(str(interval_minutes), encoding="utf-8")


def remove_windows_task() -> None:
    failures = []
    for task_name in (TASK_NAME, LEGACY_TASK_NAME):
        if not _windows_task_exists(task_name):
            continue
        result = subprocess.run(
            ["schtasks.exe", "/Delete", "/TN", task_name, "/F"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode:
            failures.append((result.stderr or result.stdout).strip() or task_name)
    if failures:
        raise ValueError("; ".join(failures))
    data_dir = application_data_dir()
    (data_dir / "run-scheduler.vbs").unlink(missing_ok=True)
    (data_dir / "run-scheduler.cmd").unlink(missing_ok=True)


def open_windows_task_scheduler() -> None:
    os.startfile("taskschd.msc")


def _windows_task_exists(task_name: str) -> bool:
    result = subprocess.run(
        ["schtasks.exe", "/Query", "/TN", task_name],
        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return result.returncode == 0


def windows_task_installed() -> bool:
    _migrate_legacy_windows_task()
    return _windows_task_exists(TASK_NAME)

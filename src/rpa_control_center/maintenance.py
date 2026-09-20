"""Retention and portable backup operations for local administration."""

from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import time

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .executors import EXECUTOR_TYPES
from .models import Robot, Run
from .service import _remove_log_directory


ACTIVE_STATES = {"queued", "starting", "running", "cancelling"}
FINAL_STATES = {"completed", "failed", "cancelled", "timed_out", "interrupted"}
EXPORT_VERSION = 1


def _require_no_active_runs(engine) -> None:
    with Session(engine) as session:
        active = session.scalar(select(Run.id).where(Run.state.in_(ACTIVE_STATES)).limit(1))
    if active:
        raise ValueError("Existem execuções ativas ou na fila. Cancele-as primeiro.")


def _sqlite_path(engine) -> Path:
    if engine.dialect.name != "sqlite" or not engine.url.database or engine.url.database == ":memory:":
        raise ValueError("Esta operação de banco completo está disponível apenas para SQLite local.")
    return Path(engine.url.database).resolve()


def purge_old_runs(engine, logs_root: Path, days: int) -> tuple[int, int]:
    if days <= 0:
        raise ValueError("A retenção deve ser maior que zero dias.")
    _require_no_active_runs(engine)
    cutoff = time.time() - (days * 86_400)
    with Session(engine) as session, session.begin():
        run_ids = list(session.scalars(
            select(Run.id).where(
                Run.state.in_(FINAL_STATES),
                func.coalesce(Run.ended_at, Run.created_at) < cutoff,
            )
        ))
        if run_ids:
            session.execute(delete(Run).where(Run.id.in_(run_ids)))
    failures = sum(not _remove_log_directory(logs_root, run_id) for run_id in run_ids)
    return len(run_ids), failures


def export_robots(engine, destination: Path) -> int:
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Session(engine) as session:
        robots = list(session.scalars(select(Robot).order_by(Robot.name)))
    payload = {
        "format": "rpa-control-center-robots",
        "version": EXPORT_VERSION,
        "exported_at": time.time(),
        "robots": [
            {
                "name": robot.name,
                "executor_type": robot.executor_type,
                "script": robot.script,
                "interpreter": robot.interpreter,
                "cwd": robot.cwd,
                "arguments": list(robot.arguments),
                "timeout": robot.timeout,
                "active": robot.active,
            }
            for robot in robots
        ],
    }
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(robots)


def import_robots(engine, source: Path) -> tuple[int, int]:
    _require_no_active_runs(engine)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Backup de cadastros inválido: {error}") from error
    if payload.get("format") != "rpa-control-center-robots" or payload.get("version") != EXPORT_VERSION:
        raise ValueError("Formato ou versão do backup de cadastros não suportado.")
    items = payload.get("robots")
    if not isinstance(items, list):
        raise ValueError("O backup não contém uma lista válida de automações.")

    names: set[str] = set()
    created = updated = 0
    with Session(engine) as session, session.begin():
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("O backup contém uma automação inválida.")
            name = str(item.get("name", "")).strip()
            executor_type = str(item.get("executor_type", ""))
            arguments = item.get("arguments", [])
            timeout = item.get("timeout")
            if not name or name in names:
                raise ValueError("O backup contém nome vazio ou duplicado.")
            if executor_type not in EXECUTOR_TYPES:
                raise ValueError(f"Tipo de executor inválido para {name}.")
            if not isinstance(arguments, list) or not isinstance(timeout, (int, float)) or timeout <= 0:
                raise ValueError(f"Argumentos ou timeout inválidos para {name}.")
            names.add(name)
            robot = session.scalar(select(Robot).where(Robot.name == name))
            values = {
                "executor_type": executor_type,
                "script": str(item.get("script", "")),
                "interpreter": str(item.get("interpreter", "")),
                "cwd": str(item.get("cwd", "")),
                "arguments": [str(value) for value in arguments],
                "timeout": float(timeout),
                "active": bool(item.get("active", True)),
            }
            if robot is None:
                session.add(Robot(name=name, **values))
                created += 1
            else:
                for field, value in values.items():
                    setattr(robot, field, value)
                updated += 1
    return created, updated


def backup_sqlite(engine, destination: Path) -> Path:
    source_path = _sqlite_path(engine)
    destination = destination.resolve()
    if destination == source_path:
        raise ValueError("Escolha um arquivo diferente do banco em uso.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source_path)) as source, closing(sqlite3.connect(destination)) as target:
        source.backup(target)
    return destination


def restore_sqlite(engine, source: Path) -> None:
    _require_no_active_runs(engine)
    target_path = _sqlite_path(engine)
    source = source.resolve()
    if source == target_path:
        raise ValueError("O arquivo selecionado já é o banco em uso.")
    if not source.is_file():
        raise ValueError("Arquivo de backup não encontrado.")

    try:
        with closing(sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)) as candidate:
            if candidate.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("O backup SQLite falhou na verificação de integridade.")
            tables = {row[0] for row in candidate.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            if not {"robots", "runs", "alembic_version"}.issubset(tables):
                raise ValueError("O arquivo não é um backup válido do Zanella Orchestrator.")
    except sqlite3.DatabaseError as error:
        raise ValueError(f"Backup SQLite inválido: {error}") from error

    safety_path = target_path.with_suffix(target_path.suffix + ".before-restore")
    engine.dispose()
    try:
        with closing(sqlite3.connect(target_path)) as current, closing(sqlite3.connect(safety_path)) as safety:
            current.backup(safety)
        with closing(sqlite3.connect(source)) as backup, closing(sqlite3.connect(target_path)) as current:
            backup.backup(current)
    except Exception:
        if safety_path.exists():
            with closing(sqlite3.connect(safety_path)) as safety, closing(sqlite3.connect(target_path)) as current:
                safety.backup(current)
        raise
    finally:
        safety_path.unlink(missing_ok=True)

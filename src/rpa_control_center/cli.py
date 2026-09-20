"""Command-line entry point used by operators and Windows Task Scheduler."""

import argparse
from pathlib import Path
import sys

from .database import application_data_dir, database_url, upgrade_database
from .engine import run_engine
from .executors import EXECUTOR_TYPES
from .service import add_robot, cancel, enqueue, list_runs
from .scheduler import run_scheduler
from .store import make_engine


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="rcc")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    add = commands.add_parser("robot-add")
    add.add_argument("name")
    add.add_argument("target")
    add.add_argument("--type", choices=EXECUTOR_TYPES, default="python")
    add.add_argument("--executable", "--python", dest="executable", default=sys.executable)
    add.add_argument("--cwd", default=".")
    add.add_argument("--timeout", type=float, default=3600)
    add.add_argument("arguments", nargs="*")
    queue = commands.add_parser("enqueue")
    queue.add_argument("robot_id")
    stop = commands.add_parser("cancel")
    stop.add_argument("run_id")
    commands.add_parser("runs")
    commands.add_parser("engine")
    commands.add_parser("scheduler")
    return root


def main() -> None:
    args = parser().parse_args()
    url = database_url()
    if args.command == "init":
        upgrade_database(url)
        print("Database ready")
        return
    engine = make_engine(url)
    try:
        if args.command == "robot-add":
            print(add_robot(
                engine, args.name, str(Path(args.target).resolve()), str(Path(args.executable).resolve()),
                str(Path(args.cwd).resolve()), args.arguments, args.timeout, args.type,
            ))
        elif args.command == "enqueue":
            print(enqueue(engine, args.robot_id))
        elif args.command == "cancel":
            print(cancel(engine, args.run_id))
        elif args.command == "runs":
            runs, _ = list_runs(engine)
            for run in runs:
                print(run.id, run.state, run.business_result, run.exit_code)
        elif args.command == "engine":
            print(f"Processed {run_engine(engine, application_data_dir() / 'logs')} run(s)")
        elif args.command == "scheduler":
            scheduled, processed = run_scheduler(engine, application_data_dir() / "logs")
            print(f"Scheduled {scheduled}; processed {processed} run(s)")
    finally:
        engine.dispose()

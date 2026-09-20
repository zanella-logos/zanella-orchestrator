from types import SimpleNamespace
import sys

import rpa_control_center.cli as cli


def test_runs_command_handles_paginated_service_result(monkeypatch, capsys):
    engine = SimpleNamespace(dispose=lambda: None)
    run = SimpleNamespace(
        id="run-1",
        state="completed",
        business_result="success",
        exit_code=0,
    )
    monkeypatch.setattr(cli, "database_url", lambda: "sqlite://")
    monkeypatch.setattr(cli, "make_engine", lambda _: engine)
    monkeypatch.setattr(cli, "list_runs", lambda _: ([run], 1))
    monkeypatch.setattr(sys, "argv", ["rcc", "runs"])

    cli.main()

    assert capsys.readouterr().out.strip() == "run-1 completed success 0"


def test_scheduler_command_runs_tick_and_engine(monkeypatch, capsys):
    engine = SimpleNamespace(dispose=lambda: None)
    monkeypatch.setattr(cli, "database_url", lambda: "sqlite://")
    monkeypatch.setattr(cli, "make_engine", lambda _: engine)
    monkeypatch.setattr(cli, "run_scheduler", lambda *_: (2, 3))
    monkeypatch.setattr(sys, "argv", ["rcc", "scheduler"])

    cli.main()

    assert capsys.readouterr().out.strip() == "Scheduled 2; processed 3 run(s)"

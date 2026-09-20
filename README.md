<p align="right"><strong>English</strong> · <a href="README.pt-BR.md">Português (Brasil)</a></p>

<p align="center">
  <img src="assets/branding/zanella-orchestrator-icon.png" alt="Zanella Orchestrator logo" width="160">
</p>

# Zanella Orchestrator

**Local-first orchestration for automation workflows.**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-06B6D4)](https://www.microsoft.com/windows)
[![Python](https://img.shields.io/badge/Python-3.12%2B-3B82F6)](https://www.python.org/)
[![Release](https://img.shields.io/badge/release-0.1.0--rc2-F59E0B)](RELEASE_NOTES.md)

## Download for Windows

[![Download Windows installer](https://img.shields.io/badge/Download-Windows%20Installer-06B6D4?style=for-the-badge&logo=windows11&logoColor=white)](https://github.com/zanella-logos/zanella-orchestrator/releases/download/v0.1.0-rc2/Zanella-Orchestrator-Setup-0.1.0-rc2-windows-x64.exe)

**[Download the `.exe` installer](https://github.com/zanella-logos/zanella-orchestrator/releases/download/v0.1.0-rc2/Zanella-Orchestrator-Setup-0.1.0-rc2-windows-x64.exe)** · [View the latest release](https://github.com/zanella-logos/zanella-orchestrator/releases/latest) · [Portable package and checksum](https://github.com/zanella-logos/zanella-orchestrator/releases/tag/v0.1.0-rc2)

Compatible with 64-bit Windows 10 and 11. The application is not digitally signed yet, so Windows may display a security warning. Verify the SHA-256 checksum published with the release before installing.

**Zanella Orchestrator Community** is a local execution and orchestration engine focused on simplicity, privacy, and control. It helps RPA developers and small teams manage Python, PowerShell, Batch, executable, Node.js, and Java automations from one interface without requiring cloud infrastructure.

**Why Zanella Orchestrator Community?**

- **Local-first:** runs on your workstation or local server, without vendor lock-in.
- **SQLite out of the box:** no database setup is required; PostgreSQL remains optional.
- **Multiple executors:** Python, PowerShell, Batch, EXE, Node.js, and Java JAR files.
- **Clear operations:** FIFO queue, execution history, native log capture, and separate technical and business outcomes.
- **Basic scheduling:** one Windows Task Scheduler trigger activates schedules managed by the application.

Planned **Zanella Orchestrator Pro** modules include remote nodes, advanced calendars with dependencies and retries, RBAC, and advanced SLA dashboards.

## Development environment

Requires Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).

```powershell
uv sync --extra postgres --extra ui
uv run pytest -q
```

`uv.lock` pins dependencies. SQLAlchemy and Alembic handle persistence, pywin32 provides Windows process controls, and Flet powers the desktop interface.

Open the interface:

```powershell
.venv\Scripts\rcc-ui.exe
```

The application can register automations, enqueue or start them immediately, process the queue without blocking the window, cancel executions, browse history, and display logs. See the Portuguese [user manual](docs/MANUAL-USUARIO.md) for detailed UI instructions and [Flet versus Python](docs/FLET-INTERFACE.md) for the control and callback mapping.

## Local PostgreSQL

PostgreSQL is optional for normal use. With a local PostgreSQL server installed and running:

```powershell
uv run python scripts/setup_postgresql.py
uv run python scripts/validate_postgresql.py
```

The setup requests the administrative password without displaying or storing it. It creates the restricted `rcc_app` user, the `rpa_control_center` operational database, and the disposable `rpa_control_center_test` database. A random application password is stored in Windows Credential Manager.

Run setup under the same Windows account that will run Zanella Orchestrator and its scheduled task. The script stops when it finds an existing user and does not alter earlier installations automatically.

## Implemented

- Robot and execution models with an immutable configuration snapshot per run.
- Initial migration and transactional queue claiming validated on SQLite and PostgreSQL 18.
- Per-installation Windows mutex to guarantee sequential execution across sessions.
- Suspended process creation, Windows Job Object assignment, and controlled startup.
- Full child-process tree termination when the final Job Object handle closes.
- Real-process tests for concurrency, termination, and supervisor failure.
- Sequential engine with UTF-8 streaming logs, timeouts, cancellation, recovery, and optional business outcomes.
- CLI for migrations, registration, queueing, history, cancellation, scheduling, and processing.
- Flet, Chrome, and validation demo robots covering screenshots and execution outcomes.
- Robot editing, activation, deactivation, immediate execution, and guarded removal.
- Individual completed-run removal with its log directory.
- Colored technical-state and business-outcome indicators.
- Command adapters for Python, PowerShell, Batch, EXE, Node.js, and Java JAR files.

All entry points in one installation must use the same mutex identifier. The scheduler was validated under the same Windows account as the application. Transactional claiming alone does not prevent two different jobs from running simultaneously; the mutex is also required.

Validation on 2026-09-17: 38 tests passed and 1 PostgreSQL test was skipped. Coverage includes SQLite, generic executors, repeatable migrations, concurrency, Job Objects, supervisor failure, success, business failure, technical failure, sequential queueing, logs, timeout, cancellation, browser capture, editing, activation, and removals. PostgreSQL has a separate credential-aware validation flow.

## Database and migrations

For the default SQLite database, create a `data` directory and run:

```powershell
uv run alembic upgrade head
```

Set `RCC_DATABASE_URL` to use PostgreSQL through psycopg. Never store passwords in versioned files. The validation script builds `RCC_TEST_POSTGRES_URL` only inside the test process and refuses databases that already contain tables.

## Operational validation through the UI

Register `demo/browser_evidence_robot.py` as Python to validate a real Chrome child process. The demo uses a local page and temporary profile, then saves `RCC-evidencia-<run>.png` to the Desktop without requiring internet access.

Register `demo/validation_robot.py` with one of these arguments:

- `success`: emits progressive logs and reports business success;
- `business_error`: exits with code zero but reports a business failure;
- `technical_error`: exits with code 7 and a technical failure;
- `hang`: creates a child process and waits for timeout or cancellation.

Use a short timeout with `hang` to validate `timed_out`, or a long timeout followed by **Cancelar** to validate `cancelled`. Enqueue two `success` runs to confirm sequential ordering.

## Release candidate

Version `0.1.0-rc2` is available for external validation on another Windows machine. It includes an installer, portable package, SHA-256 checksums, and [release notes](RELEASE_NOTES.md).

## Windows executable

The project follows the official `flet build` structure with `main.py` as its entry point and configuration in `pyproject.toml`. Packaged builds store the database, logs, and configuration in `FLET_APP_STORAGE_DATA`; development uses the project `data` directory.

```powershell
.venv\Scripts\flet.exe build windows --python-version 3.13 --no-compile-app --yes --no-rich-output
```

Python sources remain in the package because Alembic discovers revisions under `migrations\versions`. The build is written to `build\windows`; Inno Setup builds the installer from `installer\Zanella-Orchestrator.iss`.

Locally validated candidate: `dist\Zanella-Orchestrator-0.1.0-rc2-windows-x64.zip`. Verify it with `dist\SHA256SUMS.txt`.

## CLI

```powershell
uv run rcc init
uv run rcc robot-add "Example" "C:\path\robot.py" --python "C:\path\.venv\Scripts\python.exe" --cwd "C:\path" --timeout 3600
uv run rcc robot-add "PowerShell" "C:\path\robot.ps1" --type powershell --executable "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" --cwd "C:\path"
uv run rcc enqueue ROBOT_ID
uv run rcc engine
uv run rcc runs
uv run rcc scheduler
uv run rcc cancel RUN_ID
```

`engine` processes the queue until empty. Complete logs are stored in `data/logs/<run_id>`; the database stores paths, states, timestamps, exit codes, and declared business outcomes.

External runtimes are not bundled. Node.js, Java, and other executables must be installed separately and registered with their paths. The PowerShell adapter applies `ExecutionPolicy Bypass` only to the child session and does not change the global Windows policy.

Multilanguage validation on 2026-09-17 ran Python/Flet, PowerShell 5.1, Node.js 22.16.0, and OpenJDK 25.0.3 LTS through the real queue with exit code `0` and business outcome `success`. The generic adapter also launched an executable directly.

## Product direction

| Zanella Orchestrator Community | Zanella Orchestrator Pro |
| --- | --- |
| Python, PowerShell, EXE, Batch, Node.js, and Java | Remote nodes across multiple machines |
| Manual execution and local sequential queue | Invisible Windows service |
| Logs, history, timeout, and cancellation | Advanced SLA and analytics dashboards |
| SQLite out of the box and optional PostgreSQL | Enterprise authentication: RBAC, Active Directory, and SSO |
| Basic scheduling through one Windows trigger | Advanced calendars, dependencies, retries, and cron |
| Basic module API | Advanced Teams, Slack, and webhook alerts |

Docker will remain optional infrastructure. The Windows executor stays native; a remote mobile dashboard may be added later. Redis is not required at this stage.

Scope: [MVP](MVP.md). Technical decisions: [foundation](docs/decisao-fundacao.md) and [generic executor](docs/decisao-executor-generico.md).

## License

Copyright 2026 Victor César Zanella

Licensed under the [Apache License 2.0](LICENSE).

## Author

**Victor César Zanella** is an automation and RPA professional, content creator, and author. He created Zanella Orchestrator to make local automation execution more organized, transparent, and accessible—because even robots need someone to organize the queue.

- [LinkedIn](https://www.linkedin.com/in/victor-zlogos)
- [GitHub](https://github.com/zanella-logos)
- [Nerd Profeta on YouTube](https://www.youtube.com/@nerdprofeta) — nerd and gaming content, livestreams, and biblical reflections.
- Book: [**A Jornada do Nerd para se tornar um Profeta**](https://link.amazon/B09CPEwfe).

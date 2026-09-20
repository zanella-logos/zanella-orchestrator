"""Run the PostgreSQL foundation test using the credential store."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import quote
import uuid

from rpa_control_center.credentials import get_postgres_password, POSTGRES_USERNAME


def main() -> int:
    password = quote(get_postgres_password(), safe="")
    environment = os.environ.copy()
    environment["RCC_TEST_POSTGRES_URL"] = (
        f"postgresql+psycopg://{POSTGRES_USERNAME}:{password}"
        "@localhost:5432/rpa_control_center_test"
    )
    test_directory = (
        Path(os.environ["LOCALAPPDATA"])
        / "RpaControlCenter"
        / "pytest"
        / str(uuid.uuid4())
    )
    test_directory.mkdir(parents=True)
    try:
        return subprocess.call(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "--basetemp",
                str(test_directory),
                "tests",
            ],
            env=environment,
        )
    finally:
        shutil.rmtree(test_directory, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

"""Flet build entry point."""

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from rpa_control_center.ui import run  # noqa: E402


if __name__ == "__main__":
    run()

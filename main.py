"""Flet build entry point."""

from pathlib import Path
import os
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

if __name__ == "__main__":
    if os.environ.get("RCC_SCHEDULER_MODE") == "1":
        from rpa_control_center.cli import main

        sys.argv = ["rcc", "scheduler"]
        try:
            main()
        except Exception:
            import traceback
            from rpa_control_center.database import application_data_dir

            (application_data_dir() / "scheduler-error.log").write_text(
                traceback.format_exc(), encoding="utf-8"
            )
            os._exit(1)
        os._exit(0)
    else:
        from rpa_control_center.ui import run

        run()

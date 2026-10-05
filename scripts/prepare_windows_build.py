"""Stage only application sources so local test data cannot enter a release."""

from pathlib import Path
import shutil
import uuid


root = Path(__file__).resolve().parents[1]
staging = root / "build" / ("rc6-source-" + uuid.uuid4().hex[:8])
staging.mkdir(parents=True, exist_ok=False)
for name in ("main.py", "pyproject.toml", "alembic.ini"):
    shutil.copy2(root / name, staging / name)
for name in ("src", "migrations", "assets"):
    shutil.copytree(root / name, staging / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
print(staging)

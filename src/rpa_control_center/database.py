"""Database configuration and migrations."""

from pathlib import Path
import os
import tomllib
from urllib.parse import quote

from alembic import command
from alembic.config import Config

from .credentials import get_postgres_password


def application_data_dir() -> Path:
    configured = os.environ.get("RCC_DATA_DIR") or os.environ.get("FLET_APP_STORAGE_DATA")
    path = Path(configured) if configured else Path("data").resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_url(config_path: Path | None = None) -> str:
    if config_path is None:
        packaged_storage = os.environ.get("FLET_APP_STORAGE_DATA")
        config_path = Path(packaged_storage) / "config.toml" if packaged_storage else Path("config.toml")
    if not config_path.exists():
        path = application_data_dir() / "control_center.db"
        return "sqlite:///" + path.as_posix()
    config = tomllib.loads(config_path.read_text(encoding="utf-8"))["database"]
    if config.get("backend", "sqlite") == "sqlite":
        path = Path(config.get("sqlite_path", "data/control_center.db")).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return "sqlite:///" + path.as_posix()
    password = quote(get_postgres_password(), safe="")
    return (
        f"postgresql+psycopg://{config.get('username', 'rcc_app')}:{password}"
        f"@{config.get('host', 'localhost')}:{config.get('port', 5432)}"
        f"/{config.get('database', 'rpa_control_center')}"
    )


def upgrade_database(url: str) -> None:
    project_root = Path(__file__).resolve().parents[2]
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("script_location", str(project_root / "migrations"))
    config.attributes["database_url"] = url
    command.upgrade(config, "head")

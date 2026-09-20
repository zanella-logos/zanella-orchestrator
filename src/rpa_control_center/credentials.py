"""Read application secrets from the operating-system credential store."""

import keyring


POSTGRES_SERVICE = "rpa-control-center/postgresql"
POSTGRES_USERNAME = "rcc_app"


def get_postgres_password() -> str:
    password = keyring.get_password(POSTGRES_SERVICE, POSTGRES_USERNAME)
    if not password:
        raise RuntimeError(
            "PostgreSQL credential not configured for the current Windows user. "
            "Run scripts/setup_postgresql.py."
        )
    return password

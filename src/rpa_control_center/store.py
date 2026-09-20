"""Short transactions for queue reservation; no transaction spans robot execution."""

from sqlalchemy import create_engine, event, select, update
from sqlalchemy.orm import Session

from .models import Run


def make_engine(url: str):
    engine = create_engine(url, hide_parameters=True)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def configure(connection, _):
            connection.isolation_level = None
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")

        @event.listens_for(engine, "begin")
        def begin(connection):
            connection.exec_driver_sql("BEGIN")
    return engine


def claim_next(engine):
    """Atomically reserve one item. Caller must also hold the installation lock."""
    with Session(engine) as session, session.begin():
        query = select(Run.id).where(Run.state == "queued").order_by(Run.created_at, Run.id).limit(1)
        # A single conditional UPDATE works on SQLite and PostgreSQL. A competing
        # PostgreSQL transaction may return no row; the caller can poll again.
        run_id = session.scalar(
            update(Run).where(Run.id == query.scalar_subquery(), Run.state == "queued")
            .values(state="starting").returning(Run.id)
        )
        return run_id


def claim_specific(engine, run_id: str) -> bool:
    """Atomically claim a specific queued run by ID.

    Returns True if the run was successfully claimed (it was still queued).
    Returns False if the run is no longer in queued state (already claimed or
    cancelled elsewhere), so the caller knows not to proceed.
    """
    with Session(engine) as session, session.begin():
        claimed = session.scalar(
            update(Run)
            .where(Run.id == run_id, Run.state == "queued")
            .values(state="starting")
            .returning(Run.id)
        )
        return claimed is not None

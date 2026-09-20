import os

from alembic import context

from rpa_control_center.models import Base
from rpa_control_center.store import make_engine

url = context.config.attributes.get("database_url") or os.environ.get(
    "RCC_DATABASE_URL", context.config.get_main_option("sqlalchemy.url")
)
if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = make_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()

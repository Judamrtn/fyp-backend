"""
Alembic migration environment.
Auto-imports all models so Alembic can detect schema changes.
"""
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import Base and ALL models so Alembic sees them
from app.database import Base
import app.models  # noqa: F401 — triggers all model imports

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    """Get DB URL from env or alembic.ini."""
    from app.config import settings
    return settings.database_url


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url             = url,
        target_metadata = target_metadata,
        literal_binds   = True,
        dialect_opts    = {"paramstyle": "named"},
        compare_type    = True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import create_engine
    connectable = create_engine(get_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection      = connection,
            target_metadata = target_metadata,
            compare_type    = True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
"""
Alembic environment configuration (async).

This script is invoked by Alembic for every migration command. It:
    - Loads the database URL from `app.config.settings`.
    - Imports all ORM models so that `Base.metadata` is fully populated.
    - Configures both online (async) and offline migration modes.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ============================================================
# Project imports
# ============================================================

# The project's settings object (holds DATABASE_URL).
from app.config.settings import settings

# Importing the models package registers ALL models with Base.metadata.
# Do NOT remove this import — Alembic needs it for autogenerate.
from app.models import Base  # noqa: F401


# ============================================================
# Alembic Config
# ============================================================

config = context.config

# Programmatically inject the DB URL from the project settings.
# This keeps credentials out of alembic.ini.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Configure Python logging from alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata target for autogenerate.
target_metadata = Base.metadata


# ============================================================
# Offline migrations
# ============================================================

def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    In this mode, Alembic generates SQL scripts without connecting
    to the database.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ============================================================
# Online migrations
# ============================================================

def do_run_migrations(connection: Connection) -> None:
    """Configure the context and run migrations on a live connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        # Render `server_default` only when explicitly set.
        render_as_batch=True,  # useful for SQLite ALTER limitations
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations through it."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using an async engine."""
    asyncio.run(run_async_migrations())


# ============================================================
# Entry point
# ============================================================

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
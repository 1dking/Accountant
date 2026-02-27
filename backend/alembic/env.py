"""Alembic environment configuration for async SQLAlchemy."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import Settings
from app.database import Base

# Import all models so Base.metadata knows about them
import app.auth.models  # noqa: F401
import app.documents.models  # noqa: F401
import app.collaboration.models  # noqa: F401
import app.notifications.models  # noqa: F401
import app.calendar.models  # noqa: F401
import app.accounting.models  # noqa: F401
import app.contacts.models  # noqa: F401
import app.invoicing.models  # noqa: F401
import app.income.models  # noqa: F401
import app.recurring.models  # noqa: F401
import app.budgets.models  # noqa: F401
import app.email.models  # noqa: F401
import app.integrations.gmail.models  # noqa: F401
import app.integrations.plaid.models  # noqa: F401
import app.integrations.stripe.models  # noqa: F401
import app.integrations.twilio.models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Load settings (database_url comes from .env)
settings = Settings()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL without connecting)."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with an async engine."""
    connectable = create_async_engine(settings.database_url, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

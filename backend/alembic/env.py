"""
Alembic env.py – migration environment configuration.

Key customisations vs. default:
  • Reads DATABASE_URL from the application settings (honours .env).
  • Imports all SQLAlchemy models so Alembic can auto-detect table changes.
  • Supports both online (run_migrations_online) and offline modes.
"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ── Make app importable from alembic/ subdirectory ────────────────────────────
# Adjust if your project root is elsewhere.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Import app settings and ALL models ───────────────────────────────────────
from app.core.config import get_settings  # noqa: E402
from app.database.connection import Base  # noqa: E402
import app.database.models  # noqa: F401, E402  ← registers all tables with Base.metadata

settings = get_settings()

# ── Alembic Config ────────────────────────────────────────────────────────────
config = context.config

# Override the sqlalchemy.url from alembic.ini with the live app setting
config.set_main_option("sqlalchemy.url", settings.database_url)

# Set up logging from the alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata – Alembic uses this to detect schema changes
target_metadata = Base.metadata


# ── Offline mode (generates SQL script without a live DB connection) ──────────
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode (applies migrations to a live database) ───────────────────────
def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,   # Detect column type changes
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

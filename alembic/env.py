from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.backend.persistence.schema import metadata

config = context.config

if config.config_file_name is not None:
    # disable_existing_loggers=False: a migration must NOT silence the application's own loggers.
    # The default (True) disables every logger not named in alembic.ini — including `callosum` and
    # `callosum.llm.usage` — so a real startup auto-migration would otherwise kill usage logging
    # (and forced the `_loud()` re-enable hack in startup.py, kept now only as defense-in-depth).
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = metadata


def include_object(object, name, type_, reflected, compare_to):
    # chunks_fts (inc 209/A3) is a raw `CREATE VIRTUAL TABLE ... USING fts5` (migration 0026) — an external-content
    # FTS5 index with no SQLAlchemy Core `Table` equivalent, so it (and the shadow tables SQLite generates for it:
    # _data/_idx/_docsize/_config) can never appear in `target_metadata`. Without this exclusion, `alembic check`
    # (tests/test_migrations.py) would report them as permanent, un-fixable drift on every run.
    if type_ == "table" and name.startswith("chunks_fts"):
        return False
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        if connection.dialect.name == "sqlite":
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")

        context.configure(connection=connection, target_metadata=target_metadata, include_object=include_object)

        with context.begin_transaction():
            context.run_migrations()

        if connection.dialect.name == "sqlite":
            connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

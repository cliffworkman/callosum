"""CI gate (backlog #20 ratchet): a fresh temp DB must reach `alembic upgrade head` cleanly, and the
resulting schema must match the SQLAlchemy models exactly (`alembic check` — zero autogenerate drift).
Together these catch both a broken migration (execution) and a model/migration mismatch (drift) that the
rest of the suite — which seeds its DBs via `metadata.create_all()`, not through the migration chain — never
exercises.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, inspect

from alembic import command
from alembic.config import Config

REPO_ROOT = Path(__file__).resolve().parent.parent


def _config_for(db_url: str) -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_alembic_upgrade_head_succeeds_on_a_fresh_db(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'migration-upgrade.sqlite'}"
    command.upgrade(_config_for(db_url), "head")


def test_alembic_check_reports_no_model_drift(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'migration-check.sqlite'}"
    cfg = _config_for(db_url)
    command.upgrade(cfg, "head")
    command.check(cfg)


def test_wip_tool_run_migration_upgrades_an_existing_0050_database(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'migration-wip-tool-runs.sqlite'}"
    cfg = _config_for(db_url)
    command.upgrade(cfg, "0050_wip_snapshots")
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE wip_findings")
        conn.exec_driver_sql("DROP TABLE wip_tool_runs")
        conn.exec_driver_sql("DROP TABLE tool_runs")
    engine.dispose()

    command.upgrade(cfg, "head")

    engine = create_engine(db_url)
    assert {"tool_runs", "wip_tool_runs", "wip_findings"} <= set(inspect(engine).get_table_names())
    engine.dispose()

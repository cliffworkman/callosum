"""CI gate (backlog #20 ratchet): a fresh temp DB must reach `alembic upgrade head` cleanly, and the
resulting schema must match the SQLAlchemy models exactly (`alembic check` — zero autogenerate drift).
Together these catch both a broken migration (execution) and a model/migration mismatch (drift) that the
rest of the suite — which seeds its DBs via `metadata.create_all()`, not through the migration chain — never
exercises.
"""

from __future__ import annotations

import json
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


def test_emerging_citing_topic_snapshot_table_is_at_head(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'migration-emerging-topics.sqlite'}"
    cfg = _config_for(db_url)
    command.upgrade(cfg, "head")
    engine = create_engine(db_url)
    columns = {column["name"] for column in inspect(engine).get_columns("my_publication_emerging_topic_cache")}
    assert columns == {"id", "scope_key", "scope", "topics", "coverage", "computed_at"}
    engine.dispose()


def test_top_factor_records_table_is_at_head(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'migration-top-factor.sqlite'}"
    cfg = _config_for(db_url)
    command.upgrade(cfg, "head")
    engine = create_engine(db_url)
    columns = {column["name"] for column in inspect(engine).get_columns("top_factor_records")}
    assert columns == {"id", "issn", "eissn", "journal", "categories_json", "total", "retrieved_at"}
    engine.dispose()


def test_ajol_records_table_is_at_head(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'migration-ajol.sqlite'}"
    cfg = _config_for(db_url)
    command.upgrade(cfg, "head")
    engine = create_engine(db_url)
    columns = {column["name"] for column in inspect(engine).get_columns("ajol_records")}
    assert columns == {
        "id",
        "issn",
        "eissn",
        "journal",
        "country",
        "jpps_status",
        "is_diamond",
        "source_url",
        "retrieved_at",
    }
    engine.dispose()


def test_usage_events_table_is_at_head(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'migration-usage-events.sqlite'}"
    cfg = _config_for(db_url)
    command.upgrade(cfg, "head")
    engine = create_engine(db_url)
    columns = {column["name"] for column in inspect(engine).get_columns("usage_events")}
    assert columns == {"id", "event_type", "count", "duration_ms", "created_at"}
    engine.dispose()


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


def test_domain_scoped_gap_migration_preserves_the_all_publications_snapshot(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'migration-domain-scoped-gaps.sqlite'}"
    cfg = _config_for(db_url)
    command.upgrade(cfg, "0052_my_publication_citation_gaps")
    engine = create_engine(db_url)
    with engine.begin() as conn:
        # Migration 0001 creates tables from current metadata on a fresh database, so explicitly recreate the
        # deployed Increment-386 shape before exercising the 0052 -> head upgrade path.
        conn.exec_driver_sql("DROP TABLE my_publication_citation_gap_cache")
        conn.exec_driver_sql(
            """
            CREATE TABLE my_publication_citation_gap_cache (
                id INTEGER PRIMARY KEY,
                candidates JSON NOT NULL,
                coverage JSON NOT NULL,
                computed_at VARCHAR(40) NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            INSERT INTO my_publication_citation_gap_cache
                (id, candidates, coverage, computed_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                1,
                json.dumps([{"openalex_work_id": "W301"}]),
                json.dumps({"checked": 2}),
                "2026-07-25T12:30:00+00:00",
            ),
        )
    engine.dispose()

    command.upgrade(cfg, "head")

    engine = create_engine(db_url)
    with engine.connect() as conn:
        row = (
            conn.exec_driver_sql(
                """
            SELECT scope_key, scope, candidates, coverage, computed_at
            FROM my_publication_citation_gap_cache
            """
            )
            .mappings()
            .one()
        )
    assert row["scope_key"] == "all"
    assert json.loads(row["scope"])["kind"] == "all"
    assert json.loads(row["candidates"])[0]["openalex_work_id"] == "W301"
    assert json.loads(row["coverage"])["checked"] == 2
    assert row["computed_at"] == "2026-07-25T12:30:00+00:00"
    assert {"scope_key", "scope"} <= {
        column["name"] for column in inspect(engine).get_columns("my_publication_citation_gap_cache")
    }
    engine.dispose()


def test_followed_authors_migration_upgrades_an_existing_0068_database(tmp_path):
    """Regression: 0069's guarded create originally added the UNIQUE constraint via a separate
    op.create_unique_constraint() call, which SQLite's dialect cannot ALTER onto an existing table
    (NotImplementedError). A fresh-DB test alone can't catch this -- migration 0001 creates every
    current-metadata table via metadata.create_all() (which handles the constraint natively), so the
    guarded 0069 branch never actually ran on a fresh DB. Only a real pre-existing deployed database
    (upgrade to 0068, drop the tables migration 0001 pre-created, then upgrade to head) exercises the
    branch that Alembic's ALTER-based path actually executes."""
    db_url = f"sqlite:///{tmp_path / 'migration-followed-authors.sqlite'}"
    cfg = _config_for(db_url)
    command.upgrade(cfg, "0068_ajol_records")
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE followed_author_candidates")
        conn.exec_driver_sql("DROP TABLE followed_authors")
    engine.dispose()

    command.upgrade(cfg, "head")

    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO followed_authors (author_id, display_name, matched_by) VALUES ('A1', 'A', 'name')"
        )
        try:
            conn.exec_driver_sql(
                "INSERT INTO followed_authors (author_id, display_name, matched_by) VALUES ('A1', 'B', 'name')"
            )
            duplicate_rejected = False
        except Exception:
            duplicate_rejected = True
    engine.dispose()
    assert duplicate_rejected  # the UNIQUE constraint on author_id survived the real ALTER-based upgrade path

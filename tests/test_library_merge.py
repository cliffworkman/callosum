import json
from pathlib import Path

from sqlalchemy import create_engine, insert, select

from alembic import command
from alembic.config import Config
from app.backend.persistence import schema
from app.backend.persistence.schema import merge_operations, papers


def _fresh_engine(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'm.sqlite'}")
    schema.metadata.create_all(engine)
    return engine


def test_merge_operations_roundtrip_and_merged_into_column(tmp_path):
    engine = _fresh_engine(tmp_path)
    with engine.begin() as conn:
        a = conn.execute(insert(papers).values(title="A", csl_json={})).inserted_primary_key[0]
        b = conn.execute(insert(papers).values(title="B", csl_json={}, merged_into=a)).inserted_primary_key[0]
        op_id = conn.execute(
            insert(merge_operations).values(
                canonical_paper_id=a, merged_paper_id=b, snapshot_json=json.dumps({"repoints": []}), status="active"
            )
        ).inserted_primary_key[0]
        row = conn.execute(select(merge_operations).where(merge_operations.c.id == op_id)).mappings().one()
        assert row["status"] == "active" and row["canonical_paper_id"] == a and row["merged_paper_id"] == b
        assert conn.execute(select(papers.c.merged_into).where(papers.c.id == b)).scalar_one() == a


def test_migrations_upgrade_head_creates_merge_schema(tmp_path):
    db = tmp_path / "mig.sqlite"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db}")
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db}")
    from sqlalchemy import inspect

    insp = inspect(engine)
    assert "merge_operations" in insp.get_table_names()
    assert "merged_into" in {c["name"] for c in insp.get_columns("papers")}

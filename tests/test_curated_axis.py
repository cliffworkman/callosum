"""inc 211 (A7 SP1) — the curated-axis primitive: kind, manual ordering, freeze/revert."""

from __future__ import annotations

import sqlalchemy as sa

from app.backend.persistence.database import make_engine


def test_position_column_exists(temp_db_url):
    engine = make_engine(temp_db_url)
    cols = {c["name"] for c in sa.inspect(engine).get_columns("cluster_node_papers")}
    engine.dispose()
    assert "position" in cols

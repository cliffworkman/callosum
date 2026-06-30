"""inc 211 (A7 SP1) — the curated-axis primitive: kind, manual ordering, freeze/revert."""

from __future__ import annotations

import sqlalchemy as sa

from app.backend.clustering.axis_assignments import (
    add_manual_assignment,
    append_member_position,
    ensure_axis_node,
)
from app.backend.clustering.axis_scoring import create_axis
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper, get_papers_for_cluster_node


def _paper(conn, title):
    return create_paper(conn, title=title, csl_json={"title": title})


def test_position_column_exists(temp_db_url):
    engine = make_engine(temp_db_url)
    cols = {c["name"] for c in sa.inspect(engine).get_columns("cluster_node_papers")}
    engine.dispose()
    assert "position" in cols


def test_manual_add_appends_position_and_reads_in_order(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        axis_id = create_axis(conn, label="Aim 2")
        ids = [_paper(conn, t) for t in ("One", "Two", "Three")]
        for pid in ids:
            add_manual_assignment(conn, axis_id=axis_id, paper_id=pid)
            append_member_position(conn, axis_id=axis_id, paper_id=pid)
        node_id = ensure_axis_node(conn, axis_id)
        order = [r["id"] for r in get_papers_for_cluster_node(conn, node_id)]
    engine.dispose()
    assert order == ids  # insertion order == position order

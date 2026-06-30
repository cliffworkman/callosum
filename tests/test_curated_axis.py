"""inc 211 (A7 SP1) — the curated-axis primitive: kind, manual ordering, freeze/revert."""

from __future__ import annotations

import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy import insert, select

from app.backend.api import create_app
from app.backend.clustering.axis_assignments import (
    add_manual_assignment,
    append_member_position,
    ensure_axis_node,
    freeze_to_curated,
    revert_to_keyword,
    set_member_order,
)
from app.backend.clustering.axis_scoring import create_axis
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper, get_papers_for_cluster_node
from app.backend.persistence.schema import axes
from app.backend.persistence.schema import cluster_node_papers as cnp


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


def test_set_member_order_validates_and_writes(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        axis_id = create_axis(conn, label="Aim 2")
        ids = [_paper(conn, t) for t in ("A", "B", "C")]
        for pid in ids:
            add_manual_assignment(conn, axis_id=axis_id, paper_id=pid)
            append_member_position(conn, axis_id=axis_id, paper_id=pid)
        set_member_order(conn, axis_id=axis_id, paper_ids=list(reversed(ids)))
        node_id = ensure_axis_node(conn, axis_id)
        order = [r["id"] for r in get_papers_for_cluster_node(conn, node_id)]
    engine.dispose()
    assert order == list(reversed(ids))


def test_set_member_order_rejects_foreign_id_set(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        axis_id = create_axis(conn, label="Aim")
        a, b = _paper(conn, "A"), _paper(conn, "B")
        for pid in (a, b):
            add_manual_assignment(conn, axis_id=axis_id, paper_id=pid)
        raised = False
        try:
            set_member_order(conn, axis_id=axis_id, paper_ids=[a, 99999])  # 99999 not a member
        except ValueError:
            raised = True
    engine.dispose()
    assert raised


def test_order_endpoint_422_on_non_curated_axis(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        axis_id = create_axis(conn, label="Keyword axis")  # kind defaults standard
        ids = [_paper(conn, t) for t in ("A", "B")]
        for pid in ids:
            add_manual_assignment(conn, axis_id=axis_id, paper_id=pid)
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.put(f"/axes/{axis_id}/order", json={"paper_ids": ids}).status_code == 422


def _kind(conn, axis_id):
    return conn.execute(select(axes.c.kind).where(axes.c.id == axis_id)).scalar_one()


def test_freeze_keeps_assigned_plus_manual_drops_uncertain(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        axis_id = create_axis(conn, label="Topic")  # standard
        node_id = ensure_axis_node(conn, axis_id)
        hi = _paper(conn, "assigned")
        conn.execute(insert(cnp).values(cluster_node_id=node_id, paper_id=hi, confidence=0.6))
        lo = _paper(conn, "uncertain")
        conn.execute(insert(cnp).values(cluster_node_id=node_id, paper_id=lo, confidence=0.2))
        man = _paper(conn, "manual")
        add_manual_assignment(conn, axis_id=axis_id, paper_id=man)
        freeze_to_curated(conn, axis_id=axis_id, cutoff=0.35)
        kind = _kind(conn, axis_id)
        rows = get_papers_for_cluster_node(conn, node_id)
    engine.dispose()
    assert kind == "curated"
    assert [r["id"] for r in rows] == [hi, man]  # uncertain dropped; assigned (0.6) ordered before manual
    assert all(r["confidence"] is None for r in rows)  # all demoted to manual


def test_revert_keeps_members_clears_order(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        axis_id = create_axis(conn, label="Aim", kind="curated")
        node_id = ensure_axis_node(conn, axis_id)
        ids = [_paper(conn, t) for t in ("A", "B")]
        for pid in ids:
            add_manual_assignment(conn, axis_id=axis_id, paper_id=pid)
            append_member_position(conn, axis_id=axis_id, paper_id=pid)
        revert_to_keyword(conn, axis_id=axis_id)
        kind = _kind(conn, axis_id)
        members = {r["id"] for r in get_papers_for_cluster_node(conn, node_id)}
        positions = [r[0] for r in conn.execute(select(cnp.c.position).where(cnp.c.cluster_node_id == node_id))]
    engine.dispose()
    assert kind == "standard"
    assert members == set(ids)  # members survive
    assert all(p is None for p in positions)  # order cleared


def test_create_curated_via_endpoint_and_bad_kind_422(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    ok = client.post("/axes", json={"label": "Aim 2", "kind": "curated"})
    assert ok.status_code == 201 and ok.json()["kind"] == "curated"
    assert client.post("/axes", json={"label": "X", "kind": "folder"}).status_code == 422
    assert client.post("/axes", json={"label": "Y", "kind": "my_publications"}).status_code == 422


def test_patch_freeze_then_revert_via_endpoint(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        axis_id = create_axis(conn, label="Topic")
        pid = _paper(conn, "member")
        add_manual_assignment(conn, axis_id=axis_id, paper_id=pid)
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    frozen = client.patch(f"/axes/{axis_id}", json={"kind": "curated"})
    assert frozen.status_code == 200 and frozen.json()["kind"] == "curated"
    reverted = client.patch(f"/axes/{axis_id}", json={"kind": "standard"})
    assert reverted.status_code == 200 and reverted.json()["kind"] == "standard"
    # member survives the round trip
    clusters = client.get(f"/axes/{axis_id}/clusters").json()
    member_ids = {p["id"] for node in clusters for p in node["papers"]}
    assert pid in member_ids

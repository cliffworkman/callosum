"""Reversible un-merge (#16) — the undo net for the inc-161 non-destructive merge.

Merge (paper_merge.py) records a self-contained reversal snapshot on a merge_operations row; unmerge
(paper_unmerge.py) replays it. These tests prove the schema, the functional round-trip (merge → un-merge
restores the survivor's record + the husk's moved data + removes the added union links), the merge-origin
affordance, the Trash/purge guards for merged-away papers, and the endpoint contract.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, insert, select

from alembic import command
from alembic.config import Config
from app.backend.api import create_app
from app.backend.metadata.paper_merge import merge_papers
from app.backend.metadata.paper_unmerge import merge_origin, unmerge
from app.backend.persistence import profile_repo, schema
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_paper, get_paper
from app.backend.persistence.schema import (
    annotations,
    attachments,
    cluster_node_papers,
    cluster_nodes,
    merge_operations,
    notes,
    paper_external_identifiers,
    papers,
)
from app.backend.persistence.tags_repo import add_tag_to_paper, get_tags_for_paper


def _migrated(tmp_path: Path):
    url = f"sqlite:///{(tmp_path / 'm.sqlite').as_posix()}"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    return make_engine(url)


# --- schema (from the reversibility foundation) -----------------------------------------------------------------


def test_merge_operations_roundtrip_and_merged_into_column(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'schema.sqlite'}")
    schema.metadata.create_all(engine)
    with engine.begin() as conn:
        a = conn.execute(insert(papers).values(title="A", csl_json={})).inserted_primary_key[0]
        b = conn.execute(insert(papers).values(title="B", csl_json={}, merged_into=a)).inserted_primary_key[0]
        op_id = conn.execute(
            insert(merge_operations).values(
                canonical_paper_id=a, merged_paper_id=b, snapshot_json=json.dumps({"husks": []}), status="active"
            )
        ).inserted_primary_key[0]
        row = conn.execute(select(merge_operations).where(merge_operations.c.id == op_id)).mappings().one()
        assert row["status"] == "active" and row["canonical_paper_id"] == a
        assert conn.execute(select(papers.c.merged_into).where(papers.c.id == b)).scalar_one() == a


def test_migrations_upgrade_head_creates_merge_schema(tmp_path):
    engine = _migrated(tmp_path)
    from sqlalchemy import inspect

    insp = inspect(engine)
    assert "merge_operations" in insp.get_table_names()
    assert "merged_into" in {c["name"] for c in insp.get_columns("papers")}
    engine.dispose()


# --- seeding + the reversibility round-trip ---------------------------------------------------------------------


def _seed_merge_pair(conn) -> tuple[int, int, dict]:
    """A survivor + a husk carrying every kind of association a merge moves/unions. Returns (survivor, husk, ids)."""
    survivor = create_paper(conn, title="Survivor", csl_json={"title": "Survivor", "URL": "https://osf.io/x/"})
    husk = create_paper(
        conn,
        title="Husk (published)",
        csl_json={"title": "Husk (published)", "DOI": "10.1/pub"},
        doi="10.1/pub",
        openalex_work_id="W99",
    )
    s_att = create_attachment(
        conn,
        paper_id=survivor,
        storage_mode="linked",
        availability="available",
        content_type="application/pdf",
        checksum="chk-s",
        attachment_type="pdf",
        role="primary",
    )
    create_attachment(
        conn,
        paper_id=husk,
        storage_mode="linked",
        availability="available",
        content_type="application/pdf",
        checksum="chk-h",
        attachment_type="pdf",
        role="primary",
    )
    conn.execute(insert(annotations).values(paper_id=husk, page=1, source="user"))
    conn.execute(insert(notes).values(paper_id=husk, body="a note"))
    conn.execute(insert(paper_external_identifiers).values(paper_id=husk, provider="pmid", identifier="777"))
    add_tag_to_paper(conn, husk, "neuro")  # union onto survivor
    axis_id = int(conn.execute(insert(schema.axes).values(label="Ax", description="d")).inserted_primary_key[0])
    node_id = int(
        conn.execute(insert(cluster_nodes).values(axis_id=axis_id, parent_id=None, label="n")).inserted_primary_key[0]
    )
    conn.execute(insert(cluster_node_papers).values(cluster_node_id=node_id, paper_id=husk, confidence=None))
    conn.execute(insert(schema.profile).values(starred_paper_ids=[husk], research_domains=[]))  # My-Pubs ref to husk
    return survivor, husk, {"s_att": s_att, "node_id": node_id}


def test_merge_then_unmerge_restores_survivor_and_husk(tmp_path):
    engine = _migrated(tmp_path)
    with engine.begin() as conn:
        survivor, husk, ids = _seed_merge_pair(conn)
        survivor_csl_before = get_paper(conn, survivor)["csl_json"]

        result = merge_papers(
            conn,
            survivor_id=survivor,
            merged_ids=[husk],
            metadata={"doi": "10.1/pub"},
            primary_attachment_id=ids["s_att"],
        )
        # merged state: husk hidden + adopted DOI on survivor
        assert get_paper(conn, survivor)["doi"] == "10.1/pub"
        assert get_paper(conn, husk)["merged_into"] == survivor
        assert conn.execute(select(func.count()).where(attachments.c.paper_id == survivor)).scalar_one() == 2
        assert {t["name"] for t in get_tags_for_paper(conn, survivor)} == {"neuro"}

        unmerge(conn, merge_operation_id=result.merge_operation_id)

        # survivor restored: DOI back to None, csl_json back to the original (lineage note gone), imported_source cleared
        s = get_paper(conn, survivor)
        assert s["doi"] is None
        assert s["csl_json"] == survivor_csl_before
        # husk restored: live again, its id columns back, its moved rows back
        h = get_paper(conn, husk)
        assert h["deleted_at"] is None and h["merged_into"] is None
        assert h["doi"] == "10.1/pub" and h["openalex_work_id"] == "W99"
        for table in (attachments, annotations, notes, paper_external_identifiers):
            assert conn.execute(select(func.count()).where(table.c.paper_id == husk)).scalar_one() >= 1
        assert conn.execute(select(func.count()).where(attachments.c.paper_id == survivor)).scalar_one() == 1  # own PDF
        # union links removed from the survivor; the husk keeps its own
        assert get_tags_for_paper(conn, survivor) == []
        assert {t["name"] for t in get_tags_for_paper(conn, husk)} == {"neuro"}
        assert (
            conn.execute(
                select(func.count()).where(
                    cluster_node_papers.c.paper_id == survivor, cluster_node_papers.c.cluster_node_id == ids["node_id"]
                )
            ).scalar_one()
            == 0
        )
        # My-Pubs star restored to the husk; the op is undone
        assert profile_repo.get_profile(conn)["starred_paper_ids"] == [husk]
        assert (
            conn.execute(
                select(merge_operations.c.status).where(merge_operations.c.id == result.merge_operation_id)
            ).scalar_one()
            == "undone"
        )
    engine.dispose()


def test_merge_origin_and_double_unmerge_guard(tmp_path):
    engine = _migrated(tmp_path)
    with engine.begin() as conn:
        survivor, husk, _ = _seed_merge_pair(conn)
        result = merge_papers(conn, survivor_id=survivor, merged_ids=[husk])

        origin = merge_origin(conn, survivor)
        assert origin["merge_operation_id"] == result.merge_operation_id
        assert origin["merged_from_titles"] == ["Husk (published)"]

        unmerge(conn, merge_operation_id=result.merge_operation_id)
        assert merge_origin(conn, survivor) is None  # no longer an active merge

        import pytest

        with pytest.raises(ValueError):
            unmerge(conn, merge_operation_id=result.merge_operation_id)  # already undone
    engine.dispose()


# --- Trash/purge guards for merged-away papers ------------------------------------------------------------------


class _NoVec:
    def delete(self, *args, **kwargs): ...


def test_merged_away_husk_hidden_from_trash_and_not_purgeable(tmp_path):
    from app.backend.persistence import repository
    from app.backend.persistence.paper_lifecycle_repo import purge_paper, restore_paper, soft_delete_paper

    engine = _migrated(tmp_path)
    with engine.begin() as conn:
        survivor, husk, _ = _seed_merge_pair(conn)
        merge_papers(conn, survivor_id=survivor, merged_ids=[husk])

        trash_ids = {r["id"] for r in repository.list_papers(conn, only_deleted=True)}
        assert husk not in trash_ids  # merged-away, not naively-restorable trash
        assert purge_paper(conn, husk, vector_store=_NoVec()) is False  # un-merge first

        soft_delete_paper(conn, survivor)
        assert purge_paper(conn, survivor, vector_store=_NoVec()) is False  # active-merge canonical
        restore_paper(conn, survivor)
    engine.dispose()


# --- endpoint contract ------------------------------------------------------------------------------------------


def test_unmerge_endpoint_roundtrip(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        survivor, husk, _ = _seed_merge_pair(conn)
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    merged = client.post("/papers/merge", json={"survivor_id": survivor, "merged_ids": [husk]})
    assert merged.status_code == 200, merged.text
    op_id = merged.json()["merge_operation_id"]

    origin = client.get(f"/papers/{survivor}/merge-origin")
    assert origin.status_code == 200 and origin.json()["merge_operation_id"] == op_id

    undo = client.post(f"/merge/{op_id}/undo")
    assert undo.status_code == 200 and undo.json()["restored_ids"] == [husk]
    # husk is live again; origin now null
    assert husk in {p["id"] for p in client.get("/papers").json()}
    assert client.get(f"/papers/{survivor}/merge-origin").json() is None
    assert client.post(f"/merge/{op_id}/undo").status_code == 422  # already undone

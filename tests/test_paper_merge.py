"""Tests for the non-destructive paper merge (inc 161).

The researcher's case (preprint + published copy): merge keeps BOTH PDFs, ensures the OSF link survives, and loses
no source data — the merged-away copy goes to Trash. Engine-level unit tests cover the migrations + lineage; the
endpoint tests cover the 422/409/200 contract.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select

from alembic import command
from alembic.config import Config
from app.backend.api import create_app
from app.backend.metadata.paper_merge import (
    MergeValidationError,
    merge_papers,
)
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import (
    create_attachment,
    create_chunk,
    create_paper,
    get_paper,
    soft_delete_paper,
)
from app.backend.persistence.schema import (
    annotations,
    attachments,
    axes,
    chunks,
    cluster_node_papers,
    cluster_nodes,
    notes,
    paper_external_identifiers,
    paper_tags,
)
from app.backend.persistence.tags_repo import add_tag_to_paper


def _migrated(tmp_path: Path):
    url = f"sqlite:///{(tmp_path / 'merge.sqlite').as_posix()}"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    return make_engine(url)


def _attach(conn, paper_id, *, checksum, role=None):
    return create_attachment(
        conn,
        paper_id=paper_id,
        storage_mode="linked",
        availability="available",
        content_type="application/pdf",
        checksum=checksum,
        attachment_type="pdf",
        role=role,
    )


def _chunk(conn, paper_id, attachment_id, *, version):
    return create_chunk(
        conn,
        paper_id=paper_id,
        attachment_id=attachment_id,
        text="a passage",
        page_start=1,
        page_end=1,
        bbox_coordinate_system="pdf-points-top-left",
        extraction_tool="fixture",
        extraction_version="1",
        chunking_strategy="paragraph",
        chunk_version=version,
        source_attachment_checksum=checksum_for(version),
        bbox_json=[{"page": 1, "x0": 1, "y0": 2, "x1": 3, "y1": 4}],
    )


def checksum_for(version: str) -> str:
    return f"chk-{version}"


def _manual_axis_member(conn, paper_id) -> int:
    axis_id = int(conn.execute(insert(axes).values(label="Ax", description="d")).inserted_primary_key[0])
    node_id = int(
        conn.execute(insert(cluster_nodes).values(axis_id=axis_id, parent_id=None, label="n")).inserted_primary_key[0]
    )
    conn.execute(insert(cluster_node_papers).values(cluster_node_id=node_id, paper_id=paper_id, confidence=None))
    return node_id


def _seed_preprint_and_published(conn) -> tuple[int, int]:
    """Survivor = a preprint (OSF URL + a PDF, no DOI); merged = the published copy (DOI + a PDF)."""
    preprint = create_paper(
        conn,
        title="Risk evaluation in observers (preprint)",
        csl_json={
            "type": "article",
            "title": "Risk evaluation in observers (preprint)",
            "URL": "https://osf.io/abc12/",
            "author": [{"literal": "Ada Lovelace"}],
        },
        year=2023,
        first_author_family_name="Lovelace",
    )
    published = create_paper(
        conn,
        title="Risk evaluation in observers",
        csl_json={
            "type": "article-journal",
            "title": "Risk evaluation in observers",
            "DOI": "10.123/published",
            "container-title": "Journal of Risk",
            "author": [{"literal": "Ada Lovelace"}],
        },
        year=2024,
        doi="10.123/published",
        venue="Journal of Risk",
        openalex_work_id="W42",
        first_author_family_name="Lovelace",
    )
    return preprint, published


# ---------------------------------------------------------------------------------------------------------------
# Engine-level


def test_merge_migrates_all_source_data_to_survivor(tmp_path: Path) -> None:
    engine = _migrated(tmp_path)
    with engine.begin() as conn:
        survivor, merged = _seed_preprint_and_published(conn)
        s_att = _attach(conn, survivor, checksum="chk-pre", role="primary")
        m_att = _attach(conn, merged, checksum="chk-pub", role="primary")
        _chunk(conn, merged, m_att, version="cv-pub")
        conn.execute(insert(annotations).values(paper_id=merged, attachment_id=m_att, page=1, source="user"))
        conn.execute(insert(notes).values(paper_id=merged, body="a note"))
        conn.execute(insert(paper_external_identifiers).values(paper_id=merged, provider="pmid", identifier="999"))
        add_tag_to_paper(conn, merged, "neuroscience")
        node = _manual_axis_member(conn, merged)

        merge_papers(conn, survivor_id=survivor, merged_ids=[merged], primary_attachment_id=s_att)

        # every source row now belongs to the survivor; none left on the husk
        for table in (attachments, chunks, annotations, notes, paper_external_identifiers):
            assert conn.execute(select(func.count()).where(table.c.paper_id == merged)).scalar_one() == 0
        assert (
            conn.execute(select(func.count()).where(attachments.c.paper_id == survivor)).scalar_one() == 2
        )  # both PDFs
        assert conn.execute(select(func.count()).where(chunks.c.paper_id == survivor)).scalar_one() == 1
        # tag + manual axis membership unioned onto the survivor
        assert conn.execute(select(func.count()).where(paper_tags.c.paper_id == survivor)).scalar_one() == 1
        assert (
            conn.execute(
                select(func.count()).where(
                    cluster_node_papers.c.paper_id == survivor, cluster_node_papers.c.cluster_node_id == node
                )
            ).scalar_one()
            == 1
        )
        # the husk is in Trash (reversible audit), the survivor stays live
        assert get_paper(conn, merged)["deleted_at"] is not None
        assert get_paper(conn, survivor)["deleted_at"] is None
    engine.dispose()


def test_lineage_note_and_both_links_survive(tmp_path: Path) -> None:
    engine = _migrated(tmp_path)
    with engine.begin() as conn:
        survivor, merged = _seed_preprint_and_published(conn)
        # user keeps the preprint as survivor but adopts the published DOI; OSF URL stays (survivor's, untouched)
        merge_papers(conn, survivor_id=survivor, merged_ids=[merged], metadata={"doi": "10.123/published"})
        s = get_paper(conn, survivor)
        assert s["doi"] == "10.123/published"  # adopted
        assert s["csl_json"]["URL"] == "https://osf.io/abc12/"  # OSF link survives
        note = s["csl_json"]["note"]
        assert "Merged from" in note and "10.123/published" in note  # lineage captures the merged identifier
        assert s["imported_source"] == "merged"
        # DOI is allowed to remain on the merged husk; csl_json also keeps it for audit.
        m = get_paper(conn, merged)
        assert m["doi"] == "10.123/published"
        assert m["csl_json"]["DOI"] == "10.123/published"
    engine.dispose()


def test_adopts_openalex_id_survivor_lacks(tmp_path: Path) -> None:
    engine = _migrated(tmp_path)
    with engine.begin() as conn:
        survivor, merged = _seed_preprint_and_published(conn)  # survivor has no openalex id; merged has W42
        merge_papers(conn, survivor_id=survivor, merged_ids=[merged])
        assert get_paper(conn, survivor)["openalex_work_id"] == "W42"  # adopted
        assert get_paper(conn, merged)["openalex_work_id"] is None  # freed on the husk
    engine.dispose()


def test_primary_attachment_pick(tmp_path: Path) -> None:
    engine = _migrated(tmp_path)
    with engine.begin() as conn:
        survivor, merged = _seed_preprint_and_published(conn)
        s_att = _attach(conn, survivor, checksum="chk-pre", role="primary")
        _attach(conn, merged, checksum="chk-pub", role="primary")
        # keep the preprint's PDF as primary
        merge_papers(conn, survivor_id=survivor, merged_ids=[merged], primary_attachment_id=s_att)
        primaries = [
            int(r[0])
            for r in conn.execute(
                select(attachments.c.id).where(attachments.c.paper_id == survivor, attachments.c.role == "primary")
            )
        ]
        assert primaries == [s_att]  # exactly one primary, the chosen preprint PDF
    engine.dispose()


def test_idempotent_shared_tag_merge(tmp_path: Path) -> None:
    engine = _migrated(tmp_path)
    with engine.begin() as conn:
        survivor, merged = _seed_preprint_and_published(conn)
        add_tag_to_paper(conn, survivor, "shared")
        add_tag_to_paper(conn, merged, "shared")  # both already have it → must not violate the composite PK
        merge_papers(conn, survivor_id=survivor, merged_ids=[merged])
        assert conn.execute(select(func.count()).where(paper_tags.c.paper_id == survivor)).scalar_one() == 1
    engine.dispose()


def test_validation_errors(tmp_path: Path) -> None:
    engine = _migrated(tmp_path)
    with engine.begin() as conn:
        survivor, merged = _seed_preprint_and_published(conn)
        with pytest.raises(MergeValidationError):
            merge_papers(conn, survivor_id=survivor, merged_ids=[])  # nothing to merge
        with pytest.raises(MergeValidationError):
            merge_papers(conn, survivor_id=survivor, merged_ids=[survivor])  # survivor ∈ merged
        with pytest.raises(MergeValidationError):
            merge_papers(conn, survivor_id=survivor, merged_ids=[999999])  # non-existent
        soft_delete_paper(conn, merged)
        with pytest.raises(MergeValidationError):
            merge_papers(conn, survivor_id=survivor, merged_ids=[merged])  # trashed → not live
    engine.dispose()


def test_merge_allows_doi_already_on_outside_paper(tmp_path: Path) -> None:
    engine = _migrated(tmp_path)
    with engine.begin() as conn:
        survivor, merged = _seed_preprint_and_published(conn)
        create_paper(conn, title="Outsider", csl_json={"title": "Outsider"}, doi="10.999/outside")
        merge_papers(conn, survivor_id=survivor, merged_ids=[merged], metadata={"doi": "10.999/outside"})
        assert get_paper(conn, survivor)["doi"] == "10.999/outside"
    engine.dispose()


# ---------------------------------------------------------------------------------------------------------------
# Endpoint


def test_endpoint_merge_happy_path(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        survivor, merged = _seed_preprint_and_published(conn)
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post(
        "/papers/merge",
        json={"survivor_id": survivor, "merged_ids": [merged], "metadata": {"doi": "10.123/published"}},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["survivor_id"] == survivor and body["merged_ids"] == [merged] and body["trashed"] == [merged]
    assert isinstance(body["merge_operation_id"], int)  # the undo handle (#16)
    # The merged copy leaves the live library AND the plain Trash list — it's "merged away" (a distinct reversible
    # state), reachable only via un-merge on the survivor (a naive Trash-restore would give an empty husk). #16.
    live_ids = {p["id"] for p in client.get("/papers").json()}
    trash_ids = {p["id"] for p in client.get("/papers", params={"deleted": "true"}).json()}
    assert survivor in live_ids and merged not in live_ids
    assert merged not in trash_ids
    assert client.get(f"/papers/{survivor}").json()["doi"] == "10.123/published"


def test_endpoint_422_on_self_merge(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        survivor, _ = _seed_preprint_and_published(conn)
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post("/papers/merge", json={"survivor_id": survivor, "merged_ids": [survivor]})
    assert r.status_code == 422


def test_endpoint_allows_duplicate_doi_during_merge(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        survivor, merged = _seed_preprint_and_published(conn)
        create_paper(conn, title="Outsider", csl_json={"title": "Outsider"}, doi="10.999/outside")
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    r = client.post(
        "/papers/merge",
        json={"survivor_id": survivor, "merged_ids": [merged], "metadata": {"doi": "10.999/outside"}},
    )
    assert r.status_code == 200
    assert client.get(f"/papers/{survivor}").json()["doi"] == "10.999/outside"

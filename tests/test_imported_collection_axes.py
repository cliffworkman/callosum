from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, insert, select, update

from app.backend.api import create_app
from app.backend.importers.collection_axes import (
    create_imported_collection_axes,
    list_imported_axis_candidates,
)
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import (
    axes,
    cluster_node_papers,
    collection_papers,
    collections,
    imported_collection_axes,
)


class _FakeModel:
    name = "fake-imported-collection-axes"
    version = "v1"
    dimension = 4
    normalization = "none"

    def encode_texts(self, texts):
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]


def _seed_hierarchy(conn, *, source: str = "zotero") -> tuple[int, int, int, int]:
    paper_1 = create_paper(conn, title="Root paper", csl_json={"type": "article-journal", "title": "Root paper"})
    paper_2 = create_paper(conn, title="Nested paper", csl_json={"type": "article-journal", "title": "Nested paper"})
    root_id = int(
        conn.execute(
            insert(collections).values(name="Program evaluation", import_source=source, external_id="root")
        ).inserted_primary_key[0]
    )
    child_id = int(
        conn.execute(
            insert(collections).values(
                name="Null replications", import_source=source, external_id="child", parent_id=root_id
            )
        ).inserted_primary_key[0]
    )
    conn.execute(insert(collection_papers).values(collection_id=root_id, paper_id=paper_1))
    conn.execute(insert(collection_papers).values(collection_id=child_id, paper_id=paper_2))
    return root_id, child_id, paper_1, paper_2


def test_curated_axes_roll_up_nested_members_and_are_idempotent(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        root_id, _, paper_1, paper_2 = _seed_hierarchy(conn)
        empty_root = int(
            conn.execute(
                insert(collections).values(name="Empty folder", import_source="zotero", external_id="empty")
            ).inserted_primary_key[0]
        )

        preview = list_imported_axis_candidates(conn, import_source="zotero")
        by_name = {candidate.name: candidate for candidate in preview}
        assert by_name["Program evaluation"].descendant_count == 1
        assert by_name["Program evaluation"].paper_ids == (paper_1, paper_2)
        assert by_name["Empty folder"].paper_ids == ()

        first = create_imported_collection_axes(conn, import_source="zotero", axis_kind="curated")
        second = create_imported_collection_axes(conn, import_source="zotero", axis_kind="curated")

        assert len(first.created_axis_ids) == 1
        assert first.skipped_empty_collection_ids == (empty_root,)
        assert second.created_axis_ids == ()
        assert second.existing_axis_ids == first.created_axis_ids
        assert second.skipped_empty_collection_ids == (empty_root,)
        assert conn.execute(select(func.count()).select_from(imported_collection_axes)).scalar_one() == 1
        axis = conn.execute(select(axes).where(axes.c.id == first.created_axis_ids[0])).mappings().one()
        members = list(
            conn.execute(
                select(
                    cluster_node_papers.c.paper_id, cluster_node_papers.c.confidence, cluster_node_papers.c.position
                ).order_by(cluster_node_papers.c.position)
            )
        )
    assert axis["kind"] == "curated"
    assert members == [(paper_1, None, 0), (paper_2, None, 1)]


def test_standard_axis_keeps_folder_members_as_unordered_manual_anchors(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _, _, paper_1, paper_2 = _seed_hierarchy(conn, source="mendeley")
        result = create_imported_collection_axes(conn, import_source="mendeley", axis_kind="standard")
        axis = conn.execute(select(axes).where(axes.c.id == result.created_axis_ids[0])).mappings().one()
        members = list(
            conn.execute(
                select(
                    cluster_node_papers.c.paper_id, cluster_node_papers.c.confidence, cluster_node_papers.c.position
                ).order_by(cluster_node_papers.c.paper_id)
            )
        )
    assert axis["kind"] == "standard"
    assert members == [(paper_1, None, None), (paper_2, None, None)]


def test_deleting_imported_axis_clears_provenance_and_allows_one_replacement(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _seed_hierarchy(conn)
        first = create_imported_collection_axes(conn, import_source="zotero", axis_kind="curated")
        conn.execute(delete(axes).where(axes.c.id == first.created_axis_ids[0]))
        assert conn.execute(select(func.count()).select_from(imported_collection_axes)).scalar_one() == 0
        replacement = create_imported_collection_axes(conn, import_source="zotero", axis_kind="curated")
    assert len(replacement.created_axis_ids) == 1


def test_imported_collection_axis_action_is_bounded_and_caps_labels(temp_db_url: str, monkeypatch) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="Paper", csl_json={"type": "article-journal", "title": "Paper"})
        collection_id = int(
            conn.execute(
                insert(collections).values(name="x" * 250, import_source="zotero", external_id="long")
            ).inserted_primary_key[0]
        )
        conn.execute(insert(collection_papers).values(collection_id=collection_id, paper_id=paper_id))
        monkeypatch.setattr("app.backend.importers.collection_axes.MAX_AXES_PER_ACTION", 0)
        try:
            create_imported_collection_axes(conn, import_source="zotero", axis_kind="curated")
        except ValueError as exc:
            assert "per-action safety limit" in str(exc)
        else:
            raise AssertionError("axis batch beyond the configured bound must fail closed")
        assert conn.execute(select(func.count()).select_from(axes)).scalar_one() == 0

        monkeypatch.setattr("app.backend.importers.collection_axes.MAX_AXES_PER_ACTION", 100)
        created = create_imported_collection_axes(conn, import_source="zotero", axis_kind="curated")
        label = conn.execute(select(axes.c.label).where(axes.c.id == created.created_axis_ids[0])).scalar_one()
    assert len(label) == 200
    assert label.endswith("…")


def test_collection_hierarchy_fails_closed_on_cycle_or_cross_source_parent(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        root_id, child_id, _, _ = _seed_hierarchy(conn)
        conn.execute(update(collections).where(collections.c.id == root_id).values(parent_id=child_id))
        try:
            list_imported_axis_candidates(conn, import_source="zotero")
        except ValueError as exc:
            assert "cycle" in str(exc)
        else:
            raise AssertionError("cyclic collection hierarchy must fail closed")

        conn.execute(update(collections).where(collections.c.id == root_id).values(parent_id=None))
        foreign_parent = int(
            conn.execute(
                insert(collections).values(name="Foreign", import_source="endnote", external_id="foreign")
            ).inserted_primary_key[0]
        )
        conn.execute(update(collections).where(collections.c.id == root_id).values(parent_id=foreign_parent))
        try:
            list_imported_axis_candidates(conn, import_source="zotero")
        except ValueError as exc:
            assert "outside its source" in str(exc)
        else:
            raise AssertionError("cross-source collection parent must fail closed")


def test_imported_collection_axes_api_previews_creates_and_schedules_standard_scoring(
    temp_db_url: str, monkeypatch
) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        root_id, _, _, _ = _seed_hierarchy(conn)

    calls: list[tuple[str, int]] = []

    def _fake_score(app, job_id: str, axis_id: int, cutoff=0.35) -> None:
        calls.append((job_id, axis_id))

    monkeypatch.setattr("app.backend.api.routers.library_collections.run_axis_score_job", _fake_score)
    client = TestClient(create_app(db_url=temp_db_url, embedding_model=_FakeModel()))
    preview = client.get("/library/imported-collections/axes", params={"import_source": "zotero"})
    assert preview.status_code == 200
    assert preview.json()["collections"] == [
        {
            "collection_id": root_id,
            "name": "Program evaluation",
            "import_source": "zotero",
            "descendant_count": 1,
            "paper_count": 2,
            "axis_id": None,
            "axis_kind": None,
        }
    ]

    created = client.post(
        "/library/imported-collections/axes", json={"import_source": "zotero", "axis_kind": "standard"}
    )
    assert created.status_code == 200
    body = created.json()
    assert len(body["created_axis_ids"]) == 1
    assert len(body["score_job_ids"]) == 1
    assert calls == [(body["score_job_ids"][0], body["created_axis_ids"][0])]

    repeated = client.post(
        "/library/imported-collections/axes", json={"import_source": "zotero", "axis_kind": "curated"}
    )
    assert repeated.status_code == 200
    assert repeated.json()["created_axis_ids"] == []
    assert repeated.json()["existing_axis_ids"] == body["created_axis_ids"]
    assert repeated.json()["score_job_ids"] == []


def test_imported_collection_axes_api_rejects_unknown_source_and_kind(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/library/imported-collections/axes", params={"import_source": "other"}).status_code == 422
    assert (
        client.post(
            "/library/imported-collections/axes", json={"import_source": "zotero", "axis_kind": "other"}
        ).status_code
        == 422
    )

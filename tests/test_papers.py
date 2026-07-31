from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select

from app.backend.api import create_app
from app.backend.embeddings.models import DEFAULT_NORMALIZATION
from app.backend.embeddings.retrieval import search_similar
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.metadata.enrich_sources import EnrichmentRegistry
from app.backend.persistence.database import make_engine
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES
from app.backend.persistence.repository import (
    create_attachment,
    create_chunk,
    create_paper,
    purge_paper,
    soft_delete_paper,
)
from app.backend.persistence.schema import (
    axes,
    chunks,
    cluster_node_papers,
    cluster_nodes,
    embeddings,
    paper_urls,
    papers,
)
from integrations.crossref import CrossrefClient
from tests.api_helpers import (
    _seed_library,
)


class _FakeCrossrefFetcher:
    def __init__(self, status_code: int, body: dict) -> None:
        self.status_code = status_code
        self.body = body

    def __call__(self, doi: str, *, headers: dict, timeout: float):
        return self.status_code, self.body


def _crossref_body(doi: str) -> dict:
    return {
        "message": {
            "DOI": doi,
            "type": "journal-article",
            "title": ["Resolved Title"],
            "container-title": ["Resolved Journal"],
            "issued": {"date-parts": [[2020, 3, 4]]},
            "author": [{"given": "Grace", "family": "Hopper"}],
            "abstract": "Resolved abstract.",
        }
    }


def test_papers_list_counts_pagination_and_query_filter(temp_db_url: str) -> None:
    _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))

    first_page = client.get("/papers", params={"limit": 1, "offset": 0}).json()
    second_page = client.get("/papers", params={"limit": 1, "offset": 1}).json()
    title_filter = client.get("/papers", params={"q": "signal"}).json()
    author_filter = client.get("/papers", params={"q": "lovelace"}).json()

    assert len(first_page) == 1
    assert first_page[0]["title"] == "Facial Anomaly Perception"
    assert first_page[0]["authors"] == ["Ada Lovelace"]
    assert first_page[0]["attachment_count"] == 4
    assert first_page[0]["chunk_count"] == 2
    assert second_page[0]["title"] == "Signal Detection Theory"
    assert [paper["title"] for paper in title_filter] == ["Signal Detection Theory"]
    assert [paper["title"] for paper in author_filter] == ["Facial Anomaly Perception"]


def test_papers_list_axis_filter(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)  # only the facial paper is assigned to the axis
    client = TestClient(create_app(db_url=temp_db_url))
    axis_id = seeded["axis_id"]

    filtered = client.get("/papers", params={"axis_id": axis_id}).json()
    assert {p["id"] for p in filtered} == {seeded["facial_paper_id"]}  # the unassigned paper is excluded
    assert client.get("/papers", params={"axis_id": axis_id, "q": "zzznope"}).json() == []  # composes with q
    assert client.get("/papers", params={"axis_id": 999999}).json() == []  # unknown axis → empty

    client.delete(f"/papers/{seeded['facial_paper_id']}")  # soft-delete → trashed papers excluded
    assert client.get("/papers", params={"axis_id": axis_id}).json() == []


def test_paper_position_matches_list_order(temp_db_url: str) -> None:
    # inc 319: GET /papers/{id}/position drives the library's "reveal the selected paper" scroll — its index
    # must always agree with what GET /papers itself would return for the identical params.
    seeded = _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))
    facial_id = seeded["facial_paper_id"]
    signal_id = seeded["signal_paper_id"]

    # default sort ("added" = id asc) — position must equal the id's index in GET /papers's own ordering
    added_order = [p["id"] for p in client.get("/papers").json()]
    for pid in (facial_id, signal_id):
        assert client.get(f"/papers/{pid}/position").json() == {"index": added_order.index(pid)}

    # a different sort ("recent" = id desc) reorders the set — position must track it, not just the default
    recent_order = [p["id"] for p in client.get("/papers", params={"sort": "recent"}).json()]
    assert recent_order == list(reversed(added_order))
    for pid in (facial_id, signal_id):
        r = client.get(f"/papers/{pid}/position", params={"sort": "recent"})
        assert r.json()["index"] == recent_order.index(pid)


def test_paper_position_404_when_excluded_by_filter(temp_db_url: str) -> None:
    # A paper that doesn't match the given filters is a 404, never a "closest match" — the frontend's signal to
    # skip the reveal rather than clear/relax the caller's filter (the user's explicit requirement, inc 319).
    seeded = _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))
    axis_id = seeded["axis_id"]
    facial_id = seeded["facial_paper_id"]
    signal_id = seeded["signal_paper_id"]

    # facial IS assigned to the axis → matches; signal is NOT → 404
    assert client.get(f"/papers/{facial_id}/position", params={"axis_id": axis_id}).json() == {"index": 0}
    assert client.get(f"/papers/{signal_id}/position", params={"axis_id": axis_id}).status_code == 404

    # a trashed paper doesn't match the live-scope default, but does under deleted=true
    client.delete(f"/papers/{facial_id}")
    assert client.get(f"/papers/{facial_id}/position").status_code == 404
    assert client.get(f"/papers/{facial_id}/position", params={"deleted": "true"}).json() == {"index": 0}


def test_paper_position_unknown_paper_404(temp_db_url: str) -> None:
    _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/papers/999999/position").status_code == 404


def test_papers_list_axis_hide_uncertain(temp_db_url: str) -> None:
    # A10: the axis_hide_uncertain filter must match the card's assigned-only view — assigned (confidence >=
    # the axis cutoff) + manual (NULL) shown, uncertain (confidence < cutoff) hidden. Shown == summarized.
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        assigned = create_paper(conn, title="Assigned", csl_json={"title": "Assigned"})  # >= cutoff
        uncertain = create_paper(conn, title="Uncertain", csl_json={"title": "Uncertain"})  # < cutoff
        manual = create_paper(conn, title="Manual", csl_json={"title": "Manual"})  # confidence NULL
        axis_id = int(
            conn.execute(
                insert(axes).values(label="A10 axis", description="d", scoring_gain=0.35)
            ).inserted_primary_key[0]
        )
        node = int(
            conn.execute(
                insert(cluster_nodes).values(
                    axis_id=axis_id, parent_id=None, label="n", description="d", confidence=0.8
                )
            ).inserted_primary_key[0]
        )
        conn.execute(insert(cluster_node_papers).values(cluster_node_id=node, paper_id=assigned, confidence=0.6))
        conn.execute(insert(cluster_node_papers).values(cluster_node_id=node, paper_id=uncertain, confidence=0.2))
        conn.execute(insert(cluster_node_papers).values(cluster_node_id=node, paper_id=manual, confidence=None))
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    # default (no hide): every member shown — the inc-63 behavior is unchanged
    assert {p["id"] for p in client.get("/papers", params={"axis_id": axis_id}).json()} == {assigned, uncertain, manual}
    # hide-uncertain: only the assigned + manual papers — matching the card's assigned-only view
    hidden = client.get("/papers", params={"axis_id": axis_id, "axis_hide_uncertain": "true"}).json()
    assert {p["id"] for p in hidden} == {assigned, manual}


def test_papers_list_needs_review_filter(temp_db_url: str) -> None:
    # The "Unsorted" view: scaffold + Crossref-unresolved + NULL-source papers; resolved/user-edited excluded.
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        scaffold = create_paper(
            conn, title="Raw Scaffold", csl_json={"title": "Raw Scaffold"}, imported_source="pdf-scaffold"
        )
        unresolved = create_paper(
            conn, title="Unresolved DOI", csl_json={"title": "Unresolved DOI"}, imported_source="crossref-unresolved"
        )
        no_source = create_paper(conn, title="No Source", csl_json={"title": "No Source"})  # imported_source NULL
        resolved = create_paper(conn, title="Resolved", csl_json={"title": "Resolved"}, imported_source="crossref")
        edited = create_paper(conn, title="Edited", csl_json={"title": "Edited"}, imported_source="user-edited")
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    unsorted = client.get("/papers", params={"needs_review": "true"}).json()
    assert {p["id"] for p in unsorted} == {scaffold, unresolved, no_source}  # resolved + user-edited excluded
    # default (no filter) still lists every live paper
    assert {p["id"] for p in client.get("/papers").json()} == {scaffold, unresolved, no_source, resolved, edited}

    client.delete(f"/papers/{scaffold}")  # soft-delete → trashed papers stay excluded from the Unsorted view too
    assert {p["id"] for p in client.get("/papers", params={"needs_review": "true"}).json()} == {unresolved, no_source}


def test_search_covers_all_authors_and_scopes(temp_db_url: str) -> None:
    # The old search only looked at title + first_author_family_name → a non-first author was unfindable.
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        coauthored = create_paper(
            conn,
            title="Resilience signature",
            csl_json={
                "type": "article-journal",
                "title": "Resilience signature",
                "author": [{"family": "Lythe"}, {"family": "Workman", "given": "Clifford"}],
                "container-title": "Psychological Medicine",
            },
            first_author_family_name="Lythe",
            venue="Psychological Medicine",
        )
        other = create_paper(
            conn,
            title="Banana farming",
            csl_json={"type": "article-journal", "title": "Banana farming", "author": [{"family": "Turing"}]},
            first_author_family_name="Turing",
            venue="Agriculture Today",
        )
    client = TestClient(create_app(db_url=temp_db_url))

    def ids(**params):
        return {p["id"] for p in client.get("/papers", params=params).json()}

    # default "all" finds the co-authored paper by its NON-first author (the bug fix)
    assert ids(q="workman") == {coauthored}
    # scope=author finds it; scope=title does not (workman isn't in the title)
    assert ids(q="workman", search_field="author") == {coauthored}
    assert ids(q="workman", search_field="title") == set()
    # scope=journal matches the venue; "all" also reaches the journal field
    assert ids(q="psychological", search_field="journal") == {coauthored}
    assert ids(q="agriculture") == {other}


def test_oversized_search_query_rejected_at_boundary(temp_db_url: str) -> None:
    # A q longer than SQLite's SQLITE_MAX_LIKE_PATTERN_LENGTH (50000) becomes a LIKE pattern
    # `%<q>%` that raised `OperationalError: LIKE or GLOB pattern too complex` -> HTTP 500 (QA route_22)
    # — but only once SQLite actually evaluates the LIKE against a row, so seed one paper first.
    # The boundary length cap (rule #4) rejects oversized input cleanly with a 422 before it reaches the
    # DB, for every search scope — never a raw 500.
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        create_paper(
            conn,
            title="Seed",
            csl_json={"type": "article-journal", "title": "Seed", "author": [{"family": "Seed"}]},
            first_author_family_name="Seed",
        )
    client = TestClient(create_app(db_url=temp_db_url))
    huge = "a" * 50_001
    for field in ("all", "fulltext", "title"):
        r = client.get("/papers", params={"q": huge, "search_field": field})
        assert r.status_code == 422, f"scope {field}: expected 422, got {r.status_code}"
    # a normal-length query is unaffected
    assert client.get("/papers", params={"q": "seed"}).status_code == 200


def test_filter_by_item_type_and_item_types_endpoint(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        art1 = create_paper(
            conn,
            title="Article One",
            csl_json={"type": "article-journal", "title": "Article One"},
            item_type="article-journal",
        )
        art2 = create_paper(
            conn,
            title="Article Two",
            csl_json={"type": "article-journal", "title": "Article Two"},
            item_type="article-journal",
        )
        book = create_paper(conn, title="A Book", csl_json={"type": "book", "title": "A Book"}, item_type="book")
        typeless = create_paper(conn, title="Typeless", csl_json={"title": "Typeless"})  # item_type NULL
    client = TestClient(create_app(db_url=temp_db_url))

    def ids(**params):
        return {p["id"] for p in client.get("/papers", params=params).json()}

    # exact item_type filter (bound value); composes with the no-filter listing
    assert ids(item_type="article-journal") == {art1, art2}
    assert ids(item_type="book") == {book}
    assert ids(item_type="thesis") == set()  # a type not present → empty
    assert ids() == {art1, art2, book, typeless}  # no filter → everything live

    # the facet endpoint: only types actually present, with counts, most-common first; NULL item_type excluded
    assert client.get("/papers/item-types").json() == [
        {"item_type": "article-journal", "count": 2},
        {"item_type": "book", "count": 1},
    ]

    # composes with soft-delete: trashing the book drops it from both the filter and the facet list
    client.delete(f"/papers/{book}")
    assert ids(item_type="book") == set()
    assert [f["item_type"] for f in client.get("/papers/item-types").json()] == ["article-journal"]


def test_library_sort_orders(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:  # titles/years/authors chosen so each sort key yields a distinct order
        create_paper(
            conn,
            title="Cherry",
            csl_json={"type": "article-journal", "title": "Cherry"},
            year=2020,
            first_author_family_name="Carter",
        )
        create_paper(
            conn,
            title="Apple",
            csl_json={"type": "article-journal", "title": "Apple"},
            year=2024,
            first_author_family_name="Adams",
        )
        create_paper(
            conn,
            title="Banana",
            csl_json={"type": "article-journal", "title": "Banana"},
            year=2011,
            first_author_family_name="Baker",
        )
        create_paper(
            conn, title="Durian", csl_json={"type": "article-journal", "title": "Durian"}
        )  # no year/author → sorts last
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    def titles(sort):
        return [p["title"] for p in client.get("/papers", params={"sort": sort}).json()]

    assert titles("added") == ["Cherry", "Apple", "Banana", "Durian"]  # id asc (creation order) — the default
    assert titles("recent") == ["Durian", "Banana", "Apple", "Cherry"]  # id desc
    assert titles("title") == ["Apple", "Banana", "Cherry", "Durian"]  # A–Z
    assert titles("title_desc") == ["Durian", "Cherry", "Banana", "Apple"]  # Z–A (inc 94)
    assert titles("year_desc") == ["Apple", "Cherry", "Banana", "Durian"]  # 2024, 2020, 2011, NULL-last
    assert titles("year_asc") == ["Banana", "Cherry", "Apple", "Durian"]  # 2011, 2020, 2024, NULL-last
    assert titles("author") == ["Apple", "Banana", "Cherry", "Durian"]  # Adams, Baker, Carter, NULL-last
    assert titles("author_desc") == ["Cherry", "Banana", "Apple", "Durian"]  # Carter, Baker, Adams, NULL-last (inc 94)
    assert titles("bogus") == ["Cherry", "Apple", "Banana", "Durian"]  # unknown key → default "added"


def test_export_citations_each_format_and_validation(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = create_paper(
            conn,
            title="Export Alpha",
            csl_json={
                "type": "article-journal",
                "title": "Export Alpha",
                "author": [{"family": "Adams", "given": "A"}],
                "issued": {"date-parts": [[2021]]},
                "DOI": "10.9/alpha",
            },
            doi="10.9/alpha",
            year=2021,
            first_author_family_name="Adams",
        )
        b = create_paper(
            conn, title="Export Beta", csl_json={"type": "article-journal", "title": "Export Beta"}, year=2022
        )
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    bib = client.post("/papers/export", json={"paper_ids": [a, b], "format": "bibtex"})
    assert bib.status_code == 200 and bib.headers["content-type"].startswith("application/x-bibtex")
    assert 'attachment; filename="callosum-citations.bib"' in bib.headers["content-disposition"]
    assert "@article" in bib.text and "Export Alpha" in bib.text and "Export Beta" in bib.text

    ris = client.post("/papers/export", json={"paper_ids": [a], "format": "ris"})
    assert ris.status_code == 200 and ris.headers["content-type"].startswith("application/x-research-info-systems")
    assert "TY  - JOUR" in ris.text and "DO  - 10.9/alpha" in ris.text

    csl = client.post("/papers/export", json={"paper_ids": [a], "format": "csl-json"})
    assert csl.status_code == 200 and csl.headers["content-type"].startswith("application/json")
    assert csl.json()[0]["title"] == "Export Alpha"

    assert client.post("/papers/export", json={"paper_ids": [a], "format": "bogus"}).status_code == 422  # bad format
    assert client.post("/papers/export", json={"paper_ids": [], "format": "bibtex"}).status_code == 422  # no ids
    assert (
        client.post("/papers/export", json={"paper_ids": [999999], "format": "bibtex"}).status_code == 422
    )  # none exist

    client.delete(f"/papers/{a}")  # trash Alpha → excluded from export; Beta still exports
    only_b = client.post("/papers/export", json={"paper_ids": [a, b], "format": "bibtex"})
    assert only_b.status_code == 200 and "Export Alpha" not in only_b.text and "Export Beta" in only_b.text
    client.delete(f"/papers/{b}")  # both trashed → no live papers → 422
    assert client.post("/papers/export", json={"paper_ids": [a, b], "format": "bibtex"}).status_code == 422


def test_paper_detail_returns_metadata_and_attachments_and_404(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))

    response = client.get(f"/papers/{seeded['facial_paper_id']}")
    missing = client.get("/papers/999999")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == seeded["facial_paper_id"]
    assert body["doi"] == "10.123/facial"
    assert body["csl_json"]["title"] == "Facial Anomaly Perception"
    assert body["attachment_count"] == 4
    assert body["chunk_count"] == 2
    filenames = [attachment["filename"] for attachment in body["attachments"]]
    assert filenames == ["facial.pdf", "posix-facial.pdf", "drive-slash-facial.pdf", "bare-facial.pdf"]
    assert body["attachments"][0]["availability"] == "available"
    assert missing.status_code == 404


def test_paper_chunks_returns_coordinate_metadata_with_pagination(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))

    first = client.get(f"/papers/{seeded['facial_paper_id']}/chunks", params={"limit": 1}).json()
    second = client.get(f"/papers/{seeded['facial_paper_id']}/chunks", params={"limit": 1, "offset": 1}).json()
    missing = client.get("/papers/999999/chunks")

    assert len(first) == 1
    assert first[0]["text"] == "Facial anomalies influence social judgments."
    assert first[0]["page_start"] == 1
    assert first[0]["bbox_coordinate_system"] == "pdf-points-top-left"
    assert first[0]["bbox_json"] == [{"page": 1, "x0": 10, "y0": 20, "x1": 120, "y1": 40}]
    assert second[0]["page_start"] == 2
    assert missing.status_code == 404


def test_paper_pdf_streams_inline_pdf_for_present_local_attachment(temp_db_url: str, tmp_path: Path) -> None:
    pdf_path = tmp_path / "present-facial.pdf"
    pdf_bytes = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    pdf_path.write_bytes(pdf_bytes)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(
            conn,
            title="Paper With Local PDF",
            csl_json={"type": "article-journal", "title": "Paper With Local PDF"},
            processing_tier="fully-chunked",
        )
        create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="linked",
            availability="available",
            original_path=str(pdf_path),
            resolved_path=str(pdf_path),
            content_type="application/pdf",
            attachment_type="pdf",
            role="primary",
        )
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    response = client.get(f"/papers/{paper_id}/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("inline")
    assert response.content == pdf_bytes


def test_seed_renderable_paper_serves_real_pdf_with_truthful_bbox(temp_db_url: str) -> None:
    # inc 120 — pins the QA fixture (QA-POLICY "pin the seed"): the seeded "renderable" paper must serve a real
    # on-disk PDF and carry a chunk whose bbox truthfully locates its quote, so QA can exercise the PDF viewer +
    # the coordinate-honesty invariant. If a future seed edit breaks this, pytest catches it here, not just QA.
    seeded = _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))

    pdf = client.get(f"/papers/{seeded['renderable_paper_id']}/pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content[:5] == b"%PDF-"

    chunks = client.get(f"/papers/{seeded['renderable_paper_id']}/chunks").json()
    assert chunks[0]["text"] == "Facial anomalies influence social judgments in observers."
    assert chunks[0]["bbox_json"] == [{"page": 1, "x0": 72.0, "y0": 187.1, "x1": 378.1, "y1": 203.6}]
    assert chunks[0]["bbox_coordinate_system"] == "pdf-points-top-left"


def test_paper_pdf_falls_back_to_original_path_when_resolved_missing(temp_db_url: str, tmp_path: Path) -> None:
    pdf_path = tmp_path / "original-only.pdf"
    pdf_bytes = b"%PDF-1.7\noriginal-path fallback\n%%EOF\n"
    pdf_path.write_bytes(pdf_bytes)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(
            conn,
            title="Paper With Only Original Path",
            csl_json={"type": "article-journal", "title": "Paper With Only Original Path"},
            processing_tier="fully-chunked",
        )
        create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="linked",
            availability="available",
            original_path=str(pdf_path),
            resolved_path=None,
            content_type="application/pdf",
            attachment_type="pdf",
            role="primary",
        )
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    response = client.get(f"/papers/{paper_id}/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == pdf_bytes


def test_paper_pdf_404_with_honest_detail_when_no_local_file(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(
            conn,
            title="URL Only Paper",
            csl_json={"type": "article-journal", "title": "URL Only Paper"},
            processing_tier="metadata-only",
        )
        create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="url",
            availability="available",
            content_type="application/pdf",
            attachment_type="pdf",
            role="primary",
        )
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    response = client.get(f"/papers/{paper_id}/pdf")

    assert response.status_code == 404
    assert response.json() == {"detail": "PDF not available locally for this paper"}


def test_paper_pdf_404_when_file_missing_on_disk(temp_db_url: str, tmp_path: Path) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(
            conn,
            title="Paper With Stale Path",
            csl_json={"type": "article-journal", "title": "Paper With Stale Path"},
            processing_tier="fully-chunked",
        )
        create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="linked",
            availability="available",
            original_path=str(tmp_path / "gone.pdf"),
            resolved_path=str(tmp_path / "gone.pdf"),
            content_type="application/pdf",
            attachment_type="pdf",
            role="primary",
        )
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    response = client.get(f"/papers/{paper_id}/pdf")

    assert response.status_code == 404
    assert response.json() == {"detail": "PDF not available locally for this paper"}


def test_paper_pdf_attachment_id_serves_the_chosen_non_primary_attachment(temp_db_url: str, tmp_path: Path) -> None:
    # #5: post-merge, a paper can carry 2+ PDF attachments; ?attachment_id lets a caller open a specific one
    # instead of always the primary.
    primary_path = tmp_path / "primary.pdf"
    primary_path.write_bytes(b"%PDF-1.4\nprimary\n%%EOF\n")
    other_path = tmp_path / "other.pdf"
    other_bytes = b"%PDF-1.4\nnon-primary\n%%EOF\n"
    other_path.write_bytes(other_bytes)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(
            conn,
            title="Paper With Two PDFs",
            csl_json={"type": "article-journal", "title": "Paper With Two PDFs"},
            processing_tier="fully-chunked",
        )
        create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="linked",
            availability="available",
            original_path=str(primary_path),
            resolved_path=str(primary_path),
            content_type="application/pdf",
            attachment_type="pdf",
            role="primary",
        )
        other_id = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="linked",
            availability="available",
            original_path=str(other_path),
            resolved_path=str(other_path),
            content_type="application/pdf",
            attachment_type="pdf",
            role=None,
        )
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    response = client.get(f"/papers/{paper_id}/pdf", params={"attachment_id": other_id})

    assert response.status_code == 200
    assert response.content == other_bytes


def test_paper_pdf_attachment_id_404s_for_another_papers_attachment(temp_db_url: str, tmp_path: Path) -> None:
    pdf_path = tmp_path / "elsewhere.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF\n")
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        other_paper_id = create_paper(
            conn,
            title="A Different Paper",
            csl_json={"type": "article-journal", "title": "A Different Paper"},
            processing_tier="fully-chunked",
        )
        foreign_attachment_id = create_attachment(
            conn,
            paper_id=other_paper_id,
            storage_mode="linked",
            availability="available",
            original_path=str(pdf_path),
            resolved_path=str(pdf_path),
            content_type="application/pdf",
            attachment_type="pdf",
            role="primary",
        )
        paper_id = create_paper(
            conn,
            title="This Paper",
            csl_json={"type": "article-journal", "title": "This Paper"},
            processing_tier="metadata-only",
        )
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    response = client.get(f"/papers/{paper_id}/pdf", params={"attachment_id": foreign_attachment_id})

    assert response.status_code == 404
    assert response.json() == {"detail": "Attachment not found for this paper"}


def test_paper_pdf_attachment_id_404s_for_nonexistent_id(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(
            conn,
            title="No Such Attachment",
            csl_json={"type": "article-journal", "title": "No Such Attachment"},
            processing_tier="metadata-only",
        )
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    response = client.get(f"/papers/{paper_id}/pdf", params={"attachment_id": 999999})

    assert response.status_code == 404
    assert response.json() == {"detail": "Attachment not found for this paper"}


def test_paper_pdf_attachment_id_404s_for_a_non_pdf_attachment(temp_db_url: str, tmp_path: Path) -> None:
    docx_path = tmp_path / "supplement.docx"
    docx_path.write_bytes(b"not a pdf")
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(
            conn,
            title="Paper With A Non-PDF Attachment",
            csl_json={"type": "article-journal", "title": "Paper With A Non-PDF Attachment"},
            processing_tier="metadata-only",
        )
        docx_id = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="linked",
            availability="available",
            original_path=str(docx_path),
            resolved_path=str(docx_path),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            attachment_type="docx",
            role="supplementary-text",
        )
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    response = client.get(f"/papers/{paper_id}/pdf", params={"attachment_id": docx_id})

    assert response.status_code == 404
    assert response.json() == {"detail": "This attachment is not a PDF"}


def test_paper_pdf_attachment_id_404s_when_chosen_attachment_unavailable_on_disk(
    temp_db_url: str, tmp_path: Path
) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(
            conn,
            title="Paper With A Missing Chosen Attachment",
            csl_json={"type": "article-journal", "title": "Paper With A Missing Chosen Attachment"},
            processing_tier="metadata-only",
        )
        missing_id = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="linked",
            availability="available",
            original_path=str(tmp_path / "gone.pdf"),
            resolved_path=str(tmp_path / "gone.pdf"),
            content_type="application/pdf",
            attachment_type="pdf",
            role=None,
        )
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    response = client.get(f"/papers/{paper_id}/pdf", params={"attachment_id": missing_id})

    assert response.status_code == 404
    assert response.json() == {"detail": "PDF not available locally for this attachment"}


def test_paper_detail_cleans_jats_abstract_without_mutating_stored_value(temp_db_url: str) -> None:
    raw = (
        "<jats:title>Abstract</jats:title><jats:p>Resting‐state connectivity in MCI. "
        "<jats:italic>Hum Brain Mapp</jats:italic>.</jats:p>"
    )
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(
            conn,
            title="JATS Abstract Paper",
            abstract=raw,
            csl_json={"id": "jats", "type": "article-journal", "title": "JATS Abstract Paper"},
        )
    engine.dispose()

    body = TestClient(create_app(db_url=temp_db_url)).get(f"/papers/{paper_id}").json()
    assert body["abstract"] == raw  # raw JATS preserved on the response
    assert body["abstract_display"] == "<p>Resting‐state connectivity in MCI. <em>Hum Brain Mapp</em>.</p>"
    assert "jats" not in body["abstract_display"]
    assert (
        "jats" not in body["abstract_text"].lower() and "<" not in body["abstract_text"]
    )  # editable textarea: tag-free
    assert "Resting‐state connectivity in MCI." in body["abstract_text"]

    engine = make_engine(temp_db_url)
    with engine.connect() as conn:
        stored = conn.execute(select(papers.c.abstract).where(papers.c.id == paper_id)).scalar_one()
    engine.dispose()
    assert stored == raw  # stored column untouched


# ── PATCH /papers/{id} — editable Details pane (inc 49) ───────────────────────


def test_patch_paper_updates_columns_csl_and_marks_user_edited(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))

    response = client.patch(
        f"/papers/{seeded['signal_paper_id']}",
        json={"venue": "Nature Neuroscience", "volume": "12", "year": 2025},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["venue"] == "Nature Neuroscience"
    assert body["year"] == 2025
    assert body["csl_json"]["container-title"] == "Nature Neuroscience"
    assert body["csl_json"]["volume"] == "12"  # csl-only field has no column
    assert body["csl_json"]["issued"] == {"date-parts": [[2025]]}
    assert body["imported_source"] == "user-edited"
    assert body["title"] == "Signal Detection Theory"  # untouched


def test_patch_paper_is_partial_and_preserves_untouched_fields(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))

    body = client.patch(f"/papers/{seeded['facial_paper_id']}", json={"citation_key": "newkey"}).json()

    assert body["citation_key"] == "newkey"
    assert body["doi"] == "10.123/facial"  # untouched
    assert body["title"] == "Facial Anomaly Perception"


def test_patch_paper_authors_round_trip_as_literal(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))

    body = client.patch(f"/papers/{seeded['signal_paper_id']}", json={"authors": ["Baez S", "Herrera E"]}).json()

    assert body["authors"] == ["Baez S", "Herrera E"]
    assert body["csl_json"]["author"] == [{"literal": "Baez S"}, {"literal": "Herrera E"}]


def test_patch_paper_extra_urls_round_trip(temp_db_url: str) -> None:  # inc 214 (#5)
    seeded = _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))
    pid = seeded["signal_paper_id"]

    body = client.patch(f"/papers/{pid}", json={"extra_urls": ["https://osf.io/abc", " https://preprint ", ""]}).json()
    assert body["extra_urls"] == ["https://osf.io/abc", "https://preprint"]  # cleaned, empties dropped
    assert body["csl_json"]["extra_urls"] == ["https://osf.io/abc", "https://preprint"]
    assert [u["url"] for u in body["urls"]] == ["https://osf.io/abc", "https://preprint"]

    detail = client.get(f"/papers/{pid}").json()  # persisted + surfaced on GET
    assert detail["extra_urls"] == ["https://osf.io/abc", "https://preprint"]
    with make_engine(temp_db_url).begin() as conn:
        assert (
            conn.execute(select(func.count()).select_from(paper_urls).where(paper_urls.c.paper_id == pid)).scalar_one()
            == 2
        )

    cleared = client.patch(f"/papers/{pid}", json={"extra_urls": []}).json()  # clears
    assert cleared["extra_urls"] == [] and "extra_urls" not in cleared["csl_json"]
    with make_engine(temp_db_url).begin() as conn:
        assert (
            conn.execute(select(func.count()).select_from(paper_urls).where(paper_urls.c.paper_id == pid)).scalar_one()
            == 0
        )


def test_paper_url_rows_add_update_delete_and_validate(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))
    pid = seeded["signal_paper_id"]

    created = client.post(f"/papers/{pid}/urls", json={"url": "https://osf.io/project", "label": "OSF"})
    assert created.status_code == 201
    row = created.json()
    assert row["url"] == "https://osf.io/project" and row["label"] == "OSF" and row["id"]
    detail = client.get(f"/papers/{pid}").json()
    assert detail["extra_urls"] == ["https://osf.io/project"]
    assert detail["urls"][0]["label"] == "OSF"
    assert detail["csl_json"]["extra_urls"] == ["https://osf.io/project"]

    updated = client.post(f"/papers/{pid}/urls", json={"url": "https://osf.io/project", "label": "Project page"})
    assert updated.status_code == 201 and updated.json()["id"] == row["id"]
    assert client.get(f"/papers/{pid}").json()["urls"][0]["label"] == "Project page"
    assert client.post(f"/papers/{pid}/urls", json={"url": "ftp://example.org/file"}).status_code == 422
    assert client.delete(f"/papers/{pid}/urls/{row['id']}").status_code == 204
    detail = client.get(f"/papers/{pid}").json()
    assert detail["extra_urls"] == []
    assert "extra_urls" not in detail["csl_json"]


def test_patch_paper_extra_urls_reserved_against_generic_patch(temp_db_url: str) -> None:  # inc 214
    seeded = _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))
    # extra_urls is a reserved key → the generic "More" passthrough must reject it (422).
    assert client.patch(f"/papers/{seeded['signal_paper_id']}", json={"csl": {"extra_urls": "x"}}).status_code == 422


def test_patch_paper_generic_csl_passthrough_and_reserved_key_rejected(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))
    pid = seeded["facial_paper_id"]

    ok = client.patch(f"/papers/{pid}", json={"csl": {"publisher": "Springer"}})
    reserved = client.patch(f"/papers/{pid}", json={"csl": {"title": "hijack"}})

    assert ok.status_code == 200
    assert ok.json()["csl_json"]["publisher"] == "Springer"
    assert reserved.status_code == 422


def test_patch_paper_empty_title_and_no_fields_rejected(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))
    pid = seeded["facial_paper_id"]

    assert client.patch(f"/papers/{pid}", json={"title": "   "}).status_code == 422
    assert client.patch(f"/papers/{pid}", json={}).status_code == 422
    assert client.patch("/papers/999999", json={"venue": "X"}).status_code == 404


def test_patch_paper_allows_duplicate_doi_for_merge_workflow(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))

    # signal has no DOI; setting it to facial's DOI should mark a duplicate candidate rather than block cleanup.
    response = client.patch(f"/papers/{seeded['signal_paper_id']}", json={"doi": "10.123/facial"})

    assert response.status_code == 200
    assert response.json()["doi"] == "10.123/facial"


# ── POST /papers/{id}/re-resolve — DOI correction & re-fetch (inc 49) ─────────


def test_reresolve_populates_metadata_from_crossref(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    app = create_app(
        db_url=temp_db_url,
        crossref_client=CrossrefClient(fetcher=_FakeCrossrefFetcher(200, _crossref_body("10.123/facial"))),
    )
    app.state.enrich_registry = EnrichmentRegistry()  # inc 307: no keyword-import network on re-resolve
    client = TestClient(app)

    body = client.post(f"/papers/{seeded['facial_paper_id']}/re-resolve").json()

    assert body["title"] == "Resolved Title"
    assert body["venue"] == "Resolved Journal"
    assert body["year"] == 2020
    assert body["imported_source"] == "crossref"
    assert "Hopper" in body["authors"][0]


def test_crossref_adapter_captures_and_dedupes_subject() -> None:
    from integrations.crossref.adapter import _crossref_message_to_csl

    csl = _crossref_message_to_csl(
        {"title": ["T"], "subject": ["Neuroscience", "Cognitive Science", "neuroscience", " "]}, "10.1/x"
    )
    assert csl["subject"] == [
        "Neuroscience",
        "Cognitive Science",
    ]  # blanks dropped, case-insensitive dedupe, order kept
    assert "subject" not in _crossref_message_to_csl({"title": ["T"]}, "10.1/x")  # no subject → no key


def test_reresolve_imports_crossref_subjects_as_keyword_tags(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    pid = seeded["facial_paper_id"]
    body = _crossref_body("10.123/facial")
    body["message"]["subject"] = ["Neuroscience", "Vision"]
    app = create_app(db_url=temp_db_url, crossref_client=CrossrefClient(fetcher=_FakeCrossrefFetcher(200, body)))
    app.state.enrich_registry = EnrichmentRegistry()  # inc 307: only Crossref subjects here, no keyword-import network
    client = TestClient(app)

    detail = client.post(f"/papers/{pid}/re-resolve").json()
    assert {"Neuroscience", "Vision"} <= {t["name"] for t in detail["tags"]}  # subjects → keyword tags
    detail2 = client.post(f"/papers/{pid}/re-resolve").json()  # idempotent: no dupes
    assert sorted(t["name"] for t in detail2["tags"]) == sorted(t["name"] for t in detail["tags"])
    nid = next(t["id"] for t in detail2["tags"] if t["name"] == "Neuroscience")
    assert pid in {p["id"] for p in client.get("/papers", params={"tag_id": nid}).json()}  # filterable like any tag


class _KwSource:
    """A registry source advertising inc-306/307 keyword tags (no network) — for the re-resolve keyword test."""

    name = "kw"
    keyword_source = "keyword:openalex"

    def __init__(self, names) -> None:
        self._names = list(names)

    def fetch(self, conn, ref):
        return None

    def keywords(self, conn, ref):
        return list(self._names)


def test_reresolve_also_imports_registry_keyword_tags(temp_db_url: str) -> None:
    """inc 307: 🔎 re-resolve now also applies the registry keyword sources (OpenAlex topics / PubMed MeSH), not
    just Crossref subjects — matching Fill-metadata. The tags carry their source provenance."""
    seeded = _seed_library(temp_db_url)
    pid = seeded["facial_paper_id"]
    app = create_app(
        db_url=temp_db_url,
        crossref_client=CrossrefClient(fetcher=_FakeCrossrefFetcher(200, _crossref_body("10.123/facial"))),
    )
    app.state.enrich_registry = EnrichmentRegistry().register(_KwSource(["Face Perception", "Social Cognition"]))
    client = TestClient(app)

    detail = client.post(f"/papers/{pid}/re-resolve").json()
    tags = {t["name"]: t["source"] for t in detail["tags"]}
    assert tags.get("Face Perception") == "keyword:openalex"  # registry keyword source, not just Crossref subjects
    assert tags.get("Social Cognition") == "keyword:openalex"


def test_reresolve_requires_a_doi(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    client = TestClient(
        create_app(db_url=temp_db_url, crossref_client=CrossrefClient(fetcher=_FakeCrossrefFetcher(200, {})))
    )

    response = client.post(f"/papers/{seeded['signal_paper_id']}/re-resolve")  # no DOI

    assert response.status_code == 422


def test_reresolve_is_graceful_when_crossref_misses(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    app = create_app(
        db_url=temp_db_url,
        crossref_client=CrossrefClient(fetcher=_FakeCrossrefFetcher(404, {"status": "error"})),
    )
    app.state.enrich_registry = EnrichmentRegistry()  # inc 307: no keyword-import network on re-resolve
    client = TestClient(app)

    response = client.post(f"/papers/{seeded['facial_paper_id']}/re-resolve")

    assert response.status_code == 200
    assert response.json()["imported_source"] == "crossref-unresolved"


def test_reresolve_forces_past_a_user_edit(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    app = create_app(
        db_url=temp_db_url,
        crossref_client=CrossrefClient(fetcher=_FakeCrossrefFetcher(200, _crossref_body("10.123/facial"))),
    )
    app.state.enrich_registry = EnrichmentRegistry()  # inc 307: no keyword-import network on re-resolve
    client = TestClient(app)
    pid = seeded["facial_paper_id"]

    client.patch(f"/papers/{pid}", json={"venue": "My Manual Edit"})  # marks user-edited
    body = client.post(f"/papers/{pid}/re-resolve").json()

    assert body["imported_source"] == "crossref"
    assert body["venue"] == "Resolved Journal"  # force overrode the manual edit


# ── per-identifier re-resolve: PMID / arXiv via OpenAlex (inc 226) ────────────


class _FakeOpenAlex:
    """A hermetic OpenAlex stand-in: returns a CSL for a known key, records the refs it was called with."""

    def __init__(self, csl_by_key: dict) -> None:
        self.csl_by_key = csl_by_key
        self.refs: list = []

    def fetch_work_csl(self, conn, ref):
        self.refs.append(ref)
        if ref.pmid:
            return self.csl_by_key.get(f"pmid:{ref.pmid}")
        if ref.doi:
            return self.csl_by_key.get(f"doi:{ref.doi.lower()}")
        return None


_OA_CSL = {
    "title": "Resolved by OpenAlex",
    "DOI": "10.1/oa",
    "issued": {"date-parts": [[2022]]},
    "container-title": "OA Journal",
    "type": "article-journal",
    "author": [{"family": "Doe"}],
}


def test_reresolve_from_pmid_overwrites_via_openalex(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="stub", csl_json={"title": "stub", "PMID": "12345"})
    engine.dispose()
    fake = _FakeOpenAlex({"pmid:12345": dict(_OA_CSL)})
    client = TestClient(create_app(db_url=temp_db_url, openalex_client=fake))

    body = client.post(f"/papers/{pid}/re-resolve", json={"source": "pmid"}).json()
    assert body["title"] == "Resolved by OpenAlex" and body["year"] == 2022
    assert body["imported_source"] == "openalex"
    assert body["csl_json"]["PMID"] == "12345"  # the identifier the user clicked is preserved
    assert fake.refs and fake.refs[0].pmid == "12345"


def test_reresolve_from_arxiv_uses_synthesized_doi(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="stub", csl_json={"title": "stub", "arxiv": "2401.00001"})
    engine.dispose()
    fake = _FakeOpenAlex({"doi:10.48550/arxiv.2401.00001": dict(_OA_CSL)})
    client = TestClient(create_app(db_url=temp_db_url, openalex_client=fake))

    body = client.post(f"/papers/{pid}/re-resolve", json={"source": "arxiv"}).json()
    assert body["title"] == "Resolved by OpenAlex"
    assert body["csl_json"]["arxiv"] == "2401.00001"  # preserved (OpenAlex CSL omits it)
    assert fake.refs and fake.refs[0].doi == "10.48550/arXiv.2401.00001"


def test_reresolve_from_identifier_miss_is_graceful(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="Keep me", csl_json={"title": "Keep me", "PMID": "999"})
    engine.dispose()
    fake = _FakeOpenAlex({})  # nothing matches → a miss
    client = TestClient(create_app(db_url=temp_db_url, openalex_client=fake))

    resp = client.post(f"/papers/{pid}/re-resolve", json={"source": "pmid"})
    assert resp.status_code == 200  # graceful, never 500
    assert resp.json()["title"] == "Keep me"  # record left untouched on a miss


def test_reresolve_from_identifier_422_when_absent(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="No ids", csl_json={"title": "No ids"})
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url, openalex_client=_FakeOpenAlex({})))
    assert client.post(f"/papers/{pid}/re-resolve", json={"source": "pmid"}).status_code == 422
    assert client.post(f"/papers/{pid}/re-resolve", json={"source": "arxiv"}).status_code == 422


# ── soft-delete / Trash / restore (inc 54) ───────────────────────────────────


def _library_ids(client: TestClient, *, deleted: bool = False) -> set[int]:
    return {p["id"] for p in client.get("/papers", params={"deleted": str(deleted).lower()}).json()}


def _cluster_paper_ids(client: TestClient, axis_id: int) -> set[int]:
    data = client.get(f"/axes/{axis_id}/clusters").json()
    return {p["id"] for node in data for p in node["papers"]}


def test_soft_delete_hides_from_library_and_lists_in_trash(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))
    pid = seeded["facial_paper_id"]

    assert client.delete(f"/papers/{pid}").status_code == 204
    assert pid not in _library_ids(client)  # gone from the live library
    assert pid in _library_ids(client, deleted=True)  # present in the Trash listing


def test_restore_returns_paper_to_library(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))
    pid = seeded["facial_paper_id"]
    client.delete(f"/papers/{pid}")

    restored = client.post(f"/papers/{pid}/restore")

    assert restored.status_code == 200 and restored.json()["id"] == pid
    assert pid in _library_ids(client)
    assert pid not in _library_ids(client, deleted=True)


def test_delete_and_restore_404_paths(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))
    pid = seeded["facial_paper_id"]

    assert client.delete("/papers/999999").status_code == 404  # unknown
    assert client.post("/papers/999999/restore").status_code == 404  # unknown
    assert client.post(f"/papers/{pid}/restore").status_code == 404  # live paper isn't in Trash
    assert client.delete(f"/papers/{pid}").status_code == 204
    assert client.delete(f"/papers/{pid}").status_code == 404  # already trashed


def test_trashed_paper_excluded_from_axis_clusters(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url))
    pid, axis_id = seeded["facial_paper_id"], seeded["axis_id"]

    assert pid in _cluster_paper_ids(client, axis_id)  # seeded into the axis's cluster
    client.delete(f"/papers/{pid}")
    assert pid not in _cluster_paper_ids(client, axis_id)  # trashed → gone from the axis


# ── permanent delete / empty Trash (inc 65) ──────────────────────────────────


class _TwoDimModel:
    name = "m"
    version = "v"
    dimension = 2
    normalization = DEFAULT_NORMALIZATION

    def encode_texts(self, texts):
        return [[0.0, 1.0] for _ in texts]


def _seed_indexed_paper(conn, store, *, title: str, checksum: str, chunk_vec, paper_vec) -> dict:
    """A paper + chunk + their `embeddings` rows + vectors in the store (mirrors a fully-indexed paper)."""
    pid = create_paper(
        conn, title=title, csl_json={"type": "article-journal", "title": title}, processing_tier="fully-chunked"
    )
    att = create_attachment(
        conn,
        paper_id=pid,
        storage_mode="linked",
        availability="available",
        content_type="application/pdf",
        checksum=checksum,
        import_source="t",
        attachment_type="pdf",
        role="primary",
    )
    cid = create_chunk(
        conn,
        paper_id=pid,
        attachment_id=att,
        text=f"{title} body",
        page_start=1,
        page_end=1,
        bbox_coordinate_system="pdf-points-top-left",
        extraction_tool="fix",
        extraction_version="1",
        chunking_strategy="p",
        chunk_version="v1",
        source_attachment_checksum=checksum,
        bbox_json=[{"page": 1, "x0": 1, "y0": 1, "x1": 2, "y1": 2}],
    )
    emb = {}
    for ttype, tid, vec, key in (("paper", pid, paper_vec, "paper"), ("chunk", cid, chunk_vec, "chunk")):
        eid = int(
            conn.execute(
                insert(embeddings).values(
                    target_type=ttype,
                    target_id=tid,
                    model_name="m",
                    model_version="v",
                    dimension=2,
                    normalization=DEFAULT_NORMALIZATION,
                    source_text_version="t1",
                )
            ).inserted_primary_key[0]
        )
        store.add(conn, embedding_id=eid, vector=vec)
        emb[key] = eid
    return {"paper_id": pid, "chunk_id": cid, "emb": emb}


def test_purge_paper_removes_embeddings_and_vectors_without_orphaning(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    store = InMemoryVectorStore()
    with engine.begin() as conn:
        gone = _seed_indexed_paper(
            conn, store, title="Purge Me", checksum="purge-chk", chunk_vec=[0.0, 1.0], paper_vec=[1.0, 0.0]
        )
        keep = _seed_indexed_paper(
            conn, store, title="Keep Me", checksum="keep-chk", chunk_vec=[0.0, 1.0], paper_vec=[1.0, 0.0]
        )

        assert soft_delete_paper(conn, gone["paper_id"]) is True
        assert purge_paper(conn, gone["paper_id"], vector_store=store) is True

        # the purged paper's rows are gone (paper, chunks, and its NON-cascaded embeddings)
        assert (
            conn.execute(select(func.count()).select_from(papers).where(papers.c.id == gone["paper_id"])).scalar_one()
            == 0
        )
        assert (
            conn.execute(
                select(func.count()).select_from(chunks).where(chunks.c.paper_id == gone["paper_id"])
            ).scalar_one()
            == 0
        )
        assert (
            conn.execute(
                select(func.count()).select_from(embeddings).where(embeddings.c.id.in_(list(gone["emb"].values())))
            ).scalar_one()
            == 0
        )
        # its vectors are gone from the store; the kept paper's row + vectors survive
        assert gone["emb"]["paper"] not in store.vectors and gone["emb"]["chunk"] not in store.vectors
        assert keep["emb"]["paper"] in store.vectors and keep["emb"]["chunk"] in store.vectors
        assert (
            conn.execute(select(func.count()).select_from(papers).where(papers.c.id == keep["paper_id"])).scalar_one()
            == 1
        )

        # retrieval must NOT orphan-crash: no leftover vector points at a deleted embedding/chunk/paper
        hits = search_similar(
            conn,
            query_vector=[0.0, 1.0],
            model=_TwoDimModel(),
            vector_store=store,
            top_k=5,
            document_roles=ARTICLE_DOCUMENT_ROLES,
        )
        assert hits and all(h.paper_id == keep["paper_id"] for h in hits)
    engine.dispose()


def test_purge_paper_refuses_a_live_paper(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    engine = make_engine(temp_db_url)
    store = InMemoryVectorStore()
    with engine.begin() as conn:
        # a live (non-trashed) paper is never purged in one step
        assert purge_paper(conn, seeded["facial_paper_id"], vector_store=store) is False
        assert (
            conn.execute(
                select(func.count()).select_from(papers).where(papers.c.id == seeded["facial_paper_id"])
            ).scalar_one()
            == 1
        )
    engine.dispose()


def test_permanent_delete_endpoint_only_from_trash(temp_db_url: str) -> None:
    seeded = _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url, vector_store=InMemoryVectorStore()))
    pid = seeded["facial_paper_id"]

    assert client.delete(f"/papers/{pid}/permanent").status_code == 404  # live paper can't be purged
    assert client.delete(f"/papers/{pid}").status_code == 204  # move to Trash
    assert client.delete(f"/papers/{pid}/permanent").status_code == 204  # now purge
    assert pid not in _library_ids(client)
    assert pid not in _library_ids(client, deleted=True)  # gone from Trash too
    assert client.delete(f"/papers/{pid}/permanent").status_code == 404  # already purged


def test_permanent_delete_removes_only_owned_managed_files(temp_db_url: str, tmp_path: Path, monkeypatch) -> None:
    managed_root = tmp_path / "managed-library"
    managed_root.mkdir()
    monkeypatch.setenv("CALLOSUM_LIBRARY_DIR", str(managed_root))
    managed_file = managed_root / "owned.pdf"
    linked_file = managed_root / "linked.pdf"
    outside_file = tmp_path / "outside.pdf"
    for path in (managed_file, linked_file, outside_file):
        path.write_bytes(b"%PDF-test")

    seeded = _seed_library(temp_db_url)
    pid = seeded["facial_paper_id"]
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        for path, storage_mode in (
            (managed_file, "managed"),
            (linked_file, "linked"),
            (outside_file, "managed"),
        ):
            create_attachment(
                conn,
                paper_id=pid,
                storage_mode=storage_mode,
                availability="available",
                original_path=str(path),
                resolved_path=str(path),
                content_type="application/pdf",
                attachment_type="pdf",
                role="primary",
            )
    engine.dispose()

    client = TestClient(create_app(db_url=temp_db_url, vector_store=InMemoryVectorStore()))
    assert client.delete(f"/papers/{pid}").status_code == 204
    assert client.delete(f"/papers/{pid}/permanent").status_code == 204

    assert not managed_file.exists()
    assert linked_file.exists()
    assert outside_file.exists()


def test_permanent_delete_preserves_managed_file_until_last_reference_is_purged(
    temp_db_url: str, tmp_path: Path, monkeypatch
) -> None:
    managed_root = tmp_path / "managed-library"
    managed_root.mkdir()
    monkeypatch.setenv("CALLOSUM_LIBRARY_DIR", str(managed_root))
    shared_file = managed_root / "shared.pdf"
    shared_file.write_bytes(b"%PDF-test")

    seeded = _seed_library(temp_db_url)
    first, second = seeded["facial_paper_id"], seeded["signal_paper_id"]
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        for paper_id in (first, second):
            create_attachment(
                conn,
                paper_id=paper_id,
                storage_mode="managed",
                availability="available",
                original_path=str(shared_file),
                resolved_path=str(shared_file),
                content_type="application/pdf",
                attachment_type="pdf",
                role="primary",
            )
    engine.dispose()

    client = TestClient(create_app(db_url=temp_db_url, vector_store=InMemoryVectorStore()))
    assert client.delete(f"/papers/{first}").status_code == 204
    assert client.delete(f"/papers/{first}/permanent").status_code == 204
    assert shared_file.exists()

    assert client.delete(f"/papers/{second}").status_code == 204
    assert client.delete(f"/papers/{second}/permanent").status_code == 204
    assert not shared_file.exists()


def test_managed_file_staging_failure_leaves_paper_in_trash(temp_db_url: str, tmp_path: Path, monkeypatch) -> None:
    managed_root = tmp_path / "managed-library"
    managed_root.mkdir()
    monkeypatch.setenv("CALLOSUM_LIBRARY_DIR", str(managed_root))
    managed_files = [managed_root / "first.pdf", managed_root / "locked.pdf"]
    for path in managed_files:
        path.write_bytes(b"%PDF-test")

    seeded = _seed_library(temp_db_url)
    pid = seeded["facial_paper_id"]
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        for path in managed_files:
            create_attachment(
                conn,
                paper_id=pid,
                storage_mode="managed",
                availability="available",
                original_path=str(path),
                resolved_path=str(path),
                content_type="application/pdf",
                attachment_type="pdf",
                role="primary",
            )
    engine.dispose()

    move_count = 0

    def fail_move(source: Path, destination: Path) -> None:
        nonlocal move_count
        move_count += 1
        if move_count == 2:
            raise OSError("simulated file lock")
        source.replace(destination)

    monkeypatch.setattr("app.backend.paper_purge._move_file", fail_move)
    client = TestClient(create_app(db_url=temp_db_url, vector_store=InMemoryVectorStore()))
    assert client.delete(f"/papers/{pid}").status_code == 204
    response = client.delete(f"/papers/{pid}/permanent")

    assert response.status_code == 409
    assert response.json()["detail"].startswith("Paper remains in Trash:")
    assert pid in _library_ids(client, deleted=True)
    assert all(path.exists() for path in managed_files)


def test_database_purge_failure_restores_staged_managed_file(temp_db_url: str, tmp_path: Path, monkeypatch) -> None:
    managed_root = tmp_path / "managed-library"
    managed_root.mkdir()
    monkeypatch.setenv("CALLOSUM_LIBRARY_DIR", str(managed_root))
    managed_file = managed_root / "rollback.pdf"
    managed_file.write_bytes(b"%PDF-test")

    seeded = _seed_library(temp_db_url)
    pid = seeded["facial_paper_id"]
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        create_attachment(
            conn,
            paper_id=pid,
            storage_mode="managed",
            availability="available",
            original_path=str(managed_file),
            resolved_path=str(managed_file),
            content_type="application/pdf",
            attachment_type="pdf",
            role="primary",
        )
    engine.dispose()

    client = TestClient(
        create_app(db_url=temp_db_url, vector_store=InMemoryVectorStore()), raise_server_exceptions=False
    )
    assert client.delete(f"/papers/{pid}").status_code == 204

    def fail_purge(*args, **kwargs) -> bool:
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr("app.backend.paper_purge.purge_paper", fail_purge)
    assert client.delete(f"/papers/{pid}/permanent").status_code == 500
    assert managed_file.exists()
    assert pid in _library_ids(client, deleted=True)


def test_empty_trash_purges_all_trashed_only(temp_db_url: str, tmp_path: Path, monkeypatch) -> None:
    seeded = _seed_library(temp_db_url)
    client = TestClient(create_app(db_url=temp_db_url, vector_store=InMemoryVectorStore()))
    facial, signal = seeded["facial_paper_id"], seeded["signal_paper_id"]
    managed_root = tmp_path / "managed-library"
    managed_root.mkdir()
    monkeypatch.setenv("CALLOSUM_LIBRARY_DIR", str(managed_root))
    managed_file = managed_root / "empty-trash.pdf"
    managed_file.write_bytes(b"%PDF-test")
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        create_attachment(
            conn,
            paper_id=facial,
            storage_mode="managed",
            availability="available",
            original_path=str(managed_file),
            resolved_path=str(managed_file),
            content_type="application/pdf",
            attachment_type="pdf",
            role="primary",
        )
    engine.dispose()
    client.delete(f"/papers/{facial}")  # trash only the facial paper; signal stays live

    resp = client.post("/papers/trash/empty")

    assert resp.status_code == 200 and resp.json()["purged"] == 1
    assert _library_ids(client, deleted=True) == set()  # Trash is empty
    assert signal in _library_ids(client)  # the live paper is untouched
    assert not managed_file.exists()


def test_trashed_paper_excluded_from_retrieval(temp_db_url: str) -> None:
    # inc 66: a soft-deleted (in-Trash, not-yet-purged) paper must not be a retrieval candidate.
    engine = make_engine(temp_db_url)
    store = InMemoryVectorStore()
    with engine.begin() as conn:
        a = _seed_indexed_paper(
            conn, store, title="Alpha", checksum="ret-a", chunk_vec=[0.0, 1.0], paper_vec=[1.0, 0.0]
        )
        b = _seed_indexed_paper(conn, store, title="Beta", checksum="ret-b", chunk_vec=[0.0, 1.0], paper_vec=[1.0, 0.0])
        model = _TwoDimModel()

        before = {
            h.paper_id
            for h in search_similar(
                conn,
                query_vector=[0.0, 1.0],
                model=model,
                vector_store=store,
                top_k=10,
                target_types=("chunk",),
                document_roles=ARTICLE_DOCUMENT_ROLES,
            )
        }
        assert {a["paper_id"], b["paper_id"]} <= before  # both papers retrievable

        assert soft_delete_paper(conn, a["paper_id"]) is True
        after = {
            h.paper_id
            for h in search_similar(
                conn,
                query_vector=[0.0, 1.0],
                model=model,
                vector_store=store,
                top_k=10,
                target_types=("chunk",),
                document_roles=ARTICLE_DOCUMENT_ROLES,
            )
        }
        assert a["paper_id"] not in after and b["paper_id"] in after  # trashed → excluded; live stays
    engine.dispose()


# ── duplicate detection (inc 56) ─────────────────────────────────────────────


class _DistinctEmbedModel:
    """One-hot per position → orthogonal → the embedding dedup layer never fires (isolate identifier/title)."""

    name = "distinct-test"
    version = "v1"
    dimension = 4
    normalization = "whitespace-lower-v1"

    def encode_texts(self, texts):
        n = len(texts)
        return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


def test_scan_duplicates_flags_a_shared_identifier_pair(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = create_paper(conn, title="Dup A", csl_json={"type": "article-journal", "title": "Dup A", "PMID": "12345"})
        b = create_paper(conn, title="Dup B", csl_json={"type": "article-journal", "title": "Dup B", "PMID": "12345"})
        create_paper(conn, title="Solo", csl_json={"type": "article-journal", "title": "Solo", "PMID": "99"})
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url, embedding_model=_DistinctEmbedModel()))

    started = client.post("/papers/duplicates")
    assert started.status_code == 202
    result = client.get(f"/papers/duplicates/{started.json()['job_id']}").json()

    assert result["status"] == "done"
    assert len(result["groups"]) == 1
    group = result["groups"][0]
    assert group["reason"] == "shared PMID" and group["confidence"] == 0.99
    assert {p["id"] for p in group["papers"]} == {a, b}


def test_scan_duplicates_empty_when_no_dupes(temp_db_url: str) -> None:
    _seed_library(temp_db_url)  # facial + signal are distinct papers
    client = TestClient(create_app(db_url=temp_db_url, embedding_model=_DistinctEmbedModel()))

    started = client.post("/papers/duplicates")
    result = client.get(f"/papers/duplicates/{started.json()['job_id']}").json()

    assert result["status"] == "done" and result["groups"] == []


def test_dismissed_duplicate_pair_is_not_re_flagged(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = create_paper(conn, title="Dup A", csl_json={"type": "article-journal", "title": "Dup A", "PMID": "12345"})
        b = create_paper(conn, title="Dup B", csl_json={"type": "article-journal", "title": "Dup B", "PMID": "12345"})
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url, embedding_model=_DistinctEmbedModel()))

    def scan():
        started = client.post("/papers/duplicates")
        return client.get(f"/papers/duplicates/{started.json()['job_id']}").json()

    assert len(scan()["groups"]) == 1  # flagged

    assert client.post("/papers/duplicates/dismiss", json={"paper_ids": [a, b]}).status_code == 204
    assert scan()["groups"] == []  # persistent: never re-flagged

    assert (
        client.post("/papers/duplicates/dismiss", json={"paper_ids": [b, a]}).status_code == 204
    )  # idempotent (any order)
    assert scan()["groups"] == []

    assert client.post("/papers/duplicates/dismiss", json={"paper_ids": [a]}).status_code == 422  # <2 ids
    assert client.post("/papers/duplicates/dismiss", json={"paper_ids": [a, 999999]}).status_code == 422  # <2 existing


def test_dismissed_pair_can_be_listed_and_undismissed(temp_db_url: str) -> None:
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = create_paper(conn, title="Dup A", csl_json={"type": "article-journal", "title": "Dup A", "PMID": "12345"})
        b = create_paper(conn, title="Dup B", csl_json={"type": "article-journal", "title": "Dup B", "PMID": "12345"})
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url, embedding_model=_DistinctEmbedModel()))

    def scan():
        started = client.post("/papers/duplicates")
        return client.get(f"/papers/duplicates/{started.json()['job_id']}").json()

    assert len(scan()["groups"]) == 1
    assert client.post("/papers/duplicates/dismiss", json={"paper_ids": [a, b]}).status_code == 204
    assert scan()["groups"] == []  # suppressed

    listed = client.get("/papers/duplicates/dismissed")
    assert listed.status_code == 200
    pairs = listed.json()["pairs"]
    assert len(pairs) == 1
    low, high = (a, b) if a < b else (b, a)
    assert pairs[0]["low"]["id"] == low and pairs[0]["high"]["id"] == high  # canonical, with titles
    assert pairs[0]["low"]["title"] and pairs[0]["high"]["title"]

    assert client.post("/papers/duplicates/undismiss", json={"paper_ids": [b, a]}).status_code == 204  # any order
    assert client.get("/papers/duplicates/dismissed").json()["pairs"] == []  # gone
    assert len(scan()["groups"]) == 1  # flagged again

    assert (
        client.post("/papers/duplicates/undismiss", json={"paper_ids": [a, b]}).status_code == 204
    )  # idempotent no-op
    assert client.post("/papers/duplicates/undismiss", json={"paper_ids": [a]}).status_code == 422  # <2 ids


def test_paper_read_marker(temp_db_url: str) -> None:
    # inc 220: a manual read/unread toggle + an Unread/Read library filter. Read state is the user's, never auto.
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = create_paper(conn, title="Paper A", csl_json={"title": "Paper A"})
        b = create_paper(conn, title="Paper B", csl_json={"title": "Paper B"})
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    # both start unread
    assert client.get(f"/papers/{a}").json()["read_at"] is None
    assert {p["id"] for p in client.get("/papers", params={"read_status": "unread"}).json()} == {a, b}
    assert client.get("/papers", params={"read_status": "read"}).json() == []

    # mark A read
    detail = client.post(f"/papers/{a}/read", json={"read": True})
    assert detail.status_code == 200 and detail.json()["read_at"] is not None
    assert {p["id"] for p in client.get("/papers", params={"read_status": "read"}).json()} == {a}
    assert {p["id"] for p in client.get("/papers", params={"read_status": "unread"}).json()} == {b}

    # "Unread first" sort (experience-pass interim): with A read, the unread B sorts ahead of A
    client.post(f"/papers/{a}/read", json={"read": True})
    ordered = [p["id"] for p in client.get("/papers", params={"sort": "unread"}).json()]
    assert ordered.index(b) < ordered.index(a)

    # unmark A
    assert client.post(f"/papers/{a}/read", json={"read": False}).json()["read_at"] is None
    assert client.get("/papers", params={"read_status": "read"}).json() == []

    # 404 on a nonexistent paper
    assert client.post("/papers/999999/read", json={"read": True}).status_code == 404


def test_paper_priority_marker(temp_db_url: str) -> None:
    # inc 220: a user-set priority (high/normal/low) — a hand label, never an AI score. Filter + "By priority" sort.
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        hi = create_paper(conn, title="High one", csl_json={"title": "High one"})
        lo = create_paper(conn, title="Low one", csl_json={"title": "Low one"})
        un = create_paper(conn, title="Unset one", csl_json={"title": "Unset one"})
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))

    assert client.get(f"/papers/{hi}").json()["priority"] is None
    assert client.post(f"/papers/{hi}/priority", json={"priority": "high"}).json()["priority"] == "high"
    assert client.post(f"/papers/{lo}/priority", json={"priority": "low"}).json()["priority"] == "low"

    # off-allowlist → 422 (stored value unchanged); 404 on a nonexistent paper
    assert client.post(f"/papers/{hi}/priority", json={"priority": "urgent"}).status_code == 422
    assert client.get(f"/papers/{hi}").json()["priority"] == "high"
    assert client.post("/papers/999999/priority", json={"priority": "high"}).status_code == 404

    # filter to a level
    assert {p["id"] for p in client.get("/papers", params={"priority": "high"}).json()} == {hi}

    # By-priority sort: high → low → unset (NULL last)
    ordered = [p["id"] for p in client.get("/papers", params={"sort": "priority"}).json()]
    assert ordered == [hi, lo, un]

    # clear via null
    assert client.post(f"/papers/{hi}/priority", json={"priority": None}).json()["priority"] is None
    assert client.get("/papers", params={"priority": "high"}).json() == []


def test_priority_sort_recency_tiebreak_within_tier(temp_db_url: str) -> None:
    # inc 223: within each priority tier (especially the unset bucket) "By priority" falls back to recency
    # (most-recently-added first = id DESC), so a large unset tier isn't one undifferentiated oldest-first block.
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        un_old = create_paper(conn, title="Unset old", csl_json={"title": "Unset old"})
        hi_old = create_paper(conn, title="High old", csl_json={"title": "High old"})
        un_new = create_paper(conn, title="Unset new", csl_json={"title": "Unset new"})
        hi_new = create_paper(conn, title="High new", csl_json={"title": "High new"})
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.post(f"/papers/{hi_old}/priority", json={"priority": "high"}).status_code == 200
    assert client.post(f"/papers/{hi_new}/priority", json={"priority": "high"}).status_code == 200

    ordered = [p["id"] for p in client.get("/papers", params={"sort": "priority"}).json()]
    # high tier first (newest-added first within it), then the unset tier (newest-added first within it).
    assert ordered == [hi_new, hi_old, un_new, un_old]


def test_titles_for_ids(temp_db_url: str) -> None:
    # inc 304: id→title map for per-item progress labels; missing ids omitted, blank falls back to "paper <id>".
    from app.backend.persistence.repository import titles_for_ids

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = create_paper(conn, title="Alpha", csl_json={"title": "Alpha"})
        b = create_paper(conn, title="Beta", csl_json={"title": "Beta"})
        assert titles_for_ids(conn, [a, b, 99999]) == {a: "Alpha", b: "Beta"}
        assert titles_for_ids(conn, []) == {}
    engine.dispose()


def test_list_missing_pdf_filter(temp_db_url: str, tmp_path: Path) -> None:
    # inc 301: `missing_pdf=true` → only papers with no LOCAL PDF (mirrors Text-Health no_local_pdf).
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        has_pdf = create_paper(conn, title="Has PDF", csl_json={"title": "Has PDF"})
        create_attachment(
            conn,
            paper_id=has_pdf,
            storage_mode="linked",
            availability="available",
            original_path=str(pdf),
            resolved_path=str(pdf),
            content_type="application/pdf",
            attachment_type="pdf",
            role="primary",
        )
        no_att = create_paper(conn, title="No attachment", csl_json={"title": "No attachment"})
        non_pdf = create_paper(conn, title="Non-PDF only", csl_json={"title": "Non-PDF only"})
        create_attachment(
            conn,
            paper_id=non_pdf,
            storage_mode="linked",
            availability="available",
            resolved_path="x.txt",
            content_type="text/plain",
            attachment_type="text",
        )
        wanted = create_paper(conn, title="Wanted PDF (no local file)", csl_json={"title": "Wanted"})
        create_attachment(
            conn,
            paper_id=wanted,
            storage_mode="url",  # a known-but-unfetched PDF (a URL reference, no local file)
            availability="missing",
            content_type="application/pdf",
            attachment_type="pdf",
        )  # no resolved_path → counts as "missing PDF"
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    assert {has_pdf, no_att, non_pdf, wanted} <= {p["id"] for p in client.get("/papers").json()}
    missing = {p["id"] for p in client.get("/papers", params={"missing_pdf": "true"}).json()}
    assert no_att in missing and non_pdf in missing and wanted in missing  # no local PDF
    assert has_pdf not in missing  # has a local PDF → excluded


def test_trash_listing_applies_read_and_priority_filters(temp_db_url: str) -> None:
    # inc 301: the read/priority filters (and missing_pdf) now work on the Trash (deleted) listing too.
    from app.backend.persistence.repository import set_paper_priority, soft_delete_paper

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        hi = create_paper(conn, title="Trashed High", csl_json={"title": "Trashed High"})
        lo = create_paper(conn, title="Trashed Low", csl_json={"title": "Trashed Low"})
        set_paper_priority(conn, hi, "high")
        soft_delete_paper(conn, hi)
        soft_delete_paper(conn, lo)
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    trashed = {p["id"] for p in client.get("/papers", params={"deleted": "true"}).json()}
    assert trashed == {hi, lo}
    high_trashed = {p["id"] for p in client.get("/papers", params={"deleted": "true", "priority": "high"}).json()}
    assert high_trashed == {hi}  # the priority filter applies to the deleted listing too

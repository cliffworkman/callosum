"""My Publications Layer-4 grounded citation gaps (inc 386)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import insert

from app.backend.api import create_app
from app.backend.clustering.axis_assignments import add_manual_assignment, ensure_axis_node
from app.backend.clustering.axis_scoring import create_axis
from app.backend.clustering.my_publication_gaps import compute_my_publication_citation_gaps
from app.backend.clustering.my_publications import CANDIDATE_CONFIDENCE, MY_PUBLICATIONS_KIND
from app.backend.persistence.database import make_engine
from app.backend.persistence.my_publication_gap_repo import (
    read_my_publication_citation_gap_cache,
    replace_my_publication_citation_gap_cache,
)
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import cluster_node_papers, my_publication_citation_gap_cache


class _GraphClient:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.fail_anchor_meta = False
        self.work_ids = {
            "10.1/own-a": "W101",
            "10.1/own-b": "W102",
            "10.1/unconfirmed": "W103",
        }
        self.references = {
            "10.1/own-a": ["W201", "W202", "W900", "not-an-id"],
            "10.1/own-b": ["W201", "W202"],
            "10.1/unconfirmed": ["W203"],
        }
        self.anchor_meta = {
            "W201": _meta("W201", "10.2/reference-a", "Shared Reference A", 2010),
            "W202": _meta("W202", "10.2/reference-b", "Shared Reference B", 2011),
        }
        self.citing = {
            "W201": [
                _meta("W301", "10.3/best", "Best grounded gap", 2024),
                _meta("W302", "10.3/one", "One-anchor gap", 2023),
                _meta("W900", "10.3/direct", "Already cited directly", 2022),
                _meta("bad-id", "10.3/bad", "Invalid id", 2020),
            ],
            "W202": [
                _meta("W301", "10.3/best", "Best grounded gap", 2024),
                _meta("W101", "10.1/own-a", "Own paper", 2020),
                _meta("W401", "10.3/existing", "Already in library", 2021),
            ],
        }

    def with_cache_engine(self, _engine):
        return self

    def fetch_work_id(self, _conn, ref):
        self.calls.append(("work-id", ref.doi))
        return self.work_ids.get(ref.doi)

    def fetch_referenced_works(self, _conn, ref):
        self.calls.append(("references", ref.doi))
        return self.references.get(ref.doi, [])

    def fetch_works_by_ids(self, _conn, ids, *, with_abstract=True):
        self.calls.append(("anchor-meta", "|".join(ids)))
        if self.fail_anchor_meta:
            raise RuntimeError("simulated OpenAlex failure")
        assert with_abstract is False
        return [self.anchor_meta[work_id] for work_id in ids if work_id in self.anchor_meta]

    def fetch_citing_works(self, _conn, work_id):
        self.calls.append(("citing", work_id))
        return self.citing.get(work_id, [])


class _UnresolvedResolution:
    resolved = False
    csl_json = None
    error = None


class _NoCrossref:
    def resolve_doi(self, _conn, _doi):
        return _UnresolvedResolution()


def _meta(work_id: str, doi: str, title: str, year: int) -> dict:
    return {
        "openalex_work_id": work_id,
        "doi": doi,
        "title": title,
        "authors": ["A. Researcher", "B. Scholar"],
        "year": year,
    }


def _seed_my_publications(conn) -> tuple[int, int]:
    own_a = create_paper(
        conn,
        title="Own publication A",
        doi="10.1/own-a",
        csl_json={"title": "Own publication A", "DOI": "10.1/own-a"},
    )
    own_b = create_paper(
        conn,
        title="Own publication B",
        doi="10.1/own-b",
        csl_json={"title": "Own publication B", "DOI": "10.1/own-b"},
    )
    unconfirmed = create_paper(
        conn,
        title="Name-only candidate",
        doi="10.1/unconfirmed",
        csl_json={"title": "Name-only candidate", "DOI": "10.1/unconfirmed"},
    )
    create_paper(
        conn,
        title="Already in library",
        doi="10.3/existing",
        csl_json={"title": "Already in library", "DOI": "10.3/existing"},
    )
    axis_id = create_axis(conn, label="My Publications", kind=MY_PUBLICATIONS_KIND)
    add_manual_assignment(conn, axis_id=axis_id, paper_id=own_a)
    add_manual_assignment(conn, axis_id=axis_id, paper_id=own_b)
    node_id = ensure_axis_node(conn, axis_id)
    conn.execute(
        insert(cluster_node_papers).values(
            cluster_node_id=node_id,
            paper_id=unconfirmed,
            confidence=CANDIDATE_CONFIDENCE,
        )
    )
    return own_a, own_b


def test_compute_citation_gaps_is_grounded_and_excludes_direct_existing_and_unconfirmed(temp_db_url):
    engine = make_engine(temp_db_url)
    graph = _GraphClient()
    with engine.begin() as conn:
        own_a, own_b = _seed_my_publications(conn)
        candidates, coverage = compute_my_publication_citation_gaps(
            conn,
            openalex_client=graph,
            dismissed=set(),
        )
    engine.dispose()

    assert [candidate.openalex_work_id for candidate in candidates] == ["W301", "W302"]
    best = candidates[0]
    assert best.shared_reference_count == 2
    assert best.source_publication_count == 2
    assert {item["reference_openalex_work_id"] for item in best.evidence} == {"W201", "W202"}
    assert {source["paper_id"] for item in best.evidence for source in item["source_papers"]} == {own_a, own_b}
    assert all(call[1] != "10.1/unconfirmed" for call in graph.calls if call[0] in {"work-id", "references"})
    assert coverage["checked"] == coverage["with_doi"] == coverage["total"] == 2
    assert coverage["shared_anchor_count"] == 2
    assert "not an exhaustive" in coverage["note"]


def test_compute_citation_gaps_honors_dismissal_and_candidate_cap(temp_db_url):
    engine = make_engine(temp_db_url)
    graph = _GraphClient()
    with engine.begin() as conn:
        _seed_my_publications(conn)
        candidates, _ = compute_my_publication_citation_gaps(
            conn,
            openalex_client=graph,
            dismissed={"W301"},
            max_candidates=1,
        )
    engine.dispose()
    assert [candidate.openalex_work_id for candidate in candidates] == ["W302"]


def test_empty_citation_gap_snapshot_is_distinct_from_not_computed(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        assert read_my_publication_citation_gap_cache(conn) is None
        replace_my_publication_citation_gap_cache(
            conn,
            [],
            {
                "checked": 0,
                "with_doi": 0,
                "total": 0,
                "shared_anchor_count": 0,
                "publication_cap_reached": False,
                "note": "No confirmed publications.",
            },
            computed_at="2026-07-25T00:00:00+00:00",
        )
        snapshot = read_my_publication_citation_gap_cache(conn)
    engine.dispose()
    assert snapshot is not None
    assert snapshot["candidates"] == [] and snapshot["computed_at"].startswith("2026-07-25")


def _drive_refresh(client: TestClient) -> dict:
    started = client.post("/my-publications/citation-gaps/refresh", json={})
    assert started.status_code == 202
    job_id = started.json()["job_id"]
    result = {}
    for _ in range(30):
        result = client.get(f"/my-publications/citation-gaps/refresh/{job_id}").json()
        if result["status"] in ("done", "error"):
            break
    return result


def test_citation_gap_api_refresh_is_explicit_cached_and_read_time_filtered(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        own_a, own_b = _seed_my_publications(conn)
    engine.dispose()
    graph = _GraphClient()
    client = TestClient(
        create_app(
            db_url=temp_db_url,
            openalex_client=graph,
            crossref_client=_NoCrossref(),
        )
    )

    never = client.get("/my-publications/citation-gaps")
    assert never.status_code == 200 and never.json()["computed_at"] is None
    assert graph.calls == []

    done = _drive_refresh(client)
    assert done["status"] == "done"
    assert done["result"]["count"] == 2
    assert done["result"]["coverage"]["checked"] == 2
    calls_after_refresh = list(graph.calls)

    listed = client.get("/my-publications/citation-gaps").json()
    assert [candidate["openalex_work_id"] for candidate in listed["candidates"]] == ["W301", "W302"]
    evidence_ids = {
        source["paper_id"] for item in listed["candidates"][0]["evidence"] for source in item["source_papers"]
    }
    assert evidence_ids == {own_a, own_b}
    client.get("/my-publications/citation-gaps")
    assert graph.calls == calls_after_refresh  # plain reads never fetch

    dismissed = client.post(
        "/gaps/dismiss",
        json={"openalex_work_id": "W301", "doi": "10.3/best"},
    )
    assert dismissed.status_code == 204
    assert [
        candidate["openalex_work_id"] for candidate in client.get("/my-publications/citation-gaps").json()["candidates"]
    ] == ["W302"]

    added = client.post(
        "/gaps/add",
        json={"doi": "10.3/one", "openalex_work_id": "W302", "title": "One-anchor gap"},
    )
    assert added.status_code == 200 and added.json()["status"] == "imported"
    assert client.get("/my-publications/citation-gaps").json()["candidates"] == []


def test_failed_citation_gap_refresh_preserves_previous_snapshot(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _seed_my_publications(conn)
    engine.dispose()
    graph = _GraphClient()
    client = TestClient(create_app(db_url=temp_db_url, openalex_client=graph))
    assert _drive_refresh(client)["status"] == "done"
    before = client.get("/my-publications/citation-gaps").json()

    graph.fail_anchor_meta = True
    failed = _drive_refresh(client)
    assert failed["status"] == "error" and "simulated OpenAlex failure" in failed["detail"]
    after = client.get("/my-publications/citation-gaps").json()
    assert after == before


def test_citation_gap_read_drops_evidence_for_trashed_source_papers(temp_db_url):
    engine = make_engine(temp_db_url)
    graph = _GraphClient()
    with engine.begin() as conn:
        own_a, own_b = _seed_my_publications(conn)
        candidates, coverage = compute_my_publication_citation_gaps(
            conn,
            openalex_client=graph,
            dismissed=set(),
        )
        replace_my_publication_citation_gap_cache(
            conn,
            candidates,
            coverage,
            computed_at="2026-07-25T00:00:00+00:00",
        )
        conn.exec_driver_sql("UPDATE papers SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?", (own_a,))
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    listed = client.get("/my-publications/citation-gaps").json()["candidates"]
    assert listed
    assert all(
        source["paper_id"] == own_b
        for candidate in listed
        for evidence in candidate["evidence"]
        for source in evidence["source_papers"]
    )


def test_citation_gap_read_drops_malformed_cached_metadata(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        conn.execute(
            insert(my_publication_citation_gap_cache).values(
                id=1,
                candidates=[{"openalex_work_id": "not-an-id"}, "not-an-object"],
                coverage={"checked": "not-an-integer"},
                computed_at="2026-07-25T00:00:00+00:00",
            )
        )
    engine.dispose()
    response = TestClient(create_app(db_url=temp_db_url)).get("/my-publications/citation-gaps")
    assert response.status_code == 200
    assert response.json()["candidates"] == [] and response.json()["coverage"] is None

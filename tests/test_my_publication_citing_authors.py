"""My Publications Layer-4 authors citing your work (inc 391)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.clustering.axis_assignments import add_manual_assignment
from app.backend.clustering.axis_scoring import create_axis
from app.backend.clustering.my_publication_citing_authors import compute_citing_authors
from app.backend.clustering.my_publication_gap_scope import citation_gap_domain_key
from app.backend.clustering.my_publications import MY_PUBLICATIONS_KIND
from app.backend.persistence.database import make_engine
from app.backend.persistence.my_publication_citing_author_repo import (
    MAX_CACHED_SCOPES,
    read_citing_author_cache,
    replace_citing_author_cache,
)
from app.backend.persistence.profile_repo import (
    set_openalex_author_id,
    set_research_domains,
    upsert_profile,
)
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import my_publication_citing_author_cache
from integrations.openalex import OpenAlexClient
from integrations.openalex.citing_authors import (
    CitingAuthorMetadataUnavailable,
    OpenAlexCitingAuthorsClient,
)


class _WorkIdClient:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.ids = {"10.1/own-a": "W101", "10.1/own-b": "W102"}

    def with_cache_engine(self, _engine):
        return self

    def fetch_work_id(self, _conn, ref):
        self.calls.append(ref.doi)
        return self.ids.get(ref.doi)


class _CitingClient:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], int, int]] = []
        self.fail = False

    def with_cache_engine(self, _engine):
        return self

    def fetch_window(self, _conn, work_ids, *, start_year, end_year):
        self.calls.append((tuple(work_ids), start_year, end_year))
        if self.fail:
            raise RuntimeError("simulated citing-author failure")
        if start_year == 2023:
            return [
                _citing("W501", 2025, ["W101"], [("A9", "R. Reader"), ("A2", "Prior Coauthor")]),
                _citing("W502", 2024, ["W102"], [("A9", "R. Reader"), ("A2", "Prior Coauthor")]),
                _citing("W503", 2025, ["W101"], [("A8", "One-off Author")]),
                _citing("bad-id", 2025, ["W102"], [("A9", "R. Reader")]),
            ], False
        return [], False

    def fetch_source_authorships(self, _conn, work_ids):
        if self.fail:
            raise RuntimeError("simulated citing-author failure")
        return {
            "W101": {
                "openalex_work_id": "W101",
                "authors": [{"id": "A1", "name": "Profile Author"}, {"id": "A2", "name": "Prior Coauthor"}],
                "authorship_count": 2,
                "authorship_cap_reached": False,
            },
            "W102": {
                "openalex_work_id": "W102",
                "authors": [{"id": "A1", "name": "Profile Author"}, {"id": "A3", "name": "Another Coauthor"}],
                "authorship_count": 2,
                "authorship_cap_reached": False,
            },
        }


class _AuthorshipFetcher:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def __call__(self, path, *, params, headers, timeout):  # noqa: ANN001
        self.calls.append(dict(params))
        return 200, {
            "results": [
                {
                    "id": "https://openalex.org/W101",
                    "authorships": [
                        {"author": {"id": "https://openalex.org/A1", "display_name": "Profile Author"}},
                        {"author": {"id": "https://openalex.org/A2", "display_name": "Prior Coauthor"}},
                    ],
                },
                {
                    "id": "https://openalex.org/W999",
                    "authorships": [{"author": {"id": "https://openalex.org/A9", "display_name": "Wrong Work"}}],
                },
            ]
        }


def _citing(
    work_id: str,
    year: int,
    sources: list[str],
    authors: list[tuple[str, str]],
) -> dict:
    return {
        "openalex_work_id": work_id,
        "doi": f"10.5/{work_id.lower()}",
        "title": f"Citing {work_id}",
        "year": year,
        "authors": [name for _, name in authors],
        "author_records": [{"id": author_id, "name": name} for author_id, name in authors],
        "authorship_count": len(authors),
        "primary_topic": None,
        "cited_source_work_ids": sources,
    }


def _seed(conn) -> tuple[int, int, str]:
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
    axis_id = create_axis(conn, label="My Publications", kind=MY_PUBLICATIONS_KIND)
    add_manual_assignment(conn, axis_id=axis_id, paper_id=own_a)
    add_manual_assignment(conn, axis_id=axis_id, paper_id=own_b)
    upsert_profile(conn, display_name="Profile Author", name_variants=[], orcid=None)
    set_openalex_author_id(conn, "A1")
    set_research_domains(
        conn,
        [{"label": "Methods", "terms": ["methods"], "paper_ids": [own_a, own_b]}],
    )
    return own_a, own_b, citation_gap_domain_key([own_a, own_b])


def test_openalex_source_authorships_are_bounded_normalized_and_cached(temp_db_url):
    fetcher = _AuthorshipFetcher()
    adapter = OpenAlexCitingAuthorsClient(OpenAlexClient(fetcher=fetcher, mailto="test@example.org"))
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        works = adapter.fetch_source_authorships(conn, ["W102", "W101"])
        cached = adapter.fetch_source_authorships(conn, ["W101", "W102"])
        invalid = adapter.fetch_source_authorships(conn, ["not-a-work"])
    engine.dispose()

    assert len(fetcher.calls) == 1
    assert fetcher.calls[0]["filter"] == "openalex:W101|W102"
    assert fetcher.calls[0]["select"] == "id,authorships"
    assert works == cached
    assert works["W101"]["authors"][1] == {"id": "A2", "name": "Prior Coauthor"}
    assert "W999" not in works and invalid == {}


def test_openalex_source_authorship_failure_is_not_empty_result(temp_db_url):
    def unavailable(path, *, params, headers, timeout):  # noqa: ANN001
        return 503, {"error": "unavailable"}

    adapter = OpenAlexCitingAuthorsClient(OpenAlexClient(fetcher=unavailable))
    engine = make_engine(temp_db_url)
    with engine.begin() as conn, pytest.raises(CitingAuthorMetadataUnavailable):
        adapter.fetch_source_authorships(conn, ["W101"])
    engine.dispose()

    malformed = OpenAlexCitingAuthorsClient(OpenAlexClient(fetcher=lambda path, **kwargs: (200, {"results": {}})))
    engine = make_engine(temp_db_url)
    with engine.begin() as conn, pytest.raises(CitingAuthorMetadataUnavailable, match="malformed"):
        malformed.fetch_source_authorships(conn, ["W102"])
    engine.dispose()


def test_compute_citing_authors_uses_visible_counts_evidence_and_coauthor_exclusion(temp_db_url):
    engine = make_engine(temp_db_url)
    work_client = _WorkIdClient()
    citing_client = _CitingClient()
    with engine.begin() as conn:
        own_a, own_b, _ = _seed(conn)
        authors, coverage = compute_citing_authors(
            conn,
            openalex_client=work_client,
            citing_client=citing_client,
            current_year=2026,
        )
    engine.dispose()

    assert [author.author_id for author in authors] == ["A9"]
    author = authors[0]
    assert (author.citing_work_count, author.cited_publication_count, author.latest_year) == (2, 2, 2025)
    assert {source["paper_id"] for work in author.citing_works for source in work["cited_publications"]} == {
        own_a,
        own_b,
    }
    assert coverage["start_year"] == 2020 and coverage["end_year"] == 2025
    assert coverage["coauthor_checked_publication_count"] == 2
    assert coverage["excluded_coauthor_count"] == 2
    assert "not collaboration fit" in coverage["note"]


def test_compute_citing_authors_requires_resolved_profile_and_preserves_unresolved_snapshot(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _seed(conn)
        set_openalex_author_id(conn, None)
        with pytest.raises(RuntimeError, match="Resolve your OpenAlex author profile"):
            compute_citing_authors(
                conn,
                openalex_client=_WorkIdClient(),
                citing_client=_CitingClient(),
                current_year=2026,
            )
        set_openalex_author_id(conn, "A1")
        work_client = _WorkIdClient()
        work_client.ids = {}
        with pytest.raises(RuntimeError, match="prior author snapshot preserved"):
            compute_citing_authors(
                conn,
                openalex_client=work_client,
                citing_client=_CitingClient(),
                current_year=2026,
            )
    engine.dispose()


def _drive_refresh(client: TestClient, domain_keys: list[str] | None = None) -> dict:
    started = client.post(
        "/my-publications/citing-authors/refresh",
        json={"domain_keys": domain_keys or []},
    )
    assert started.status_code == 202
    job_id = started.json()["job_id"]
    result = {}
    for _ in range(30):
        result = client.get(f"/my-publications/citing-authors/refresh/{job_id}").json()
        if result["status"] in ("done", "error"):
            break
    return result


def test_citing_author_api_is_explicit_scoped_cached_and_failure_preserves_snapshot(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        own_a, own_b, domain_key = _seed(conn)
    engine.dispose()
    work_client = _WorkIdClient()
    citing_client = _CitingClient()
    client = TestClient(create_app(db_url=temp_db_url, openalex_client=work_client))
    client.app.state.openalex_citing_authors_client = citing_client
    scoped_path = f"/my-publications/citing-authors?domain_key={domain_key}"

    never = client.get(scoped_path)
    assert never.status_code == 200 and never.json()["computed_at"] is None
    assert work_client.calls == [] and citing_client.calls == []

    done = _drive_refresh(client, [domain_key])
    assert done["status"] == "done" and done["result"]["count"] == 1
    assert done["result"]["scope"]["domain_labels"] == ["Methods"]
    listed = client.get(scoped_path).json()
    assert listed["authors"][0]["author_id"] == "A9"
    assert listed["authors"][0]["citing_work_count"] == 2
    assert {
        source["paper_id"] for work in listed["authors"][0]["citing_works"] for source in work["cited_publications"]
    } == {own_a, own_b}
    calls_after_refresh = (list(work_client.calls), list(citing_client.calls))
    client.get(scoped_path)
    assert (work_client.calls, citing_client.calls) == calls_after_refresh
    assert client.get("/my-publications/citing-authors").json()["computed_at"] is None

    citing_client.fail = True
    failed = _drive_refresh(client, [domain_key])
    assert failed["status"] == "error" and "simulated citing-author failure" in failed["detail"]
    assert client.get(scoped_path).json() == listed


def test_citing_author_scope_is_server_validated(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url, openalex_client=_WorkIdClient()))
    invalid = "domain:" + ("f" * 20)
    assert client.get(f"/my-publications/citing-authors?domain_key={invalid}").status_code == 422
    assert (
        client.post(
            "/my-publications/citing-authors/refresh",
            json={"domain_keys": [invalid]},
        ).status_code
        == 422
    )


def test_citing_author_read_rechecks_live_confirmed_sources_and_profile_identity(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        own_a, own_b, _ = _seed(conn)
        authors, coverage = compute_citing_authors(
            conn,
            openalex_client=_WorkIdClient(),
            citing_client=_CitingClient(),
            current_year=2026,
        )
        replace_citing_author_cache(
            conn,
            authors,
            {**coverage, "scope_kind": "all", "domain_count": 0, "domain_labels": []},
            computed_at="2026-07-26T00:00:00+00:00",
        )
        conn.exec_driver_sql("UPDATE papers SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?", (own_b,))
    engine.dispose()

    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/my-publications/citing-authors").json()["authors"] == []

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        conn.exec_driver_sql("UPDATE papers SET deleted_at = NULL WHERE id = ?", (own_b,))
        set_openalex_author_id(conn, "A9")
    engine.dispose()
    assert client.get("/my-publications/citing-authors").json()["authors"] == []


def test_citing_author_cache_is_bounded_and_malformed_rows_fail_plain(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        for index in range(MAX_CACHED_SCOPES + 1):
            replace_citing_author_cache(
                conn,
                [],
                {},
                computed_at=f"2026-07-26T00:00:{index:02d}+00:00",
                scope_key=f"scope:{index}",
            )
        rows = conn.exec_driver_sql(
            "SELECT scope_key FROM my_publication_citing_author_cache ORDER BY computed_at"
        ).scalars()
        assert list(rows) == [f"scope:{index}" for index in range(1, MAX_CACHED_SCOPES + 1)]
        conn.execute(
            my_publication_citing_author_cache.insert().values(
                scope_key="all",
                scope={"kind": "all"},
                authors=[{"author_id": "not-an-author"}, "not-an-object"],
                coverage={"checked": "not-an-integer"},
                computed_at="2026-07-26T00:01:00+00:00",
            )
        )
        assert read_citing_author_cache(conn) is not None
    engine.dispose()
    response = TestClient(create_app(db_url=temp_db_url)).get("/my-publications/citing-authors")
    assert response.status_code == 200
    assert response.json()["authors"] == [] and response.json()["coverage"] is None

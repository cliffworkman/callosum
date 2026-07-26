"""My Publications Layer-4 emerging citing topics (inc 390)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.clustering.axis_assignments import add_manual_assignment
from app.backend.clustering.axis_scoring import create_axis
from app.backend.clustering.my_publication_gap_scope import citation_gap_domain_key
from app.backend.clustering.my_publication_topics import compute_emerging_citing_topics
from app.backend.clustering.my_publications import MY_PUBLICATIONS_KIND
from app.backend.persistence.database import make_engine
from app.backend.persistence.my_publication_topic_repo import (
    MAX_CACHED_SCOPES,
    read_emerging_topic_cache,
    replace_emerging_topic_cache,
)
from app.backend.persistence.profile_repo import set_research_domains, upsert_profile
from app.backend.persistence.repository import create_paper
from app.backend.persistence.schema import my_publication_emerging_topic_cache
from integrations.openalex import OpenAlexClient
from integrations.openalex.citing_topics import (
    MAX_SOURCE_WORKS,
    CitingTopicWindowUnavailable,
    OpenAlexCitingTopicsClient,
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


class _TopicWindowClient:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[str, ...], int, int]] = []
        self.fail = False

    def with_cache_engine(self, _engine):
        return self

    def fetch_window(self, _conn, work_ids, *, start_year, end_year):
        self.calls.append((tuple(work_ids), start_year, end_year))
        if self.fail:
            raise RuntimeError("simulated topic-window failure")
        if start_year == 2023:
            return [
                _citing("W501", 2025, "T1", "Evidence Synthesis", ["W101"]),
                _citing("W502", 2024, "T1", "Evidence Synthesis", ["W101", "W102"]),
                _citing("W503", 2025, "T2", "Sparse Topic", ["W102"]),
                _citing("bad-id", 2025, "T1", "Evidence Synthesis", ["W101"]),
            ], False
        return [
            _citing("W401", 2022, "T1", "Evidence Synthesis", ["W102"]),
            _citing("W402", 2021, "T2", "Sparse Topic", ["W101"]),
            {**_citing("W403", 2020, "T3", "No Link", ["W999"]), "primary_topic": None},
        ], False


class _Fetcher:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def __call__(self, path, *, params, headers, timeout):  # noqa: ANN001
        self.calls.append(dict(params))
        return 200, {
            "meta": {"next_cursor": None},
            "results": [
                {
                    "id": "https://openalex.org/W501",
                    "doi": "https://doi.org/10.5/recent",
                    "title": "Recent citing work",
                    "publication_year": 2025,
                    "authorships": [{"author": {"display_name": "C. Author"}}],
                    "primary_topic": {
                        "id": "https://openalex.org/T1",
                        "display_name": "Evidence Synthesis",
                        "subfield": {"display_name": "Research Methods"},
                        "field": {"display_name": "Social Sciences"},
                        "domain": {"display_name": "Social Sciences"},
                    },
                    "referenced_works": [
                        "https://openalex.org/W101",
                        "https://openalex.org/W999",
                    ],
                }
            ],
        }


def _citing(work_id: str, year: int, topic_id: str, topic_name: str, sources: list[str]) -> dict:
    return {
        "openalex_work_id": work_id,
        "doi": f"10.5/{work_id.lower()}",
        "title": f"Citing {work_id}",
        "year": year,
        "authors": ["C. Author"],
        "primary_topic": {
            "id": topic_id,
            "name": topic_name,
            "subfield": "Research Methods",
            "field": "Social Sciences",
            "domain": "Social Sciences",
        },
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
    upsert_profile(conn, display_name="A. Researcher", name_variants=[], orcid=None)
    set_research_domains(
        conn,
        [{"label": "Methods", "terms": ["methods"], "paper_ids": [own_a, own_b]}],
    )
    return own_a, own_b, citation_gap_domain_key([own_a, own_b])


def test_openalex_citing_topic_window_is_bounded_normalized_and_cached(temp_db_url):
    fetcher = _Fetcher()
    adapter = OpenAlexCitingTopicsClient(OpenAlexClient(fetcher=fetcher, mailto="test@example.org"))
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        works, capped = adapter.fetch_window(conn, ["W102", "W101"], start_year=2023, end_year=2025)
        cached, cached_capped = adapter.fetch_window(conn, ["W101", "W102"], start_year=2023, end_year=2025)
        invalid = adapter.fetch_window(
            conn,
            [f"W{index + 1}" for index in range(MAX_SOURCE_WORKS + 1)],
            start_year=2023,
            end_year=2025,
        )
    engine.dispose()

    assert len(fetcher.calls) == 1
    assert fetcher.calls[0]["filter"] == (
        "cites:W101|W102,from_publication_date:2023-01-01,to_publication_date:2025-12-31"
    )
    assert fetcher.calls[0]["per-page"] == "100"
    assert works == cached and capped is cached_capped is False
    assert works[0]["primary_topic"]["id"] == "T1"
    assert works[0]["cited_source_work_ids"] == ["W101"]
    assert invalid == ([], False)


def test_openalex_citing_topic_window_failure_is_not_an_empty_result(temp_db_url):
    def unavailable(path, *, params, headers, timeout):  # noqa: ANN001
        return 503, {"error": "unavailable"}

    adapter = OpenAlexCitingTopicsClient(OpenAlexClient(fetcher=unavailable))
    engine = make_engine(temp_db_url)
    with engine.begin() as conn, pytest.raises(CitingTopicWindowUnavailable):
        adapter.fetch_window(conn, ["W101"], start_year=2023, end_year=2025)
    engine.dispose()


def test_compute_emerging_topics_uses_visible_equal_window_counts_and_evidence(temp_db_url):
    engine = make_engine(temp_db_url)
    work_client = _WorkIdClient()
    topic_client = _TopicWindowClient()
    with engine.begin() as conn:
        own_a, own_b, _ = _seed(conn)
        topics, coverage = compute_emerging_citing_topics(
            conn,
            openalex_client=work_client,
            topic_client=topic_client,
            current_year=2026,
        )
    engine.dispose()

    assert [topic.topic_id for topic in topics] == ["T1"]
    topic = topics[0]
    assert (topic.recent_count, topic.previous_count, topic.increase) == (2, 1, 1)
    assert {
        source["paper_id"]
        for work in topic.recent_works + topic.previous_works
        for source in work["cited_publications"]
    } == {own_a, own_b}
    assert coverage["recent_start_year"] == 2023 and coverage["recent_end_year"] == 2025
    assert coverage["previous_start_year"] == 2020 and coverage["previous_end_year"] == 2022
    assert coverage["recent_work_count"] == 3 and coverage["previous_work_count"] == 2
    assert "not a forecast" in coverage["note"]


def test_compute_emerging_topics_preserves_snapshot_when_no_doi_work_resolves(temp_db_url):
    engine = make_engine(temp_db_url)
    work_client = _WorkIdClient()
    work_client.ids = {}
    with engine.begin() as conn:
        _seed(conn)
        with pytest.raises(RuntimeError, match="prior topic snapshot preserved"):
            compute_emerging_citing_topics(
                conn,
                openalex_client=work_client,
                topic_client=_TopicWindowClient(),
                current_year=2026,
            )
    engine.dispose()


def _drive_refresh(client: TestClient, domain_keys: list[str] | None = None) -> dict:
    started = client.post(
        "/my-publications/emerging-citing-topics/refresh",
        json={"domain_keys": domain_keys or []},
    )
    assert started.status_code == 202
    job_id = started.json()["job_id"]
    result = {}
    for _ in range(30):
        result = client.get(f"/my-publications/emerging-citing-topics/refresh/{job_id}").json()
        if result["status"] in ("done", "error"):
            break
    return result


def test_emerging_topic_api_is_explicit_scoped_cached_and_failure_preserves_snapshot(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        own_a, own_b, domain_key = _seed(conn)
    engine.dispose()
    work_client = _WorkIdClient()
    topic_client = _TopicWindowClient()
    client = TestClient(create_app(db_url=temp_db_url, openalex_client=work_client))
    client.app.state.openalex_citing_topics_client = topic_client
    scoped_path = f"/my-publications/emerging-citing-topics?domain_key={domain_key}"

    never = client.get(scoped_path)
    assert never.status_code == 200 and never.json()["computed_at"] is None
    assert work_client.calls == [] and topic_client.calls == []

    done = _drive_refresh(client, [domain_key])
    assert done["status"] == "done" and done["result"]["count"] == 1
    assert done["result"]["scope"]["domain_labels"] == ["Methods"]
    listed = client.get(scoped_path).json()
    assert listed["topics"][0]["topic_id"] == "T1"
    assert listed["topics"][0]["increase"] == 1
    assert {
        source["paper_id"] for work in listed["topics"][0]["recent_works"] for source in work["cited_publications"]
    } == {own_a, own_b}
    calls_after_refresh = (list(work_client.calls), list(topic_client.calls))
    client.get(scoped_path)
    assert (work_client.calls, topic_client.calls) == calls_after_refresh
    assert client.get("/my-publications/emerging-citing-topics").json()["computed_at"] is None

    topic_client.fail = True
    failed = _drive_refresh(client, [domain_key])
    assert failed["status"] == "error" and "simulated topic-window failure" in failed["detail"]
    assert client.get(scoped_path).json() == listed


def test_emerging_topic_scope_is_server_validated(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url, openalex_client=_WorkIdClient()))
    invalid = "domain:" + ("f" * 20)
    assert client.get(f"/my-publications/emerging-citing-topics?domain_key={invalid}").status_code == 422
    assert (
        client.post(
            "/my-publications/emerging-citing-topics/refresh",
            json={"domain_keys": [invalid]},
        ).status_code
        == 422
    )


def test_emerging_topic_read_rechecks_live_confirmed_sources(temp_db_url):
    engine = make_engine(temp_db_url)
    work_client = _WorkIdClient()
    topic_client = _TopicWindowClient()
    with engine.begin() as conn:
        own_a, own_b, _ = _seed(conn)
        topics, coverage = compute_emerging_citing_topics(
            conn,
            openalex_client=work_client,
            topic_client=topic_client,
            current_year=2026,
        )
        replace_emerging_topic_cache(
            conn,
            topics,
            {
                **coverage,
                "scope_kind": "all",
                "domain_count": 0,
                "domain_labels": [],
            },
            computed_at="2026-07-26T00:00:00+00:00",
        )
        conn.exec_driver_sql("UPDATE papers SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?", (own_b,))
    engine.dispose()

    listed = TestClient(create_app(db_url=temp_db_url)).get("/my-publications/emerging-citing-topics").json()
    assert listed["topics"][0]["recent_count"] == 2
    assert listed["topics"][0]["previous_count"] == 0
    assert all(
        source["paper_id"] == own_a
        for work in listed["topics"][0]["recent_works"]
        for source in work["cited_publications"]
    )


def test_emerging_topic_cache_is_bounded_and_malformed_rows_fail_plain(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        for index in range(MAX_CACHED_SCOPES + 1):
            replace_emerging_topic_cache(
                conn,
                [],
                {},
                computed_at=f"2026-07-26T00:00:{index:02d}+00:00",
                scope_key=f"scope:{index}",
            )
        rows = conn.exec_driver_sql(
            "SELECT scope_key FROM my_publication_emerging_topic_cache ORDER BY computed_at"
        ).scalars()
        assert list(rows) == [f"scope:{index}" for index in range(1, MAX_CACHED_SCOPES + 1)]
        conn.execute(
            my_publication_emerging_topic_cache.insert().values(
                scope_key="all",
                scope={"kind": "all"},
                topics=[{"topic_id": "not-a-topic"}, "not-an-object"],
                coverage={"checked": "not-an-integer"},
                computed_at="2026-07-26T00:01:00+00:00",
            )
        )
        assert read_emerging_topic_cache(conn) is not None
    engine.dispose()
    response = TestClient(create_app(db_url=temp_db_url)).get("/my-publications/emerging-citing-topics")
    assert response.status_code == 200
    assert response.json()["topics"] == [] and response.json()["coverage"] is None

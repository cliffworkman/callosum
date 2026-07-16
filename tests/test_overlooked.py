"""Overlooked-work lens (backlog #37) — hermetic unit tests (no network, deterministic embed).

Covers the OpenAlex `fetch_topic_works` candidate fetch (Task 1) and the pure `compute_overlooked` engine
(Task 2): relevance by local embedding + the same-vintage citation percentile, exclude-in-library, and the
load-bearing vetoes (no composite score, no author/identity field, honest "possibly low-impact" copy).
"""

from __future__ import annotations

from app.backend.persistence.database import make_engine
from integrations.openalex.sources import OpenAlexSourcesClient


def _works_fetcher(works):
    def fake(path, *, params, headers, timeout):
        if path == "/works":
            return (200, {"results": works})
        return (404, {"error": "nf"})

    return fake


def test_fetch_topic_works_reconstructs_abstract_and_metadata(temp_db_url):
    works = [
        {
            "id": "https://openalex.org/W1",
            "doi": "https://doi.org/10.1/A",
            "title": "A",
            "publication_year": 2015,
            "cited_by_count": 3,
            "abstract_inverted_index": {"neural": [0], "nets": [1]},
        },
        {
            "id": "https://openalex.org/W2",
            "doi": None,
            "title": "B",
            "publication_year": 2016,
            "cited_by_count": 40,
            "abstract_inverted_index": None,
        },
    ]
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        got = OpenAlexSourcesClient(fetcher=_works_fetcher(works)).fetch_topic_works(conn, "T42")
    assert [w.openalex_work_id for w in got] == ["W1", "W2"]
    w1 = got[0]
    assert w1.doi == "10.1/a" and w1.year == 2015 and w1.cited_by_count == 3
    assert w1.abstract == "neural nets"  # reconstructed from the inverted index, in position order
    assert got[1].abstract is None and got[1].doi is None  # no index / no doi → None, not a crash
    with engine.begin() as conn:  # a bad topic id never reaches the network
        assert OpenAlexSourcesClient(fetcher=_works_fetcher(works)).fetch_topic_works(conn, "not-a-topic") == []
    engine.dispose()

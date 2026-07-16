"""Overlooked-work lens (backlog #37) — hermetic unit tests (no network, deterministic embed).

Covers the OpenAlex `fetch_topic_works` candidate fetch (Task 1) and the pure `compute_overlooked` engine
(Task 2): relevance by local embedding + the same-vintage citation percentile, exclude-in-library, and the
load-bearing vetoes (no composite score, no author/identity field, honest "possibly low-impact" copy).
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.clustering.axis_scoring import create_axis
from app.backend.embeddings.models import DEFAULT_NORMALIZATION
from app.backend.embeddings.vector_store import InMemoryVectorStore
from app.backend.methods.overlooked import OverlookedCandidate, compute_overlooked
from app.backend.persistence.database import make_engine
from app.backend.persistence.overlooked_repo import read_overlooked_candidates, replace_overlooked_candidates
from app.backend.persistence.repository import create_paper
from integrations.openalex.sources import OpenAlexSourcesClient, TopicWork


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


def test_fetch_topic_works_transmits_only_the_topic_id(temp_db_url):
    """The outbound request carries ONLY the topic id + fixed paging/select params — no library text egresses
    (the load-bearing egress invariant; candidate abstracts come BACK and are embedded on-device)."""
    sent = []

    def rec(path, *, params, headers, timeout):
        sent.append((path, params))
        return (200, {"results": []})

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        OpenAlexSourcesClient(fetcher=rec).fetch_topic_works(conn, "T7")
    assert len(sent) == 1
    path, params = sent[0]
    assert path == "/works"
    assert params["filter"] == "primary_topic.id:T7"
    assert set(params) <= {"filter", "per-page", "select", "mailto"}  # nothing but the topic id + fixed fields
    engine.dispose()


# --- Task 2: the compute_overlooked engine -----------------------------------

_VOCAB = ["neural", "vision", "plant"]


class _KeywordEmbed:
    """Deterministic bag-of-VOCAB embedding (the publishers/inc-228 test pattern) — a text's vector is which VOCAB
    words it contains, so cosine similarity to an axis label is controllable without a real model."""

    name = "kw-overlooked"
    version = "v1"
    dimension = len(_VOCAB)
    normalization = DEFAULT_NORMALIZATION

    def encode_texts(self, texts):
        return [[1.0 if w in str(t).lower() else 0.0 for w in _VOCAB] for t in texts]


class _FakeSources:
    """A sources client stand-in: a fixed topic + a fixed candidate-works list (no network)."""

    def __init__(self, topic, works):
        self._topic = topic
        self._works = works

    def fetch_topic_for_subject(self, conn, subject):
        return self._topic

    def fetch_topic_works(self, conn, topic_id, *, cap=200):
        return list(self._works)


def _sample_works():
    # All 2015. Relevance to axis "neural": W1/W2 = 1.0, W3 ≈ 0.707, W4/W5 = 0.
    # cited_by = [0, 50, 1, 60, 70] → same-year percentile rank (fraction cited fewer):
    #   W1 0.0 · W2 0.4 · W3 0.2 · W4 0.6 · W5 0.8
    return [
        TopicWork("W1", "10.1/w1", "Neural nets", 2015, 0, "neural"),
        TopicWork("W2", "10.1/w2", "Neural theory", 2015, 50, "neural"),  # relevant but well-cited → NOT overlooked
        TopicWork("W3", "10.1/w3", "Neural vision", 2015, 1, "neural vision"),
        TopicWork("W4", "10.1/w4", "Plant A", 2015, 60, "plant"),
        TopicWork("W5", "10.1/w5", "Plant B", 2015, 70, "plant"),
    ]


def test_compute_overlooked_surfaces_relevant_undercited(temp_db_url):
    engine = make_engine(temp_db_url)
    store = InMemoryVectorStore()
    with engine.begin() as conn:
        axis_id = create_axis(conn, label="neural")
        out = compute_overlooked(
            conn,
            axis_id=axis_id,
            sources_client=_FakeSources("T1", _sample_works()),
            model=_KeywordEmbed(),
            vector_store=store,
            low_percentile=0.25,
            min_year_peers=4,
        )
    # Surfaced = relevant AND under-cited for its vintage, ranked by relevance (desc).
    assert [c.openalex_work_id for c in out] == ["W1", "W3"]
    assert out[0].relevance > out[1].relevance
    assert "W2" not in [c.openalex_work_id for c in out]  # relevant but well-cited → correctly not flagged
    # Both separable inputs are present on every row...
    assert all(c.relevance is not None and c.year_percentile is not None for c in out)
    # ...and NEITHER a composite score NOR an author/identity field ever appears (the load-bearing vetoes).
    blob = json.dumps([c.to_dict() for c in out]).lower()
    assert "score" not in blob
    for c in out:
        assert not any(("author" in k) or ("score" in k) for k in c.to_dict())
    engine.dispose()


def test_compute_overlooked_no_percentile_when_too_few_same_year_peers(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        axis_id = create_axis(conn, label="neural")
        out = compute_overlooked(
            conn,
            axis_id=axis_id,
            sources_client=_FakeSources("T1", _sample_works()),
            model=_KeywordEmbed(),
            vector_store=InMemoryVectorStore(),
            low_percentile=0.25,
            min_year_peers=6,  # more than the 5 same-year peers available → no percentile → nothing surfaced
        )
    assert out == []  # honest: too few same-vintage peers to rank → we do not guess


def test_compute_overlooked_excludes_in_library(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        create_paper(conn, title="Neural nets", csl_json={"title": "Neural nets", "DOI": "10.1/w1"}, doi="10.1/w1")
        axis_id = create_axis(conn, label="neural")
        out = compute_overlooked(
            conn,
            axis_id=axis_id,
            sources_client=_FakeSources("T1", _sample_works()),
            model=_KeywordEmbed(),
            vector_store=InMemoryVectorStore(),
            low_percentile=0.25,
            min_year_peers=4,
        )
    ids = [c.openalex_work_id for c in out]
    assert "W1" not in ids  # already in the library → dropped (this is discovery)
    assert "W3" in ids  # the pipeline still surfaces the remaining relevant, under-cited candidate
    engine.dispose()


# --- Task 3: the overlooked_candidates cache ---------------------------------


def test_overlooked_repo_round_trips_both_visible_inputs(temp_db_url):
    engine = make_engine(temp_db_url)
    cands = [
        OverlookedCandidate("W1", "10.1/w1", "Neural nets", 2015, 3, relevance=0.91, year_percentile=0.1),
        OverlookedCandidate("W2", None, "Neural theory", 2016, 0, relevance=0.72, year_percentile=None),
    ]
    with engine.begin() as conn:
        assert read_overlooked_candidates(conn, 7) == ([], None)  # uncomputed scope
        replace_overlooked_candidates(conn, 7, cands, computed_at="2026-07-16T00:00:00Z")
    with engine.begin() as conn:
        rows, computed_at = read_overlooked_candidates(conn, 7)
    assert computed_at == "2026-07-16T00:00:00Z"
    by_id = {r["openalex_work_id"]: r for r in rows}
    assert by_id["W1"]["relevance"] == 0.91 and by_id["W1"]["year_percentile"] == 0.1  # both inputs persisted
    assert by_id["W1"]["cited_by_count"] == 3 and by_id["W1"]["doi"] == "10.1/w1"
    assert by_id["W2"]["year_percentile"] is None  # honest null survives the round-trip
    assert "author" not in " ".join(k for r in rows for k in r).lower()  # identity-agnostic: no author column
    # A refresh is authoritative — replacing the scope with fewer rows drops the stale one.
    with engine.begin() as conn:
        replace_overlooked_candidates(conn, 7, cands[:1], computed_at="2026-07-16T01:00:00Z")
        rows2, _ = read_overlooked_candidates(conn, 7)
    assert [r["openalex_work_id"] for r in rows2] == ["W1"]
    engine.dispose()


# --- Task 4: the async job + endpoints ---------------------------------------


def _lens_app(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    with make_engine(temp_db_url).begin() as conn:
        axis_id = create_axis(conn, label="neural")
    client.app.state.openalex_sources_client = _FakeSources("T1", _sample_works())
    client.app.state.embedding_model = _KeywordEmbed()
    return client, axis_id


def _drive_refresh(client, axis_id):
    r = client.post("/overlooked/refresh", json={"axis_id": axis_id})
    assert r.status_code == 202, r.text
    jid = r.json()["job_id"]
    data = {}
    for _ in range(60):
        data = client.get(f"/overlooked/refresh/{jid}").json()
        if data["status"] in ("done", "error"):
            break
    return data


def test_overlooked_endpoints_refresh_then_list(temp_db_url):
    client, axis_id = _lens_app(temp_db_url)
    done = _drive_refresh(client, axis_id)
    assert done["status"] == "done", done
    assert done["result"]["count"] == 2  # W1 + W3 surfaced

    listed = client.get("/overlooked", params={"axis_id": axis_id})
    assert listed.status_code == 200
    body = listed.json()
    ids = [c["openalex_work_id"] for c in body["candidates"]]
    assert ids == ["W1", "W3"]  # ranked by relevance
    assert body["computed_at"] is not None
    # Every row carries BOTH separable inputs, and NEITHER a composite score NOR an author/identity field.
    for c in body["candidates"]:
        assert "relevance" in c and "year_percentile" in c
        assert not any(("author" in k) or ("score" in k) for k in c)
    assert "score" not in json.dumps(body).lower()


def test_overlooked_list_filters_dismissed(temp_db_url):
    client, axis_id = _lens_app(temp_db_url)
    _drive_refresh(client, axis_id)
    # Dismiss via the reused gap-dismiss flow → GET /overlooked no longer surfaces it (no recompute needed).
    assert client.post("/gaps/dismiss", json={"openalex_work_id": "W1"}).status_code == 204
    ids = [c["openalex_work_id"] for c in client.get("/overlooked", params={"axis_id": axis_id}).json()["candidates"]]
    assert "W1" not in ids and "W3" in ids


def test_overlooked_refresh_requires_axis_id(temp_db_url):
    client, _ = _lens_app(temp_db_url)
    assert client.post("/overlooked/refresh", json={}).status_code == 422  # axis_id required
    assert client.get("/overlooked").status_code == 422  # axis_id required
    assert client.get("/overlooked/refresh/nope").status_code == 404  # unknown job

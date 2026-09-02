"""inc 228 (backlog #25 SP2) — the topical overlooked-work remediation: the OpenAlex candidate machinery
(related_works/concepts + batch fetch + topic candidates w/ abstract), the local-embedding ranker (add-only,
identity-agnostic), and the async endpoint. Surface relevant work the list omits — never a verdict, never identity,
no drop, no quota."""

from __future__ import annotations

from app.backend.methods.overlooked_work import rank_overlooked
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from integrations.openalex.adapter import OpenAlexClient, _meta_from_work, _meta_with_abstract

# --- canned OpenAlex blobs ---------------------------------------------------

VOCAB = ["risk", "decision", "uncertainty", "plant", "memory"]


class FakeEmbed:
    """A deterministic keyword embedding model (the inc-185 test pattern) — CI never downloads SPECTER."""

    name = "fake"
    version = "fake"

    def encode_texts(self, texts):
        return [[1.0 if w in str(t).lower() else 0.0 for w in VOCAB] for t in texts]


def _cand(wid, *, title, words, concepts, doi=None, in_library=False):
    return {
        "openalex_work_id": wid,
        "doi": doi,
        "title": title,
        "abstract": " ".join(words),
        "concepts": concepts,
        "authors": ["A B"],
        "year": 2020,
        "venue": "Nature",
        "in_library": in_library,
    }


def _cand_blob(wid, *, title, words, concepts, doi=None):
    return {
        "id": f"https://openalex.org/{wid}",
        "doi": (f"https://doi.org/{doi}" if doi else None),
        "title": title,
        "abstract_inverted_index": {w: [i] for i, w in enumerate(words)},
        "concepts": [{"display_name": c} for c in concepts],
        "authorships": [{"author": {"display_name": "A B"}}],
        "cited_by_count": 10,
        "primary_location": {"source": {"display_name": "Nature"}},
        "publication_year": 2020,
    }


def _focal_blob(doi, *, ref_ids, related, topic="T100"):
    return {
        "id": "https://openalex.org/W0",
        "doi": f"https://doi.org/{doi}",
        "title": "Risk and decision under uncertainty",
        "abstract_inverted_index": {"risk": [0], "decision": [1], "uncertainty": [2]},
        "referenced_works": [f"https://openalex.org/{w}" for w in ref_ids],
        "related_works": [f"https://openalex.org/{w}" for w in related],
        "primary_topic": {"id": f"https://openalex.org/{topic}", "display_name": "Decision science"},
        "concepts": [{"display_name": "Risk"}, {"display_name": "Decision"}],
        "authorships": [{"author": {"display_name": "Pat Doe"}}],
        "cited_by_count": 5,
    }


def _fetcher(focal_by_doi, by_id, topic_results):
    def fake(path, *, params, headers, timeout):
        if path.startswith("/doi:"):
            doi = path[len("/doi:") :]
            return (200, focal_by_doi[doi]) if doi in focal_by_doi else (404, {"error": "nf"})
        filt = params.get("filter") or ""
        if filt.startswith("openalex_id:"):
            ids = filt[len("openalex_id:") :].split("|")
            return (200, {"results": [by_id[i] for i in ids if i in by_id]})
        if filt.startswith("primary_topic.id:"):
            return (200, {"results": topic_results})
        return (404, {"error": "nf"})

    return fake


# --- adapter: candidate fields + batch fetch ---------------------------------


def test_meta_surfaces_related_and_concepts_and_abstract():
    blob = _cand_blob("W1", title="T", words=["risk", "decision"], concepts=["Risk", "Decision"])
    blob["related_works"] = ["https://openalex.org/W7", "https://openalex.org/Wbad", "https://openalex.org/W8"]
    meta = _meta_from_work(blob)
    assert meta["related_works"] == ["W7", "W8"]  # Wbad dropped (not ^W\d+$)
    assert meta["concepts"] == ["Risk", "Decision"]
    assert "abstract" not in meta  # abstract is candidate-only, not in the base meta
    rich = _meta_with_abstract(blob)
    assert rich["abstract"] == "risk decision"


def test_meta_treats_malformed_collection_fields_as_absent_and_bounds_abstract():
    work = {
        "id": "https://openalex.org/W1",
        "authorships": {"not": "a list"},
        "related_works": 42,
        "concepts": "not a list",
        "grants": {"not": "a list"},
        "referenced_works": 42,
        "abstract_inverted_index": {"word": list(range(10_000))},
    }
    meta = _meta_with_abstract(work)
    assert meta is not None
    assert meta["authors"] == [] and meta["related_works"] == [] and meta["referenced_works"] == []
    assert len(meta["abstract"]) <= 20_000 and len(meta["abstract"].split()) <= 5_000


def test_fetch_works_by_ids_batches_validates_failcloses(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        by_id = {"W1": _cand_blob("W1", title="A", words=["risk"], concepts=["Risk"])}
        client = OpenAlexClient(fetcher=_fetcher({}, by_id, []))
        out = client.fetch_works_by_ids(conn, ["W1", "bad", "W2"])  # "bad" dropped; W2 absent → just W1
        assert [c["openalex_work_id"] for c in out] == ["W1"] and out[0]["abstract"] == "risk"
        assert client.fetch_works_by_ids(conn, ["nope"]) == []  # no valid ids → no request
        bad = OpenAlexClient(fetcher=lambda p, **k: (500, None))
        assert bad.fetch_works_by_ids(conn, ["W5"]) == []  # non-200 → fail-closed
    engine.dispose()


# --- the ranker --------------------------------------------------------------


def test_rank_orders_thresholds_and_shared_concepts():
    focal = "Risk and decision under uncertainty. risk decision uncertainty"
    cands = [
        _cand("W1", title="Risk decision models", words=["risk", "decision"], concepts=["Risk", "Decision"]),
        _cand("W2", title="Plant biology", words=["plant"], concepts=["Plant"]),  # off-topic
        _cand(
            "W3",
            title="Decision under risk",
            words=["decision", "risk", "uncertainty"],
            concepts=["Decision"],
            in_library=True,
        ),
    ]
    r = rank_overlooked(
        focal_text=focal, candidates=cands, focal_concepts=["Risk", "Decision"], embedding_model=FakeEmbed()
    )
    ids = [c.openalex_work_id for c in r]
    assert ids[0] == "W3"  # cosine 1.0 ranks first
    assert "W2" not in ids  # off-topic, below the 0.55 threshold → not shown
    by = {c.openalex_work_id: c for c in r}
    assert by["W1"].shared_concepts == ["Risk", "Decision"] and by["W3"].in_library is True


def test_rank_empty_inputs():
    assert (
        rank_overlooked(
            focal_text="",
            candidates=[_cand("W1", title="x", words=["risk"], concepts=[])],
            focal_concepts=[],
            embedding_model=FakeEmbed(),
        )
        == []
    )
    assert rank_overlooked(focal_text="risk", candidates=[], focal_concepts=[], embedding_model=FakeEmbed()) == []


def test_no_identity_in_ranker():
    """Injecting author gender/race fields into a candidate changes nothing — the ranker never reads them."""
    base = _cand("W1", title="Risk decision", words=["risk", "decision"], concepts=["Risk"])
    poisoned = {**base, "gender": "f", "author_race": "x", "sex": "m"}
    a = rank_overlooked(
        focal_text="risk decision", candidates=[base], focal_concepts=["Risk"], embedding_model=FakeEmbed()
    )
    b = rank_overlooked(
        focal_text="risk decision", candidates=[poisoned], focal_concepts=["Risk"], embedding_model=FakeEmbed()
    )
    assert [c.to_dict() for c in a] == [c.to_dict() for c in b]
    blob = str([c.to_dict() for c in a]).lower()
    assert "gender" not in blob and "race" not in blob


# --- the async endpoint ------------------------------------------------------

from fastapi.testclient import TestClient  # noqa: E402

from app.backend.api import create_app  # noqa: E402


def _seed(conn, title, doi):
    return create_paper(conn, title=title, csl_json={"title": title, "DOI": doi}, doi=doi)


def _drive(client, paper_id):
    r = client.post("/methods/citation-equity/overlooked", json={"paper_id": paper_id})
    if r.status_code != 202:
        return r
    jid = r.json()["job_id"]
    data = {}
    for _ in range(40):
        data = client.get(f"/methods/citation-equity/overlooked/{jid}").json()
        if data["status"] in ("done", "error"):
            break
    return data


def test_overlooked_endpoint_produces_candidates(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _seed(conn, "Focal", "10.1/f")
        _seed(conn, "Already have", "10.1/inlib")  # a candidate already in the library (matched by DOI)
    engine.dispose()
    focal = _focal_blob("10.1/f", ref_ids=["W9"], related=["W1", "W2", "W3"])
    by_id = {
        "W1": _cand_blob(
            "W1", title="Risk decision models", words=["risk", "decision"], concepts=["Risk", "Decision"], doi="10.1/c1"
        ),
        "W2": _cand_blob("W2", title="Plant biology", words=["plant"], concepts=["Plant"]),  # off-topic
        "W3": _cand_blob(
            "W3",
            title="Decision under risk",
            words=["decision", "risk", "uncertainty"],
            concepts=["Decision"],
            doi="10.1/inlib",
        ),
    }
    topic = [
        _cand_blob("W5", title="Uncertainty in decisions", words=["uncertainty", "decision"], concepts=["Decision"])
    ]
    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.openalex_client = OpenAlexClient(fetcher=_fetcher({"10.1/f": focal}, by_id, topic))
    client.app.state.embedding_model = FakeEmbed()

    done = _drive(client, pid)
    assert done["status"] == "done"
    rep = done["report"]
    by = {c["openalex_work_id"]: c for c in rep["candidates"]}
    assert "W1" in by and "W3" in by and "W5" in by
    assert "W2" not in by  # off-topic → excluded below the relevance bar
    assert by["W3"]["in_library"] is True and by["W1"]["in_library"] is False  # W3 == seeded 10.1/inlib
    assert "Decision" in by["W1"]["shared_concepts"]
    assert rep["shown"] == 3 and rep["considered"] >= 3


def test_overlooked_excludes_already_cited(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _seed(conn, "Focal", "10.1/f")
    engine.dispose()
    # W1 is BOTH related AND already cited (in referenced_works) → must be excluded
    focal = _focal_blob("10.1/f", ref_ids=["W1"], related=["W1", "W2"])
    by_id = {
        "W1": _cand_blob("W1", title="Risk decision", words=["risk", "decision"], concepts=["Risk"]),
        "W2": _cand_blob(
            "W2", title="Decision risk uncertainty", words=["decision", "risk", "uncertainty"], concepts=["Decision"]
        ),
    }
    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.openalex_client = OpenAlexClient(fetcher=_fetcher({"10.1/f": focal}, by_id, []))
    client.app.state.embedding_model = FakeEmbed()
    done = _drive(client, pid)
    ids = {c["openalex_work_id"] for c in done["report"]["candidates"]}
    assert "W1" not in ids and "W2" in ids  # the already-cited W1 is dropped


def test_overlooked_404_and_422(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        no_doi = _seed(conn, "No DOI", None)
    engine.dispose()
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.post("/methods/citation-equity/overlooked", json={"paper_id": 99999}).status_code == 404
    assert client.post("/methods/citation-equity/overlooked", json={"paper_id": no_doi}).status_code == 422


def test_overlooked_empty_state(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _seed(conn, "Focal", "10.1/f")
    engine.dispose()
    focal = _focal_blob("10.1/f", ref_ids=[], related=[])  # no related, no topic candidates
    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.openalex_client = OpenAlexClient(fetcher=_fetcher({"10.1/f": focal}, {}, []))
    client.app.state.embedding_model = FakeEmbed()
    done = _drive(client, pid)
    assert done["status"] == "done" and done["report"]["shown"] == 0


def test_overlooked_status_404_unknown_job(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/methods/citation-equity/overlooked/nope").status_code == 404

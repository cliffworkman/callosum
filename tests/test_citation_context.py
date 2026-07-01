"""inc 232 (B4 SP1) — "how this paper is cited": the Semantic Scholar client (parse / paginate / cap / fail-closed /
DOI-validate), the pure stance classifier (counts + evidence, unclassified never guessed, no composite score), and
the async endpoint. Hermetic: an injected fake S2 fetcher + a fake local NLI stance scorer — no network, no model."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.methods.citation_context import classify_citation_contexts
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from app.backend.summarization.verification import Stance
from integrations.semantic_scholar.adapter import CitingContext, SemanticScholarClient


def _citing(title, sentence, *, doi=None, influential=False, year=2022):
    return {
        "isInfluential": influential,
        "contexts": [sentence] if sentence else [],
        "citingPaper": {
            "title": title,
            "year": year,
            "authors": [{"name": "A Author"}],
            "externalIds": {"DOI": doi} if doi else {},
        },
    }


class _FakeStance:
    """A deterministic stand-in for the local NLI: the citing sentence (passage) decides the stance."""

    def classify_stance(self, *, sentence: str, passage: str):
        p = passage.lower()
        if "confirms" in p or "consistent" in p:
            return Stance(label="support", confidence=0.91, probs={"support": 0.91, "contrast": 0.05, "mention": 0.04})
        if "however" in p or "fails" in p or "contradicts" in p:
            return Stance(label="contrast", confidence=0.84, probs={"support": 0.1, "contrast": 0.84, "mention": 0.06})
        if not p.strip():
            return None
        return Stance(label="mention", confidence=0.6, probs={"support": 0.2, "contrast": 0.2, "mention": 0.6})


# --- the Semantic Scholar client --------------------------------------------


def test_client_parses_paginates_and_caps(temp_db_url):
    pages = {
        0: {"data": [_citing("Cite A", "This confirms the finding.", doi="10.1/a", influential=True)], "next": 1},
        1: {"data": [_citing("Cite B", "However, we could not replicate it.", doi="10.1/b")], "next": None},
    }

    def fetcher(path, *, params, headers, timeout):
        assert path == "/paper/DOI:10.1%2Ffocal/citations"  # DOI path-encoded, no injection
        return 200, pages[int(params["offset"])]

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        client = SemanticScholarClient(fetcher=fetcher)
        out = client.fetch_citation_contexts(conn, "10.1/focal")
        assert [c.citing_title for c in out] == ["Cite A", "Cite B"]
        assert out[0].is_influential and out[0].sentences == ["This confirms the finding."]
        assert out[1].citing_doi == "10.1/b"
        # a second call is served from cache (fetcher would KeyError on a 3rd offset if it ran again)
        assert len(client.fetch_citation_contexts(conn, "10.1/focal")) == 2
    engine.dispose()


def test_client_validates_doi_and_fails_closed(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        # a non-DOI id → no request is made at all
        client = SemanticScholarClient(
            fetcher=lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not fetch"))
        )
        assert client.fetch_citation_contexts(conn, "not-a-doi") == []

        # a transient failure → [] and NOT cached (a retry can still succeed)
        state = {"fail": True}

        def flaky(path, *, params, headers, timeout):
            if state["fail"]:
                raise RuntimeError("network down")
            return 200, {"data": [_citing("Later", "confirms it")], "next": None}

        bad = SemanticScholarClient(fetcher=flaky)
        assert bad.fetch_citation_contexts(conn, "10.1/x") == []
        state["fail"] = False
        assert len(bad.fetch_citation_contexts(conn, "10.1/x")) == 1  # not poisoned by the earlier failure
    engine.dispose()


# --- the pure classifier ----------------------------------------------------


def test_classifier_counts_keeps_evidence_and_never_guesses():
    contexts = [
        CitingContext("A", 2022, ["X"], "10.1/a", ["This confirms the result."], True),
        CitingContext("B", 2021, ["Y"], "10.1/b", ["However, it fails to replicate."], False),
        CitingContext("C", 2020, ["Z"], "10.1/c", ["We use their method."], False),
        CitingContext("D", 2019, [], None, [], False),  # no citing sentence → counted, never classified
    ]
    rep = classify_citation_contexts(contexts=contexts, focal_claim="Focal paper claim", stance_scorer=_FakeStance())
    assert rep.total_citations == 4 and rep.with_context == 3 and rep.classified == 3
    assert rep.counts == {"support": 1, "contrast": 1, "mention": 1}
    assert "score" not in rep.to_dict()  # counts only — no composite score
    by_title = {i.citing_title: i for i in rep.items}
    assert by_title["A"].stance == "support" and by_title["A"].sentence == "This confirms the result."  # evidence kept
    assert by_title["D"].stance is None and by_title["D"].sentence == ""  # unclassifiable, not guessed


def test_classifier_no_scorer_or_no_claim_leaves_unclassified():
    contexts = [CitingContext("A", 2022, ["X"], None, ["This confirms it."], False)]
    # no focal claim → nothing to classify against
    rep = classify_citation_contexts(contexts=contexts, focal_claim="", stance_scorer=_FakeStance())
    assert rep.with_context == 1 and rep.classified == 0 and rep.items[0].stance is None


# --- the async endpoint -----------------------------------------------------


def _seed(conn, title, doi):
    return create_paper(conn, title=title, csl_json={"title": title, "DOI": doi} if doi else {"title": title}, doi=doi)


def _app(temp_db_url, *, fetcher):
    return create_app(
        db_url=temp_db_url,
        semantic_scholar_client=SemanticScholarClient(fetcher=fetcher),
        stance_scorer=_FakeStance(),
    )


def _drive(client, paper_id):
    r = client.post("/papers/citation-context/run", json={"paper_id": paper_id})
    if r.status_code != 202:
        return r
    jid = r.json()["job_id"]
    data = {}
    for _ in range(40):
        data = client.get(f"/papers/citation-context/run/{jid}").json()
        if data["status"] in ("done", "error"):
            break
    return data


def test_endpoint_runs_and_classifies(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _seed(conn, "Focal", "10.1/focal")
    engine.dispose()

    def fetcher(path, *, params, headers, timeout):
        return 200, {
            "data": [
                _citing("Cite A", "This confirms the finding.", doi="10.1/a", influential=True),
                _citing("Cite B", "However, we could not replicate it.", doi="10.1/b"),
                _citing("Cite C", "See prior work.", doi="10.1/c"),
            ],
            "next": None,
        }

    client = TestClient(_app(temp_db_url, fetcher=fetcher))
    done = _drive(client, pid)
    assert done["status"] == "done"
    rep = done["report"]
    assert rep["total_citations"] == 3 and rep["classified"] == 3
    assert rep["counts"]["support"] == 1 and rep["counts"]["contrast"] == 1 and rep["counts"]["mention"] == 1
    assert any(i["sentence"] and i["stance"] for i in rep["items"])  # evidence + stance carried through


def test_endpoint_404_422_and_empty(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        no_doi = _seed(conn, "No DOI", None)
        has_doi = _seed(conn, "Has DOI", "10.1/none")
    engine.dispose()
    client = TestClient(_app(temp_db_url, fetcher=lambda *a, **k: (200, {"data": [], "next": None})))
    assert client.post("/papers/citation-context/run", json={"paper_id": 999999}).status_code == 404
    assert client.post("/papers/citation-context/run", json={"paper_id": no_doi}).status_code == 422
    assert client.get("/papers/citation-context/run/nope").status_code == 404
    done = _drive(client, has_doi)  # no citations → honest empty
    assert done["status"] == "done" and done["report"]["total_citations"] == 0

from __future__ import annotations

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.api.routers import reference_integrity as ref_router
from app.backend.methods.retraction import RetractionChecker, RetractionSignal
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from integrations.crossref.adapter import CrossrefClient
from integrations.semantic_scholar.adapter import SemanticScholarClient
from tests.test_citation_context import _FakeStance


def _paper(conn, title: str, doi: str | None) -> int:
    return create_paper(conn, title=title, doi=doi, csl_json={"title": title, "DOI": doi} if doi else {"title": title})


def _ref(title: str, *, doi: str | None = None, sentence: str = "We build on this.", year: int = 2020):
    return {
        "isInfluential": False,
        "contexts": [sentence] if sentence else [],
        "citedPaper": {
            "title": title,
            "year": year,
            "authors": [{"name": "R Author"}],
            "externalIds": {"DOI": doi} if doi else {},
            "abstract": title + " claim",
        },
    }


class _CrossrefMiss:
    def __call__(self, doi, *, headers, timeout):
        return 404, {"status": "error"}


class _OpenAlex:
    def __init__(self, records=None, referenced=None, work_meta=None):
        self.records = records or {}
        self.referenced = referenced or {}
        self.work_meta = work_meta or {}

    def fetch_work_csl(self, conn, ref):
        key = (ref.doi or ref.title or "").lower()
        return self.records.get(key)

    def fetch_referenced_works(self, conn, ref):
        return self.referenced.get((ref.doi or "").lower(), [])

    def fetch_work_meta(self, conn, work_id):
        return self.work_meta.get(work_id)


def _client(temp_db_url, refs_by_doi, *, openalex=None, retraction_flag_dois=None):
    def fetcher(path, *, params, headers, timeout):
        for doi, refs in refs_by_doi.items():
            if f"DOI:{doi.replace('/', '%2F')}/references" in path:
                return 200, {"data": refs, "next": None}
        return 200, {"data": [], "next": None}

    flags = {d.lower() for d in (retraction_flag_dois or [])}

    def retraction(conn, paper):
        return (
            RetractionSignal(source="crossref", status="retracted", notice_doi="10.1/notice", reason="registry")
            if str(paper.get("doi") or "").lower() in flags
            else None
        )

    app = create_app(
        db_url=temp_db_url,
        semantic_scholar_client=SemanticScholarClient(fetcher=fetcher),
        stance_scorer=_FakeStance(),
        crossref_client=CrossrefClient(fetcher=_CrossrefMiss()),
        openalex_client=openalex or _OpenAlex(),
    )
    app.state.retraction_checkers = [RetractionChecker("crossref", retraction)]
    return TestClient(app)


def _drive(client: TestClient, paper_id: int):
    r = client.post(f"/papers/{paper_id}/reference-integrity/run")
    if r.status_code != 202:
        return r
    jid = r.json()["job_id"]
    data = {}
    for _ in range(40):
        data = client.get(f"/reference-integrity/run/{jid}").json()
        if data["status"] in ("done", "error"):
            break
    assert data["status"] == "done", data
    return data["report"]


def test_existence_miss_is_could_not_verify_not_nonexistence_verdict(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, "Focal", "10.1/focal")
    engine.dispose()
    client = _client(temp_db_url, {"10.1/focal": [_ref("Hard to resolve transliterated title")]})

    report = _drive(client, pid)

    assert report["active_count"] == 1
    signal = report["items"][0]["signals"][0]
    assert signal["detector_status"] == "could_not_verify"
    text = str(signal["evidence"]).lower()
    assert "could not verify" in text
    for forbidden in ("does not exist", "fake", "fabricated", "invalid", "bad citation", "verified good"):
        assert forbidden not in text
    assert signal["evidence"]["sources_queried"] == ["openalex:title"]
    assert report["last_checked_at"]
    assert any(s["provider"] == "Semantic Scholar" and s["status"] == "success" for s in report["provider_statuses"])
    assert any(s["provider"] == "Reference detectors" and s["status"] == "success" for s in report["provider_statuses"])


def test_run_status_reports_progress_and_done_progress_payload(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, "Focal", "10.1/focal")
    engine.dispose()
    client = _client(temp_db_url, {"10.1/focal": [_ref("Unknown")]})

    started = client.post(f"/papers/{pid}/reference-integrity/run")
    assert started.status_code == 202
    data = client.get(f"/reference-integrity/run/{started.json()['job_id']}").json()

    assert data["status"] == "done"
    assert data["progress"]["label"] == "Reference check complete"
    assert data["progress"]["current"] == data["progress"]["total"]
    assert data["report"]["checked_count"] == 1


def test_provider_failure_is_reported_without_erasing_fallback_results(temp_db_url):
    class _BoomSemanticScholar:
        def fetch_reference_contexts(self, conn, doi):
            raise RuntimeError("rate limited")

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, "Focal", "10.1/focal")
    engine.dispose()
    openalex = _OpenAlex(
        referenced={"10.1/focal": ["W123"]},
        work_meta={"W123": {"title": "Fallback Reference", "authors": ["R Author"], "year": 2020}},
    )
    app = create_app(
        db_url=temp_db_url,
        semantic_scholar_client=_BoomSemanticScholar(),
        stance_scorer=_FakeStance(),
        crossref_client=CrossrefClient(fetcher=_CrossrefMiss()),
        openalex_client=openalex,
    )
    app.state.retraction_checkers = [RetractionChecker("crossref", lambda conn, paper: None)]

    report = _drive(TestClient(app), pid)

    statuses = {(s["provider"], s["status"]) for s in report["provider_statuses"]}
    assert ("Semantic Scholar", "failed") in statuses
    assert ("OpenAlex", "success") in statuses
    assert report["checked_count"] == 1


def test_bulk_reference_run_checks_selected_doi_papers_and_skips_no_doi(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = _paper(conn, "Paper A", "10.1/a")
        b = _paper(conn, "Paper B", "10.1/b")
        no_doi = _paper(conn, "No DOI", None)
    engine.dispose()
    client = _client(temp_db_url, {"10.1/a": [_ref("Unknown A")], "10.1/b": [_ref("Unknown B")]})

    started = client.post("/reference-integrity/run-selected", json={"paper_ids": [a, b, no_doi, 999999, a]})
    assert started.status_code == 202
    data = client.get(f"/reference-integrity/run/{started.json()['job_id']}").json()

    assert data["status"] == "done"
    assert data["progress"]["label"] == "Selected reference checks complete"
    summary = data["bulk_report"]
    assert summary["requested_count"] == 4  # duplicate paper id was de-duped
    assert summary["checked_count"] == 2
    assert summary["skipped_no_doi"] == [no_doi]
    assert summary["not_found"] == [999999]
    assert summary["failed_count"] == 0
    assert summary["active_paper_count"] == 2
    overview = {row["paper_id"]: row["active_count"] for row in client.get("/reference-integrity/overview").json()}
    assert overview[a] == 1 and overview[b] == 1


def test_bulk_reference_run_rejects_empty_selection(temp_db_url):
    client = _client(temp_db_url, {})

    response = client.post("/reference-integrity/run-selected", json={"paper_ids": []})

    assert response.status_code == 422


def test_retraction_signal_is_distinct_and_stronger_than_search_miss(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, "Focal", "10.1/focal")
    engine.dispose()
    refs = [_ref("Unknown", sentence="We cite this."), _ref("Retracted Work", doi="10.1/retracted")]
    client = _client(temp_db_url, {"10.1/focal": refs}, retraction_flag_dois={"10.1/retracted"})

    report = _drive(client, pid)
    statuses = {s["detector_status"] for item in report["items"] for s in item["signals"]}

    assert "could_not_verify" in statuses
    assert "known_retraction_signal" in statuses
    retraction = next(s for item in report["items"] for s in item["signals"] if s["detector_kind"] == "retraction")
    assert retraction["evidence"]["label"] == "Known retraction signal"
    assert retraction["evidence"]["sources"] == ["crossref"]


def test_own_library_propagates_but_reviews_are_per_citation_instance(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        a = _paper(conn, "Paper A", "10.1/a")
        b = _paper(conn, "Paper B", "10.1/b")
    engine.dispose()
    refs = {"10.1/a": [_ref("Shared Unverified")], "10.1/b": [_ref("Shared Unverified")]}
    client = _client(temp_db_url, refs)

    a_report = _drive(client, a)
    a_instance = a_report["items"][0]["id"]
    b_report = _drive(client, b)

    assert any(s["detector_kind"] == "own_library_propagation" for s in b_report["items"][0]["signals"])
    client.post(f"/reference-integrity/instances/{a_instance}/review", json={"state": "dismissed"})
    b_after = client.get(f"/papers/{b}/reference-integrity").json()
    assert b_after["items"][0]["review_state"] == "unreviewed"
    assert b_after["active_count"] == 1


def test_review_states_drive_active_warning_without_positive_promotion(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, "Focal", "10.1/focal")
    engine.dispose()
    client = _client(temp_db_url, {"10.1/focal": [_ref("Unknown")]})

    report = _drive(client, pid)
    iid = report["items"][0]["id"]
    assert report["active_count"] == 1
    assert client.get("/reference-integrity/overview").json()[0]["active_count"] == 1

    dismissed = client.post(f"/reference-integrity/instances/{iid}/review", json={"state": "dismissed"}).json()
    assert dismissed["active_count"] == 0
    assert client.get("/reference-integrity/overview").json() == []
    assert "verified" not in str(dismissed).lower() and "clean" not in str(dismissed).lower()

    confirmed = client.post(f"/reference-integrity/instances/{iid}/review", json={"state": "confirmed_problem"}).json()
    assert confirmed["active_count"] == 1
    assert confirmed["items"][0]["review_state"] == "confirmed_problem"


def test_new_retraction_signal_invalidates_prior_dismissal_but_unchanged_signal_preserves_it(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, "Focal", "10.1/focal")
    engine.dispose()
    refs = {"10.1/focal": [_ref("Later Retracted", doi="10.1/later")]}
    clean = _client(temp_db_url, refs)
    report = _drive(clean, pid)
    iid = report["items"][0]["id"]
    dismissed = clean.post(f"/reference-integrity/instances/{iid}/review", json={"state": "dismissed"}).json()
    assert dismissed["active_count"] == 0

    # Same signal set after restart/run preserves the dismissal.
    clean_again = _client(temp_db_url, refs)
    same = _drive(clean_again, pid)
    assert same["items"][0]["review_state"] == "dismissed"
    assert same["active_count"] == 0

    # Fresh detector data adds a materially new retraction signal, producing a new unreviewed fingerprint.
    flagged = _client(temp_db_url, refs, retraction_flag_dois={"10.1/later"})
    changed = _drive(flagged, pid)
    assert changed["items"][0]["review_state"] == "unreviewed"
    assert changed["items"][0]["reopened"] is True
    assert any(s["detector_kind"] == "retraction" for s in changed["items"][0]["signals"])
    assert changed["active_count"] == 1


def test_context_hint_never_mutates_review_or_suppresses_detector_signals(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, "Focal", "10.1/focal")
    engine.dispose()
    client = _client(
        temp_db_url,
        {"10.1/focal": [_ref("Unknown", sentence="However, this fails in later studies.")]},
    )

    report = _drive(client, pid)
    item = report["items"][0]

    assert item["context"]["hint"].startswith("Context hint:")
    assert item["review_state"] == "unreviewed"
    assert item["signals"][0]["detector_status"] == "could_not_verify"
    assert report["active_count"] == 1


def test_openalex_referenced_works_fallback_when_semantic_scholar_has_no_references(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, "Focal", "10.1/focal")
    engine.dispose()
    openalex = _OpenAlex(
        referenced={"10.1/focal": ["W123"]},
        work_meta={
            "W123": {"title": "Retracted Via OpenAlex", "authors": ["R Author"], "year": 2020, "doi": "10.1/oa"}
        },
    )
    client = _client(temp_db_url, {"10.1/focal": []}, openalex=openalex, retraction_flag_dois={"10.1/oa"})

    report = _drive(client, pid)
    item = report["items"][0]

    assert item["source"] == "openalex:referenced_works"
    assert report["checked_count"] == 1
    assert item["context"]["openalex_work_id"] == "W123"
    assert {s["detector_kind"] for s in item["signals"]} == {"retraction"}
    assert item["signals"][0]["evidence"]["label"] == "Known retraction signal"


def test_openalex_fallback_uses_default_client_when_not_injected(temp_db_url, monkeypatch):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, "Focal", "10.1/focal")
    engine.dispose()
    fake_openalex = _OpenAlex(
        referenced={"10.1/focal": ["W123"]},
        work_meta={"W123": {"title": "Resolved Via Default OpenAlex", "authors": ["R Author"], "year": 2020}},
    )
    monkeypatch.setattr(ref_router, "OpenAlexClient", lambda: fake_openalex)

    client = create_app(
        db_url=temp_db_url,
        semantic_scholar_client=SemanticScholarClient(fetcher=lambda path, **kw: (200, {"data": [], "next": None})),
        stance_scorer=_FakeStance(),
        crossref_client=CrossrefClient(fetcher=_CrossrefMiss()),
    )
    client.state.retraction_checkers = [RetractionChecker("crossref", lambda conn, paper: None)]
    report = _drive(TestClient(client), pid)

    assert report["checked_count"] == 1
    assert report["active_count"] == 0
    assert report["items"] == []


def test_review_state_survives_restart_and_resolved_reference_clears_only_reference_warning(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = _paper(conn, "Focal", "10.1/focal")
    engine.dispose()
    refs = {"10.1/focal": [_ref("Unknown")]}
    client = _client(temp_db_url, refs)
    report = _drive(client, pid)
    iid = report["items"][0]["id"]
    client.post(f"/reference-integrity/instances/{iid}/review", json={"state": "dismissed"})

    restarted = _client(temp_db_url, refs)
    assert restarted.get(f"/papers/{pid}/reference-integrity").json()["items"][0]["review_state"] == "dismissed"

    openalex = _OpenAlex(
        {"unknown": {"title": "Unknown", "issued": {"date-parts": [[2020]]}, "author": [{"literal": "R Author"}]}}
    )
    resolved = _client(temp_db_url, refs, openalex=openalex)
    cleared = _drive(resolved, pid)
    assert cleared["active_count"] == 0
    assert cleared["checked_count"] == 1
    assert cleared["items"] == []
    assert "verified good" not in str(cleared).lower()


def test_endpoint_negative_paths_and_no_doi(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        no_doi = _paper(conn, "No DOI", None)
    engine.dispose()
    client = _client(temp_db_url, {})

    assert client.get("/papers/999999/reference-integrity").status_code == 404
    assert client.post("/papers/999999/reference-integrity/run").status_code == 404
    assert client.post(f"/papers/{no_doi}/reference-integrity/run").status_code == 422
    assert client.get("/reference-integrity/run/nope").status_code == 404
    assert client.post("/reference-integrity/instances/999999/review", json={"state": "dismissed"}).status_code == 404

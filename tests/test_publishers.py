"""PUBLISHERS "where to submit" journal-finder — SP1a (backlog #40).

Hermetic: fake OpenAlex-sources + DOAJ-journals fetchers + a deterministic keyword embed model (CI never downloads
SPECTER or hits the network). Covers the two clients, the pure profile engine + local ranking, and the async
endpoint — including the load-bearing vetoes: no composite score, no "predatory" label, every candidate (incl.
closed journals) appears, and **the abstract is never in any outbound request**.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.methods.publishers import build_profiles, derive_oa_color
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper
from integrations.doaj.journals import DoajJournal, DoajJournalsClient, _journal_from_body
from integrations.openalex.adapter import OpenAlexClient
from integrations.openalex.sources import OpenAlexSourcesClient, SourceMeta
from integrations.scielo.journals import ScieloJournal, ScieloJournalsClient

VOCAB = ["memory", "attention", "risk", "plant"]


class FakeEmbed:
    """Deterministic keyword embedding — a text's vector is its bag-of-VOCAB (the inc-185/228 test pattern)."""

    name = "fake"
    version = "fake"

    def encode_texts(self, texts):
        return [[1.0 if w in str(t).lower() else 0.0 for w in VOCAB] for t in texts]


# --- canned blobs ------------------------------------------------------------


def _work(sid, name, issn_l, *, is_oa=True, is_in_doaj=True):
    return {
        "primary_location": {
            "source": {
                "id": f"https://openalex.org/{sid}",
                "display_name": name,
                "issn_l": issn_l,
                "is_oa": is_oa,
                "is_in_doaj": is_in_doaj,
            }
        }
    }


def _src(sid, name, issn_l, *, is_oa=True, is_in_doaj=True, apc=None, two_yr=None, h=None, works=None, concepts=None):
    return {
        "id": f"https://openalex.org/{sid}",
        "display_name": name,
        "issn_l": issn_l,
        "issn": [issn_l],
        "is_oa": is_oa,
        "is_in_doaj": is_in_doaj,
        "apc_usd": apc,
        "summary_stats": {"2yr_mean_citedness": two_yr, "h_index": h},
        "works_count": works,
        "homepage_url": f"https://{sid.lower()}.example",
        "x_concepts": [{"display_name": c} for c in (concepts or [])],
        "type": "journal",
    }


def _doaj_rec(*, has_apc, amount=None, currency=None, seal=False, subjects=None, keywords=None):
    apc = {"has_apc": False} if not has_apc else {"has_apc": True, "max": [{"price": amount, "currency": currency}]}
    return {
        "bibjson": {
            "apc": apc,
            "waiver": {"has_waiver": True, "url": "https://waiver.example"},
            "license": [{"type": "CC BY"}],
            "subject": [{"term": s} for s in (subjects or [])],
            "keywords": keywords or [],
        },
        "admin": {"seal": seal},
    }


def _sources_fetcher(topic_by_subject, works, sources_by_id, *, record=None):
    def fake(path, *, params, headers, timeout):
        if record is not None:
            record.append(path + "?" + json.dumps(params, sort_keys=True))
        if path == "/topics":
            tid = topic_by_subject.get((params.get("search") or "").lower())
            return (200, {"results": [{"id": f"https://openalex.org/{tid}"}]}) if tid else (200, {"results": []})
        if path == "/works":
            return (200, {"results": works})
        if path == "/sources":
            filt = params.get("filter") or ""
            ids = filt[len("openalex_id:") :].split("|") if filt.startswith("openalex_id:") else []
            return (200, {"results": [sources_by_id[i] for i in ids if i in sources_by_id]})
        return (404, {"error": "nf"})

    return fake


def _doaj_fetcher(by_issn, *, record=None):
    def fake(query, *, headers, timeout):
        if record is not None:
            record.append(query)
        issn = query[len("issn:") :] if query.startswith("issn:") else ""
        rec = by_issn.get(issn)
        return (200, {"results": [rec]}) if rec else (200, {"results": []})

    return fake


def _scielo_rec(collection, code, *, title=None, country=None):
    rec = {"collection": collection, "code": code}
    if title is not None:
        rec["v100"] = [{"_": title}]
    if country is not None:
        rec["v310"] = [{"_": country}]
    return rec


def _scielo_fetcher(by_issn, *, record=None):
    """Fake for ScieloJournalsClient — returns a bare list matching the real confirmed API shape (empty = not
    indexed), keyed directly by the bare ISSN string (unlike DOAJ, no "issn:" prefix)."""

    def fake(issn, *, headers, timeout):
        if record is not None:
            record.append(issn)
        return 200, list(by_issn.get(issn, []))

    return fake


def _adapter_fetcher(focal_by_doi, *, record=None):
    """Fake for the DOI→work adapter (paper path → primary_topic). Signature matches OpenAlexClient's fetcher."""

    def fake(path, *, params, headers, timeout):
        if record is not None:
            record.append(path + "?" + json.dumps(params, sort_keys=True))
        if path.startswith("/doi:"):
            doi = path[len("/doi:") :]
            return (200, focal_by_doi[doi]) if doi in focal_by_doi else (404, {"error": "nf"})
        return (404, {"error": "nf"})

    return fake


def _focal(doi, *, topic="T1"):
    return {
        "id": "https://openalex.org/W0",
        "doi": f"https://doi.org/{doi}",
        "title": "Memory and attention",
        "primary_topic": {"id": f"https://openalex.org/{topic}", "display_name": "Cognitive neuroscience"},
        "authorships": [{"author": {"display_name": "Pat Doe"}}],
    }


# --- clients -----------------------------------------------------------------


def test_topic_resolution_and_candidate_pool_and_details(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        works = [
            _work("S1", "Memory J", "1111-1111"),
            _work("S1", "Memory J", "1111-1111"),
            _work("S2", "Closed J", "2222-2222", is_oa=False, is_in_doaj=False),
        ]
        sources = {
            "S1": _src("S1", "Memory J", "1111-1111", two_yr=3.2, h=40, works=900, concepts=["Memory"]),
            "S2": _src("S2", "Closed J", "2222-2222", is_oa=False, is_in_doaj=False, concepts=["Plant"]),
        }
        client = OpenAlexSourcesClient(fetcher=_sources_fetcher({"neuroscience": "T1"}, works, sources))
        assert client.fetch_topic_for_subject(conn, "neuroscience") == "T1"
        assert client.fetch_topic_for_subject(conn, "  ") is None  # empty → no request
        stubs = client.fetch_candidate_sources(conn, "T1")
        assert [s.source_id for s in stubs] == ["S1", "S2"]  # S1 twice → ranked first by frequency
        assert client.fetch_candidate_sources(conn, "bad-id") == []  # invalid topic id → no request
        details = client.fetch_source_details(conn, ["S1", "S2", "bad"])
        assert set(details) == {"S1", "S2"}  # "bad" dropped before the request
        assert details["S1"].is_in_doaj is True and details["S1"].two_year_mean_citedness == 3.2
        assert details["S2"].is_oa is False
    engine.dispose()


def test_sources_client_fail_closed(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        client = OpenAlexSourcesClient(fetcher=lambda p, **k: (500, None))
        assert client.fetch_topic_for_subject(conn, "x") is None
        assert client.fetch_candidate_sources(conn, "T1") == []
        assert client.fetch_source_details(conn, ["S1"]) == {}
    engine.dispose()


def test_doaj_journal_parse_and_validation(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        by_issn = {"1111-1111": _doaj_rec(has_apc=False, seal=True, subjects=["Neuroscience"], keywords=["memory"])}
        client = DoajJournalsClient(fetcher=_doaj_fetcher(by_issn))
        j = client.fetch_journal(conn, "1111-1111")
        assert j is not None and j.apc_amount == 0.0 and j.seal is True and j.license == ["CC BY"]
        assert j.apc_has_waiver is True and "Neuroscience" in j.subjects
        assert client.fetch_journal(conn, "not-an-issn") is None  # validated → no request
        assert client.fetch_journal(conn, "9999-9999") is None  # not found → None
    engine.dispose()


def test_doaj_gold_apc_parse():
    j = _journal_from_body({"results": [_doaj_rec(has_apc=True, amount=2000, currency="USD")]})
    assert j is not None and j.apc_amount == 2000.0 and j.apc_currency == "USD" and j.seal is False


def test_scielo_journal_parse_and_validation(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        by_issn = {"0102-311X": [_scielo_rec("scl", "0102-311X-1", title="Test Journal", country="BR")]}
        client = ScieloJournalsClient(fetcher=_scielo_fetcher(by_issn))
        j = client.fetch_journal(conn, "0102-311X")
        assert j is not None and j.collections == ["scl"] and j.title == "Test Journal" and j.country == "BR"
        assert client.fetch_journal(conn, "not-an-issn") is None  # validated -> no request
        assert client.fetch_journal(conn, "9999-9999") is None  # confirmed real-API shape: [] -> not indexed
    engine.dispose()


def test_scielo_multi_collection_parse(temp_db_url):
    """Confirmed real-API shape: a journal indexed under multiple SciELO collections returns one object per
    collection -- these must merge into one ScieloJournal, not silently keep only the first/last."""
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        by_issn = {
            "0102-311X": [
                _scielo_rec("spa", "0102-311X-1", title="Cadernos de Saúde Pública"),
                _scielo_rec("scl", "0102-311X-2"),
            ]
        }
        client = ScieloJournalsClient(fetcher=_scielo_fetcher(by_issn))
        j = client.fetch_journal(conn, "0102-311X")
        assert j.collections == ["spa", "scl"]
        assert j.codes == ["0102-311X-1", "0102-311X-2"]
        assert j.title == "Cadernos de Saúde Pública"  # taken from whichever record carries v100 first
    engine.dispose()


def test_scielo_journal_cache_roundtrip(temp_db_url):
    """A second lookup for the same ISSN reads the cache, not the fetcher -- and preserves the not-indexed
    verdict across the cache boundary too."""
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        calls: list[str] = []
        hit_by_issn = {"0102-311X": [_scielo_rec("scl", "0102-311X-1")]}
        client = ScieloJournalsClient(fetcher=_scielo_fetcher(hit_by_issn, record=calls))
        assert client.fetch_journal(conn, "0102-311X") is not None
        assert client.fetch_journal(conn, "0102-311X") is not None
        assert calls == ["0102-311X"]  # second call served from cache

        miss_client = ScieloJournalsClient(fetcher=_scielo_fetcher({}, record=calls))
        assert miss_client.fetch_journal(conn, "9999-9999") is None
        assert miss_client.fetch_journal(conn, "9999-9999") is None
        assert calls == ["0102-311X", "9999-9999"]  # the not-indexed [] result is cached too
    engine.dispose()


# --- pure engine -------------------------------------------------------------


def test_derive_oa_color():
    diamond = SourceMeta("S1", "J", is_in_doaj=True)
    gold = SourceMeta("S2", "J", is_in_doaj=True)
    oa_other = SourceMeta("S3", "J", is_oa=True, is_in_doaj=False)
    closed = SourceMeta("S4", "J", is_oa=False, is_in_doaj=False)
    assert derive_oa_color(diamond, DoajJournal(apc_amount=0.0)) == "diamond"
    assert derive_oa_color(gold, DoajJournal(apc_amount=2000.0)) == "gold"
    assert derive_oa_color(gold, None) == "gold"  # in DOAJ but no record → default gold, not diamond
    assert derive_oa_color(oa_other, None) == "oa-other"
    assert derive_oa_color(closed, None) == "closed"


def _profiles_setup():
    cands = [
        SourceMeta(
            "S1",
            "Memory J",
            issns=["1111-1111"],
            issn_l="1111-1111",
            is_oa=True,
            is_in_doaj=True,
            two_year_mean_citedness=3.2,
            concepts=["Memory"],
        ),
        SourceMeta(
            "S2",
            "Plant Closed J",
            issns=["2222-2222"],
            issn_l="2222-2222",
            is_oa=False,
            is_in_doaj=False,
            concepts=["Plant"],
        ),
    ]
    doaj = {
        "1111-1111": DoajJournal(apc_amount=0.0, seal=True, subjects=["Neuroscience"], keywords=["memory", "attention"])
    }
    return cands, doaj


def test_build_profiles_fit_orders_and_every_candidate_appears():
    cands, doaj = _profiles_setup()
    rep = build_profiles(cands, doaj, abstract="memory attention", embedding_model=FakeEmbed(), weighting=0.0)
    assert rep.shown == 2 and rep.considered == 2  # the closed journal appears too (no OA-only filter)
    assert rep.profiles[0].source_id == "S1"  # fit dominates at weighting 0
    assert rep.profiles[0].fit > rep.profiles[1].fit
    assert rep.profiles[0].oa_color == "diamond" and rep.profiles[0].doaj_seal is True
    assert rep.profiles[0].elevated_for == []  # weighting 0 → nothing "elevated"
    closed = next(p for p in rep.profiles if p.source_id == "S2")
    assert closed.oa_color == "closed" and closed.is_in_doaj is False


def test_build_profiles_weighting_elevates_open_goods():
    cands, doaj = _profiles_setup()
    # An abstract that matches the CLOSED journal's scope, so fit alone would rank it first...
    rep = build_profiles(cands, doaj, abstract="plant", embedding_model=FakeEmbed(), weighting=1.0)
    assert rep.profiles[0].source_id == "S1"  # ...but full openness weighting elevates the diamond+Seal journal
    assert "diamond OA (free to publish + free to read)" in rep.profiles[0].elevated_for
    assert "DOAJ Seal" in rep.profiles[0].elevated_for
    assert next(p for p in rep.profiles if p.source_id == "S2").elevated_for == []  # closed → no goods


def test_build_profiles_no_composite_score_no_predatory():
    cands, doaj = _profiles_setup()
    rep = build_profiles(cands, doaj, abstract="memory", embedding_model=FakeEmbed(), weighting=0.5)
    blob = json.dumps(rep.to_dict()).lower()
    assert "predator" not in blob  # never labels a journal predatory
    assert "openness_score" not in blob and "legitimacy_score" not in blob  # no composite score field
    for p in rep.profiles:  # the only bare numeric ranking signal shown is `fit`; `top_factor.total` is always
        # accompanied by its category basis (Principles #7), never a bare "*score*" key on the profile itself
        assert not any(k.endswith("score") for k in p.to_dict())
    # legitimacy absence is shown as neutral fact (a deferred-sources list), never a flag
    assert any("COPE" in s for s in rep.profiles[0].legitimacy_absent)
    # SciELO + TOP Factor were wired in (backlog #40) -- no longer named as deferred
    assert not any("SciELO" in s for s in rep.profiles[0].legitimacy_absent)
    assert not any("TOP Factor" in s for s in rep.profiles[0].legitimacy_absent)
    assert any("regional indexes (AJOL, Redalyc, Latindex)" == s for s in rep.profiles[0].legitimacy_absent)
    assert any("self-archiving policy" == s for s in rep.profiles[0].legitimacy_absent)


def test_build_profiles_empty():
    rep = build_profiles([], {}, abstract="memory", embedding_model=FakeEmbed())
    assert rep.shown == 0 and rep.considered == 0 and rep.profiles == []
    assert rep.top_factor_coverage == {"count": 0, "retrieved_at": None}


def test_build_profiles_wires_scielo_and_top_factor_facts():
    cands, doaj = _profiles_setup()
    scielo_by_issn = {"1111-1111": ScieloJournal(collections=["scl", "spa"], codes=["c1"], title="Memory J")}
    top_factor_by_issn = {
        "1111-1111": {
            "total": 5,
            "categories": [{"name": "Data transparency", "score": 2, "max": 3, "justification": "Encouraged"}],
        }
    }
    rep = build_profiles(
        cands,
        doaj,
        scielo_by_issn,
        top_factor_by_issn,
        abstract="memory attention",
        embedding_model=FakeEmbed(),
        weighting=0.0,
        top_factor_db_status={"count": 812, "retrieved_at": "2026-03-12T00:00:00+00:00"},
    )
    s1 = next(p for p in rep.profiles if p.source_id == "S1")
    assert s1.scielo_collections == ["scl", "spa"]
    assert s1.top_factor == {
        "total": 5,
        "categories": [{"name": "Data transparency", "score": 2, "max": 3, "justification": "Encouraged"}],
    }
    assert "Indexed in SciELO (scl, spa)" in s1.legitimacy_signals
    assert "Has a TOP Factor transparency assessment" in s1.legitimacy_signals
    s2 = next(p for p in rep.profiles if p.source_id == "S2")  # no SciELO/TOP Factor data for the closed journal
    assert s2.scielo_collections == [] and s2.top_factor is None
    assert not any("SciELO" in sig or "TOP Factor" in sig for sig in s2.legitimacy_signals)
    assert rep.top_factor_coverage == {"count": 812, "retrieved_at": "2026-03-12T00:00:00+00:00"}


def test_build_profiles_top_factor_never_downloaded_is_honest():
    """A per-journal `top_factor: None` is ambiguous in isolation (no row for this journal vs. the mirror was
    never downloaded at all) -- the report-level `top_factor_coverage` is the disambiguator."""
    cands, doaj = _profiles_setup()
    rep = build_profiles(
        cands,
        doaj,
        abstract="memory",
        embedding_model=FakeEmbed(),
        top_factor_db_status={"count": 0, "retrieved_at": None},
    )
    assert rep.top_factor_coverage == {"count": 0, "retrieved_at": None}
    assert all(p.top_factor is None for p in rep.profiles)


# --- endpoint ----------------------------------------------------------------


def _endpoint_app(temp_db_url, *, record_sources=None, record_doaj=None, record_scielo=None, focal_by_doi=None):
    works = [
        _work("S1", "Memory J", "1111-1111"),
        _work("S1", "Memory J", "1111-1111"),
        _work("S2", "Closed J", "2222-2222", is_oa=False, is_in_doaj=False),
    ]
    sources = {
        "S1": _src("S1", "Memory J", "1111-1111", two_yr=3.2, h=40, works=900, concepts=["Memory"]),
        "S2": _src("S2", "Closed J", "2222-2222", is_oa=False, is_in_doaj=False, concepts=["Plant"]),
    }
    by_issn = {
        "1111-1111": _doaj_rec(has_apc=False, seal=True, subjects=["Neuroscience"], keywords=["memory", "attention"])
    }
    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.openalex_sources_client = OpenAlexSourcesClient(
        fetcher=_sources_fetcher({"neuroscience": "T1"}, works, sources, record=record_sources)
    )
    client.app.state.doaj_journals_client = DoajJournalsClient(fetcher=_doaj_fetcher(by_issn, record=record_doaj))
    # Always wired to a fake (never left to fall back to a real live-HTTP client mid-test), mirroring DOAJ above.
    client.app.state.scielo_journals_client = ScieloJournalsClient(fetcher=_scielo_fetcher({}, record=record_scielo))
    if focal_by_doi is not None:
        client.app.state.openalex_client = OpenAlexClient(fetcher=_adapter_fetcher(focal_by_doi))
    client.app.state.embedding_model = FakeEmbed()
    return client


def _drive(client, body):
    r = client.post("/methods/publishers/run", json=body)
    if r.status_code != 202:
        return r.status_code, None
    jid = r.json()["job_id"]
    data = {}
    for _ in range(40):
        data = client.get(f"/methods/publishers/run/{jid}").json()
        if data["status"] in ("done", "error"):
            break
    return 202, data


def test_endpoint_paste_path(temp_db_url):
    client = _endpoint_app(temp_db_url)
    _, done = _drive(client, {"abstract": "memory attention in the brain", "subject": "neuroscience"})
    assert done["status"] == "done", done
    rep = done["report"]
    assert rep["topic_id"] == "T1" and rep["shown"] == 2  # both journals, incl. the closed one
    by = {p["source_id"]: p for p in rep["profiles"]}
    assert by["S1"]["oa_color"] == "diamond" and by["S1"]["apc_amount"] == 0.0 and by["S1"]["doaj_seal"] is True
    assert "S2" in by and by["S2"]["oa_color"] == "closed"
    assert "predator" not in json.dumps(rep).lower()


def test_endpoint_paper_path(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(
            conn,
            title="Memory & attention",
            csl_json={"title": "Memory & attention", "DOI": "10.1/f"},
            doi="10.1/f",
            abstract="A study of memory and attention.",
        )
    engine.dispose()
    client = _endpoint_app(temp_db_url, focal_by_doi={"10.1/f": _focal("10.1/f", topic="T1")})
    _, done = _drive(client, {"paper_id": pid})
    assert done["status"] == "done", done
    assert done["report"]["topic_id"] == "T1" and done["report"]["shown"] == 2


def test_endpoint_validation(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        no_doi = create_paper(conn, title="No DOI", csl_json={"title": "No DOI"}, doi=None)
    engine.dispose()
    client = _endpoint_app(temp_db_url)
    assert client.post("/methods/publishers/run", json={}).status_code == 422  # neither input
    assert (
        client.post("/methods/publishers/run", json={"paper_id": 1, "abstract": "x", "subject": "y"}).status_code == 422
    )  # both
    assert client.post("/methods/publishers/run", json={"paper_id": 99999}).status_code == 404
    assert client.post("/methods/publishers/run", json={"paper_id": no_doi}).status_code == 422
    assert client.get("/methods/publishers/run/nope").status_code == 404


def test_abstract_never_transmitted(temp_db_url):
    """The abstract is embedded locally — it must appear in NO outbound request (the load-bearing invariant)."""
    rec_sources: list[str] = []
    rec_doaj: list[str] = []
    rec_scielo: list[str] = []
    client = _endpoint_app(temp_db_url, record_sources=rec_sources, record_doaj=rec_doaj, record_scielo=rec_scielo)
    token = "SECRETABSTRACTTOKEN"
    _, done = _drive(client, {"abstract": f"{token} memory attention", "subject": "neuroscience"})
    assert done["status"] == "done"
    outbound = " ".join(rec_sources + rec_doaj + rec_scielo)
    assert token not in outbound  # the abstract text is never in a topic/works/sources/DOAJ/SciELO request
    assert rec_sources  # sanity: requests were actually made (topic + works + sources)
    assert rec_scielo  # sanity: SciELO was actually queried (every candidate gets one live call)


# --- WIP manuscript wiring (inc 404) ------------------------------------------


def _poll_scan(client: TestClient, job_id: str) -> None:
    for _ in range(30):
        result = client.get(f"/wip/scan/{job_id}").json()
        if result["status"] in {"done", "error"}:
            assert result["status"] == "done"
            return
    raise AssertionError("scan did not finish")


def _manuscript(client: TestClient, folder: Path) -> int:
    folder.mkdir()
    (folder / "draft.txt").write_text("An early idea.", encoding="utf-8")
    root = client.post("/wip/watch-roots", json={"path": str(folder), "discovery_mode": "folder"}).json()
    scan = client.post(f"/wip/watch-roots/{root['id']}/scan").json()
    _poll_scan(client, scan["job_id"])
    return client.get("/wip/manuscripts").json()[0]["id"]


def test_manuscript_run_persists_a_receipt_and_lists_for_the_manuscript(temp_db_url, tmp_path: Path):
    client = _endpoint_app(temp_db_url)
    manuscript_id = _manuscript(client, tmp_path / "Draft")

    _, done = _drive(
        client, {"abstract": "memory attention in the brain", "subject": "neuroscience", "manuscript_id": manuscript_id}
    )
    assert done["status"] == "done", done
    rep = done["report"]

    runs = client.get(f"/wip/manuscripts/{manuscript_id}/journal-runs")
    assert runs.status_code == 200
    listed = runs.json()["runs"]
    assert len(listed) == 1
    assert listed[0]["topic_id"] == rep["topic_id"]
    assert listed[0]["considered"] == rep["considered"]
    assert listed[0]["shown"] == rep["shown"]
    assert listed[0]["weighting"] == rep["weighting"]


def test_manuscript_run_rejects_paper_id_and_manuscript_id_together(temp_db_url):
    client = _endpoint_app(temp_db_url)
    r = client.post("/methods/publishers/run", json={"paper_id": 1, "manuscript_id": 1})
    assert r.status_code == 422


def test_manuscript_run_404s_for_a_missing_manuscript(temp_db_url):
    client = _endpoint_app(temp_db_url)
    r = client.post(
        "/methods/publishers/run",
        json={"abstract": "memory attention", "subject": "neuroscience", "manuscript_id": 999999},
    )
    assert r.status_code == 404


def test_journal_runs_list_404s_for_a_missing_manuscript_and_is_scoped(temp_db_url, tmp_path: Path):
    client = _endpoint_app(temp_db_url)
    assert client.get("/wip/manuscripts/999999/journal-runs").status_code == 404

    manuscript_a = _manuscript(client, tmp_path / "DraftA")
    manuscript_b = _manuscript(client, tmp_path / "DraftB")
    _drive(client, {"abstract": "memory attention", "subject": "neuroscience", "manuscript_id": manuscript_a})

    assert len(client.get(f"/wip/manuscripts/{manuscript_a}/journal-runs").json()["runs"]) == 1
    assert client.get(f"/wip/manuscripts/{manuscript_b}/journal-runs").json()["runs"] == []


def test_wip_journal_runs_route_remains_local_only(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    headers = {"host": "example.com"}
    assert client.get("/wip/manuscripts/1/journal-runs", headers=headers).status_code == 403

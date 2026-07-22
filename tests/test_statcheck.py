"""Tests for statcheck (inc 95) — deterministic NHST p-value recomputation. Hermetic (no network, no LLM).
The crux is correctness: a correctly-rounded / one-tailed result must NOT be flagged (no false positives)."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.backend.api import create_app
from app.backend.methods.statcheck import recompute_p, run_statcheck
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper, list_papers
from app.backend.persistence.schema import open_science_signals
from app.backend.persistence.signals_repo import get_statcheck_summary, store_statcheck


def _chunk(text, page=1, section=None):
    chunk = {"text": text, "page_start": page}
    if section:
        chunk["section"] = section
    return chunk


def test_consistent_t():
    rep = run_statcheck([_chunk("There was a significant effect, t(28) = 2.10, p = .04, overall.")])
    assert rep.checked == 1
    r = rep.results[0]
    assert r.test_type == "t" and r.consistency == "consistent"
    assert abs(r.computed_p - 0.045) < 0.01  # ~.0448


def test_inconsistent_same_significance():
    # computed ~.045 (significant); reported .001 (also significant) → value wrong, decision unchanged
    rep = run_statcheck([_chunk("t(28) = 2.10, p = .001")])
    assert rep.results[0].consistency == "inconsistent"
    assert rep.inconsistent == 1 and rep.decision_errors == 0


def test_decision_error():
    # t = 1.5 → computed ~.14 (non-significant), but reported p = .04 (significant) → the decision flips
    rep = run_statcheck([_chunk("t(28) = 1.5, p = .04")])
    assert rep.results[0].consistency == "decision-error"
    assert rep.decision_errors == 1 and rep.inconsistent == 0


def test_correct_rounding_not_flagged():
    # the recomputation must account for the stat's rounding — a correctly-rounded p is consistent
    assert run_statcheck([_chunk("t(28) = 2.10, p = .045")]).results[0].consistency == "consistent"


def test_one_tailed_not_flagged():
    # one-tailed p ~ .022 — a two-tailed-only check would false-flag; the one-tailed reading is consistent
    assert run_statcheck([_chunk("t(28) = 2.10, p = .02")]).results[0].consistency == "consistent"


def test_all_forms_detected():
    text = "F(2, 45) = 3.10, p = .05; r(30) = .42, p = .02; χ2(1) = 5.20, p = .02; z = 2.10, p = .04"
    rep = run_statcheck([_chunk(text)])
    assert {r.test_type for r in rep.results} == {"F", "r", "chi2", "z"}


# ── backlog #27: the reported test statistic can be a BOUND ("<"/">"), not just an exact "=" value — e.g.
# "F(1,44) < 1, p > .05", a common way to report a clearly-null result without an exact F. Reference p-values
# below were computed directly (scipy.stats), not guessed: F(1,44) at F=1 → p≈0.3228 (one-sided, matching
# recompute_p's F convention); t(28) at t=1 (two-tailed) → p≈0.3259; t(28) at t=3 (two-tailed) → p≈0.00562.


def test_stat_bound_less_than_consistent_with_nonsignificant_p():
    # true F is SOMEWHERE below 1, so true p is ABOVE p(F=1)≈.323 — comfortably consistent with "p > .05"
    # for every possible true value, not just some of them (the strongest, least-ambiguous case).
    rep = run_statcheck([_chunk("There was no effect, F(1, 44) < 1, p > .05, overall.")])
    assert rep.checked == 1
    r = rep.results[0]
    assert r.test_type == "F" and r.consistency == "consistent"
    assert abs(r.computed_p - 0.3228) < 0.001  # the p-value AT the reported bound (F=1), not a point estimate


def test_stat_bound_less_than_inconsistent_with_small_p():
    # true |t| is SOMEWHERE below 1 → true p is ABOVE p(t=1)≈.326 (two-tailed) or ≈.163 (one-tailed fallback) —
    # "p < .01" is impossible for ANY value consistent with "t(28) < 1", not just improbable.
    rep = run_statcheck([_chunk("t(28) < 1, p < .01")])
    assert rep.checked == 1
    assert rep.results[0].consistency == "inconsistent"


def test_stat_bound_less_than_ambiguous_not_flagged():
    # t_crit(.05, df=28) ≈ 2.048, which is BELOW the reported bound of 3 — so some values of |t| in (0, 3) would
    # give p <= .05 and others (e.g. |t|=1, p≈.326) would give p > .05. The reported "p > .05" is NOT provably
    # wrong (a valid true value exists that satisfies it), so this must NOT be flagged, even though it also
    # isn't provably right for every value in the range — the same "does a valid value exist" standard the
    # existing "=" path already applies.
    rep = run_statcheck([_chunk("t(28) < 3, p > .05")])
    assert rep.checked == 1
    assert rep.results[0].consistency == "consistent"


def test_stat_bound_greater_than_consistent():
    # true |t| is SOMEWHERE above 3 → true p is BELOW p(t=3)≈.0056 — consistent with a reported "p < .01".
    rep = run_statcheck([_chunk("t(28) > 3, p < .01")])
    assert rep.checked == 1
    assert rep.results[0].consistency == "consistent"


def test_stat_bound_never_produces_decision_error():
    # a bound never yields a point estimate, so it must never be classified as a "decision-error" (that
    # classification requires comparing an exact recomputed significance against the reported one) — even for
    # an input that's clearly a wrong/contradictory pairing, the correct classification is "inconsistent".
    rep = run_statcheck([_chunk("t(28) < 1, p = .001")])
    assert rep.checked == 1
    assert rep.results[0].consistency == "inconsistent"
    assert rep.decision_errors == 0


def test_stat_equals_still_works_unchanged():
    # the "=" path (the dominant, pre-existing case) must be completely unaffected by the new comparator group.
    rep = run_statcheck([_chunk("t(28) = 2.10, p = .04")])
    assert rep.results[0].test_type == "t" and rep.results[0].consistency == "consistent"


def test_no_statistics_text():
    rep = run_statcheck([_chunk("Prose about treatment and weighting, with no inline statistics at all.")])
    assert rep.checked == 0 and rep.results == []


def test_page_provenance_from_chunk():
    rep = run_statcheck([_chunk("introduction prose", 1), _chunk("Results: t(10) = 2.0, p = .07.", 5)])
    assert rep.checked == 1 and rep.results[0].page == 5


def test_section_provenance_from_chunk():
    rep = run_statcheck([_chunk("Results: t(10) = 2.0, p = .07.", 5, section="results")])
    assert rep.checked == 1
    assert rep.results[0].section == "results"
    assert rep.results[0].consistency == "consistent"


def test_result_carries_bounded_extracted_text_context():
    text = (
        "Before the model, participants completed the task. "
        "The main contrast was reported as t(28) = 1.5, p = .04 in the results section. "
        "The authors then discussed robustness checks."
    )
    rep = run_statcheck([_chunk(text)])
    assert rep.checked == 1
    context = rep.results[0].context
    assert "The main contrast was reported as t(28) = 1.5, p = .04" in context
    assert len(context) <= 326


def test_recompute_p_known_values():
    assert abs(recompute_p("t", 2.048, 28, None) - 0.05) < 0.01  # critical t(28) ≈ 2.048 → p ≈ .05
    assert abs(recompute_p("z", 1.96, 0, None) - 0.05) < 0.005  # z = 1.96 → p ≈ .05
    assert recompute_p("r", 1.5, 10, None) is None  # |r| ≥ 1 is degenerate → None, not a crash


def test_statcheck_endpoint(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="Stats Paper", csl_json={"type": "article-journal", "title": "Stats Paper"})
        attachment_id = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="managed",
            availability="available",
            checksum="ck1",
            content_type="application/pdf",
        )
        create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=attachment_id,
            text="In the results, t(28) = 1.5, p = .04 and t(28) = 2.10, p = .04.",
            page_start=3,
            page_end=3,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="x",
            extraction_version="1",
            chunking_strategy="s",
            chunk_version="v1",
            source_attachment_checksum="ck1",
            section="results",
        )
        empty_id = create_paper(conn, title="No Text", csl_json={"title": "No Text"})  # metadata-only

    client = TestClient(create_app(db_url=temp_db_url))
    data = client.get(f"/papers/{paper_id}/statcheck").json()
    assert data["checked"] == 2 and data["decision_errors"] == 1  # the t=1.5/p=.04 flips significance
    assert all(r["page"] == 3 for r in data["results"])  # page provenance from the chunk
    assert all(r["section"] == "results" for r in data["results"])  # section provenance from the chunk
    assert all("context" in r and "In the results" in r["context"] for r in data["results"])
    assert all(r["coordinate_precision"] == "region" for r in data["results"])

    assert client.get(f"/papers/{empty_id}/statcheck").json() == {  # no chunks → honest empty, not an error
        "checked": 0,
        "inconsistent": 0,
        "decision_errors": 0,
        "results": [],
    }
    assert client.get("/papers/999999/statcheck").status_code == 404


def test_statcheck_endpoint_exposes_exact_anchor_when_pdf_locator_matches_page(temp_db_url, monkeypatch):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="Stats Paper", csl_json={"type": "article-journal", "title": "Stats Paper"})
        attachment_id = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="managed",
            availability="available",
            checksum="ck-exact",
            content_type="application/pdf",
        )
        create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=attachment_id,
            text="The primary test was t(28) = 1.5, p = .04.",
            page_start=7,
            page_end=7,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="x",
            extraction_version="1",
            chunking_strategy="s",
            chunk_version="v1",
            source_attachment_checksum="ck-exact",
        )

    def fake_locator(conn, got_attachment_id, quote):
        assert got_attachment_id == attachment_id
        assert quote == "t(28) = 1.5, p = .04"
        return SimpleNamespace(
            found=True,
            page_start=7,
            page_end=7,
            rectangles=({"page": 7, "x0": 10, "y0": 20, "x1": 90, "y1": 34},),
        )

    monkeypatch.setattr("app.backend.api.routers.methods.locate_quote_for_attachment", fake_locator)
    data = TestClient(create_app(db_url=temp_db_url)).get(f"/papers/{paper_id}/statcheck").json()
    result = data["results"][0]
    assert result["coordinate_precision"] == "exact"
    assert result["bbox_json"][0]["coordinate_precision"] == "exact"
    assert result["bbox_json"][0]["page"] == 7


def test_statcheck_endpoint_does_not_claim_exact_for_locator_page_mismatch(temp_db_url, monkeypatch):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id = create_paper(conn, title="Duplicate Stat", csl_json={"title": "Duplicate Stat"})
        attachment_id = create_attachment(
            conn,
            paper_id=paper_id,
            storage_mode="managed",
            availability="available",
            checksum="ck-mismatch",
            content_type="application/pdf",
        )
        create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=attachment_id,
            text="Later in the paper, t(28) = 1.5, p = .04.",
            page_start=9,
            page_end=9,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="x",
            extraction_version="1",
            chunking_strategy="s",
            chunk_version="v1",
            source_attachment_checksum="ck-mismatch",
        )

    def wrong_page_locator(conn, got_attachment_id, quote):
        return SimpleNamespace(
            found=True,
            page_start=2,
            page_end=2,
            rectangles=({"page": 2, "x0": 10, "y0": 20, "x1": 90, "y1": 34},),
        )

    monkeypatch.setattr("app.backend.api.routers.methods.locate_quote_for_attachment", wrong_page_locator)
    data = TestClient(create_app(db_url=temp_db_url)).get(f"/papers/{paper_id}/statcheck").json()
    result = data["results"][0]
    assert result["page"] == 9
    assert result["coordinate_precision"] == "region"
    assert result["bbox_json"] is None


def _stat_chunk(conn, title, checksum, text):
    pid = create_paper(conn, title=title, csl_json={"title": title})
    att = create_attachment(
        conn,
        paper_id=pid,
        storage_mode="managed",
        availability="available",
        checksum=checksum,
        content_type="application/pdf",
    )
    create_chunk(
        conn,
        paper_id=pid,
        attachment_id=att,
        text=text,
        page_start=1,
        page_end=1,
        bbox_coordinate_system="pdf-points-top-left",
        extraction_tool="x",
        extraction_version="1",
        chunking_strategy="s",
        chunk_version="v1",
        source_attachment_checksum=checksum,
    )
    return pid


def test_store_statcheck_upserts(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        pid = create_paper(conn, title="P", csl_json={"title": "P"})
        store_statcheck(conn, pid, checked=5, inconsistent=2, decision_errors=1)
        assert get_statcheck_summary(conn, pid)["status"] == "inconsistent"
        store_statcheck(conn, pid, checked=5, inconsistent=0, decision_errors=0)  # re-run, now clean
        assert get_statcheck_summary(conn, pid)["status"] == "consistent"  # status flips
        rows = list(conn.execute(select(open_science_signals).where(open_science_signals.c.paper_id == pid)))
        assert len(rows) == 1  # OR REPLACE → exactly one row, never a duplicate


def test_list_papers_signal_filter(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        good = create_paper(conn, title="Good", csl_json={"title": "Good"})
        bad = create_paper(conn, title="Bad", csl_json={"title": "Bad"})
        store_statcheck(conn, good, checked=3, inconsistent=0, decision_errors=0)
        store_statcheck(conn, bad, checked=3, inconsistent=1, decision_errors=0)
        assert [r["id"] for r in list_papers(conn, signal="statcheck-inconsistent")] == [bad]
        assert {r["id"] for r in list_papers(conn, signal="bogus")} == {good, bad}  # unknown → ignored (no filter)


def test_statcheck_batch_run_then_filter(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _stat_chunk(conn, "Bad Stats", "b", "We found t(28) = 1.5, p = .04.")  # decision error
        _stat_chunk(conn, "Good Stats", "g", "We found t(28) = 2.10, p = .04.")  # consistent
        create_paper(conn, title="No Stats", csl_json={"title": "No Stats"})  # metadata-only → not flagged
    client = TestClient(create_app(db_url=temp_db_url))
    started = client.post("/methods/statcheck/run")
    assert started.status_code == 202
    job_id = started.json()["job_id"]
    result = {}
    for _ in range(30):
        result = client.get(f"/methods/statcheck/run/{job_id}").json()
        if result["status"] in ("done", "error"):
            break
    assert result["status"] == "done", result
    assert result["summary"] == {"total": 3, "checked": 2, "flagged": 1}
    flagged = client.get("/papers", params={"signal": "statcheck-inconsistent"}).json()
    assert [p["title"] for p in flagged] == ["Bad Stats"]  # only the inconsistent paper, never a rank
    assert client.get("/methods/statcheck/summary").json()["flagged"] == 1  # drives the library "N flagged" chip
    assert client.get("/methods/statcheck/run/nope").status_code == 404


def test_statcheck_batch_commits_per_paper_partial_progress(temp_db_url, monkeypatch):
    """inc C: a failure storing the 2nd paper's statcheck leaves the 1st paper's signal committed and the job
    completes (per-paper commit + skip). The old single-transaction batch would roll back the 1st too and error."""
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        _stat_chunk(conn, "Bad Stats", "b", "We found t(28) = 1.5, p = .04.")  # decision error → flagged (1st)
        _stat_chunk(conn, "Good Stats", "g", "We found t(28) = 2.10, p = .04.")  # 2nd — its store is forced to fail
        create_paper(conn, title="No Stats", csl_json={"title": "No Stats"})
    engine.dispose()

    from app.backend.api.routers import methods as methods_mod

    real_store = methods_mod.store_statcheck
    calls = {"n": 0}

    def flaky_store(conn, paper_id, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:  # papers processed id-ASC → the 2nd store is "Good Stats"
            raise RuntimeError("boom storing the 2nd paper's statcheck")
        return real_store(conn, paper_id, **kwargs)

    monkeypatch.setattr(methods_mod, "store_statcheck", flaky_store)
    client = TestClient(create_app(db_url=temp_db_url))
    job_id = client.post("/methods/statcheck/run").json()["job_id"]
    result = {}
    for _ in range(30):
        result = client.get(f"/methods/statcheck/run/{job_id}").json()
        if result["status"] in ("done", "error"):
            break
    assert result["status"] == "done"  # per-paper skip → the run completes
    flagged = client.get("/papers", params={"signal": "statcheck-inconsistent"}).json()
    assert [p["title"] for p in flagged] == ["Bad Stats"]  # the 1st paper's signal committed before the 2nd failed

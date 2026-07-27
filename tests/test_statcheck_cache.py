"""Tests for the per-paper statcheck result cache (inc 400) — cache-then-explicit-rescan, never a silent
live recompute. The crux: a cached-then-redisplayed result must be byte-identical to what a live run would
show, including the exact/region coordinate-precision fields (invariant #2) — a cache is only honest if it
never degrades the evidence it's replaying."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.backend.api import create_app
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_attachment, create_chunk, create_paper


def _stat_chunk(conn, title, checksum, text, *, page=1):
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
        page_start=page,
        page_end=page,
        bbox_coordinate_system="pdf-points-top-left",
        extraction_tool="x",
        extraction_version="1",
        chunking_strategy="s",
        chunk_version="v1",
        source_attachment_checksum=checksum,
    )
    return pid, att


def test_cached_is_empty_before_any_check_and_404s_for_a_missing_paper(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id, _ = _stat_chunk(conn, "Unchecked Paper", "ck-1", "t(28) = 2.10, p = .04")
    client = TestClient(create_app(db_url=temp_db_url))
    result = client.get(f"/papers/{paper_id}/statcheck/cached").json()
    assert result == {
        "cached": False,
        "checked": 0,
        "inconsistent": 0,
        "decision_errors": 0,
        "results": [],
        "coverage": None,
        "computed_at": None,
        "stale": False,
    }
    assert client.get("/papers/999999/statcheck/cached").status_code == 404
    assert client.post("/papers/999999/statcheck/rescan").status_code == 404


def test_rescan_computes_persists_and_overwrites_a_single_row(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id, _ = _stat_chunk(conn, "Decision Error Paper", "ck-2", "t(28) = 1.5, p = .04")
    client = TestClient(create_app(db_url=temp_db_url))

    first = client.post(f"/papers/{paper_id}/statcheck/rescan").json()
    assert first["cached"] is True
    assert first["checked"] == 1
    assert first["decision_errors"] == 1
    assert first["computed_at"] is not None
    assert first["stale"] is False

    cached = client.get(f"/papers/{paper_id}/statcheck/cached").json()
    assert cached == first  # the GET must reflect exactly what the rescan just stored

    second = client.post(f"/papers/{paper_id}/statcheck/rescan").json()
    assert second["checked"] == 1  # re-running overwrites (OR REPLACE on the paper_id PK), never duplicates
    assert client.get(f"/papers/{paper_id}/statcheck/cached").json() == second


def test_cache_reproduces_exact_precision_byte_identical_to_a_live_run(temp_db_url, monkeypatch):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id, attachment_id = _stat_chunk(conn, "Exact Anchor Paper", "ck-exact", "t(28) = 1.5, p = .04", page=7)

    def fake_locator(conn, got_attachment_id, quote):
        assert got_attachment_id == attachment_id
        return SimpleNamespace(
            found=True,
            page_start=7,
            page_end=7,
            rectangles=({"page": 7, "x0": 10, "y0": 20, "x1": 90, "y1": 34},),
        )

    monkeypatch.setattr("app.backend.api.routers.methods.locate_quote_for_attachment", fake_locator)
    client = TestClient(create_app(db_url=temp_db_url))
    live = client.get(f"/papers/{paper_id}/statcheck").json()
    rescanned = client.post(f"/papers/{paper_id}/statcheck/rescan").json()
    cached = client.get(f"/papers/{paper_id}/statcheck/cached").json()

    assert live["results"][0]["coordinate_precision"] == "exact"
    assert live["results"] == rescanned["results"] == cached["results"]  # byte-identical, cache included
    assert cached["results"][0]["bbox_json"][0]["coordinate_precision"] == "exact"


def test_cache_reproduces_region_precision_byte_identical_to_a_live_run(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id, _ = _stat_chunk(conn, "Region Paper", "ck-region", "t(28) = 2.10, p = .04", page=3)
    client = TestClient(create_app(db_url=temp_db_url))
    live = client.get(f"/papers/{paper_id}/statcheck").json()
    cached = client.post(f"/papers/{paper_id}/statcheck/rescan").json()

    assert live["results"][0]["coordinate_precision"] == "region"  # no locator patched -> falls back to region
    assert live["results"] == cached["results"]


def test_cache_flags_stale_after_content_changes_but_still_returns_the_old_result(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        paper_id, attachment_id = _stat_chunk(conn, "Reprocessed Paper", "ck-before", "t(28) = 1.5, p = .04")
    client = TestClient(create_app(db_url=temp_db_url))
    original = client.post(f"/papers/{paper_id}/statcheck/rescan").json()
    assert original["stale"] is False

    # Simulate a reprocess: a new chunk with a different source_attachment_checksum (a real reprocess always
    # mints a new chunk id + checksum even if the extracted text is byte-identical).
    with engine.begin() as conn:
        create_chunk(
            conn,
            paper_id=paper_id,
            attachment_id=attachment_id,
            text="t(28) = 1.5, p = .04",
            page_start=1,
            page_end=1,
            bbox_coordinate_system="pdf-points-top-left",
            extraction_tool="x",
            extraction_version="2",
            chunking_strategy="s",
            chunk_version="v2",
            source_attachment_checksum="ck-after",
        )

    stale_view = client.get(f"/papers/{paper_id}/statcheck/cached").json()
    assert stale_view["stale"] is True
    assert stale_view["results"] == original["results"]  # the OLD result, verbatim -- never silently replaced
    assert stale_view["checked"] == original["checked"]

    refreshed = client.post(f"/papers/{paper_id}/statcheck/rescan").json()
    assert refreshed["stale"] is False
    assert client.get(f"/papers/{paper_id}/statcheck/cached").json()["stale"] is False


def test_library_batch_run_warms_the_per_paper_cache(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        flagged_id, _ = _stat_chunk(conn, "Bad Stats", "ck-bad", "We found t(28) = 1.5, p = .04.")
        clean_id, _ = _stat_chunk(conn, "Good Stats", "ck-good", "We found t(28) = 2.10, p = .04.")
    client = TestClient(create_app(db_url=temp_db_url))

    assert client.get(f"/papers/{flagged_id}/statcheck/cached").json()["cached"] is False
    job_id = client.post("/methods/statcheck/run").json()["job_id"]
    for _ in range(30):
        result = client.get(f"/methods/statcheck/run/{job_id}").json()
        if result["status"] in ("done", "error"):
            break
    assert result["status"] == "done", result

    flagged_cached = client.get(f"/papers/{flagged_id}/statcheck/cached").json()
    assert flagged_cached["cached"] is True
    assert flagged_cached["decision_errors"] == 1

    clean_cached = client.get(f"/papers/{clean_id}/statcheck/cached").json()
    assert clean_cached["cached"] is True  # a clean (non-flagged) paper is warmed too, not just flagged ones
    assert clean_cached["checked"] == 1
    assert clean_cached["inconsistent"] == 0 and clean_cached["decision_errors"] == 0

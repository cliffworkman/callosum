"""TOP Factor local mirror (backlog #40) — the download-parse-replace-query chain, mirroring
tests/test_retraction_watch.py's structure. The CSV header is built from TOP_FACTOR_CATEGORIES itself (the same
list the parser uses) rather than hand-typed, so the test can't silently drift from the real confirmed column
names."""

from __future__ import annotations

from app.backend.persistence.database import make_engine
from app.backend.persistence.top_factor_repo import (
    lookup_top_factor_record,
    replace_top_factor_records,
    top_factor_db_status,
)
from integrations.top_factor.adapter import (
    TOP_FACTOR_CATEGORIES,
    TopFactorClient,
    download_top_factor_database,
    parse_top_factor_csv,
)


def _header() -> str:
    cols = ["Journal", "Issn", "Eissn", "Description", "Publisher", "Societies", "Author guideline url"]
    for name, _ in TOP_FACTOR_CATEGORIES:
        cols += [f"{name} score", f"{name} justification"]
    cols.append("Total")
    return ",".join(cols)


def _row(*, journal, issn="", eissn="", scores=None, total="") -> str:
    """`scores` is a dict of {category_name: raw_score_string} — omitted categories get empty cells."""
    scores = scores or {}
    cells = [journal, issn, eissn, "desc", "", "", "http://x"]
    for name, _ in TOP_FACTOR_CATEGORIES:
        cells += [str(scores.get(name, "")), ""]
    cells.append(str(total))
    return ",".join(cells)


FAKE_CSV = "\n".join(
    [
        _header(),
        _row(journal="Issn Only", issn="0040-5736", scores={"Data citation": "1"}, total="1"),
        _row(journal="Eissn Only", eissn="1234-5678", scores={"Data transparency": "2"}, total="2"),
        _row(journal="Both", issn="0037-7686", eissn="0037-7687", scores={"Replication": "3"}, total="3"),
        _row(journal="Neither -- skipped", issn="", eissn="", total="9"),
        _row(journal="Malformed score", issn="1111-1111", scores={"Data citation": "not-a-number"}, total="0"),
        _row(
            journal="Malformed total", issn="2222-2222", scores={"Data citation": "2", "Replication": "1"}, total="oops"
        ),
    ]
)


def test_parse_maps_categories_and_skips_rows_without_any_issn():
    records = parse_top_factor_csv(FAKE_CSV)
    by_issn = {r["issn"] or r["eissn"]: r for r in records}
    assert set(by_issn) == {"0040-5736", "1234-5678", "0037-7686", "1111-1111", "2222-2222"}  # "Neither" skipped

    issn_only = by_issn["0040-5736"]
    assert issn_only["issn"] == "0040-5736" and issn_only["eissn"] is None
    assert issn_only["total"] == 1
    assert {"name": "Data citation", "score": 1, "max": 3, "justification": None} in issn_only["categories"]

    eissn_only = by_issn["1234-5678"]
    assert eissn_only["issn"] is None and eissn_only["eissn"] == "1234-5678"

    both = by_issn["0037-7686"]
    assert both["issn"] == "0037-7686" and both["eissn"] == "0037-7687"


def test_malformed_score_cell_omits_category_not_fabricates_zero():
    records = parse_top_factor_csv(FAKE_CSV)
    row = next(r for r in records if r["issn"] == "1111-1111")
    names = {c["name"] for c in row["categories"]}
    assert "Data citation" not in names  # the malformed cell is omitted, never silently coerced to 0
    assert row["total"] == 0  # Total cell itself parsed cleanly here


def test_malformed_total_cell_is_derived_from_summed_category_scores():
    records = parse_top_factor_csv(FAKE_CSV)
    row = next(r for r in records if r["issn"] == "2222-2222")
    assert row["total"] == 3  # "oops" -> derived: 2 (Data citation) + 1 (Replication)


def test_replace_and_lookup_by_issn_or_eissn(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        replace_top_factor_records(conn, parse_top_factor_csv(FAKE_CSV), retrieved_at="2026-03-12T00:00:00Z")
        by_issn = lookup_top_factor_record(conn, "0040-5736")
        by_eissn = lookup_top_factor_record(conn, "1234-5678")
        miss = lookup_top_factor_record(conn, "9999-9999")
        status = top_factor_db_status(conn)
    engine.dispose()
    assert by_issn == {
        "total": 1,
        "categories": [{"name": "Data citation", "score": 1, "max": 3, "justification": None}],
    }
    assert by_eissn is not None and by_eissn["total"] == 2
    assert miss is None
    assert status["count"] == 5 and status["retrieved_at"] == "2026-03-12T00:00:00Z"


def test_top_factor_db_status_reports_never_downloaded_then_counts(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        never = top_factor_db_status(conn)
        replace_top_factor_records(conn, parse_top_factor_csv(FAKE_CSV), retrieved_at="t1")
        after = top_factor_db_status(conn)
    engine.dispose()
    assert never == {"count": 0, "retrieved_at": None}  # the exact ambiguity build_profiles resolves at report level
    assert after["count"] == 5 and after["retrieved_at"] == "t1"


def test_replace_is_authoritative(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        replace_top_factor_records(conn, parse_top_factor_csv(FAKE_CSV), retrieved_at="t1")
        smaller = _header() + "\n" + _row(journal="Only one now", issn="0040-5736", total="1")
        replace_top_factor_records(conn, parse_top_factor_csv(smaller), retrieved_at="t2")
        gone = lookup_top_factor_record(conn, "0037-7686")
        kept = lookup_top_factor_record(conn, "0040-5736")
        status = top_factor_db_status(conn)
    engine.dispose()
    assert gone is None and kept is not None
    assert status["count"] == 1 and status["retrieved_at"] == "t2"


def test_download_with_injected_fetcher(temp_db_url):
    def fake(url, *, timeout, max_bytes):
        assert url.startswith("https://osf.io/")
        return FAKE_CSV

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        n = download_top_factor_database(TopFactorClient(fetcher=fake), conn)
        status = top_factor_db_status(conn)
    engine.dispose()
    assert n == 5
    assert status["count"] == 5 and status["retrieved_at"]


# ---- the refresh endpoint (offline) -------------------------------------------

from fastapi.testclient import TestClient  # noqa: E402

from app.backend.api import create_app  # noqa: E402


def test_refresh_endpoint_and_status(temp_db_url):
    def fake(url, *, timeout, max_bytes):
        return FAKE_CSV

    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.top_factor_client = TopFactorClient(fetcher=fake)

    pre = client.get("/methods/top-factor/database").json()
    assert pre["count"] == 0 and pre["retrieved_at"] is None

    run = client.post("/methods/top-factor/database/refresh")
    assert run.status_code == 202
    done = client.get(f"/methods/top-factor/database/refresh/{run.json()['job_id']}").json()
    assert done["status"] == "done" and done["count"] == 5

    post = client.get("/methods/top-factor/database").json()
    assert post["count"] == 5 and post["retrieved_at"]


def test_refresh_job_404_for_unknown_id(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/methods/top-factor/database/refresh/nope").status_code == 404

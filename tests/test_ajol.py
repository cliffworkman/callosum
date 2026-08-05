"""AJOL local mirror (backlog #40, inc 451) -- the download-parse-replace-query chain, mirroring
tests/test_top_factor.py's structure. The CSV header matches the real confirmed AJOL Zenodo dataset columns
(source_id,source_url,source_title,eissn,issn_print,is_diamond,jjps_status,country) so the test can't silently
drift from the real confirmed column names -- including the real file's own typo (jjps_status, not jpps_status)."""

from __future__ import annotations

from app.backend.persistence.ajol_repo import ajol_db_status, lookup_ajol_record, replace_ajol_records
from app.backend.persistence.database import make_engine
from integrations.ajol.adapter import (
    AJOL_SNAPSHOT_DATE,
    AjolClient,
    download_ajol_database,
    parse_ajol_csv,
)

_HEADER = "source_id,source_url,source_title,eissn,issn_print,is_diamond,jjps_status,country"


def _row(
    *,
    source_id="1",
    source_url="https://www.ajol.info/index.php/x",
    title="A Journal",
    eissn="",
    issn_print="",
    is_diamond="1",
    jjps="1 Star",
    country="Nigeria",
):
    return ",".join([source_id, source_url, title, eissn, issn_print, is_diamond, jjps, country])


FAKE_CSV = "\n".join(
    [
        _HEADER,
        _row(source_id="1", eissn="2789-1895", issn_print="2958-3101", jjps="1 Star", country="Libya"),
        _row(source_id="2", eissn="2795-3726", issn_print="", jjps="2 Stars", country="Nigeria"),
        _row(source_id="3", eissn="", issn_print="2756-6811", jjps="3 Stars", country="Nigeria"),
        _row(source_id="4", eissn="NA", issn_print="NA", jjps="Pending", country="Ghana"),  # both missing (NA marker)
        _row(
            source_id="5", eissn="2616-4728", issn_print="2616-471X", jjps="Ceased", country="Ethiopia", is_diamond="0"
        ),
        _row(
            source_id="6",
            eissn="2734-3898",
            issn_print="0795-2384",
            jjps="Inactive Title",
            country="Nigeria",
            is_diamond="bogus",
        ),
        _row(
            source_id="7",
            eissn="1111-1111",
            issn_print="2222-2222",
            jjps="No Stars",
            country="Kenya",
            source_url="https://evil.example.com/notajol",
        ),  # untrusted source_url outside the AJOL prefix
    ]
)


def test_parse_maps_fields_and_skips_rows_with_no_issn():
    records = parse_ajol_csv(FAKE_CSV)
    by_issn = {r["issn"] or r["eissn"]: r for r in records}
    assert "1" not in by_issn  # source_id "4" (both eissn/issn_print == "NA") must be skipped entirely
    assert len(records) == 6  # 7 rows minus the one all-NA row

    libya = by_issn["2958-3101"]
    assert libya["eissn"] == "2789-1895" and libya["issn"] == "2958-3101"
    assert libya["journal"] == "A Journal" and libya["country"] == "Libya"
    assert libya["jpps_status"] == "1 Star"  # stored under the correct term, not the CSV's typo'd column name
    assert libya["is_diamond"] is True

    eissn_only = by_issn["2795-3726"]
    assert eissn_only["issn"] is None and eissn_only["eissn"] == "2795-3726"

    issn_only = by_issn["2756-6811"]
    assert issn_only["eissn"] is None and issn_only["issn"] == "2756-6811"


def test_NA_marker_treated_as_missing_not_a_bogus_issn_key():
    """Regression test: the real CSV encodes a missing ISSN as the literal string "NA", not an empty cell (11 of
    739 real rows have BOTH eissn and issn_print == "NA"). A naive empty-string-only check would store "NA" as a
    bogus matchable ISSN key shared across every such row."""
    records = parse_ajol_csv(FAKE_CSV)
    assert not any(r["issn"] == "NA" or r["eissn"] == "NA" for r in records)


def test_malformed_is_diamond_cell_is_none_not_fabricated_false():
    records = parse_ajol_csv(FAKE_CSV)
    row = next(r for r in records if r["issn"] == "0795-2384")
    assert row["is_diamond"] is None  # "bogus" is malformed -- unknown, never coerced to False
    ceased = next(r for r in records if r["issn"] == "2616-471X")
    assert ceased["is_diamond"] is False  # a real "0" cell parses cleanly
    assert ceased["jpps_status"] == "Ceased"  # cautionary statuses pass through plainly, never filtered


def test_source_url_outside_ajol_prefix_is_dropped():
    records = parse_ajol_csv(FAKE_CSV)
    row = next(r for r in records if r["issn"] == "2222-2222")
    assert row["source_url"] is None  # untrusted external data (rule #4) -- only ajol.info URLs are kept


def test_replace_and_lookup_by_issn_or_eissn(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        replace_ajol_records(conn, parse_ajol_csv(FAKE_CSV), retrieved_at="2026-08-05T00:00:00Z")
        by_issn = lookup_ajol_record(conn, "2958-3101")
        by_eissn = lookup_ajol_record(conn, "2795-3726")
        miss = lookup_ajol_record(conn, "9999-9999")
        status = ajol_db_status(conn)
    engine.dispose()
    assert by_issn == {
        "country": "Libya",
        "jpps_status": "1 Star",
        "is_diamond": True,
        "source_url": "https://www.ajol.info/index.php/x",
    }
    assert by_eissn is not None and by_eissn["jpps_status"] == "2 Stars"
    assert miss is None
    assert status["count"] == 6 and status["retrieved_at"] == "2026-08-05T00:00:00Z"


def test_ajol_db_status_reports_never_downloaded_then_counts(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        never = ajol_db_status(conn)
        replace_ajol_records(conn, parse_ajol_csv(FAKE_CSV), retrieved_at="t1")
        after = ajol_db_status(conn)
    engine.dispose()
    assert never == {"count": 0, "retrieved_at": None}  # the exact ambiguity build_profiles resolves at report level
    assert after["count"] == 6 and after["retrieved_at"] == "t1"


def test_replace_is_authoritative(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        replace_ajol_records(conn, parse_ajol_csv(FAKE_CSV), retrieved_at="t1")
        smaller = _HEADER + "\n" + _row(source_id="1", eissn="2789-1895", issn_print="2958-3101")
        replace_ajol_records(conn, parse_ajol_csv(smaller), retrieved_at="t2")
        gone = lookup_ajol_record(conn, "2756-6811")
        kept = lookup_ajol_record(conn, "2958-3101")
        status = ajol_db_status(conn)
    engine.dispose()
    assert gone is None and kept is not None
    assert status["count"] == 1 and status["retrieved_at"] == "t2"


def test_download_with_injected_fetcher(temp_db_url):
    def fake(url, *, timeout, max_bytes):
        assert url.startswith("https://zenodo.org/")
        return FAKE_CSV

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        n = download_ajol_database(AjolClient(fetcher=fake), conn)
        status = ajol_db_status(conn)
    engine.dispose()
    assert n == 6
    assert status["count"] == 6 and status["retrieved_at"]


# ---- the refresh endpoint (offline) -------------------------------------------

from fastapi.testclient import TestClient  # noqa: E402

from app.backend.api import create_app  # noqa: E402


def test_refresh_endpoint_and_status(temp_db_url):
    def fake(url, *, timeout, max_bytes):
        return FAKE_CSV

    client = TestClient(create_app(db_url=temp_db_url))
    client.app.state.ajol_client = AjolClient(fetcher=fake)

    pre = client.get("/methods/ajol/database").json()
    assert pre["count"] == 0 and pre["retrieved_at"] is None
    assert pre["snapshot_date"] == AJOL_SNAPSHOT_DATE  # always present, even before any download

    run = client.post("/methods/ajol/database/refresh")
    assert run.status_code == 202
    done = client.get(f"/methods/ajol/database/refresh/{run.json()['job_id']}").json()
    assert done["status"] == "done" and done["count"] == 6

    post = client.get("/methods/ajol/database").json()
    assert post["count"] == 6 and post["retrieved_at"]
    assert post["snapshot_date"] == AJOL_SNAPSHOT_DATE  # the fixed data vintage, never confused with retrieved_at


def test_refresh_job_404_for_unknown_id(temp_db_url):
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/methods/ajol/database/refresh/nope").status_code == 404

from __future__ import annotations

import pytest

from app.backend.persistence.database import make_engine
from app.backend.persistence.retraction_repo import (
    lookup_retraction_record,
    replace_retraction_records,
    retraction_db_status,
)
from integrations.retraction_watch.adapter import (
    RetractionWatchClient,
    RetractionWatchUnavailable,
    download_retraction_database,
    parse_retraction_csv,
)

# A representative Retraction Watch CSV (real-ish headers). Rows: a Retraction (+reason+notice), a Correction,
# an Expression of concern, a Reinstatement (must be SKIPPED — an un-retraction is not a finding), a no-DOI row
# (skipped), and a 2nd notice for the same original DOI as row 1 but a milder nature (most-severe must win).
FAKE_CSV = (
    "RecordID,Title,OriginalPaperDOI,RetractionDOI,RetractionNature,RetractionDate,Reason,URLS\n"
    "1,Bad Paper,10.1/Orig,10.1/Notice,Retraction,2021-03-15,+Falsification/Fabrication of Data,https://x\n"
    "2,Fix Paper,10.2/orig,10.2/notice,Correction,2020-01-01,+Error in Data,\n"
    "3,Concern Paper,10.3/orig,10.3/notice,Expression of concern,2019-06-01,,\n"
    "4,Back Paper,10.4/orig,10.4/notice,Reinstatement,2022-01-01,,\n"
    "5,No DOI,,10.5/notice,Retraction,2021-01-01,,\n"
    "6,Bad Paper (corr too),10.1/orig,10.1/corr,Correction,2020-02-02,+Error,\n"
)


def test_parse_maps_natures_and_skips_reinstatement_and_no_doi():
    records = parse_retraction_csv(FAKE_CSV)
    by_doi = {}
    for r in records:
        by_doi.setdefault(r["original_doi"], []).append(r)
    assert set(by_doi) == {"10.1/orig", "10.2/orig", "10.3/orig"}  # reinstatement + no-DOI dropped; DOI normalized
    retr = next(r for r in records if r["original_doi"] == "10.1/orig" and r["status"] == "retracted")
    assert "Falsification" in retr["reason"]
    assert retr["date"] == "2021-03-15"
    assert retr["notice_doi"] == "10.1/notice" and retr["notice_url"] == "https://doi.org/10.1/notice"
    assert next(r for r in records if r["original_doi"] == "10.2/orig")["status"] == "correction"
    assert next(r for r in records if r["original_doi"] == "10.3/orig")["status"] == "concern"


def test_replace_and_lookup_picks_most_severe(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        replace_retraction_records(conn, parse_retraction_csv(FAKE_CSV), retrieved_at="2026-06-26T00:00:00Z")
        hit = lookup_retraction_record(conn, "10.1/ORIG")  # 2 rows (retraction + correction) → retraction wins
        miss = lookup_retraction_record(conn, "10.9/none")
        status = retraction_db_status(conn)
    engine.dispose()
    assert hit["status"] == "retracted" and "Falsification" in hit["reason"]
    assert miss is None
    assert status["count"] == 4 and status["retrieved_at"] == "2026-06-26T00:00:00Z"  # 4 rows stored (1+1+1+1)


def test_replace_is_authoritative_removes_withdrawn(temp_db_url):
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        replace_retraction_records(conn, parse_retraction_csv(FAKE_CSV), retrieved_at="t1")
        # a later download no longer lists 10.1/orig → it must disappear
        smaller = "OriginalPaperDOI,RetractionNature,RetractionDate\n10.2/orig,Correction,2020-01-01\n"
        replace_retraction_records(conn, parse_retraction_csv(smaller), retrieved_at="t2")
        gone = lookup_retraction_record(conn, "10.1/orig")
        kept = lookup_retraction_record(conn, "10.2/orig")
        status = retraction_db_status(conn)
    engine.dispose()
    assert gone is None and kept is not None
    assert status["count"] == 1 and status["retrieved_at"] == "t2"


def test_download_with_injected_fetcher(temp_db_url):
    def fake(url, *, timeout, max_bytes):
        assert "x@y.z" in url  # the mailto is in the query
        return FAKE_CSV

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        n = download_retraction_database(RetractionWatchClient(fetcher=fake, mailto="x@y.z"), conn)
        status = retraction_db_status(conn)
    engine.dispose()
    assert n == 4  # 4 stored rows (the 3 distinct DOIs + the 2nd 10.1 notice)
    assert status["count"] == 4 and status["retrieved_at"]


def test_mailto_absent_fails_closed():
    client = RetractionWatchClient(fetcher=lambda *a, **k: "")
    client.mailto = None  # force absent regardless of env
    with pytest.raises(RetractionWatchUnavailable):
        client.fetch_csv()

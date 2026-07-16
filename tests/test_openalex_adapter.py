"""Tests for the OpenAlex OA-location adapter — hermetic (injected fetcher; no real network)."""

from __future__ import annotations

import sqlite3

from sqlalchemy.exc import OperationalError

from app.backend.acquisition.registry import PaperRef
from app.backend.persistence.database import make_engine
from integrations.api_cache import put_cached
from integrations.openalex import OpenAlexClient
from integrations.openalex.adapter import OPENALEX_PROVIDER


def _work(oa_status, *, version="publishedVersion", pdf_url="https://example.org/x.pdf", license_="cc-by"):
    return {
        "open_access": {"oa_status": oa_status},
        "best_oa_location": {
            "pdf_url": pdf_url,
            "version": version,
            "landing_page_url": "https://example.org/x",
            "license": license_,
        },
    }


class _Fetcher:
    def __init__(self, body, status=200):
        self.body = body
        self.status = status
        self.calls = 0

    def __call__(self, path, *, params, headers, timeout):
        self.calls += 1
        return self.status, self.body


def _client(body, status=200):
    return OpenAlexClient(fetcher=_Fetcher(body, status), mailto="test@example.org")


def test_gold_published_maps_to_gold_vor(temp_db_url):
    client = _client(_work("gold"))
    with make_engine(temp_db_url).begin() as conn:
        loc = client.lookup_best_oa(conn, PaperRef(doi="10.1/x"))
    assert loc is not None
    assert loc.oa_color == "gold" and loc.version == "vor" and loc.source == "openalex"
    assert loc.bronze_unstable is False
    assert loc.pdf_url == "https://example.org/x.pdf"


def test_bronze_is_flagged_unstable(temp_db_url):
    client = _client(_work("bronze"))
    with make_engine(temp_db_url).begin() as conn:
        loc = client.lookup_best_oa(conn, PaperRef(doi="10.1/x"))
    assert loc is not None and loc.oa_color == "bronze" and loc.bronze_unstable is True


def test_green_accepted_maps_to_green_am(temp_db_url):
    client = _client({"results": [_work("green", version="acceptedVersion")]})
    with make_engine(temp_db_url).begin() as conn:
        loc = client.lookup_best_oa(conn, PaperRef(title="Some Title"))
    assert loc is not None and loc.oa_color == "green" and loc.version == "am"


def test_closed_returns_none(temp_db_url):
    client = _client(_work("closed"))
    with make_engine(temp_db_url).begin() as conn:
        assert client.lookup_best_oa(conn, PaperRef(doi="10.1/x")) is None


def test_no_pdf_url_returns_none(temp_db_url):
    body = {"open_access": {"oa_status": "gold"}, "best_oa_location": {"version": "publishedVersion"}}
    client = _client(body)
    with make_engine(temp_db_url).begin() as conn:
        assert client.lookup_best_oa(conn, PaperRef(doi="10.1/x")) is None


def test_non_https_pdf_url_returns_none(temp_db_url):
    client = _client(_work("gold", pdf_url="http://insecure.example.org/x.pdf"))
    with make_engine(temp_db_url).begin() as conn:
        assert client.lookup_best_oa(conn, PaperRef(doi="10.1/x")) is None


def test_caches_response(temp_db_url):
    fetcher = _Fetcher(_work("gold"))
    client = OpenAlexClient(fetcher=fetcher, mailto="t@e.org")
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        assert client.lookup_best_oa(conn, PaperRef(doi="10.1/x")) is not None
    with engine.begin() as conn:
        assert client.lookup_best_oa(conn, PaperRef(doi="10.1/x")) is not None
    assert fetcher.calls == 1  # second lookup served from external_api_cache


def test_fail_closed_on_fetcher_exception(temp_db_url):
    class _Boom:
        def __call__(self, path, *, params, headers, timeout):
            raise RuntimeError("network down")

    client = OpenAlexClient(fetcher=_Boom(), mailto="t@e.org")
    with make_engine(temp_db_url).begin() as conn:
        assert client.lookup_best_oa(conn, PaperRef(doi="10.1/x")) is None  # never raises


def test_cache_write_lock_is_nonfatal():
    class _Result:
        def mappings(self):
            return self

        def first(self):
            return None

    class _LockedConn:
        def execute(self, statement):
            if statement.__class__.__name__ == "Select":
                return _Result()
            raise OperationalError("INSERT", (), sqlite3.OperationalError("database is locked"))

    put_cached(
        _LockedConn(),
        OPENALEX_PROVIDER,
        "work:W1",
        request_json={"work_id": "W1"},
        response_json={"id": "https://openalex.org/W1"},
        status_code=200,
    )

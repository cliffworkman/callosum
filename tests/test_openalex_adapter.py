"""Tests for the OpenAlex OA-location adapter — hermetic (injected fetcher; no real network)."""

from __future__ import annotations

import sqlite3

import httpx
from sqlalchemy.exc import OperationalError

from app.backend.acquisition.registry import PaperRef
from app.backend.persistence.database import make_engine
from app.backend.persistence.schema import external_api_cache
from integrations.api_cache import put_cached
from integrations.openalex import OpenAlexClient
from integrations.openalex.adapter import OPENALEX_PROVIDER
from integrations.openalex.request import bounded_openalex_get


def _work(oa_status, *, version="publishedVersion", pdf_url="https://example.org/x.pdf", license_="cc-by"):
    return {
        "title": "Some Title",
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


def test_title_search_rejects_an_unrelated_first_result(temp_db_url):
    client = _client({"results": [{**_work("green"), "title": "Completely unrelated evidence"}]})
    with make_engine(temp_db_url).begin() as conn:
        assert client.lookup_best_oa(conn, PaperRef(title="Some Title")) is None


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


def test_cached_transient_error_is_retried_instead_of_replayed(temp_db_url):
    fetcher = _Fetcher(_work("gold"))
    client = OpenAlexClient(fetcher=fetcher, mailto="t@e.org")
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        put_cached(
            conn,
            OPENALEX_PROVIDER,
            "doi:10.1/x",
            request_json={"path": "/doi:10.1/x"},
            response_json={"error": "rate limited"},
            status_code=429,
        )
        assert client.lookup_best_oa(conn, PaperRef(doi="10.1/x")) is not None
        cached = (
            conn.execute(
                external_api_cache.select().where(
                    external_api_cache.c.provider == OPENALEX_PROVIDER,
                    external_api_cache.c.cache_key == "doi:10.1/x",
                )
            )
            .mappings()
            .one()
        )
    assert fetcher.calls == 1 and cached["status_code"] == 200


def test_openalex_key_and_current_client_identity_are_sent_but_not_cached(temp_db_url, monkeypatch):
    monkeypatch.setenv("CALLOSUM_OPENALEX_API_KEY", "test-only-secret")
    seen = {}

    def fetcher(path, *, params, headers, timeout):
        seen.update({"params": params, "headers": headers})
        return 200, _work("gold")

    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        assert OpenAlexClient(fetcher=fetcher, mailto="test@example.org").lookup_best_oa(conn, PaperRef(doi="10.1/x"))
        cached = conn.execute(external_api_cache.select()).mappings().one()
    assert seen["params"]["api_key"] == "test-only-secret"
    assert seen["params"]["mailto"] == "test@example.org"
    assert seen["headers"]["User-Agent"].startswith("Callosum/0.5.2")
    assert "test-only-secret" not in str(cached["request_json"])


def test_openalex_transport_retries_429_with_retry_after(monkeypatch):
    responses = iter(
        (
            httpx.Response(429, headers={"Retry-After": "1.5"}, request=httpx.Request("GET", "https://x")),
            httpx.Response(200, json={"ok": True}, request=httpx.Request("GET", "https://x")),
        )
    )
    calls = []
    monkeypatch.setattr("integrations.openalex.request.bounded_get", lambda *args, **kwargs: next(responses))

    response = bounded_openalex_get(
        "https://api.openalex.org/works",
        params={},
        headers={},
        timeout=1,
        sleep=calls.append,
    )

    assert response.status_code == 200
    assert calls == [1.5]


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

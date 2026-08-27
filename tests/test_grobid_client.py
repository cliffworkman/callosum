from __future__ import annotations

import httpx
import pytest

from integrations.grobid.client import GrobidError, parse_fulltext


def test_parse_fulltext_happy_path():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/processFulltextDocument"
        # teiCoordinates should be in the multipart form body, not URL
        assert b"teiCoordinates" in request.content
        assert b"div" in request.content
        assert b"head" in request.content
        assert b"p" in request.content
        return httpx.Response(200, content=b"<TEI>ok</TEI>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = parse_fulltext(b"%PDF-fake-bytes", "http://127.0.0.1:8070", timeout=5.0, client=client)
    assert result == b"<TEI>ok</TEI>"


def test_parse_fulltext_refuses_compressed_responses():
    # Observed live: under heavy load GROBID returned a response whose Content-Encoding claimed gzip but whose
    # body was truncated/corrupted, raising "Error -3 while decompressing data: incorrect header check" from
    # httpx's own streaming decoder. Asking for identity encoding removes that whole failure class.
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["accept-encoding"] == "identity"
        return httpx.Response(200, content=b"<TEI>ok</TEI>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = parse_fulltext(b"bytes", "http://127.0.0.1:8070", timeout=5.0, client=client)
    assert result == b"<TEI>ok</TEI>"


def test_parse_fulltext_connection_error_raises_grobid_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(GrobidError):
        parse_fulltext(b"bytes", "http://127.0.0.1:8070", timeout=5.0, client=client)


def test_parse_fulltext_non_200_raises_grobid_error():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500, content=b"internal error")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(GrobidError):
        parse_fulltext(b"bytes", "http://127.0.0.1:8070", timeout=5.0, client=client)
    # 500 is treated as likely-permanent -- no retry loop, exactly one attempt.
    assert len(calls) == 1


def test_parse_fulltext_retries_503_then_succeeds():
    # backlog #58: a real bulk parse run 503'd on every paper -- GROBID's own internal engine pool was
    # momentarily exhausted, not a crash. 503 specifically means "try again shortly."
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) < 3:
            return httpx.Response(503, content=b"pool exhausted")
        return httpx.Response(200, content=b"<TEI>ok</TEI>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = parse_fulltext(b"bytes", "http://127.0.0.1:8070", timeout=5.0, client=client, retry_backoff_seconds=0.001)
    assert result == b"<TEI>ok</TEI>"
    assert len(calls) == 3


def test_parse_fulltext_503_exhausts_retries_and_raises():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(503, content=b"pool exhausted")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(GrobidError, match="503"):
        parse_fulltext(
            b"bytes",
            "http://127.0.0.1:8070",
            timeout=5.0,
            client=client,
            max_retries=1,
            retry_backoff_seconds=0.001,
        )
    # One initial attempt + one retry = 2 total calls before giving up.
    assert len(calls) == 2


def test_parse_fulltext_timeout_raises_grobid_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(GrobidError):
        parse_fulltext(b"bytes", "http://127.0.0.1:8070", timeout=5.0, client=client)


def test_parse_fulltext_oversized_response_raises_grobid_error_not_response_too_large():
    # backlog #56: an oversized GROBID response must fail closed as this module's own GrobidError
    # (never leak the shared http_bounds.ResponseTooLargeError type across the module boundary).
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * (11 * 1024 * 1024))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(GrobidError):
        parse_fulltext(b"bytes", "http://127.0.0.1:8070", timeout=5.0, client=client)

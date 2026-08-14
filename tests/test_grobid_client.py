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


def test_parse_fulltext_connection_error_raises_grobid_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(GrobidError):
        parse_fulltext(b"bytes", "http://127.0.0.1:8070", timeout=5.0, client=client)


def test_parse_fulltext_non_200_raises_grobid_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"internal error")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(GrobidError):
        parse_fulltext(b"bytes", "http://127.0.0.1:8070", timeout=5.0, client=client)


def test_parse_fulltext_timeout_raises_grobid_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(GrobidError):
        parse_fulltext(b"bytes", "http://127.0.0.1:8070", timeout=5.0, client=client)

from __future__ import annotations

import gzip

import httpx
import pytest

from integrations.http_bounds import ResponseTooLargeError, bounded_get, bounded_post


def _client_returning(body: bytes, *, status_code: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, content=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_bounded_get_returns_response_when_under_cap() -> None:
    client = _client_returning(b"small body")
    response = bounded_get("http://example.test/x", max_bytes=1024, client=client)
    assert response.status_code == 200
    assert response.content == b"small body"


def test_bounded_get_raises_when_over_cap() -> None:
    client = _client_returning(b"x" * 2000)
    with pytest.raises(ResponseTooLargeError):
        bounded_get("http://example.test/x", max_bytes=1024, client=client)


def test_bounded_get_response_supports_json() -> None:
    client = _client_returning(b'{"ok": true}')
    response = bounded_get("http://example.test/x", max_bytes=1024, client=client)
    assert response.json() == {"ok": True}


def test_bounded_get_preserves_status_code_and_headers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, headers={"x-demo": "1"}, content=b"missing")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    response = bounded_get("http://example.test/x", max_bytes=1024, client=client)
    assert response.status_code == 404
    assert response.headers["x-demo"] == "1"


def test_bounded_post_sends_body_and_returns_response_when_under_cap() -> None:
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(200, content=b"posted ok")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    response = bounded_post("http://example.test/x", max_bytes=1024, client=client, data={"a": "1"})
    assert response.status_code == 200
    assert response.content == b"posted ok"
    assert seen_requests[0].method == "POST"


def test_bounded_post_raises_when_over_cap() -> None:
    client = _client_returning(b"y" * 2000)
    with pytest.raises(ResponseTooLargeError):
        bounded_post("http://example.test/x", max_bytes=1024, client=client)


def test_bounded_get_handles_a_compressed_origin_response() -> None:
    """A real bug caught live (not by any prior test, since MockTransport responses here never carried a real
    Content-Encoding before): response.iter_bytes() already transparently decompresses the wire body, so the
    reconstructed Response must not still carry the original Content-Encoding/Content-Length headers, or a
    second decode is attempted against already-plain bytes on the caller's first .json()/.text/.content access
    -- this reproduced against a real Brotli-compressing origin (OpenAlex) and broke every affected metadata
    lookup, not just a rare/transient one."""
    payload = b'{"ok": true, "count": 3}'
    compressed = gzip.compress(payload)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-encoding": "gzip"}, content=compressed)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    response = bounded_get("http://example.test/x", max_bytes=1024, client=client)
    assert "content-encoding" not in response.headers  # stale compression metadata must not survive
    assert response.json() == {"ok": True, "count": 3}  # decodes on first access without a double-decode error


def test_bounded_get_closes_the_client_it_creates_when_none_supplied(monkeypatch) -> None:
    # Exercises the owns_client=True path -- no client kwarg means bounded_get must create its own
    # httpx.Client and close it afterward, never leaking a real connection pool.
    created: list[httpx.Client] = []
    real_client_cls = httpx.Client

    def spy_client(*args, **kwargs):
        client = real_client_cls(
            *args, **kwargs, transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"ok"))
        )
        created.append(client)
        return client

    monkeypatch.setattr(httpx, "Client", spy_client)
    bounded_get("http://example.test/x", max_bytes=1024)

    assert len(created) == 1
    assert created[0].is_closed

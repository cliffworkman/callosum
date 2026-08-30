from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from integrations.mendeley import client as mendeley_client
from integrations.mendeley.client import (
    DOCUMENT_MEDIA,
    FILE_MEDIA,
    FOLDER_MEDIA,
    MAX_PAGE_BYTES,
    MendeleyError,
    MendeleyLibraryClient,
    MendeleyOAuthClient,
    MendeleyOAuthConfig,
)

TOKEN = "access-token"
CLIENT_ID = "12345"
CLIENT_SECRET = "application-secret"
REDIRECT = "http://127.0.0.1:8765/mendeley/callback"


def _http(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def test_oauth_authorize_and_exchange_use_fixed_official_contract_without_secret_in_url_or_body() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_in": 3600,
                "token_type": "bearer",
            },
        )

    client = MendeleyOAuthClient(MendeleyOAuthConfig(CLIENT_ID, CLIENT_SECRET, REDIRECT), http=_http(handler))
    authorize = client.build_authorize_url(state="opaque-state")
    parsed = urlparse(authorize)
    query = parse_qs(parsed.query)
    assert (parsed.scheme, parsed.netloc, parsed.path) == ("https", "api.mendeley.com", "/oauth/authorize")
    assert query == {
        "client_id": [CLIENT_ID],
        "redirect_uri": [REDIRECT],
        "response_type": ["code"],
        "scope": ["all"],
        "state": ["opaque-state"],
    }
    assert CLIENT_SECRET not in authorize

    tokens = client.exchange_code("one-use-code")
    assert tokens.access_token == "new-access" and tokens.refresh_token == "new-refresh"
    assert CLIENT_SECRET not in repr(client.config)
    assert "new-access" not in repr(tokens) and "new-refresh" not in repr(tokens)
    request = requests[0]
    assert str(request.url) == "https://api.mendeley.com/oauth/token"
    assert CLIENT_SECRET.encode() not in request.content
    assert b"grant_type=authorization_code" in request.content
    assert request.headers["authorization"].startswith("Basic ")


def test_oauth_refresh_replaces_token_and_errors_never_echo_secret() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(401, text=f"rejected {CLIENT_SECRET}")

    client = MendeleyOAuthClient(MendeleyOAuthConfig(CLIENT_ID, CLIENT_SECRET, REDIRECT), http=_http(handler))
    with pytest.raises(MendeleyError) as exc:
        client.refresh("old-refresh")
    assert CLIENT_SECRET not in str(exc.value) and "old-refresh" not in str(exc.value)
    assert b"grant_type=refresh_token" in seen[0].content


@pytest.mark.parametrize(
    "redirect",
    [
        "https://127.0.0.1:8765/mendeley/callback",
        "http://0.0.0.0:8765/mendeley/callback",
        "http://example.test/mendeley/callback",
        "http://user:pass@127.0.0.1:8765/mendeley/callback",
        "http://127.0.0.1:8765/mendeley/callback?next=evil",
    ],
)
def test_oauth_config_rejects_non_exact_loopback_redirects(redirect: str) -> None:
    with pytest.raises(ValueError, match="loopback"):
        MendeleyOAuthConfig(CLIENT_ID, CLIENT_SECRET, redirect)


def test_versioned_library_resources_paginate_with_bearer_header_and_expected_queries() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        path = request.url.path
        if path == "/documents" and request.url.params.get("marker") is None:
            return httpx.Response(
                200,
                json=[{"id": "a1", "title": "One"}],
                headers={"Link": '<https://api.mendeley.com/documents?limit=500&view=all&marker=next>; rel="next"'},
            )
        if path == "/documents":
            return httpx.Response(200, json=[{"id": "a2", "title": "Two"}])
        if path == "/folders":
            return httpx.Response(200, json=[{"id": "f1", "name": "Folder"}])
        if path == "/files":
            return httpx.Response(200, json=[{"id": "b1", "document_id": "a1"}])
        if path == "/folders/f1/documents":
            return httpx.Response(200, json=[{"id": "a1"}, {"id": "a2"}])
        raise AssertionError(path)

    client = MendeleyLibraryClient(TOKEN, http=_http(handler))
    assert [row["id"] for row in client.list_documents()] == ["a1", "a2"]
    assert client.list_folders()[0]["name"] == "Folder"
    assert client.list_files()[0]["document_id"] == "a1"
    assert client.list_folder_document_ids("f1") == ("a1", "a2")
    assert [request.headers["accept"] for request in requests] == [
        DOCUMENT_MEDIA,
        DOCUMENT_MEDIA,
        FOLDER_MEDIA,
        FILE_MEDIA,
        DOCUMENT_MEDIA,
    ]
    assert requests[0].url.params["view"] == "all" and requests[0].url.params["limit"] == "500"


@pytest.mark.parametrize(
    "next_url",
    [
        "http://api.mendeley.com/documents?marker=x",
        "https://evil.test/documents?marker=x",
        "https://user:pass@api.mendeley.com/documents?marker=x",
        "https://api.mendeley.com/files?marker=x",
    ],
)
def test_pagination_fails_closed_if_next_link_leaves_exact_resource(next_url: str) -> None:
    client = MendeleyLibraryClient(
        TOKEN,
        http=_http(lambda _request: httpx.Response(200, json=[], headers={"Link": f'<{next_url}>; rel="next"'})),
    )
    with pytest.raises(MendeleyError, match="approved API resource"):
        client.list_documents()


def test_pagination_cycle_and_oversized_page_fail_closed() -> None:
    cycle = "https://api.mendeley.com/documents?limit=500&view=all&marker=again"

    def cycle_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[], headers={"Link": f'<{cycle}>; rel="next"'})

    with pytest.raises(MendeleyError, match="cycle"):
        MendeleyLibraryClient(TOKEN, http=_http(cycle_handler)).list_documents()

    oversized = _http(lambda _request: httpx.Response(200, content=b"x" * (MAX_PAGE_BYTES + 1)))
    with pytest.raises(MendeleyError, match="HTTP 200"):
        MendeleyLibraryClient(TOKEN, http=oversized).list_documents()


def test_collection_item_cap_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mendeley_client, "MAX_DOCUMENTS", 1)
    client = MendeleyLibraryClient(
        TOKEN, http=_http(lambda _request: httpx.Response(200, json=[{"id": "a1"}, {"id": "a2"}]))
    )
    with pytest.raises(MendeleyError, match="1 item safety limit"):
        client.list_documents()


def test_file_download_redirect_is_manual_and_strictly_allowlisted() -> None:
    requests: list[httpx.Request] = []

    def good(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(303, headers={"Location": "https://downloads.mendeley.com/signed-token"})

    client = MendeleyLibraryClient(TOKEN, http=_http(good))
    assert client.file_download_url("abc-123") == "https://downloads.mendeley.com/signed-token"
    assert len(requests) == 1 and requests[0].url.host == "api.mendeley.com"

    bad = MendeleyLibraryClient(
        TOKEN, http=_http(lambda _request: httpx.Response(303, headers={"Location": "https://evil.test/pdf"}))
    )
    with pytest.raises(MendeleyError, match="approved signed-download"):
        bad.file_download_url("abc-123")

    wrong_port = MendeleyLibraryClient(
        TOKEN,
        http=_http(
            lambda _request: httpx.Response(
                303, headers={"Location": "https://downloads.mendeley.com:444/signed-token"}
            )
        ),
    )
    with pytest.raises(MendeleyError, match="approved signed-download"):
        wrong_port.file_download_url("abc-123")


def test_malformed_resource_ids_and_provider_bodies_fail_without_token_leak() -> None:
    client = MendeleyLibraryClient(TOKEN, http=_http(lambda _request: httpx.Response(500, text=TOKEN)))
    with pytest.raises(ValueError, match="resource ID"):
        client.list_folder_document_ids("../../escape")
    with pytest.raises(MendeleyError) as exc:
        client.list_documents()
    assert TOKEN not in str(exc.value)

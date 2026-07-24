from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.backend.api.app import create_app
from app.backend.api.routers import citations as citations_router
from app.backend.citations import style_lifecycle, style_provenance, style_store
from app.backend.citations.style_repository import (
    MAX_CSL_BYTES,
    REPOSITORY_INDEX_URL,
    StyleFetchError,
    _httpx_fetcher,
    _require_public_https,
    install_prepared_style,
    install_repository_style,
    install_style_from_url,
    prepare_repository_style,
    prepare_style_from_url,
    search_repository_styles,
)


def _independent_csl(name: str, title: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<style xmlns="http://purl.org/net/xbiblio/csl" class="in-text" version="1.0">
  <info>
    <title>{title}</title>
    <title-short>{name.upper()}</title-short>
    <id>http://www.zotero.org/styles/{name}</id>
    <link href="http://www.zotero.org/styles/{name}" rel="self"/>
    <updated>2026-07-24T00:00:00+00:00</updated>
    <category citation-format="author-date"/>
    <category field="psychology"/>
  </info>
  <citation>
    <layout prefix="(" suffix=")">
      <names variable="author"><name form="short"/></names>
      <date variable="issued" prefix=", "><date-part name="year"/></date>
    </layout>
  </citation>
  <bibliography>
    <layout suffix="."><text variable="title"/></layout>
  </bibliography>
</style>
"""


def _dependent_csl(name: str, title: str, parent: str) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<style xmlns="http://purl.org/net/xbiblio/csl" version="1.0">
  <info>
    <title>{title}</title>
    <id>http://www.zotero.org/styles/{name}</id>
    <link href="http://www.zotero.org/styles/{name}" rel="self"/>
    <link href="http://www.zotero.org/styles/{parent}" rel="independent-parent"/>
    <updated>2026-07-24T00:00:00+00:00</updated>
  </info>
</style>
"""


def _catalog() -> bytes:
    return json.dumps(
        [
            {
                "title": "Journal of Testing",
                "titleShort": "J Test",
                "name": "journal-of-testing",
                "dependent": 1,
                "categories": {"format": "author-date", "fields": ["psychology", "social_science"]},
                "updated": "2026-07-23 12:00:00",
                "href": "https://www.zotero.org/styles/journal-of-testing",
            },
            {
                "title": "Testing Base",
                "titleShort": "TBASE",
                "name": "testing-base",
                "dependent": 0,
                "categories": {"format": "author-date", "fields": ["psychology"]},
                "updated": "2026-07-22 12:00:00",
                "href": "https://www.zotero.org/styles/testing-base",
            },
        ]
    ).encode()


def _fetcher(mapping: dict[str, bytes]):
    def fetch(url: str, *, timeout: float, max_bytes: int) -> bytes:
        assert timeout > 0
        data = mapping[url]
        assert len(data) <= max_bytes
        return data

    return fetch


def test_repository_search_matches_title_acronym_format_and_field() -> None:
    fetch = _fetcher({REPOSITORY_INDEX_URL: _catalog()})
    assert [row["repository_id"] for row in search_repository_styles("journal test", fetcher=fetch)["styles"]] == [
        "journal-of-testing"
    ]
    assert [row["repository_id"] for row in search_repository_styles("TBASE", fetcher=fetch)["styles"]] == [
        "testing-base"
    ]
    assert len(search_repository_styles("author-date psychology", fetcher=fetch)["styles"]) == 2
    with pytest.raises(ValueError, match="at least 2"):
        search_repository_styles("x", fetcher=fetch)


def test_repository_install_preflights_and_installs_parent_chain() -> None:
    child = _dependent_csl("journal-of-testing", "Journal of Testing", "testing-base").encode()
    parent = _independent_csl("testing-base", "Testing Base").encode()
    fetch = _fetcher(
        {
            REPOSITORY_INDEX_URL: _catalog(),
            "https://www.zotero.org/styles/journal-of-testing": child,
            "https://www.zotero.org/styles/testing-base": parent,
        }
    )
    result = install_repository_style("journal-of-testing", fetcher=fetch)
    assert result["action"] == "installed"
    assert result["style"]["full_title"] == "Journal of Testing"
    assert result["style"]["parent_style"].startswith("custom-testing-base-")
    assert [item["full_title"] for item in result["dependencies"]] == ["Testing Base"]
    assert style_store.style_exists(result["style"]["id"])
    assert style_store.style_exists(result["dependencies"][0]["id"])
    child_source = style_provenance.provenance_for(result["style"]["id"])
    parent_source = style_provenance.provenance_for(result["dependencies"][0]["id"])
    assert child_source["source_type"] == "repository"
    assert child_source["repository_id"] == "journal-of-testing"
    assert parent_source["repository_id"] == "testing-base"


def test_repository_update_check_includes_installed_custom_parent() -> None:
    child = _dependent_csl("journal-of-testing", "Journal of Testing", "testing-base").encode()
    parent = _independent_csl("testing-base", "Testing Base").encode()
    mapping = {
        REPOSITORY_INDEX_URL: _catalog(),
        "https://www.zotero.org/styles/journal-of-testing": child,
        "https://www.zotero.org/styles/testing-base": parent,
    }
    install_repository_style("journal-of-testing", fetcher=_fetcher(mapping))
    mapping["https://www.zotero.org/styles/testing-base"] = parent.replace(
        b'<layout suffix=".">',
        b'<layout prefix="[" suffix="].">',
    )

    prepared = prepare_repository_style(
        "journal-of-testing",
        fetcher=_fetcher(mapping),
        refresh_installed_parents=True,
    )
    assert prepared["action"] == "update_available"
    applied = install_prepared_style(
        prepared["token"],
        mode="repository",
        source="journal-of-testing",
        replace=True,
    )
    assert applied["action"] == "updated"
    assert applied["dependencies"][0]["full_title"] == "Testing Base"


def test_url_install_supports_guarded_dependency_fetch() -> None:
    root_url = "https://styles.example.test/journal.csl"
    parent_url = "https://styles.example.test/testing-base.csl"
    child = _dependent_csl("remote-journal", "Remote Journal", "testing-base").replace(
        "http://www.zotero.org/styles/testing-base",
        parent_url,
    )
    parent = _independent_csl("remote-base", "Remote Base").replace(
        "http://www.zotero.org/styles/remote-base",
        parent_url,
    )
    result = install_style_from_url(
        root_url,
        fetcher=_fetcher({root_url: child.encode(), parent_url: parent.encode()}),
        resolver=lambda host, port: ["93.184.216.34"],
    )
    assert result["action"] == "installed"
    assert result["style"]["full_title"] == "Remote Journal"
    assert result["dependencies"][0]["full_title"] == "Remote Base"
    assert style_provenance.provenance_for(result["style"]["id"])["source_url"] == root_url


def test_remote_preflight_installs_the_exact_cached_candidate_without_refetch() -> None:
    root_url = "https://styles.example.test/prepared.csl"
    xml = _independent_csl("prepared-style", "Prepared Style").encode()
    calls: list[str] = []

    def fetch(url: str, *, timeout: float, max_bytes: int) -> bytes:
        calls.append(url)
        return xml

    prepared = prepare_style_from_url(
        root_url,
        fetcher=fetch,
        resolver=lambda host, port: ["93.184.216.34"],
    )
    assert prepared["action"] == "ready"
    assert not style_store.custom_styles_dir().exists()
    result = install_prepared_style(
        prepared["token"],
        mode="url",
        source=root_url,
    )
    assert result["action"] == "installed"
    assert result["style"]["full_title"] == "Prepared Style"
    assert calls == [root_url]
    assert style_provenance.provenance_for(result["style"]["id"])["source_type"] == "url"


def test_remote_update_check_is_explicit_and_preserves_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_url = "https://styles.example.test/update.csl"
    xml = _independent_csl("update-style", "Update Style").encode()
    installed = install_style_from_url(
        root_url,
        fetcher=_fetcher({root_url: xml}),
        resolver=lambda host, port: ["93.184.216.34"],
    )["style"]
    calls: list[str] = []

    def prepare(url: str, *, refresh_installed_parents: bool = False):
        calls.append(url)
        assert refresh_installed_parents is True
        return {
            "token": "exact-byte-token",
            "action": "update_available",
            "style": {"id": installed["id"], "full_title": installed["full_title"]},
            "dependencies": [],
            "upstream_updated": "2026-07-25T00:00:00+00:00",
        }

    monkeypatch.setattr(style_lifecycle, "prepare_style_from_url", prepare)
    assert calls == []
    checked = style_lifecycle.check_style_update(installed["id"])
    assert calls == [root_url]
    assert checked["status"] == "update_available"
    assert checked["install"]["preflight_token"] == "exact-byte-token"
    assert checked["install"]["body"] == {"url": root_url}
    assert checked["checked_at"]
    assert style_provenance.provenance_for(installed["id"])["last_checked_at"] == checked["checked_at"]


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/style.csl",
        "https://user:secret@example.com/style.csl",
        "https://127.0.0.1/style.csl",
        "https://10.0.0.2/style.csl",
        "https://example.com:8443/style.csl",
        "https://example.com/style.csl#fragment",
    ],
)
def test_url_import_rejects_unsafe_destinations(url: str) -> None:
    with pytest.raises(ValueError):
        _require_public_https(url, resolver=lambda host, port: ["93.184.216.34"])


def test_url_import_rejects_domain_resolving_to_private_address() -> None:
    with pytest.raises(ValueError, match="private or local"):
        _require_public_https("https://styles.example.test/a.csl", resolver=lambda host, port: ["192.168.1.2"])


def test_remote_fetch_revalidates_redirect_destination() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(302, headers={"Location": "https://127.0.0.1/private.csl"})

    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False) as client:
        with pytest.raises(ValueError, match="private or local"):
            _httpx_fetcher(
                "https://styles.example.test/style.csl",
                timeout=5,
                max_bytes=MAX_CSL_BYTES,
                guard=lambda url: _require_public_https(
                    url,
                    resolver=lambda host, port: ["93.184.216.34"],
                ),
                client=client,
            )
    assert calls == ["https://styles.example.test/style.csl"]


def test_remote_fetch_enforces_streamed_size_limit() -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * 11)),
        follow_redirects=False,
    ) as client:
        with pytest.raises(StyleFetchError, match="exceeds"):
            _httpx_fetcher(
                "https://styles.example.test/style.csl",
                timeout=5,
                max_bytes=10,
                guard=lambda url: None,
                client=client,
            )


def test_url_fetch_rejects_private_connected_peer_after_public_dns() -> None:
    class PrivateStream:
        def get_extra_info(self, name: str):
            return ("10.0.0.7", 443) if name == "server_addr" else None

    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                content=b"<style/>",
                extensions={"network_stream": PrivateStream()},
            )
        ),
        follow_redirects=False,
    ) as client:
        with pytest.raises(ValueError, match="connect to a private or local"):
            _httpx_fetcher(
                "https://styles.example.test/style.csl",
                timeout=5,
                max_bytes=MAX_CSL_BYTES,
                guard=lambda url: _require_public_https(
                    url,
                    resolver=lambda host, port: ["93.184.216.34"],
                ),
                client=client,
                require_public_peer=True,
            )


def test_repository_and_url_routes_return_catalog_results(temp_db_url: str, monkeypatch) -> None:
    installed = {
        "action": "installed",
        "style": {"id": "custom-example", "full_title": "Example"},
        "source_url": "https://styles.example.test/example.csl",
        "dependencies": [],
    }
    monkeypatch.setattr(
        citations_router,
        "search_repository_styles",
        lambda query: {
            "styles": [{"repository_id": "example", "title": "Example"}],
            "query": query,
            "result_limit": 60,
            "source": "Zotero Style Repository",
            "attribution_url": "https://citationstyles.org/",
        },
    )
    monkeypatch.setattr(citations_router, "install_repository_style", lambda style_id, replace=False: installed)
    monkeypatch.setattr(citations_router, "install_style_from_url", lambda url, replace=False: installed)
    prepared = {
        "token": "prepared-token",
        "action": "ready",
        "style": {"id": "custom-example", "full_title": "Example"},
        "dependencies": [],
    }
    monkeypatch.setattr(citations_router, "prepare_repository_style", lambda style_id: prepared)
    monkeypatch.setattr(citations_router, "prepare_style_from_url", lambda url: prepared)
    monkeypatch.setattr(
        citations_router,
        "install_prepared_style",
        lambda token, mode, source, replace=False: installed,
    )
    client = TestClient(create_app(db_url=temp_db_url))

    search = client.get("/citations/styles/repository/search", params={"q": "example"})
    assert search.status_code == 200
    assert search.json()["styles"][0]["repository_id"] == "example"
    repository_validation = client.post(
        "/citations/styles/repository/validate",
        json={"repository_id": "example"},
    )
    assert repository_validation.status_code == 200
    assert repository_validation.json()["install"] == prepared
    repository = client.post(
        "/citations/styles/repository/install",
        json={"repository_id": "example", "preflight_token": "prepared-token"},
    )
    assert repository.status_code == 200
    assert repository.json()["install"] == installed
    url_validation = client.post(
        "/citations/styles/url/validate",
        json={"url": "https://styles.example.test/example.csl"},
    )
    assert url_validation.status_code == 200
    assert url_validation.json()["install"] == prepared
    url = client.post(
        "/citations/styles/url/install",
        json={
            "url": "https://styles.example.test/example.csl",
            "preflight_token": "prepared-token",
        },
    )
    assert url.status_code == 200
    assert url.json()["install"] == installed

"""OpenURL institutional link-resolver hand-off (inc 263).

The builder is pure + deterministic (no fixtures). The endpoint tests ride the conftest autouse fixture that
isolates CALLOSUM_SETTINGS_PATH to a per-test tmp file, so setting a resolver base never touches the real store.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

from app.backend.acquisition.openurl import RESOLVER_BASE_MAX_LEN, build_openurl, resolver_base_valid
from app.backend.api import create_app
from app.backend.persistence.database import make_engine
from app.backend.persistence.repository import create_paper

RESOLVER = "https://sfx.library.example.edu/sfx_local"

FULL_CSL = {
    "id": "chen2021",
    "type": "article-journal",
    "title": "Sleep & memory: a review",  # note the & — must be percent-encoded, not a raw separator
    "container-title": "Journal of Sleep",
    "ISSN": ["1234-5678"],
    "volume": "12",
    "issue": "3",
    "page": "101-115",
    "issued": {"date-parts": [[2021, 6, 1]]},
    "author": [{"given": "Mei", "family": "Chen"}, {"given": "Sam", "family": "Okafor"}],
}


def _query(url: str) -> dict[str, list[str]]:
    return parse_qs(urlsplit(url).query)


# ── the pure builder ──────────────────────────────────────────────────────────────────────────────────────


def test_build_openurl_maps_all_fields() -> None:
    url = build_openurl(RESOLVER, FULL_CSL, doi="10.1/abc")
    assert url is not None and url.startswith(RESOLVER + "?")
    q = _query(url)
    assert q["url_ver"] == ["Z39.88-2004"] and q["ctx_ver"] == ["Z39.88-2004"]
    assert q["rft_val_fmt"] == ["info:ofi/fmt:kev:mtx:journal"]
    assert q["rfr_id"] == ["info:sid/callosum"]
    assert q["rft.genre"] == ["article"]
    assert q["rft_id"] == ["info:doi/10.1/abc"]
    assert q["rft.atitle"] == ["Sleep & memory: a review"]  # decoded round-trips → it WAS encoded on the wire
    assert q["rft.jtitle"] == ["Journal of Sleep"]
    assert q["rft.issn"] == ["1234-5678"]
    assert q["rft.volume"] == ["12"] and q["rft.issue"] == ["3"]
    assert q["rft.spage"] == ["101"] and q["rft.epage"] == ["115"]
    assert q["rft.date"] == ["2021"]
    assert q["rft.aulast"] == ["Chen"] and q["rft.aufirst"] == ["Mei"]  # first author only


def test_build_openurl_percent_encodes_dangerous_chars() -> None:
    # A title with query metacharacters + a newline must not break out of the query string.
    url = build_openurl(RESOLVER, {"title": 'a & b = c "d" <e>\nf', "DOI": "10.1/x"})
    assert url is not None
    raw = urlsplit(url).query
    assert "\n" not in raw and " " not in raw  # encoded
    assert "a & b" not in raw  # the raw ampersand is not present as a separator
    assert _query(url)["rft.atitle"] == ['a & b = c "d" <e>\nf']  # but decodes back losslessly


def test_build_openurl_joins_base_that_already_has_query() -> None:
    url = build_openurl(RESOLVER + "?sid=local", {"DOI": "10.1/x", "title": "T"})
    assert url is not None and "?sid=local&" in url
    assert _query(url)["sid"] == ["local"]


def test_build_openurl_book_type_uses_book_fmt_and_btitle() -> None:
    q = _query(build_openurl(RESOLVER, {"type": "book", "title": "A Book", "container-title": "A Series"}))
    assert q["rft_val_fmt"] == ["info:ofi/fmt:kev:mtx:book"]
    assert q["rft.genre"] == ["book"]
    assert q["rft.btitle"] == ["A Series"] and "rft.jtitle" not in q


def test_build_openurl_none_without_doi_or_title() -> None:
    assert build_openurl(RESOLVER, {}) is None
    assert build_openurl(RESOLVER, {"volume": "3"}) is None  # metadata but nothing resolvable
    assert build_openurl(RESOLVER, None) is None


def test_build_openurl_none_on_invalid_base() -> None:
    assert build_openurl("ftp://x/y", {"DOI": "10.1/x"}) is None


def test_resolver_base_valid() -> None:
    assert resolver_base_valid("https://sfx.example.edu/x")
    assert resolver_base_valid("http://localhost:9000/resolve")
    assert not resolver_base_valid("ftp://x/y")
    assert not resolver_base_valid("not-a-url")
    assert not resolver_base_valid("")
    assert not resolver_base_valid(None)
    assert not resolver_base_valid("https://x/" + "a" * RESOLVER_BASE_MAX_LEN)  # over the cap


# ── the endpoint + settings boundary ──────────────────────────────────────────────────────────────────────


def _seed_paper(db_url: str) -> int:
    with make_engine(db_url).begin() as conn:
        return create_paper(
            conn,
            title="Sleep & memory",
            doi="10.1/abc",
            csl_json={"type": "article-journal", "title": "Sleep & memory", "DOI": "10.1/abc"},
        )


def test_library_link_unconfigured_by_default(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    paper_id = _seed_paper(temp_db_url)
    body = client.get(f"/papers/{paper_id}/library-link").json()
    assert body["configured"] is False and body["url"] is None  # opt-in; dormant until a base is set


def test_library_link_built_when_configured(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    paper_id = _seed_paper(temp_db_url)
    assert (
        client.put("/settings", json={"set_openurl_resolver_base": True, "openurl_resolver_base": RESOLVER}).status_code
        == 200
    )
    body = client.get(f"/papers/{paper_id}/library-link").json()
    assert body["configured"] is True
    assert body["url"].startswith(RESOLVER + "?")
    assert _query(body["url"])["rft_id"] == ["info:doi/10.1/abc"]


def test_library_link_404_for_missing_paper(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/papers/99999/library-link").status_code == 404


def test_settings_resolver_base_roundtrip_and_validation(temp_db_url: str) -> None:
    client = TestClient(create_app(db_url=temp_db_url))
    assert client.get("/settings").json()["openurl_resolver_base"] == ""
    # a non-http scheme is rejected at the boundary
    assert (
        client.put(
            "/settings", json={"set_openurl_resolver_base": True, "openurl_resolver_base": "ftp://x/y"}
        ).status_code
        == 422
    )
    # a valid base round-trips, and clearing empties it
    client.put("/settings", json={"set_openurl_resolver_base": True, "openurl_resolver_base": RESOLVER})
    assert client.get("/settings").json()["openurl_resolver_base"] == RESOLVER
    client.put("/settings", json={"set_openurl_resolver_base": True, "openurl_resolver_base": ""})
    assert client.get("/settings").json()["openurl_resolver_base"] == ""

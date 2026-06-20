"""Hermetic tests for the Increment-B OA resolver sources (DOAJ, Europe PMC, Crossref-OA, CORE, arXiv,
bioRxiv, OSF) + the cascade. Every adapter is driven by an injected fetcher — no real network.

The throughline: each source returns an ``OaLocation`` ONLY when the source's own data asserts an
authorized OA copy with a real https PDF; otherwise None. No source guesses OA, and none fetches a bare URL.
"""

from __future__ import annotations

import pytest

from app.backend.acquisition.registry import OaLocation, PaperRef, ResolverRegistry, build_default_registry
from app.backend.persistence.database import make_engine
from integrations.arxiv import ArxivClient
from integrations.biorxiv import BiorxivClient
from integrations.core import CoreClient
from integrations.crossref.adapter import CrossrefClient
from integrations.crossref.oa import crossref_oa_location
from integrations.doaj import DoajClient
from integrations.europepmc import EuropePmcClient
from integrations.osf import OsfClient


def _conn(temp_db_url):
    return make_engine(temp_db_url).begin()


# --- DOAJ (gold) ------------------------------------------------------------------------------------------


class _DoajFetcher:
    def __init__(self, body, status=200):
        self.body, self.status, self.calls = body, status, 0

    def __call__(self, query, *, headers, timeout):
        self.calls += 1
        return self.status, self.body


def _doaj_body(link):
    return {"results": [{"bibjson": {"link": [link], "license": [{"type": "CC BY"}]}}]}


def test_doaj_pdf_link_maps_to_gold_vor(temp_db_url):
    body = _doaj_body({"type": "fulltext", "url": "https://doaj.example/x.pdf", "content_type": "PDF"})
    client = DoajClient(fetcher=_DoajFetcher(body))
    with _conn(temp_db_url) as conn:
        loc = client.lookup_oa(conn, PaperRef(doi="10.1/x"))
    assert loc is not None and loc.oa_color == "gold" and loc.version == "vor" and loc.source == "doaj"
    assert loc.pdf_url == "https://doaj.example/x.pdf"


def test_doaj_html_only_landing_returns_none(temp_db_url):
    body = _doaj_body({"type": "fulltext", "url": "https://doaj.example/landing", "content_type": "HTML"})
    client = DoajClient(fetcher=_DoajFetcher(body))
    with _conn(temp_db_url) as conn:
        assert client.lookup_oa(conn, PaperRef(doi="10.1/x")) is None  # not a direct PDF → no guessing


def test_doaj_empty_results_returns_none(temp_db_url):
    client = DoajClient(fetcher=_DoajFetcher({"results": []}))
    with _conn(temp_db_url) as conn:
        assert client.lookup_oa(conn, PaperRef(doi="10.1/x")) is None


def test_doaj_fail_closed_and_caches(temp_db_url):
    class _Boom:
        calls = 0

        def __call__(self, query, *, headers, timeout):
            self.calls += 1
            raise RuntimeError("down")

    boom = _Boom()
    client = DoajClient(fetcher=boom)
    engine = make_engine(temp_db_url)
    with engine.begin() as conn:
        assert client.lookup_oa(conn, PaperRef(doi="10.1/x")) is None
    with engine.begin() as conn:
        assert client.lookup_oa(conn, PaperRef(doi="10.1/x")) is None
    assert boom.calls == 1  # the error was cached; not re-hammered


# --- Europe PMC -------------------------------------------------------------------------------------------


class _EpmcFetcher:
    def __init__(self, body, status=200):
        self.body, self.status = body, status

    def __call__(self, query, *, headers, timeout):
        return self.status, self.body


def _epmc_body(is_oa, *, pmcid="PMC123", license_="cc by"):
    return {"resultList": {"result": [{"isOpenAccess": is_oa, "pmcid": pmcid, "license": license_}]}}


def test_europepmc_oa_cc_maps_to_gold(temp_db_url):
    client = EuropePmcClient(fetcher=_EpmcFetcher(_epmc_body("Y")))
    with _conn(temp_db_url) as conn:
        loc = client.lookup_oa(conn, PaperRef(doi="10.1/x"))
    assert loc is not None and loc.oa_color == "gold" and loc.source == "europepmc"
    assert loc.pdf_url.endswith("/PMC/PMC123/fullTextPDF")


def test_europepmc_oa_noncc_maps_to_green(temp_db_url):
    client = EuropePmcClient(fetcher=_EpmcFetcher(_epmc_body("Y", license_="publisher-specific")))
    with _conn(temp_db_url) as conn:
        loc = client.lookup_oa(conn, PaperRef(doi="10.1/x"))
    assert loc is not None and loc.oa_color == "green"


def test_europepmc_not_oa_returns_none(temp_db_url):
    client = EuropePmcClient(fetcher=_EpmcFetcher(_epmc_body("N")))
    with _conn(temp_db_url) as conn:
        assert client.lookup_oa(conn, PaperRef(doi="10.1/x")) is None  # honor EPMC's own OA flag


def test_europepmc_oa_without_pmcid_returns_none(temp_db_url):
    client = EuropePmcClient(fetcher=_EpmcFetcher(_epmc_body("Y", pmcid="")))
    with _conn(temp_db_url) as conn:
        assert client.lookup_oa(conn, PaperRef(doi="10.1/x")) is None


# --- CORE (needs a key) -----------------------------------------------------------------------------------


class _CoreFetcher:
    def __init__(self, body, status=200):
        self.body, self.status, self.seen_key = body, status, None

    def __call__(self, query, *, api_key, timeout):
        self.seen_key = api_key
        return self.status, self.body


def test_core_without_key_is_noop(temp_db_url, monkeypatch):
    monkeypatch.delenv("CALLOSUM_CORE_API_KEY", raising=False)
    fetcher = _CoreFetcher({"results": []})
    client = CoreClient(fetcher=fetcher)  # api_key falls back to env → None
    with _conn(temp_db_url) as conn:
        assert client.lookup_oa(conn, PaperRef(doi="10.1/x")) is None
    assert fetcher.seen_key is None  # never even called the fetcher


def test_core_with_key_maps_to_green_am_and_sends_bearer(temp_db_url):
    body = {"results": [{"downloadUrl": "https://core.example/12345.pdf"}]}
    fetcher = _CoreFetcher(body)
    client = CoreClient(fetcher=fetcher, api_key="secret-test-key")
    with _conn(temp_db_url) as conn:
        loc = client.lookup_oa(conn, PaperRef(doi="10.1/x"))
    assert loc is not None and loc.oa_color == "green" and loc.version == "am" and loc.source == "core"
    assert fetcher.seen_key == "secret-test-key"  # key handed to the fetcher (as a Bearer header)


def test_core_with_key_no_download_url_returns_none(temp_db_url):
    client = CoreClient(fetcher=_CoreFetcher({"results": [{"id": 1}]}), api_key="k")
    with _conn(temp_db_url) as conn:
        assert client.lookup_oa(conn, PaperRef(doi="10.1/x")) is None


# --- arXiv (preprint) -------------------------------------------------------------------------------------


class _ArxivFetcher:
    def __init__(self, text, status=200):
        self.text, self.status, self.calls = text, status, 0

    def __call__(self, params, *, timeout):
        self.calls += 1
        return self.status, self.text


_ATOM_FEED = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <id>http://arxiv.org/api/query?search_query=ti:foo</id>
  <entry><id>http://arxiv.org/abs/2202.12345v1</id></entry>
</feed>"""


def test_arxiv_doi_needs_no_fetch(temp_db_url):
    fetcher = _ArxivFetcher(_ATOM_FEED)
    client = ArxivClient(fetcher=fetcher)
    with _conn(temp_db_url) as conn:
        loc = client.lookup_oa(conn, PaperRef(doi="10.48550/arXiv.2101.00001"))
    assert loc is not None and loc.oa_color == "green" and loc.version == "preprint" and loc.source == "arxiv"
    assert loc.pdf_url == "https://arxiv.org/pdf/2101.00001"
    assert fetcher.calls == 0  # the DOI carried the id


def test_arxiv_title_search_parses_entry_id(temp_db_url):
    client = ArxivClient(fetcher=_ArxivFetcher(_ATOM_FEED))
    with _conn(temp_db_url) as conn:
        loc = client.lookup_oa(conn, PaperRef(title="Foo Bar"))
    assert loc is not None and loc.pdf_url == "https://arxiv.org/pdf/2202.12345v1"


def test_arxiv_no_entry_returns_none(temp_db_url):
    feed = '<feed xmlns="http://www.w3.org/2005/Atom"><id>http://arxiv.org/api/q</id></feed>'
    client = ArxivClient(fetcher=_ArxivFetcher(feed))
    with _conn(temp_db_url) as conn:
        assert client.lookup_oa(conn, PaperRef(title="Nothing Here")) is None


# --- bioRxiv / medRxiv (preprint) -------------------------------------------------------------------------


class _BiorxivFetcher:
    """found_on: which server returns a hit ('biorxiv'/'medrxiv'); others return 'no posts found'."""

    def __init__(self, found_on, version="2"):
        self.found_on, self.version, self.servers = found_on, version, []

    def __call__(self, server, doi, *, timeout):
        self.servers.append(server)
        if server == self.found_on:
            return 200, {"collection": [{"version": self.version}]}
        return 200, {"collection": [], "messages": [{"status": "no posts found"}]}


def test_biorxiv_hit_builds_full_pdf_url(temp_db_url):
    client = BiorxivClient(fetcher=_BiorxivFetcher("biorxiv", version="3"))
    with _conn(temp_db_url) as conn:
        loc = client.lookup_oa(conn, PaperRef(doi="10.1101/2020.01.01.123456"))
    assert loc is not None and loc.oa_color == "green" and loc.version == "preprint" and loc.source == "biorxiv"
    assert loc.pdf_url == "https://www.biorxiv.org/content/10.1101/2020.01.01.123456v3.full.pdf"


def test_biorxiv_falls_through_to_medrxiv(temp_db_url):
    fetcher = _BiorxivFetcher("medrxiv")
    client = BiorxivClient(fetcher=fetcher)
    with _conn(temp_db_url) as conn:
        loc = client.lookup_oa(conn, PaperRef(doi="10.1101/2020.05.05.20099999"))
    assert loc is not None and loc.source == "medrxiv"
    assert loc.pdf_url.startswith("https://www.medrxiv.org/content/")
    assert fetcher.servers == ["biorxiv", "medrxiv"]  # tried biorxiv first


def test_biorxiv_not_found_returns_none(temp_db_url):
    client = BiorxivClient(fetcher=_BiorxivFetcher("neither"))
    with _conn(temp_db_url) as conn:
        assert client.lookup_oa(conn, PaperRef(doi="10.1101/nope")) is None


# --- OSF / PsyArXiv (preprint) ----------------------------------------------------------------------------


class _OsfFetcher:
    def __init__(self, body, status=200):
        self.body, self.status = body, status

    def __call__(self, doi, *, timeout):
        return self.status, self.body


def _osf_body(download):
    return {"data": [{"embeds": {"primary_file": {"data": {"links": {"download": download}}}}}]}


def test_osf_download_link_maps_to_green_preprint(temp_db_url):
    client = OsfClient(fetcher=_OsfFetcher(_osf_body("https://osf.io/download/abc/")))
    with _conn(temp_db_url) as conn:
        loc = client.lookup_oa(conn, PaperRef(doi="10.31234/osf.io/abcde"))
    assert loc is not None and loc.oa_color == "green" and loc.version == "preprint" and loc.source == "osf"
    assert loc.pdf_url == "https://osf.io/download/abc/"


def test_osf_no_data_returns_none(temp_db_url):
    client = OsfClient(fetcher=_OsfFetcher({"data": []}))
    with _conn(temp_db_url) as conn:
        assert client.lookup_oa(conn, PaperRef(doi="10.31234/osf.io/x")) is None


def test_osf_non_https_download_returns_none(temp_db_url):
    client = OsfClient(fetcher=_OsfFetcher(_osf_body("http://osf.io/download/abc/")))
    with _conn(temp_db_url) as conn:
        assert client.lookup_oa(conn, PaperRef(doi="10.31234/osf.io/x")) is None


# --- Crossref-OA (license-gated, reuses the CrossrefClient cache) -----------------------------------------


class _CrossrefFetcher:
    def __init__(self, message, status=200):
        self.message, self.status = message, status

    def __call__(self, doi, *, headers, timeout):
        return self.status, {"message": self.message}


def _cr_message(*, link=None, license_url=None):
    msg = {"DOI": "10.1/x", "title": ["T"]}
    if link is not None:
        msg["link"] = [link]
    if license_url is not None:
        msg["license"] = [{"URL": license_url}]
    return msg


_PDF_LINK = {"URL": "https://pub.example/x.pdf", "content-type": "application/pdf"}


def test_crossref_cc_license_pdf_maps_to_gold(temp_db_url):
    msg = _cr_message(link=_PDF_LINK, license_url="https://creativecommons.org/licenses/by/4.0/")
    client = CrossrefClient(fetcher=_CrossrefFetcher(msg))
    with _conn(temp_db_url) as conn:
        loc = crossref_oa_location(conn, PaperRef(doi="10.1/x"), client=client)
    assert loc is not None and loc.oa_color == "gold" and loc.version == "vor" and loc.source == "crossref"


def test_crossref_noncc_license_pdf_maps_to_bronze(temp_db_url):
    msg = _cr_message(link=_PDF_LINK, license_url="https://pub.example/terms")
    client = CrossrefClient(fetcher=_CrossrefFetcher(msg))
    with _conn(temp_db_url) as conn:
        loc = crossref_oa_location(conn, PaperRef(doi="10.1/x"), client=client)
    assert loc is not None and loc.oa_color == "bronze" and loc.bronze_unstable is True


def test_crossref_pdf_without_license_returns_none(temp_db_url):
    client = CrossrefClient(fetcher=_CrossrefFetcher(_cr_message(link=_PDF_LINK)))
    with _conn(temp_db_url) as conn:
        assert crossref_oa_location(conn, PaperRef(doi="10.1/x"), client=client) is None  # no license → no guessing


def test_crossref_no_pdf_link_returns_none(temp_db_url):
    msg = _cr_message(license_url="https://creativecommons.org/licenses/by/4.0/")
    client = CrossrefClient(fetcher=_CrossrefFetcher(msg))
    with _conn(temp_db_url) as conn:
        assert crossref_oa_location(conn, PaperRef(doi="10.1/x"), client=client) is None


# --- the cascade ------------------------------------------------------------------------------------------


class _FakeResolver:
    def __init__(self, rid, location):
        self.id, self._location, self.called = rid, location, False

    def resolve(self, conn, ref):
        self.called = True
        return self._location


def test_cascade_returns_first_authorized_copy(temp_db_url):
    loc = OaLocation(pdf_url="https://x.example/p.pdf", oa_color="green", version="preprint", source="second")
    first, second, third = _FakeResolver("a", None), _FakeResolver("b", loc), _FakeResolver("c", None)
    registry = ResolverRegistry()
    for r in (first, second, third):
        registry.register(r)
    with _conn(temp_db_url) as conn:
        result = registry.resolve(conn, PaperRef(doi="10.1/x"))
    assert result is second._location
    assert first.called and second.called and not third.called  # stops at the first hit


def test_new_resolver_registers_without_editing_resolve(temp_db_url):
    # The registry is closed to edits: a brand-new resolver just registers.
    registry = ResolverRegistry()
    loc = OaLocation(pdf_url="https://x.example/p.pdf", oa_color="gold", version="vor", source="novel")
    registry.register(_FakeResolver("novel", loc))
    with _conn(temp_db_url) as conn:
        assert registry.resolve(conn, PaperRef(doi="10.1/x")) is loc


def test_default_registry_cascade_order():
    ids = [r.id for r in build_default_registry().resolvers()]
    assert ids == ["openalex", "doaj", "europepmc", "crossref_oa", "core", "arxiv", "biorxiv", "osf"]


@pytest.mark.parametrize(
    "color",
    ["closed", "none", "paywalled", ""],
)
def test_oalocation_rejects_non_oa_color(color):
    # Structural guarantee (extends Increment A): a non-OA color can never become an OaLocation, so no
    # adapter can mint one for a non-OA result.
    with pytest.raises(ValueError):
        OaLocation(pdf_url="https://x.example/p.pdf", oa_color=color, version="vor", source="x")

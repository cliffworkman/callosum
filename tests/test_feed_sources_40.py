"""Hermetic tests for the inc-592 (#40) Feed sources: arXiv, Europe PMC, PsyArXiv. Each uses an injected fake
fetcher (no network); the sample payloads mirror the real API shapes probed live on 2026-09-12. One bounded
real-API verification per source is done separately (a live spot-check), not in this offline suite."""

from __future__ import annotations

from app.backend.discovery.arxiv_source import ArxivFeedSource, _safe_parse, entry_to_feed
from app.backend.discovery.europepmc_source import EuropePmcFeedSource
from app.backend.discovery.europepmc_source import record_to_entry as epmc_entry
from app.backend.discovery.psyarxiv_source import PsyArxivFeedSource
from app.backend.discovery.psyarxiv_source import record_to_entry as psy_entry

# --- arXiv (Atom XML) -------------------------------------------------------------------------------------

_ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2609.11923v1</id>
    <title>GPU-CFR: 80x Faster
      Counterfactual Regret Minimization</title>
    <published>2026-09-10T17:58:14Z</published>
    <summary>We present a fast solver.</summary>
    <author><name>Boning Li</name></author>
    <author><name>Longbo Huang</name></author>
    <arxiv:primary_category term="cs.DC"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2609.11900v2</id>
    <title>A Published Paper</title>
    <published>2026-09-10T17:00:00Z</published>
    <summary>Abstract two.</summary>
    <author><name>Jane Doe</name></author>
    <arxiv:doi>10.1000/xyz123</arxiv:doi>
    <arxiv:primary_category term="cs.AI"/>
  </entry>
</feed>"""


def test_arxiv_entry_mapping_and_dedup_and_doi():
    src = ArxivFeedSource(fetcher=lambda category, max_results, *, timeout: _ARXIV_XML)
    items = src.fetch("cs.AI", limit=10)
    assert len(items) == 2
    a = items[0]
    assert a.title == "GPU-CFR: 80x Faster Counterfactual Regret Minimization"  # multi-line title collapsed
    assert a.authors == ("Boning Li", "Longbo Huang")
    assert a.journal == "arXiv" and a.year == 2026 and a.posted_date.startswith("2026-09-10")
    assert a.url == "https://arxiv.org/abs/2609.11923v1"
    assert a.doi is None and a.dedup_key == "arxiv:2609.11923"  # no DOI → dedup by version-stripped arXiv id
    b = items[1]
    assert b.doi == "10.1000/xyz123" and b.dedup_key == "doi:10.1000/xyz123"  # DOI present → dedup by DOI


def test_arxiv_blank_category_and_malformed_return_empty():
    src = ArxivFeedSource(fetcher=lambda category, max_results, *, timeout: _ARXIV_XML)
    assert src.fetch("", limit=10) == []
    assert ArxivFeedSource(fetcher=lambda c, m, *, timeout: "not xml at all").fetch("cs.AI", limit=10) == []


def test_arxiv_safe_parse_rejects_doctype_and_nul():
    assert _safe_parse('<!DOCTYPE x [<!ENTITY a "b">]><feed/>') is None
    assert _safe_parse("<feed>\x00</feed>") is None
    assert entry_to_feed  # symbol exported for reuse


# --- Europe PMC (JSON) ------------------------------------------------------------------------------------


def _epmc_records():
    return [
        {
            "id": "42575387",
            "source": "MED",
            "doi": "10.1016/J.PARINT.2026.103363",
            "title": "Spatiotemporal dynamics of leishmaniasis",
            "authorString": "El Alaoui O, El Khiat A, Hakem A",
            "journalInfo": {"journal": {"title": "Parasitology International"}},
            "pubYear": "2027",
            "firstPublicationDate": "2026-08-10",
            "abstractText": "An abstract.",
        },
        {  # no DOI → dedup by source:id; journal absent
            "id": "PPR123",
            "source": "PPR",
            "title": "A preprint with no DOI",
            "authorString": "Solo A",
            "pubYear": "2026",
            "firstPublicationDate": "2026-09-01",
        },
    ]


def test_europepmc_entry_mapping_and_dedup():
    src = EuropePmcFeedSource(fetcher=lambda query, page_size, *, timeout: _epmc_records())
    items = src.fetch("leishmaniasis", limit=10)
    assert len(items) == 2
    a = items[0]
    assert a.doi == "10.1016/j.parint.2026.103363" and a.dedup_key == "doi:10.1016/j.parint.2026.103363"
    assert a.journal == "Parasitology International" and a.year == 2027
    assert a.authors == ("El Alaoui O", "El Khiat A", "Hakem A")
    assert a.url == "https://doi.org/10.1016/j.parint.2026.103363" and a.posted_date == "2026-08-10"
    b = items[1]
    assert b.doi is None and b.dedup_key == "epmc:PPR:PPR123"
    assert b.url == "https://europepmc.org/abstract/PPR/PPR123"
    assert src.fetch("", limit=10) == []


def test_europepmc_record_to_entry_drops_empty():
    assert epmc_entry({"title": "", "doi": ""}) is None


# --- PsyArXiv (OSF JSON:API, embedded contributors) -------------------------------------------------------


def _osf_records():
    return [
        {
            "links": {"self": "https://api.osf.io/v2/preprints/m2jf8_v2/"},
            "attributes": {
                "title": "Working Memory in Adults",
                "date_published": "2026-09-11T18:28:29.480335",
                "description": "A study.",
                "doi": None,
            },
            "embeds": {
                "contributors": {
                    "data": [
                        {"embeds": {"users": {"data": {"attributes": {"full_name": "Sam Boeve"}}}}},
                        {"embeds": {"users": {"data": {"attributes": {"full_name": "Ada Lovelace"}}}}},
                        {"attributes": {"index": 2}},  # an unregistered/embed-less contributor → skipped, no crash
                    ]
                }
            },
        }
    ]


def test_psyarxiv_entry_mapping_guid_authors_and_dedup():
    src = PsyArxivFeedSource(fetcher=lambda query, page_size, *, timeout: _osf_records())
    items = src.fetch("memory", limit=10)
    assert len(items) == 1
    a = items[0]
    assert a.title == "Working Memory in Adults" and a.journal == "PsyArXiv"
    assert a.doi is None and a.dedup_key == "osf:m2jf8"  # version suffix stripped, DOI absent → guid identity
    assert a.url == "https://osf.io/m2jf8/" and a.year == 2026
    assert a.authors == ("Sam Boeve", "Ada Lovelace")  # embed-less contributor skipped defensively
    assert a.posted_date.startswith("2026-09-11")
    assert src.fetch("", limit=10) == []


def test_psyarxiv_record_to_entry_drops_empty_and_survives_odd_shapes():
    assert psy_entry({"attributes": {"title": "", "doi": None}, "links": {"self": ""}}) is None
    # a record with a wildly-shaped contributors embed must not raise
    odd = {
        "links": {"self": "https://api.osf.io/v2/preprints/abc/"},
        "attributes": {"title": "T", "date_published": "2026-01-02"},
        "embeds": {"contributors": {"data": "not-a-list"}},
    }
    e = psy_entry(odd)
    assert e is not None and e.authors == () and e.dedup_key == "osf:abc"

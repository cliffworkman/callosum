"""OpenAlex work-object -> meta-dict mapping (split from adapter.py, inc 456 -- adapter.py was at the 600-line
cap). Pure mapping functions (no I/O, no OpenAlexClient dependency) plus the tiny cache-read helper and the
OPENALEX_PROVIDER constant they share -- the base layer both adapter.py and field_sample.py import from, so
this module never imports from either of them (no import cycle).
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import Connection

from integrations.api_cache import get_cached
from integrations.openalex.request import OPENALEX_CACHE_TTL_SECONDS

OPENALEX_PROVIDER = "openalex"
MAX_REFERENCED = 500  # cap on referenced-work ids read per paper (inc 135; bound the gap-finder fetches)
MAX_RELATED = 50  # cap on related-work ids read per paper (inc 228 overlooked-work; OpenAlex returns ~10-25)
MAX_AUTHORSHIPS = 100
MAX_ABSTRACT_WORDS = 5_000

# OpenAlex `type` -> CSL type (only the common ones; unknown -> omitted, never a guessed type -- inc 217).
_OA_TYPE_TO_CSL = {
    "article": "article-journal",
    "journal-article": "article-journal",
    "book-chapter": "chapter",
    "book": "book",
    "dataset": "dataset",
    "proceedings-article": "paper-conference",
    "preprint": "article-journal",
    "posted-content": "article-journal",
}


def _cached_response(conn: Connection, cache_key: str):
    return get_cached(conn, OPENALEX_PROVIDER, cache_key, max_age_seconds=OPENALEX_CACHE_TTL_SECONDS)


def _meta_from_work(work: Any) -> dict[str, Any] | None:
    """Map an OpenAlex work object -> a meta dict (inc 135 gap-finder; extended inc 227 citation-concentration;
    inc 456 self-citation baseline). DOI normalized lower, prefix stripped. The inc-227/228/456 keys are purely
    additive -- gap-finder/citation-count callers read only their own keys. (Author *nationality* is deliberately
    NOT extracted: the citation tool never categorizes the people cited -- see methods/citation_equity.py, inc 229.)
    """
    if not isinstance(work, dict):
        return None
    raw_id = str(work.get("id") or "")
    raw_doi = work.get("doi") or (work.get("ids") or {}).get("doi")
    doi = raw_doi.strip().lower().replace("https://doi.org/", "") if isinstance(raw_doi, str) and raw_doi else None
    title = work.get("title") or work.get("display_name")
    year = work.get("publication_year")
    authorships = [a for a in _list_value(work.get("authorships"))[:MAX_AUTHORSHIPS] if isinstance(a, dict)]
    authors = [str((a.get("author") or {}).get("display_name") or "").strip() for a in authorships]
    # inc 456: bare A... author ids (self-citation field baseline) -- sitting unused in the same response as
    # authors' display_name; capped like every other id list here.
    author_ids: list[str] = []
    for a in authorships:
        raw_aid = str((a.get("author") or {}).get("id") or "")
        aid = raw_aid.rsplit("/", 1)[-1] if raw_aid else ""
        if re.fullmatch(r"A\d+", aid) and aid not in author_ids:
            author_ids.append(aid)
    # inc 227 (citation-equity): venue + ISSN for the venue-concentration signal.
    venue_src = (work.get("primary_location") or {}).get("source") or work.get("host_venue") or {}
    venue = venue_src.get("display_name") if isinstance(venue_src, dict) else None
    issn = venue_src.get("issn_l") if isinstance(venue_src, dict) else None
    # inc 227: institution names for the institutional-concentration signal; no country/nationality extraction.
    institutions: list[str] = []
    for a in authorships:
        for inst in _list_value(a.get("institutions"))[:20]:
            if not isinstance(inst, dict):
                continue
            name = inst.get("display_name")
            if name and str(name) not in institutions and len(institutions) < 20:
                institutions.append(str(name))
    # inc 227: the focal paper's primary_topic = the "field" the reference list is shown against (id validated).
    raw_topic = work.get("primary_topic")
    primary_topic = None
    if isinstance(raw_topic, dict):
        tid = str(raw_topic.get("id") or "").rsplit("/", 1)[-1]
        if re.fullmatch(r"T\d+", tid):
            primary_topic = {"id": tid, "display_name": str(raw_topic.get("display_name") or "")}
    # inc 228 (overlooked-work SP2): related_works (OpenAlex's relatedness to this paper, bare ids) + concepts
    # (top concept names -- the shared-topic "why" for a candidate). Small lists; existing callers ignore them.
    related: list[str] = []
    for url in _list_value(work.get("related_works"))[:MAX_RELATED]:
        if isinstance(url, str):
            wid = url.rsplit("/", 1)[-1]
            if re.fullmatch(r"W\d+", wid):
                related.append(wid)
    concepts = [
        str(c.get("display_name"))
        for c in _list_value(work.get("concepts"))[:8]
        if isinstance(c, dict) and c.get("display_name")
    ]
    grants: list[dict[str, str]] = []
    for grant in _list_value(work.get("grants"))[:20]:
        if not isinstance(grant, dict):
            continue
        funder = grant.get("funder_display_name") or grant.get("funder") or grant.get("funder_name")
        award = grant.get("award_id") or grant.get("award")
        if funder or award:
            grants.append(
                {
                    key: str(value)
                    for key, value in {
                        "funder_display_name": funder,
                        "award_id": award,
                        "funder": grant.get("funder"),
                    }.items()
                    if value
                }
            )
    # inc 456: the self-citation field baseline needs to know what a field-sample paper ITSELF cites -- already
    # present in the same response (no extra HTTP), just never extracted before now.
    referenced_works: list[str] = []
    for url in _list_value(work.get("referenced_works"))[:MAX_REFERENCED]:
        if isinstance(url, str):
            wid = url.rsplit("/", 1)[-1]
            if re.fullmatch(r"W\d+", wid):
                referenced_works.append(wid)
        if len(referenced_works) >= MAX_REFERENCED:
            break
    return {
        "openalex_work_id": raw_id.rsplit("/", 1)[-1] if raw_id else None,
        "doi": doi,
        "title": str(title) if title else None,
        "year": int(year) if isinstance(year, int) else None,
        "authors": [a for a in authors if a][:8],
        "author_ids": author_ids[:8],
        "cited_by_count": int(work.get("cited_by_count") or 0),
        "venue": str(venue) if venue else None,
        "issn": str(issn) if issn else None,
        "institutions": institutions,
        "primary_topic": primary_topic,
        "related_works": related,
        "concepts": concepts,
        "grants": grants,
        "referenced_works": referenced_works,
    }


def _meta_with_abstract(work: Any) -> dict[str, Any] | None:
    """`_meta_from_work` + the reconstructed `abstract` (inc 228) -- for an overlooked-work *candidate* whose
    title+abstract we embed to rank topical relevance. Abstract is kept out of `_meta_from_work` (too large to add
    to every reference/field meta); only candidates carry it."""
    meta = _meta_from_work(work)
    if meta is None:
        return None
    meta["abstract"] = _reconstruct_abstract(work.get("abstract_inverted_index"))
    return meta


def _reconstruct_abstract(inverted_index: Any) -> str | None:
    """Rebuild plain-text from OpenAlex's `abstract_inverted_index` ({word: [positions]}). Capped; None if absent."""
    if not isinstance(inverted_index, dict) or not inverted_index:
        return None
    positions: list[tuple[int, str]] = []
    for word, idxs in inverted_index.items():
        if not isinstance(idxs, list):
            continue
        for i in idxs[:MAX_ABSTRACT_WORDS]:
            if isinstance(i, int):
                positions.append((i, str(word)))
                if len(positions) >= MAX_ABSTRACT_WORDS:
                    break
        if len(positions) >= MAX_ABSTRACT_WORDS:
            break
    if not positions:
        return None
    positions.sort()
    text = " ".join(word for _, word in positions).strip()
    return text[:20000] or None


def _csl_from_work(work: Any) -> dict[str, Any] | None:
    """Map an OpenAlex work object -> a CSL-fragment for gap-fill enrichment (inc 217). Only includes keys it can
    supply; authors are stored as CSL `{literal}` (OpenAlex doesn't split family/given reliably)."""
    if not isinstance(work, dict):
        return None
    fragment: dict[str, Any] = {}
    title = work.get("title") or work.get("display_name")
    if title:
        fragment["title"] = str(title)
    year = work.get("publication_year")
    if isinstance(year, int):
        fragment["issued"] = {"date-parts": [[year]]}
    authors = [
        {"literal": str(name)}
        for a in _list_value(work.get("authorships"))[:MAX_AUTHORSHIPS]
        if isinstance(a, dict)
        for name in [(a.get("author") or {}).get("display_name") or a.get("raw_author_name")]
        if name
    ]
    if authors:
        fragment["author"] = authors
    venue = (work.get("primary_location") or {}).get("source") or work.get("host_venue") or {}
    venue_name = venue.get("display_name") if isinstance(venue, dict) else None
    if venue_name:
        fragment["container-title"] = str(venue_name)
    csl_type = _OA_TYPE_TO_CSL.get(str(work.get("type") or "").lower())
    if csl_type:
        fragment["type"] = csl_type
    abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))
    if abstract:
        fragment["abstract"] = abstract
    raw_doi = work.get("doi") or (work.get("ids") or {}).get("doi")
    if isinstance(raw_doi, str) and raw_doi:
        fragment["DOI"] = raw_doi.strip().lower().replace("https://doi.org/", "")
    raw_pmid = (work.get("ids") or {}).get("pmid")
    if isinstance(raw_pmid, str) and raw_pmid:
        digits = "".join(ch for ch in raw_pmid if ch.isdigit())
        if digits:
            fragment["PMID"] = digits
    return fragment or None


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []

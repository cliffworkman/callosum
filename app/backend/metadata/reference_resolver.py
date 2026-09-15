"""Resolve a selected reference string to scholarly candidate(s) — the reader "Find referenced paper…" core.

Pure composition over EXISTING primitives (no new subsystem, no transport here): DOI extraction
(``metadata.doi.find_doi_in_text``), the DOI-resolution ``CrossrefClient`` (injected), Crossref's
``query.bibliographic`` search (``discovery.crossref_provider.bibliographic_search``), and the canonical
dedup ``find_existing_paper_by_identity``. It **never writes** — resolution is read-only; the add + OA steps
are separate explicit calls the caller makes against existing endpoints.

The classification is deliberately NOT a confidence score: it is one of four inspectable states —

* ``identifier_match``     — an exact DOI was found in the text and resolved (one candidate).
* ``one_candidate``        — one bibliographic result cleared the plausibility gate.
* ``multiple_candidates``  — several plausible results (the user disambiguates; never auto-picked).
* ``none``                 — nothing defensible (or the input was empty).

``error`` (separate from ``none``) means the lookup could not COMPLETE (Crossref unreachable) — distinct from
"completed, nothing plausible". The plausibility gate is component agreement (title-token overlap OR
author-surname + year agreement), conservative and directly tested — not a synthetic score.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, replace
from typing import Any, Callable

from sqlalchemy import Connection

from app.backend.discovery.crossref_provider import bibliographic_search
from app.backend.discovery.providers import Item
from app.backend.metadata.doi import find_doi_in_text
from app.backend.persistence.repository import find_existing_paper_by_identity

MAX_REFERENCE_LEN = 2000  # hard input bound (also enforced at the API boundary)
BIB_LIMIT = 5  # candidates shown at most (Crossref's own relevance order, never re-ranked)

# Generic words that must not, on their own, make an unrelated title look like agreement. Kept small and
# inspectable; the len>=4 token floor already drops most stopwords ("the", "and", "of", "in").
_GENERIC_TOKENS = frozenset(
    {
        "study",
        "analysis",
        "results",
        "effect",
        "effects",
        "using",
        "based",
        "paper",
        "review",
        "data",
        "approach",
        "model",
        "models",
        "method",
        "methods",
        "role",
        "case",
        "system",
        "systems",
        "with",
        "from",
        "this",
        "that",
        "which",
        "were",
        "into",
        "toward",
        "towards",
        "between",
        "among",
        "their",
    }
)


@dataclass(frozen=True)
class ReferenceCandidate:
    title: str
    authors: tuple[str, ...] = ()
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    in_library: bool = False
    existing_paper_id: int | None = None


@dataclass(frozen=True)
class ReferenceResolution:
    classification: str  # identifier_match | one_candidate | multiple_candidates | none
    candidates: list[ReferenceCandidate] = field(default_factory=list)
    normalized_text: str = ""
    error: str | None = None


def normalize_reference_text(raw: str | None) -> str:
    """Conservative normalization only: NFKC (ligatures/full-width), collapse whitespace/newlines, trim,
    strip ordinary trailing punctuation, hard size bound. NO dehyphenation, NO neighbor reconstruction."""
    if not raw:
        return ""
    text = unicodedata.normalize("NFKC", str(raw))
    text = re.sub(r"\s+", " ", text).strip()
    text = text.rstrip(" .,;:")
    return text[:MAX_REFERENCE_LEN].strip()


def _first_family(authors: tuple[str, ...]) -> str | None:
    if not authors:
        return None
    return authors[0].split(",")[0].strip() or None


def _significant_tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) >= 4 and t not in _GENERIC_TOKENS}


def _plausible(sel_lower: str, sel_tokens: set[str], cand: ReferenceCandidate) -> bool:
    """Suppress only OBVIOUSLY unrelated Crossref hits, on inspectable component agreement. Passes if the
    candidate title shares real tokens with the selection, OR both an author surname AND the year appear in
    the selection (covers bare 'Author (year)' selections that carry no title)."""
    title_tokens = _significant_tokens(cand.title or "")
    overlap = sel_tokens & title_tokens
    title_hit = len(overlap) >= 2 or (bool(title_tokens) and len(overlap) / len(title_tokens) >= 0.5)
    author_hit = any(
        len(fam) >= 2 and re.search(rf"\b{re.escape(fam)}\b", sel_lower)
        for a in cand.authors
        if (fam := a.split(",")[0].strip().lower())
    )
    year_hit = bool(cand.year and re.search(rf"\b{cand.year}\b", sel_lower))
    return title_hit or (author_hit and year_hit)


def _candidate_from_item(item: Item) -> ReferenceCandidate:
    return ReferenceCandidate(
        title=item.title, authors=item.authors, year=item.year, venue=item.journal, doi=item.doi, url=item.url
    )


def _csl_author_name(author: Any) -> str | None:
    if not isinstance(author, dict):
        return None
    family = (author.get("family") or "").strip()
    given = (author.get("given") or "").strip()
    if family and given:
        return f"{family}, {given}"
    return family or (author.get("literal") or "").strip() or None


def _csl_year(issued: Any) -> int | None:
    try:
        return int((issued or {}).get("date-parts", [[None]])[0][0])
    except (TypeError, ValueError, IndexError, AttributeError):
        return None


def _candidate_from_csl(csl: dict[str, Any]) -> ReferenceCandidate:
    title = csl.get("title")
    if isinstance(title, list):
        title = title[0] if title else ""
    venue = csl.get("container-title")
    if isinstance(venue, list):
        venue = venue[0] if venue else None
    doi = (str(csl.get("DOI")).lower() if csl.get("DOI") else None) or None
    authors = tuple(n for a in (csl.get("author") or []) if (n := _csl_author_name(a)))
    return ReferenceCandidate(
        title=str(title or ""),
        authors=authors,
        year=_csl_year(csl.get("issued")),
        venue=venue or None,
        doi=doi,
        url=(csl.get("URL") or (f"https://doi.org/{doi}" if doi else None)),
    )


def _mark_in_library(conn: Connection, cand: ReferenceCandidate) -> ReferenceCandidate:
    # include_trashed: this marks a candidate as already-known for display. A trashed paper still
    # counts as known — surfacing it as novel would invite a duplicate beside the trashed row.
    existing = find_existing_paper_by_identity(
        conn,
        doi=cand.doi,
        title=cand.title,
        year=cand.year,
        first_author_family_name=_first_family(cand.authors),
        include_trashed=True,
    )
    if existing is None:
        return cand
    return replace(cand, in_library=True, existing_paper_id=int(existing[1]["id"]))


def resolve_reference(
    conn: Connection,
    raw_text: str,
    *,
    crossref_client: Any | None,
    bib_search: Callable[[str], list[Item]] | None = None,
) -> ReferenceResolution:
    """Resolve normalized selection text → candidates. DOI-first (exact), else Crossref bibliographic + the
    plausibility gate. Read-only; the caller owns add + OA. ``bib_search`` is injectable for hermetic tests."""
    text = normalize_reference_text(raw_text)
    if not text:
        return ReferenceResolution(classification="none", normalized_text="")

    doi = find_doi_in_text(text)
    if doi and crossref_client is not None:
        try:
            resolution = crossref_client.resolve_doi(conn, doi)
        except Exception:  # noqa: BLE001 — a resolve failure just falls through to bibliographic
            resolution = None
        if resolution is not None and getattr(resolution, "resolved", False) and getattr(resolution, "csl_json", None):
            cand = _mark_in_library(conn, _candidate_from_csl(resolution.csl_json))
            return ReferenceResolution("identifier_match", [cand], text)
        # A DOI that did not resolve falls through to a bibliographic search of the whole selection.

    search = bib_search or (lambda q: bibliographic_search(q, limit=BIB_LIMIT))
    try:
        items = search(text)
    except Exception:  # noqa: BLE001 — transport/parse failure = lookup could not complete (distinct from none)
        return ReferenceResolution(
            classification="none",
            normalized_text=text,
            error="Couldn't complete the lookup — the Crossref request failed. Please try again.",
        )

    sel_lower = text.lower()
    sel_tokens = _significant_tokens(text)
    plausible = [c for c in (_candidate_from_item(it) for it in items) if _plausible(sel_lower, sel_tokens, c)]
    marked = [_mark_in_library(conn, c) for c in plausible[:BIB_LIMIT]]
    if not marked:
        return ReferenceResolution(classification="none", normalized_text=text)
    classification = "one_candidate" if len(marked) == 1 else "multiple_candidates"
    return ReferenceResolution(classification, marked, text)

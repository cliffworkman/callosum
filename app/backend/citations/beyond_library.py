"""Beyond-library citation suggestions.

This is the SP2 extension to the local Cite pane. It searches public metadata providers for papers that are not yet
in the user's library and returns reviewable candidates. It does not claim support from a full paper unless Callosum
has full text; abstract-level stance is labeled as weaker metadata evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any, Protocol

import httpx
from sqlalchemy import Connection, select

from app.backend.acquisition.registry import PaperRef
from app.backend.discovery.providers import Item, SourceProvider, SourceRegistry
from app.backend.persistence.repository import find_existing_paper_by_identity
from app.backend.persistence.schema import papers
from app.backend.summarization.verification import Stance, StanceScorer
from integrations.openalex.adapter import OPENALEX_BASE_URL, OpenAlexClient, _meta_with_abstract

MAX_BEYOND_TEXT_LEN = 4000
MAX_BEYOND_RESULTS = 20
EVIDENCE_MAX = 700
MAX_NEIGHBOR_ANCHORS = 3
MAX_NEIGHBOR_IDS_PER_KIND = 12
_WORD_RE = re.compile(r"[a-z][a-z0-9-]{3,}")
_STOP = {
    "about",
    "after",
    "also",
    "among",
    "because",
    "between",
    "could",
    "from",
    "have",
    "into",
    "paper",
    "research",
    "show",
    "shows",
    "study",
    "that",
    "their",
    "there",
    "these",
    "this",
    "using",
    "were",
    "with",
}


class WorkSearchFetcher(Protocol):
    def __call__(self, query: str, rows: int, *, timeout: float) -> tuple[int, dict[str, Any] | None]: ...


@dataclass(frozen=True)
class ProviderStatus:
    provider_id: str
    status: str
    result_count: int = 0
    warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass(frozen=True)
class CitationNeighborhoodAnchor:
    paper_id: int
    title: str | None
    doi: str | None
    match_score: float


@dataclass(frozen=True)
class BeyondLibrarySuggestion:
    dedup_key: str
    title: str
    sources: list[str]
    doi: str | None
    abstract: str | None
    authors: list[str]
    journal: str | None
    year: int | None
    url: str | None
    in_library: bool
    reason: str
    reason_kind: str
    evidence_text: str
    evidence_kind: str
    metadata_overlap: float
    relationship_kind: str | None = None
    relationship_label: str | None = None
    anchor_paper_id: int | None = None
    anchor_title: str | None = None
    stance: Stance | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dedup_key": self.dedup_key,
            "title": self.title,
            "sources": self.sources,
            "doi": self.doi,
            "abstract": self.abstract,
            "authors": self.authors,
            "journal": self.journal,
            "year": self.year,
            "url": self.url,
            "in_library": self.in_library,
            "reason": self.reason,
            "reason_kind": self.reason_kind,
            "evidence_text": self.evidence_text,
            "evidence_kind": self.evidence_kind,
            "metadata_overlap": self.metadata_overlap,
            "relationship_kind": self.relationship_kind,
            "relationship_label": self.relationship_label,
            "anchor_paper_id": self.anchor_paper_id,
            "anchor_title": self.anchor_title,
            "stance": (
                {"label": self.stance.label, "confidence": self.stance.confidence, "probs": self.stance.probs}
                if self.stance is not None
                else None
            ),
        }


class OpenAlexWorkSearchProvider:
    name = "openalex"

    def __init__(self, fetcher: WorkSearchFetcher | None = None, timeout: float = 15.0) -> None:
        self.fetcher = fetcher or _openalex_fetch
        self.timeout = timeout

    def search(self, query: str, limit: int) -> list[Item]:
        q = (query or "").strip()
        if not q:
            return []
        rows = min(max(limit, 1), 50)
        status, body = self.fetcher(q, rows, timeout=self.timeout)
        if status != 200 or not isinstance(body, dict):
            return []
        out: list[Item] = []
        for work in body.get("results") or []:
            meta = _meta_with_abstract(work)
            if not meta or not meta.get("title"):
                continue
            out.append(
                Item(
                    title=str(meta["title"]),
                    sources=("openalex",),
                    doi=meta.get("doi"),
                    abstract=meta.get("abstract"),
                    authors=tuple(meta.get("authors") or ()),
                    journal=meta.get("venue"),
                    year=meta.get("year"),
                    url=(f"https://openalex.org/{meta['openalex_work_id']}" if meta.get("openalex_work_id") else None),
                )
            )
        return out[:rows]


def suggest_beyond_library(
    conn: Connection,
    *,
    text: str,
    registry: SourceRegistry,
    top_k: int = 5,
    evaluate: bool = True,
    stance_scorer: StanceScorer | None = None,
    openalex_provider: SourceProvider | None = None,
    anchors: list[CitationNeighborhoodAnchor] | None = None,
    openalex_client: OpenAlexClient | None = None,
) -> tuple[list[BeyondLibrarySuggestion], list[ProviderStatus]]:
    query = " ".join((text or "").split())[:MAX_BEYOND_TEXT_LEN]
    if not query:
        return [], []
    limit = max(1, min(top_k, MAX_BEYOND_RESULTS))
    providers = [*registry.providers, openalex_provider or OpenAlexWorkSearchProvider()]
    raw_items, statuses = _search_providers(providers, query, max(limit * 3, 10))
    neighbor_items, neighbor_status = _neighborhood_items(
        conn,
        anchors=anchors or [],
        openalex_client=openalex_client or OpenAlexClient(),
    )
    raw_items.extend(item for item, _ in neighbor_items)
    statuses.append(neighbor_status)
    relations = {item.dedup_key: relation for item, relation in neighbor_items}
    items = _dedupe_mark_library(conn, raw_items)
    query_terms = _terms(query)
    suggestions: list[BeyondLibrarySuggestion] = []
    for item in items:
        if item.in_library:
            continue
        evidence = _evidence_text(item)
        overlap = _overlap(query_terms, _terms(f"{item.title} {item.abstract or ''}"))
        relation = relations.get(item.dedup_key)
        stance = None
        if evaluate and stance_scorer is not None and item.abstract:
            stance = stance_scorer.classify_stance(sentence=query, passage=item.abstract[:1200])
        suggestions.append(
            BeyondLibrarySuggestion(
                dedup_key=item.dedup_key,
                title=item.title,
                sources=list(item.sources),
                doi=item.doi,
                abstract=item.abstract,
                authors=list(item.authors),
                journal=item.journal,
                year=item.year,
                url=item.url,
                in_library=item.in_library,
                reason=_reason(item, overlap),
                reason_kind="public_metadata_search",
                evidence_text=evidence,
                evidence_kind="abstract" if item.abstract else "metadata",
                metadata_overlap=round(overlap, 4),
                relationship_kind=relation.get("kind") if relation else None,
                relationship_label=relation.get("label") if relation else None,
                anchor_paper_id=relation.get("anchor_paper_id") if relation else None,
                anchor_title=relation.get("anchor_title") if relation else None,
                stance=stance,
            )
        )
    suggestions.sort(key=lambda s: (0 if s.relationship_kind else 1, -s.metadata_overlap, s.title.lower()))
    return suggestions[:limit], statuses


def anchors_from_suggestions(conn: Connection, suggestions: list[Any]) -> list[CitationNeighborhoodAnchor]:
    paper_ids = [int(s.paper_id) for s in suggestions[:MAX_NEIGHBOR_ANCHORS] if getattr(s, "paper_id", None)]
    if not paper_ids:
        return []
    rows = (
        conn.execute(select(papers.c.id, papers.c.title, papers.c.doi).where(papers.c.id.in_(paper_ids)))
        .mappings()
        .all()
    )
    by_id = {int(r["id"]): r for r in rows}
    anchors: list[CitationNeighborhoodAnchor] = []
    for suggestion in suggestions[:MAX_NEIGHBOR_ANCHORS]:
        row = by_id.get(int(suggestion.paper_id))
        if row is None or not row["doi"]:
            continue
        anchors.append(
            CitationNeighborhoodAnchor(
                paper_id=int(suggestion.paper_id),
                title=row["title"],
                doi=str(row["doi"]),
                match_score=float(getattr(suggestion, "match_score", 0.0) or 0.0),
            )
        )
    return anchors


def _neighborhood_items(
    conn: Connection,
    *,
    anchors: list[CitationNeighborhoodAnchor],
    openalex_client: OpenAlexClient,
) -> tuple[list[tuple[Item, dict[str, Any]]], ProviderStatus]:
    out: list[tuple[Item, dict[str, Any]]] = []
    checked = 0
    for anchor in anchors[:MAX_NEIGHBOR_ANCHORS]:
        if not anchor.doi:
            continue
        checked += 1
        ref = PaperRef(doi=anchor.doi)
        try:
            work_id = openalex_client.fetch_work_id(conn, ref)
            focal_meta = openalex_client.fetch_work_meta_for(conn, ref) or {}
            referenced = openalex_client.fetch_referenced_works(conn, ref)[:MAX_NEIGHBOR_IDS_PER_KIND]
            related = (focal_meta.get("related_works") or [])[:MAX_NEIGHBOR_IDS_PER_KIND]
            cited_by = openalex_client.fetch_citing_works(conn, work_id)[:MAX_NEIGHBOR_IDS_PER_KIND] if work_id else []
        except Exception as exc:  # noqa: BLE001
            return out, ProviderStatus("openalex-neighborhood", "partial", len(out), f"{type(exc).__name__}: {exc}")
        out.extend(
            (_item_from_openalex_meta(meta, "openalex-neighborhood"), _relation("cited_by_local_match", anchor))
            for meta in openalex_client.fetch_works_by_ids(conn, referenced)
            if meta
        )
        out.extend(
            (_item_from_openalex_meta(meta, "openalex-neighborhood"), _relation("related_to_local_match", anchor))
            for meta in openalex_client.fetch_works_by_ids(conn, related)
            if meta
        )
        out.extend(
            (_item_from_openalex_meta(meta, "openalex-neighborhood"), _relation("cites_local_match", anchor))
            for meta in cited_by
            if meta
        )
    status = "success" if checked else "not_searched"
    return out, ProviderStatus("openalex-neighborhood", status, len(out))


def _item_from_openalex_meta(meta: dict[str, Any], source: str) -> Item:
    return Item(
        title=str(meta.get("title") or "Untitled OpenAlex work"),
        sources=(source,),
        doi=meta.get("doi"),
        abstract=meta.get("abstract"),
        authors=tuple(meta.get("authors") or ()),
        journal=meta.get("venue"),
        year=meta.get("year"),
        url=f"https://openalex.org/{meta['openalex_work_id']}" if meta.get("openalex_work_id") else None,
    )


def _relation(kind: str, anchor: CitationNeighborhoodAnchor) -> dict[str, Any]:
    labels = {
        "cited_by_local_match": "Cited by a locally relevant paper",
        "cites_local_match": "Cites a locally relevant paper",
        "related_to_local_match": "Related to a locally relevant paper in OpenAlex",
    }
    return {
        "kind": kind,
        "label": labels[kind],
        "anchor_paper_id": anchor.paper_id,
        "anchor_title": anchor.title,
    }


def _search_providers(
    providers: list[SourceProvider], query: str, limit: int
) -> tuple[list[Item], list[ProviderStatus]]:
    items: list[Item] = []
    statuses: list[ProviderStatus] = []
    for provider in providers:
        name = getattr(provider, "name", provider.__class__.__name__)
        try:
            found = provider.search(query, limit)
            items.extend(found)
            statuses.append(ProviderStatus(name, "success", len(found)))
        except Exception as exc:  # noqa: BLE001
            statuses.append(ProviderStatus(name, "failed", 0, f"{type(exc).__name__}: {exc}"))
    return items, statuses


def _dedupe_mark_library(conn: Connection, items: list[Item]) -> list[Item]:
    merged: dict[str, Item] = {}
    order: list[str] = []
    for item in items:
        if not item.title:
            continue
        key = item.dedup_key
        if key in merged:
            merged[key] = merged[key].merged_with(item)
        else:
            merged[key] = item
            order.append(key)
    out: list[Item] = []
    for key in order:
        item = merged[key]
        existing = find_existing_paper_by_identity(
            conn,
            doi=item.doi,
            title=item.title,
            year=item.year,
            first_author_family_name=_first_family(item.authors),
        )
        out.append(item if existing is None else replace(item, in_library=True))
    return out


def _openalex_fetch(query: str, rows: int, *, timeout: float) -> tuple[int, dict[str, Any] | None]:
    response = httpx.get(OPENALEX_BASE_URL, params={"search": query, "per-page": rows}, timeout=timeout)
    try:
        body = response.json()
    except ValueError:
        body = None
    return response.status_code, body


def _first_family(authors: tuple[str, ...]) -> str | None:
    if not authors:
        return None
    first = authors[0]
    return first.split(",")[0].strip() if "," in first else first.split(" ")[-1].strip()


def _terms(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall((text or "").lower()) if w not in _STOP}


def _overlap(query_terms: set[str], item_terms: set[str]) -> float:
    if not query_terms or not item_terms:
        return 0.0
    return len(query_terms & item_terms) / max(1, len(query_terms))


def _evidence_text(item: Item) -> str:
    text = item.abstract or f"{item.title} {item.journal or ''}".strip()
    return text if len(text) <= EVIDENCE_MAX else text[:EVIDENCE_MAX].rstrip() + "..."


def _reason(item: Item, overlap: float) -> str:
    sources = ", ".join(item.sources) if item.sources else "public metadata"
    basis = "title/abstract metadata" if item.abstract else "title metadata"
    return f"Surfaced by {sources} from {basis}; metadata term overlap {overlap:.2f}."

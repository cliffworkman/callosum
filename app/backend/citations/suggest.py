"""Highlight-to-suggest / evaluate engine (inc 156, Track C SP1a).

Given a draft sentence, **suggest** which LIBRARY papers to cite (retrieval in reverse — the guided-clustering
machinery run against the span) and, optionally, **evaluate** each candidate's stance toward the claim
(support / contrast / mention) via local NLI. Fully local — local embeddings + the local NLI model; **no egress**.
`POST /citations/suggest` (routers/citations.py) is the word-processor adapter contract: the LibreOffice
"Suggest citations" macro (SP1b) will call it, exactly as inc-108's adapter calls inc-107's render-document.

Honesty contract: every suggestion carries its matched quote + page + match-score as the **reason** (inspectable);
evidence is **region** precision (it's a chunk, never a fabricated exact rect — invariant #2); the stance is a
labeled signal with its quote + confidence, **never a bare verdict**; suggestions are candidates the author picks
(nothing auto-inserts). Ranked by sentence-match, not citation count (the bias-amplification concern is an SP3
beyond-library matter).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Connection, select

from app.backend.citations.section_scope import candidate_section_family, expected_section_family, partition_by_phase
from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.retrieval import RetrievalHit, search_similar
from app.backend.embeddings.vector_store import VectorStore
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES
from app.backend.persistence.schema import attachments, chunks, papers
from app.backend.summarization.verification import Stance, StanceScorer, classify_stances, default_stance_scorer

MAX_TEXT_LEN = 4000  # cap the untrusted draft span (resource bound)
CHUNK_TOP_K = 30  # how many chunk hits to scan before aggregating to papers
MAX_SUGGESTIONS = 20  # hard cap on returned papers (and thus on NLI passes)
QUOTE_MAX = 400  # truncate the displayed matched passage


@dataclass(frozen=True)
class Suggestion:
    paper_id: int
    title: str | None
    year: int | None
    author: str | None
    match_score: float
    chunk_id: int
    quote: str
    page_start: int | None
    page_end: int | None
    bbox_json: object | None
    coordinate_precision: str
    attachment_id: int | None
    stance: Stance | None
    section_family: str | None = None
    search_phase: str | None = None
    section_source: str | None = None  # "grobid" | "heuristic" | "none" -- candidate_section_family's provenance


def suggest_citations(
    conn: Connection,
    *,
    text: str,
    model: EmbeddingModel,
    vector_store: VectorStore,
    top_k: int = 5,
    evaluate: bool = True,
    stance_scorer: StanceScorer | None = None,
    current_heading: str | None = None,
) -> list[Suggestion]:
    query = (text or "").strip()
    if not query:
        return []
    query = query[:MAX_TEXT_LEN]
    limit = max(1, min(top_k, MAX_SUGGESTIONS))

    hits = search_similar(
        conn,
        query=query,
        model=model,
        vector_store=vector_store,
        top_k=CHUNK_TOP_K,
        target_types=("chunk",),
        document_roles=ARTICLE_DOCUMENT_ROLES,
    )
    # Best (highest-score) chunk per paper. `hits` arrive best-first, so the first time a paper appears is at its
    # best chunk; dict insertion order then ranks papers by that best chunk's score.
    best: dict[int, RetrievalHit] = {}
    for hit in hits:
        if hit.chunk_id is None:
            continue
        if hit.paper_id not in best:
            best[hit.paper_id] = hit

    # Section-aware reordering (backlog #30, Track C): compute the full best-per-paper list FIRST, then reorder,
    # THEN slice to `limit` -- reordering before slicing is what lets a matched-but-lower-raw-score paper surface
    # within top_k instead of being cut off before section-scoping ever sees it. Never filters -- every candidate
    # stays present, just reordered.
    expected_family = expected_section_family(current_heading)
    candidate_dicts: list[dict] = []
    families: dict[int, tuple[str | None, str]] = {}
    for hit in best.values():
        assert hit.chunk_id is not None
        family, source = candidate_section_family(conn, hit.chunk_id)
        families[hit.paper_id] = (family, source)
        candidate_dicts.append({"paper_id": hit.paper_id, "section_family": family})
    ordered_dicts, matched_any = partition_by_phase(candidate_dicts, expected_family)
    ordered_paper_ids = [d["paper_id"] for d in ordered_dicts][:limit]
    ranked = [best[pid] for pid in ordered_paper_ids]

    scorer: StanceScorer | None = None
    if evaluate:
        scorer = stance_scorer if stance_scorer is not None else default_stance_scorer()

    hit_rows = []
    for hit in ranked:
        assert hit.chunk_id is not None  # filtered above
        chunk = _chunk_evidence(conn, hit.chunk_id)
        chunk_text = str(chunk.get("text") or "")
        meta = _paper_meta(conn, hit.paper_id)
        hit_rows.append((hit, chunk, chunk_text, meta))

    # Batched: one NLI call for the whole ranked set instead of one per candidate (LATENCY.md).
    stances: list[Stance | None] = [None] * len(hit_rows)
    if scorer is not None and hit_rows:
        stances = classify_stances(scorer, [(query, chunk_text) for _, _, chunk_text, _ in hit_rows])

    suggestions: list[Suggestion] = []
    for (hit, chunk, chunk_text, meta), stance in zip(hit_rows, stances, strict=True):
        family, source = families[hit.paper_id]
        phase = "expected-sections" if (matched_any and family == expected_family) else None
        suggestions.append(
            Suggestion(
                paper_id=hit.paper_id,
                title=meta.get("title"),
                year=meta.get("year"),
                author=meta.get("first_author_family_name"),
                match_score=round(hit.score, 4),
                chunk_id=hit.chunk_id,
                quote=_truncate(chunk_text, QUOTE_MAX),
                page_start=hit.page_start,
                page_end=hit.page_end,
                bbox_json=_stamp_region(hit.bbox_json),
                coordinate_precision="region",
                attachment_id=_pdf_attachment_id(chunk),
                stance=stance,
                section_family=family,
                search_phase=phase,
                section_source=source,
            )
        )
    return suggestions


def _chunk_evidence(conn: Connection, chunk_id: int) -> dict:
    row = (
        conn.execute(
            select(
                chunks.c.text,
                chunks.c.attachment_id,
                attachments.c.content_type,
                attachments.c.attachment_type,
            )
            .select_from(chunks.outerjoin(attachments, attachments.c.id == chunks.c.attachment_id))
            .where(chunks.c.id == chunk_id)
        )
        .mappings()
        .first()
    )
    return dict(row) if row is not None else {}


def _pdf_attachment_id(chunk: dict) -> int | None:
    attachment_id = chunk.get("attachment_id")
    content_type = str(chunk.get("content_type") or "").strip().lower()
    attachment_type = str(chunk.get("attachment_type") or "").strip().lower()
    if attachment_id is None or (content_type != "application/pdf" and attachment_type != "pdf"):
        return None
    return int(attachment_id)


def _paper_meta(conn: Connection, paper_id: int) -> dict:
    row = (
        conn.execute(
            select(papers.c.title, papers.c.year, papers.c.first_author_family_name).where(papers.c.id == paper_id)
        )
        .mappings()
        .first()
    )
    return dict(row) if row is not None else {}


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def _stamp_region(bbox_json: object | None) -> object | None:
    # The matched evidence is a whole chunk → region precision, never a fabricated exact rect (invariant #2).
    if isinstance(bbox_json, list):
        return [{**it, "coordinate_precision": "region"} if isinstance(it, dict) else it for it in bbox_json]
    if isinstance(bbox_json, dict):
        return {**bbox_json, "coordinate_precision": "region"}
    return bbox_json

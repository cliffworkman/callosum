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

from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.retrieval import RetrievalHit, search_similar
from app.backend.embeddings.vector_store import VectorStore
from app.backend.persistence.schema import chunks, papers
from app.backend.summarization.verification import Stance, StanceScorer, default_stance_scorer

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
    stance: Stance | None


def suggest_citations(
    conn: Connection,
    *,
    text: str,
    model: EmbeddingModel,
    vector_store: VectorStore,
    top_k: int = 5,
    evaluate: bool = True,
    stance_scorer: StanceScorer | None = None,
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
    )
    # Best (highest-score) chunk per paper. `hits` arrive best-first, so the first time a paper appears is at its
    # best chunk; dict insertion order then ranks papers by that best chunk's score.
    best: dict[int, RetrievalHit] = {}
    for hit in hits:
        if hit.chunk_id is None:
            continue
        if hit.paper_id not in best:
            best[hit.paper_id] = hit
    ranked = list(best.values())[:limit]

    scorer: StanceScorer | None = None
    if evaluate:
        scorer = stance_scorer if stance_scorer is not None else default_stance_scorer()

    suggestions: list[Suggestion] = []
    for hit in ranked:
        assert hit.chunk_id is not None  # filtered above
        chunk_text = _chunk_text(conn, hit.chunk_id)
        meta = _paper_meta(conn, hit.paper_id)
        stance = scorer.classify_stance(sentence=query, passage=chunk_text) if scorer is not None else None
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
                stance=stance,
            )
        )
    return suggestions


def _chunk_text(conn: Connection, chunk_id: int) -> str:
    row = conn.execute(select(chunks.c.text).where(chunks.c.id == chunk_id)).first()
    return str(row[0]) if row and row[0] is not None else ""


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

"""B2 SP3 — re-verify an imported (relayed) synthesis against the recipient's own library.

An imported synthesis (SP2) is stored as a display blob carrying, per citation, the **sender's quote** + the source
paper's **identity**. Re-verify re-runs the **local** verification pipeline (retrieval + NLI + quote-location) over
the recipient's chunks for the same claims and **converts the synthesis in place** to a native one — its statuses are
now the recipient's, computed against their PDFs (invariants #1/#4). **Fully local — no egress, no LLM** (the
sentences already exist; only verification runs). A claim whose source paper the recipient doesn't have is left
**flagged** with no local citation (silence≠certificate — the claim shows, unverified).
"""

from __future__ import annotations

import re

from sqlalchemy import Connection, delete, func, insert, select, update

from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.retrieval import search_similar
from app.backend.embeddings.vector_store import VectorStore
from app.backend.persistence.document_roles import ARTICLE_DOCUMENT_ROLES
from app.backend.persistence.repository import find_existing_paper_by_identity, get_chunks_for_paper
from app.backend.persistence.schema import summaries, summary_sentences
from app.backend.summarization.generators import CandidateCitation
from app.backend.summarization.pipeline import (
    _combined_chunk_version,
    _combined_embedding_version,
    _persist_verification,
)
from app.backend.summarization.verification import (
    LocalCitationVerifier,
    SupportScorer,
    VerificationConfig,
    VerificationResult,
)

REVERIFIED_SOURCE = "re-verified-from-bundle"  # generated_by — the provenance survives the convert-in-place
_CHUNK_SCAN = 40  # how many chunk hits to scan when falling back to best-by-similarity


class NotImportedError(ValueError):
    """The summary isn't an imported (relayed) synthesis — nothing to re-verify (→ 422)."""


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _resolve_local_paper(conn: Connection, source: object, fallback: object) -> int | None:
    """Re-resolve the citation's source paper by identity (picks up a paper added since import); else the blob's
    stored paper_id (an older blob without a `source` identity)."""
    if isinstance(source, dict):
        found = find_existing_paper_by_identity(
            conn,
            doi=source.get("doi"),
            openalex_work_id=source.get("openalex_work_id"),
            semantic_scholar_paper_id=source.get("semantic_scholar_paper_id"),
            title=source.get("title"),
            year=source.get("year"),
            first_author_family_name=source.get("first_author_family_name"),
        )
        if found is not None:
            return int(found[1]["id"])
    return int(fallback) if isinstance(fallback, int) else None


def _best_chunk_for(
    conn: Connection, paper_id: int, *, sentence: str, quote: str, model: EmbeddingModel, vector_store: VectorStore
) -> int | None:
    """The local chunk to verify against: the one containing the sender's quote (so the quote locates exactly), else
    the best-by-similarity chunk in that paper, else any chunk of the paper."""
    rows = [
        (row["id"], row["text"]) for row in get_chunks_for_paper(conn, paper_id, document_roles=ARTICLE_DOCUMENT_ROLES)
    ]
    if not rows:
        return None
    qn = _norm(quote)
    if qn:
        for cid, text in rows:
            if qn in _norm(str(text or "")):
                return int(cid)
    hits = search_similar(
        conn,
        query=sentence,
        model=model,
        vector_store=vector_store,
        top_k=_CHUNK_SCAN,
        target_types=("chunk",),
        document_roles=ARTICLE_DOCUMENT_ROLES,
    )
    for hit in hits:
        if hit.paper_id == paper_id and hit.chunk_id is not None:
            return int(hit.chunk_id)
    return int(rows[0][0])


def reverify_imported_summary(
    conn: Connection,
    summary_id: int,
    *,
    model: EmbeddingModel,
    vector_store: VectorStore,
    support_scorer: SupportScorer | None = None,
    config: VerificationConfig | None = None,
) -> int:
    """Re-verify an imported synthesis against the local library + convert it in place to native. Returns the id."""
    row = conn.execute(select(summaries.c.imported_json).where(summaries.c.id == summary_id)).first()
    if row is None or not row[0]:
        raise NotImportedError("Only an imported synthesis can be re-verified.")
    blob = row[0]
    verifier = LocalCitationVerifier(
        model=model, vector_store=vector_store, config=config, support_scorer=support_scorer
    )

    # inc 418: resolve every sentence's citations to a local chunk id first (unchanged — depends on paper
    # resolution + quote/similarity matching, not the model), then verify the WHOLE flattened batch in ONE
    # verify_many() call instead of one verify() call per citation — same per-item logic, just batched.
    per_sentence_texts: list[str] = []
    flat_items: list[tuple[str, CandidateCitation]] = []
    item_sentence_index: list[int] = []
    for st in blob.get("sentences") or []:
        if not isinstance(st, dict):
            continue
        text = str(st.get("text") or "")
        sentence_index = len(per_sentence_texts)
        per_sentence_texts.append(text)
        for c in st.get("citations") or []:
            if not isinstance(c, dict):
                continue
            pid = _resolve_local_paper(conn, c.get("source"), c.get("paper_id"))
            if pid is None:
                continue  # source not in my library → no native citation (the sentence flags if it ends empty)
            chunk_id = _best_chunk_for(
                conn, pid, sentence=text, quote=str(c.get("quote") or ""), model=model, vector_store=vector_store
            )
            if chunk_id is None:
                continue
            flat_items.append((text, CandidateCitation(chunk_id=chunk_id, quote=str(c.get("quote") or ""))))
            item_sentence_index.append(sentence_index)

    all_results = verifier.verify_many(conn, items=flat_items, source_chunks=[])
    sentence_results: list[list[VerificationResult]] = [[] for _ in per_sentence_texts]
    for sentence_index, vr in zip(item_sentence_index, all_results, strict=True):
        sentence_results[sentence_index].append(vr)
    per_sentence: list[tuple[str, list[VerificationResult]]] = list(
        zip(per_sentence_texts, sentence_results, strict=True)
    )

    status = (
        "verified" if all(rs and all(v.verified for v in rs) for _, rs in per_sentence) and per_sentence else "flagged"
    )
    conn.execute(
        delete(summary_sentences).where(summary_sentences.c.summary_id == summary_id)
    )  # cascade citations/quotes
    conn.execute(
        update(summaries)
        .where(summaries.c.id == summary_id)
        .values(
            imported_json=None,
            overview_json=None,  # the sender's overview traced their verified set — dropped (not re-narrated; no LLM)
            overview_status="not_requested",
            overview_updated_at=func.current_timestamp(),
            status=status,
            generated_by=REVERIFIED_SOURCE,
            chunk_version_verified_against=_combined_chunk_version(all_results) if all_results else "reverify",
            embedding_version_verified_against=_combined_embedding_version(all_results) if all_results else "reverify",
            verification_version=all_results[0].verification_version if all_results else "reverify",
        )
    )
    for ordinal, (text, results) in enumerate(per_sentence):
        sentence_id = conn.execute(
            insert(summary_sentences).values(summary_id=summary_id, ordinal=ordinal, text=text)
        ).inserted_primary_key[0]
        for vr in results:
            _persist_verification(conn, sentence_id=int(sentence_id), verification=vr)
    return summary_id

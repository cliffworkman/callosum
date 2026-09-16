"""The post-admission indexing invariant: a paper admitted to the Library gets indexed, whoever admitted it.

**The rule.** If a scholarly record has been successfully admitted into the active Library and has
enough metadata to participate in the paper-level index, its indexing state must not depend on which
front end created it.

Before this, it did. Callosum has **no single successful-admission lifecycle seam** — there are a
dozen ``create_paper`` call sites and no post-admission hook — so indexing was a convention each
front end had to remember, and several did not: a paper added by DOI (Library "Add with DOI…" or the
MCP agent), saved from Discovery, or resolved from a Zotero-authored document was never embedded, so
it was invisible to every paper-level vector path until some later consumer happened to backfill it.

Rather than add a fourth "remember to embed" call site, this generalizes the one primitive that
already had the right shape — ``clustering.axis_scoring.ensure_candidate_embeddings_committing``,
which was scoped to axis-scoring candidates — into the shared invariant every admission path uses.

Two contracts are preserved deliberately:

* **One committed transaction per paper** (``commit_each``), so the slow embedding phase releases the
  SQLite write lock between papers instead of holding it across a batch.
* **Embedding failure is never fatal to admission.** A skipped paper is logged and the import still
  succeeds — an honest metadata import must not fail because the local embedding model had trouble,
  the same separation ``AddByDoiResponse`` already draws between the metadata result and the PDF job.

``embed_papers`` is idempotent per ``PAPER_TEXT_VERSION``, so calling this on an already-indexed
paper is a cheap no-op and it is safe to call from a path that may run twice.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import Engine

from app.backend.embeddings.models import EmbeddingModel
from app.backend.embeddings.pipeline import embed_papers
from app.backend.embeddings.vector_store import VectorStore
from app.backend.persistence.sqlite_retry import commit_each

_log = logging.getLogger(__name__)


def ensure_papers_indexed(
    engine: Engine,
    paper_ids: list[int],
    *,
    model: EmbeddingModel,
    vector_store: VectorStore,
) -> None:
    """Ensure each admitted paper has a current paper-level embedding. Never raises for one bad paper.

    Call this AFTER the admission transaction has committed: the paper must already be durable, since
    each embed runs in its own transaction and a failure must leave the imported paper intact.
    """
    ids = [int(pid) for pid in paper_ids if pid is not None]
    if not ids:
        return
    commit_each(
        engine,
        ids,
        lambda conn, pid: embed_papers(conn, model=model, vector_store=vector_store, paper_ids=[pid]),
        on_item_error="skip",
        logger=_log,
    )


def ensure_paper_indexed(engine: Engine, paper_id: int | None, *, model: Any, vector_store: Any) -> None:
    """Single-paper convenience for the admission endpoints, which admit one record at a time."""
    if paper_id is None:
        return
    ensure_papers_indexed(engine, [int(paper_id)], model=model, vector_store=vector_store)

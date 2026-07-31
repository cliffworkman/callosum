"""Full-text search over PDF chunk text (inc 209, A3).

The exact-string complement to the semantic axes: a SQLite **FTS5 MATCH** over `chunks.text` (the `chunks_fts`
external-content index + sync triggers, migration 0026). Distinct from `retrieval.py` (vector/semantic) — this is
verbatim lexical lookup ("find 'ultimatum game' verbatim"). Entirely local; bound params (rule #3); the raw user
query is sanitized into a safe FTS5 MATCH string (rule #4) so FTS5 operator syntax can't throw or inject the query
language, with a try/except fallback so the path never 500s. Extracted to its own module (like tags_repo /
saved_search_repo) to keep repository.py under the 600-line cap.
"""

from __future__ import annotations

import re

from sqlalchemy import Connection, RowMapping
from sqlalchemy import text as sql_text
from sqlalchemy.exc import OperationalError

from app.backend.persistence.document_roles import ARTICLE_FULLTEXT, SQLITE_DOCUMENT_ROLE_CASE_FOR_A

FULLTEXT_MAX_RESULTS = 50

# Snippet match markers — Unicode private-use chars that can't occur in extracted PDF text, so the frontend can split
# on them to bold the matched terms without colliding with real content.
SNIPPET_OPEN = ""  # U+E000 (private-use)
SNIPPET_CLOSE = ""  # U+E001 (private-use)

_TOKEN = re.compile(r"\S+")


def _safe_match(query: str) -> str | None:
    """Turn a raw user query into a safe FTS5 MATCH string. Each whitespace-separated token that has alphanumeric
    content is wrapped as a double-quoted phrase (with embedded ``"`` escaped to ``""``) and the phrases are AND-ed
    by juxtaposition. Quoting neutralizes every FTS5 operator (``*`` ``:`` ``-`` ``^`` ``( )`` ``NEAR`` ``AND`` ``OR``)
    so the query can never be an FTS5 *syntax error* or inject the query language. Returns None when no usable token
    remains (so the caller skips the query entirely)."""
    tokens = [t for t in _TOKEN.findall(query or "") if any(ch.isalnum() for ch in t)]
    if not tokens:
        return None
    return " ".join('"' + t.replace('"', '""') + '"' for t in tokens)


def search_chunks_fulltext(conn: Connection, query: str, *, limit: int = FULLTEXT_MAX_RESULTS) -> list[RowMapping]:
    """Per-occurrence full-text hits over the LIVE library's PDF chunk text, bm25-ranked. Each row:
    ``{paper_id, title, first_author_family_name, year, chunk_id, page_start, page_end, snippet}`` (the snippet wraps
    matched terms in SNIPPET_OPEN/CLOSE). Trashed papers are excluded (the retrieval/pipeline convention). Returns
    ``[]`` for an empty / no-usable-token query, and ``[]`` (never raises) on any FTS5 error."""
    match = _safe_match(query)
    if match is None:
        return []
    n = max(1, min(int(limit), FULLTEXT_MAX_RESULTS))
    stmt = sql_text(
        "SELECT c.paper_id AS paper_id, p.title AS title, "
        "p.first_author_family_name AS first_author_family_name, p.year AS year, "
        "c.id AS chunk_id, c.page_start AS page_start, c.page_end AS page_end, "
        "snippet(chunks_fts, 0, :open, :close, :ellipsis, 12) AS snippet "
        "FROM chunks_fts "
        "JOIN chunks c ON c.id = chunks_fts.rowid "
        "JOIN attachments a ON a.id = c.attachment_id "
        "JOIN papers p ON p.id = c.paper_id AND p.deleted_at IS NULL "
        f"WHERE chunks_fts MATCH :q AND ({SQLITE_DOCUMENT_ROLE_CASE_FOR_A}) = :document_role "
        "ORDER BY bm25(chunks_fts) "
        "LIMIT :n"
    )
    params = {
        "q": match,
        "open": SNIPPET_OPEN,
        "close": SNIPPET_CLOSE,
        "ellipsis": "…",
        "document_role": ARTICLE_FULLTEXT,
        "n": n,
    }
    try:
        return list(conn.execute(stmt, params).mappings())
    except OperationalError:
        return []  # defensive: _safe_match should prevent any FTS5 syntax error → no results, never a 500

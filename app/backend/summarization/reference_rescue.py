"""Reference-list exclusion with a content rescue for mislabelled prose (backlog #82, inc 611).

A reference-list entry is a pointer to a finding, not a finding, so it can never be the verbatim evidence for a
scientific claim. Chunks whose section family is ``references`` are therefore excluded from the claim-evidence
pool. GROBID's mapped ``section_kind`` is preferred over the heuristic ``chunks.section`` -- the same strict
preference ``candidate_section_family`` uses -- and NULL/unlabelled chunks are kept (silence is not a
certificate).

inc 611: the label is evidence about role, not proof of it. The ingest section tracker labels everything after a
"References" heading -- or a heading it mistook for one -- as ``references``; measured on a 251-paper library,
genuine conclusions and limitations carried the label and were removed before vector retrieval could see them. A
labelled chunk is now kept when its text demonstrably is not a reference list
(``chunk_filtering.rescued_from_reference_label``). Two phases keep this off the Ask critical path: the main fetch
is the unchanged SQL exclusion, and a narrow (id, text) query finds the labelled rows, whose full rows are fetched
only when rescued.
"""

from __future__ import annotations

import hashlib

from sqlalchemy import Connection, Select, func, or_

from app.backend.persistence.schema import chunks
from app.backend.persistence.schema_grobid import paper_sections
from app.backend.persistence.sql_batch import in_batches
from app.backend.summarization.chunk_filtering import rescued_from_reference_label

# The heuristic (chunks.section) and GROBID (paper_sections.section_kind, via classify_section_title ->
# detect_section_heading) both spell a reference LIST section this one way. One definition, so the query-scope
# and faceted candidate builders exclude references identically (backlog #82).
REFERENCES_SECTION_KEY = "references"

# text fingerprint -> rescue decision. The decision is a pure function of the text, so keying on the text itself is
# correct across libraries, database replacement and re-extraction. inc 612: it was keyed on (chunk id,
# chunk_version), which two independent libraries can share while holding different text -- a decision made for one
# was then inherited by the other. The memo confines the content check (~0.8 s for ~13k labelled chunks on a
# 251-paper library) to the first Ask that meets each text in a process.
_RESCUE_MEMO: dict[bytes, bool] = {}
_RESCUE_MEMO_CAP = 500_000


def _family():  # type: ignore[no-untyped-def]
    return func.coalesce(paper_sections.c.section_kind, chunks.c.section)


def _joined(stmt: Select) -> Select:
    return stmt.outerjoin(paper_sections, paper_sections.c.id == chunks.c.grobid_section_id)


def exclude_reference_sections(stmt: Select) -> Select:
    """The SQL half: drop references-family chunks from a ``select(chunks)`` candidate query."""
    family = _family()
    return _joined(stmt).where(or_(family.is_(None), family != REFERENCES_SECTION_KEY))


def rescue_decision(text: str) -> bool:
    """Memoized ``rescued_from_reference_label``, keyed by a fingerprint of the text it decides."""
    key = hashlib.blake2b((text or "").encode("utf-8", "surrogatepass"), digest_size=16).digest()
    cached = _RESCUE_MEMO.get(key)
    if cached is None:
        cached = rescued_from_reference_label(text or "")
        if len(_RESCUE_MEMO) >= _RESCUE_MEMO_CAP:
            _RESCUE_MEMO.clear()
        _RESCUE_MEMO[key] = cached
    return cached


def _rescued_ids(conn: Connection, stmt: Select) -> list[int]:
    labelled = conn.execute(
        _joined(stmt.with_only_columns(chunks.c.id, chunks.c.text))
        .where(_family() == REFERENCES_SECTION_KEY)
        .order_by(None)
    )
    return sorted(int(chunk_id) for chunk_id, text in labelled if rescue_decision(text))


def reference_filtered_rows(conn: Connection, stmt: Select) -> list:  # type: ignore[type-arg]
    """Rows of ``stmt`` (a ``select(chunks)`` ordered by ``chunks.id``) minus genuine reference-list chunks.

    The result is in chunk-id order, exactly as one ordered query would return it.
    """
    rows = list(conn.execute(exclude_reference_sections(stmt)).mappings())
    rescued = _rescued_ids(conn, stmt)
    if not rescued:
        return rows
    for batch in in_batches(rescued):
        rows.extend(conn.execute(stmt.where(chunks.c.id.in_(batch))).mappings())
    return sorted(rows, key=lambda row: int(row["id"]))

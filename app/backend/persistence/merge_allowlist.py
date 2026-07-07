"""The re-point allowlist that drives library merge (backlog #17). ONE hardcoded classification of every table
that references a paper, so merge/un-merge touch a fixed, reviewed surface — never a name from request data
(rule #3). ``assert_allowlist_complete`` reflects the schema and fails if a paper-referencing table is missing,
so a future table can't silently escape the merge walk (the guard that keeps this from drifting stale).
"""

from __future__ import annotations

from sqlalchemy import MetaData

# (table, paper_id_column, dedup_key | None). "union": re-point every B row (paper_id -> A). dedup_key None =>
# pure union (no collision possible); a tuple => on a row whose key already exists for A, DROP B's row instead.
UNION_TABLES: list[tuple[str, str, tuple[str, ...] | None]] = [
    ("attachments", "paper_id", None),
    ("chunks", "paper_id", None),  # embeddings ride chunks.id (target_type='chunk') — unchanged, nothing to do
    ("annotations", "paper_id", None),
    ("notes", "paper_id", None),
    ("ma_rows", "paper_id", None),  # non-FK plain column; a row links at most one paper
]

# Set-membership: re-point, DROP B's row on a unique/PK-key collision with A (keep A's).
DEDUP_TABLES: list[tuple[str, str, tuple[str, ...]]] = [
    ("paper_external_identifiers", "paper_id", ("provider", "identifier")),
    ("paper_tags", "paper_id", ("paper_id", "tag_id")),
    ("suppressed_paper_tags", "paper_id", ("paper_id", "tag_name")),
    ("collection_papers", "paper_id", ("collection_id", "paper_id")),
    ("reading_queue", "paper_id", ("paper_id",)),  # UNIQUE(paper_id): keep A's row, drop B's
    ("wanted_items", "paper_id", ("paper_id",)),  # at most one open want per paper
]

# Re-derivable caches keyed to a paper's content: snapshot B's rows, DROP them; A's stand; user re-runs to refresh.
DERIVED_DROP_TABLES: list[tuple[str, str]] = [
    ("open_science_signals", "paper_id"),
    ("paper_citation_counts", "paper_id"),
    ("cluster_node_papers", "paper_id"),
]

# Handled by bespoke code in merge_repo (still listed so the completeness guard passes):
#   dismissed_duplicate_pairs — two paper columns; drop the A-B pair, re-canonicalize (B,X)->(min,max), drop collisions
#   paper_findings           — dedup on (paper_id, source, content_key) but KEEP the reviewed row on collision
#   my_publication_decisions — UNIQUE(paper_id); "confirmed" beats "rejected", else keep A's
#   agent_writes             — target_paper_id, non-FK audit log; re-point B->A
SPECIAL_TABLES: set[str] = {
    "dismissed_duplicate_pairs",
    "paper_findings",
    "my_publication_decisions",
    "agent_writes",
}

# Paper ids embedded in JSON blobs (not caught by column reflection): (table, column). Rewritten B->A.
JSON_SCOPED: list[tuple[str, str]] = [
    ("summaries", "scope_ref_json"),
    ("profile", "starred_paper_ids"),
    ("profile", "research_domains"),
]

# Column names that reference a paper without a formal FK (the "survives a purge" plain-Integer columns).
_NON_FK_PAPER_COLUMNS = {
    ("ma_rows", "paper_id"),
    ("agent_writes", "target_paper_id"),
}


def _classified_tables() -> set[str]:
    named = {t for t, *_ in UNION_TABLES} | {t for t, *_ in DEDUP_TABLES}
    named |= {t for t, _ in DERIVED_DROP_TABLES} | set(SPECIAL_TABLES) | {t for t, _ in JSON_SCOPED}
    return named


def _tables_referencing_papers(metadata: MetaData) -> set[str]:
    referencing: set[str] = set()
    for table in metadata.tables.values():
        for column in table.columns:
            for fk in column.foreign_keys:
                if fk.column.table.name == "papers":
                    referencing.add(table.name)
        for _t, _c in _NON_FK_PAPER_COLUMNS:
            if table.name == _t and _c in table.columns:
                referencing.add(table.name)
    referencing.discard("papers")  # the papers table itself (merged_into self-FK) is not an association
    referencing.discard("merge_operations")  # bookkeeping, not a re-pointed association
    return referencing


def assert_allowlist_complete(metadata: MetaData) -> None:
    referencing = _tables_referencing_papers(metadata)
    classified = _classified_tables()
    missing = referencing - classified
    assert not missing, (
        f"tables reference papers but are not classified in the merge allowlist: {sorted(missing)}. "
        "Add each to a bucket in merge_allowlist.py (union/dedup/derived/special/json) — the merge walk must "
        "touch it or a merge will orphan/leak its rows."
    )

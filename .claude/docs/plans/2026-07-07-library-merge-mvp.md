# Library Merge + Reversible Undo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Manually merge two library entries into one canonical record — re-pointing every association from the
merged-away paper onto the survivor — with a snapshot-backed, fully-reversible un-merge.

**Architecture:** A new `merge_operations` table stores a self-contained reversal snapshot; the merged-away
paper is soft-hidden (`deleted_at` + a new `papers.merged_into` marker). A hardcoded, bucketed allowlist drives
the re-point walk (union / dedup / derived-drop / special / JSON) inside one transaction; un-merge replays the
snapshot in reverse. A read-only preview powers a field-by-field metadata picker; four endpoints + a frontend
merge dialog and undo affordances wrap it.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy Core 2.0, Alembic (guarded/additive migrations), SQLite,
pytest; React JSX chunk (esbuild), rebuilt via `tools/build_frontend.py`.

## Global Constraints

- **Branch:** `library-merge` (off `main`). The spec is committed at
  `.claude/docs/specs/2026-07-07-library-merge-design.md` — read it first; it is the source of truth for the
  re-point surface and policies.
- **600-line cap** on every `app/` + `integrations/` `.py`/`.jsx` file — machine-enforced by the pre-commit
  hook (`tools/check_line_budget.py`) + CI. Run `python tools/check_line_budget.py --list` if a file feels
  close.
- **Parameterized SQL only** (rule #3). Table and column names come **only** from the hardcoded allowlist
  constants in `merge_allowlist.py`, **never** from request data.
- **Migrations are additive + guarded** (the 0033/0034 idiom): guard `op.create_table` / `op.add_column` with
  an `inspector.get_table_names()` / `get_columns()` check; name CHECK constraints with the **short** suffix
  only (env.py's naming convention expands it — a full name gets doubled); `downgrade(): return`.
- **Migration numbering / cross-branch conflict:** this branch's alembic head is `0034_extraction_proposals`.
  The open `critical-review-design` PR also adds a `0035_*` off `0034`. Both branching off `0034` creates an
  alembic **multiple-heads** state once both reach `main`. This plan numbers its migrations `0035_merge_operations`
  → `0036_papers_merged_into` (chained off `0034`). **If PR #3 (critical-review) merges to `main` first, rebase:
  renumber these to `0036`/`0037` and set the first's `down_revision` to `0035_critical_review_candidates`.**
- **No egress, no new external fetch, no new file write.** Attachments only re-point `paper_id`; PDF files on
  disk are untouched.
- **`pytest` green is the gate.** Run **`ruff format .`** before every commit (CI runs `ruff format --check`).
- **Frontend:** after editing anything under `app/frontend/`, run `python tools/build_frontend.py` (needs a
  one-time `npm install`). Frontend chunks count against the 600-cap.
- **Reversibility is the headline invariant:** un-merge must restore **both** papers and every association
  exactly. The merge→unmerge round-trip equality test (Task 6) is the proof; treat a round-trip failure as a
  release blocker, not a Minor.
- **Naming (use verbatim across tasks):** module `app/backend/persistence/merge_repo.py`; functions
  `merge_preview(conn, canonical_id, merged_id) -> dict`, `merge_papers(conn, *, canonical_id, merged_id,
  resolved_metadata) -> int`, `unmerge(conn, *, merge_operation_id) -> int`, `merge_origin(conn, paper_id) ->
  dict | None`. Allowlist module `app/backend/persistence/merge_allowlist.py`. Router
  `app/backend/api/routers/merge.py`. Test file `tests/test_library_merge.py`.

---

## File Structure

| File | Responsibility |
|---|---|
| `app/backend/persistence/schema_merge.py` (new) | `merge_operations` Table + `MERGE_STATUSES` on shared `schema_base.metadata`; re-exported from `schema.py`. |
| `app/backend/persistence/schema.py` (modify) | Add `papers.merged_into` self-FK column; re-export `merge_operations`/`MERGE_STATUSES`. |
| `alembic/versions/0035_merge_operations.py` (new) | Guarded create of `merge_operations`. |
| `alembic/versions/0036_papers_merged_into.py` (new) | Guarded add of `papers.merged_into`. |
| `app/backend/persistence/merge_allowlist.py` (new) | Bucketed re-point registry (union / dedup / derived / special / json) + `assert_allowlist_complete(metadata)` reflection guard. |
| `app/backend/persistence/merge_repo.py` (new) | `merge_preview`, `merge_papers`, `unmerge`, `merge_origin`. The heart. |
| `app/backend/persistence/paper_lifecycle_repo.py` (modify) | `purge_paper` guard against `merged_into`. |
| `app/backend/persistence/repository.py` (modify) | Trash list `merged_into IS NULL`; `purge_all_trashed` id-select filter. |
| `app/backend/api/routers/merge.py` (new) | 4 endpoints + pydantic models. |
| `app/backend/api/app.py` (modify) | Mount `merge.router`. |
| `app/frontend/js/<next>_merge.jsx` (new) | Merge dialog + Merge action + undo toast + Detail "merged from" affordance. |
| `tests/test_library_merge.py` (new) | Repo + allowlist + API tests, incl. the round-trip proof. |
| `.claude/security-audits/2026-07-07_library-merge.md` (new) | Destructive-op audit. |
| `.claude/qa-routes/route_<n>_library_merge.md` + fixture (new) | QA route. |

---

### Task 1: Schema — `merge_operations` table + `papers.merged_into` column + migrations

**Files:**
- Create: `app/backend/persistence/schema_merge.py`
- Modify: `app/backend/persistence/schema.py` (add `merged_into` column to `papers`; re-export)
- Create: `alembic/versions/0035_merge_operations.py`, `alembic/versions/0036_papers_merged_into.py`
- Test: `tests/test_library_merge.py`

**Interfaces:**
- Produces: `merge_operations` Table, `MERGE_STATUSES = ("active", "undone")`, `papers.c.merged_into` column.

- [ ] **Step 1: Write the failing test** (append to a new `tests/test_library_merge.py`)

```python
import json
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, insert, select

from app.backend.persistence import schema
from app.backend.persistence.schema import merge_operations, papers


def _fresh_engine(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path/'m.sqlite'}")
    schema.metadata.create_all(engine)
    return engine


def test_merge_operations_roundtrip_and_merged_into_column(tmp_path):
    engine = _fresh_engine(tmp_path)
    with engine.begin() as conn:
        a = conn.execute(insert(papers).values(title="A", csl_json={})).inserted_primary_key[0]
        b = conn.execute(
            insert(papers).values(title="B", csl_json={}, merged_into=a)
        ).inserted_primary_key[0]
        op_id = conn.execute(
            insert(merge_operations).values(
                canonical_paper_id=a, merged_paper_id=b, snapshot_json=json.dumps({"repoints": []}), status="active"
            )
        ).inserted_primary_key[0]
        row = conn.execute(select(merge_operations).where(merge_operations.c.id == op_id)).mappings().one()
        assert row["status"] == "active" and row["canonical_paper_id"] == a and row["merged_paper_id"] == b
        assert conn.execute(select(papers.c.merged_into).where(papers.c.id == b)).scalar_one() == a
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `pytest tests/test_library_merge.py::test_merge_operations_roundtrip_and_merged_into_column -v`
Expected: FAIL — `ImportError: cannot import name 'merge_operations'`.

- [ ] **Step 3: Create `app/backend/persistence/schema_merge.py`**

```python
"""Reversible-merge bookkeeping — the merge_operations undo-snapshot table (backlog #17/#16).

Split onto the shared ``schema_base`` metadata (rule #1; the schema_findings/schema_summaries pattern);
re-exported from ``schema.py`` so ``from …schema import merge_operations`` keeps working. One row per merge:
the canonical survivor, the merged-away paper, a self-contained JSON reversal snapshot, and a status the
un-merge flips to ``undone``.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Table, Text, func

from app.backend.persistence.schema_base import enum_check, metadata

MERGE_STATUSES = ("active", "undone")

merge_operations = Table(
    "merge_operations",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("canonical_paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("merged_paper_id", ForeignKey("papers.id", ondelete="CASCADE"), nullable=False),
    Column("snapshot_json", Text, nullable=False),
    Column("status", String(20), nullable=False, server_default="active"),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("undone_at", DateTime),
    enum_check("status", MERGE_STATUSES, "merge_status_valid"),
    Index("ix_merge_operations_canonical", "canonical_paper_id"),
)
```

- [ ] **Step 4: Add the `merged_into` column to `papers` in `schema.py`**

In `app/backend/persistence/schema.py`, inside the `papers` Table (after the `priority` column, line ~66):

```python
    Column("priority", String(20)),  # NULL = unset; a user triage label (high/normal/low), never an AI score. inc 220.
    # NULL = not merged; set = this paper was merged away into that canonical paper (backlog #17). Paired with a
    # deleted_at stamp so the existing soft-delete filter hides it from every live query; this marks WHY + enables
    # un-merge. Self-FK (SET NULL so purging the canonical never dangles a merged marker).
    Column("merged_into", ForeignKey("papers.id", ondelete="SET NULL")),
```

At the **bottom** of `schema.py`, add to the re-export block (alongside the other `schema_*` re-exports; keep
the `# noqa: E402,F401` convention already used there):

```python
from app.backend.persistence.schema_merge import (  # noqa: E402,F401
    MERGE_STATUSES,
    merge_operations,
)
```

- [ ] **Step 5: Run the test to confirm it passes**

Run: `pytest tests/test_library_merge.py::test_merge_operations_roundtrip_and_merged_into_column -v`
Expected: PASS.

- [ ] **Step 6: Write the migration test**

```python
def test_migrations_upgrade_head_creates_merge_schema(tmp_path):
    db = tmp_path / "mig.sqlite"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db}")
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db}")
    from sqlalchemy import inspect

    insp = inspect(engine)
    assert "merge_operations" in insp.get_table_names()
    assert "merged_into" in {c["name"] for c in insp.get_columns("papers")}
```

- [ ] **Step 7: Run it to confirm it fails**

Run: `pytest tests/test_library_merge.py::test_migrations_upgrade_head_creates_merge_schema -v`
Expected: FAIL — `merge_operations` not created by migrations yet.

- [ ] **Step 8: Create `alembic/versions/0035_merge_operations.py`**

```python
"""merge_operations — the reversible-merge undo snapshot store (backlog #17/#16).

Additive + guarded (the 0034 idiom); no down-migration by design. The CHECK is named with the short suffix so
env.py's naming convention expands it to ``ck_merge_operations_merge_status_valid`` (a full name would double).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0035_merge_operations"
down_revision = "0034_extraction_proposals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "merge_operations" not in set(inspector.get_table_names()):
        op.create_table(
            "merge_operations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "canonical_paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column(
                "merged_paper_id", sa.Integer(), sa.ForeignKey("papers.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("snapshot_json", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column("undone_at", sa.DateTime()),
            sa.CheckConstraint("status IN ('active', 'undone')", name="merge_status_valid"),
        )
        op.create_index("ix_merge_operations_canonical", "merge_operations", ["canonical_paper_id"])


def downgrade() -> None:
    return
```

- [ ] **Step 9: Create `alembic/versions/0036_papers_merged_into.py`**

```python
"""papers.merged_into — marks a paper merged away into a canonical record (backlog #17). Additive + guarded."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0036_papers_merged_into"
down_revision = "0035_merge_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("papers")}
    if "merged_into" not in cols:
        # No inline FK: SQLite can't add a column with a REFERENCES clause via ALTER. The ORM-level self-FK
        # (schema.py) is what the app relies on; the column is a plain nullable Integer at the DB level.
        op.add_column("papers", sa.Column("merged_into", sa.Integer()))


def downgrade() -> None:
    return
```

- [ ] **Step 10: Run both schema tests + confirm they pass**

Run: `pytest tests/test_library_merge.py -v`
Expected: both PASS. (Note: `metadata.create_all` uses the ORM FK; alembic adds a plain column — both satisfy
`merged_into IS NULL` filtering, which is all the app needs.)

- [ ] **Step 11: `ruff format .` then commit**

```bash
ruff format .
git add app/backend/persistence/schema_merge.py app/backend/persistence/schema.py alembic/versions/0035_merge_operations.py alembic/versions/0036_papers_merged_into.py tests/test_library_merge.py
git commit -m "feat(merge): merge_operations table + papers.merged_into + migrations (#17 t1)"
```

---

### Task 2: The re-point allowlist + completeness guard

**Files:**
- Create: `app/backend/persistence/merge_allowlist.py`
- Test: `tests/test_library_merge.py`

**Interfaces:**
- Produces: `UNION_TABLES`, `DEDUP_TABLES`, `DERIVED_DROP_TABLES` (each `list[tuple]`), `SPECIAL_TABLES:
  set[str]`, `JSON_SCOPED: list[tuple[str, str]]`, and `assert_allowlist_complete(metadata) -> None`.
- Consumes (by later tasks): the four collections drive `merge_papers`/`merge_preview`.

- [ ] **Step 1: Write the failing completeness test**

```python
from app.backend.persistence.merge_allowlist import assert_allowlist_complete


def test_allowlist_covers_every_paper_referencing_table():
    # Fails if a table references papers (by FK or a paper_id-shaped column) but isn't classified into a bucket.
    assert_allowlist_complete(schema.metadata)  # raises AssertionError naming any unbucketed table
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `pytest tests/test_library_merge.py::test_allowlist_covers_every_paper_referencing_table -v`
Expected: FAIL — `ModuleNotFoundError: ...merge_allowlist`.

- [ ] **Step 3: Create `app/backend/persistence/merge_allowlist.py`**

```python
"""The re-point allowlist that drives library merge (backlog #17). ONE hardcoded classification of every table
that references a paper, so merge/un-merge touch a fixed, reviewed surface — never a name from request data
(rule #3). ``assert_allowlist_complete`` reflects the schema and fails if a paper-referencing table is missing,
so a future table can't silently escape the merge walk (the guard that keeps this from drifting stale).
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, MetaData

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
    ("suppressed_paper_tags", "paper_id", ("paper_id", "tag_id")),
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
```

> Implementer note: `_ = ForeignKey` import may be unused — drop the `ForeignKey` import if ruff flags it; only
> `MetaData` is needed for typing. Verify against `schema.metadata` which tables actually resolve (e.g. confirm
> `suppressed_paper_tags`, `reading_queue`, `cluster_node_papers` names match `schema.py`). If the guard names a
> table you didn't expect (e.g. a critical-review table after a future rebase), classify it — that's the guard
> working.

- [ ] **Step 4: Run the completeness test — confirm it passes** (fix any table-name mismatch it reports)

Run: `pytest tests/test_library_merge.py::test_allowlist_covers_every_paper_referencing_table -v`
Expected: PASS. If it fails naming a table, add that table to the correct bucket and re-run.

- [ ] **Step 5: Add a guard-bite test proving the guard actually catches a gap**

```python
def test_allowlist_guard_detects_a_missing_table(monkeypatch):
    import app.backend.persistence.merge_allowlist as al

    monkeypatch.setattr(al, "UNION_TABLES", [t for t in al.UNION_TABLES if t[0] != "annotations"])
    import pytest

    with pytest.raises(AssertionError, match="annotations"):
        al.assert_allowlist_complete(schema.metadata)
```

- [ ] **Step 6: Run it, confirm pass, `ruff format .`, commit**

```bash
pytest tests/test_library_merge.py -v
ruff format .
git add app/backend/persistence/merge_allowlist.py tests/test_library_merge.py
git commit -m "feat(merge): re-point allowlist + schema-completeness guard (#17 t2)"
```

---

### Task 3: `merge_preview` — the read-only field-by-field diff + association counts

**Files:**
- Create: `app/backend/persistence/merge_repo.py`
- Test: `tests/test_library_merge.py`

**Interfaces:**
- Consumes: `UNION_TABLES`, `DEDUP_TABLES` from `merge_allowlist`; `papers` from `schema`.
- Produces: `merge_preview(conn, canonical_id, merged_id) -> dict` with keys `fields` (`list[{field, value_a,
  value_b, agree}]`), `association_counts` (`dict[str, int]`), `warnings` (`list[{kind, detail}]`).

- [ ] **Step 1: Write the failing test**

```python
from sqlalchemy import insert
from app.backend.persistence import repository
from app.backend.persistence.merge_repo import merge_preview


def _add_paper(conn, **cols):
    cols.setdefault("csl_json", {})
    return conn.execute(insert(papers).values(**cols)).inserted_primary_key[0]


def test_merge_preview_reports_field_conflicts_and_counts(tmp_path):
    engine = _fresh_engine(tmp_path)
    with engine.begin() as conn:
        a = _add_paper(conn, title="Neural correlates", year=2023, doi="10.1/abc", csl_json={"title": "Neural correlates"})
        b = _add_paper(conn, title="Neural Correlates", year=2023, csl_json={"title": "Neural Correlates"})
        from app.backend.persistence.schema import annotations
        conn.execute(insert(annotations).values(paper_id=b, page=1, note="x", created_at=None))
        preview = merge_preview(conn, a, b)
    fields = {f["field"]: f for f in preview["fields"]}
    assert fields["title"]["agree"] is False and fields["title"]["value_a"] == "Neural correlates"
    assert fields["year"]["agree"] is True
    assert fields["doi"]["value_b"] in (None, "")  # B has no DOI
    assert preview["association_counts"]["annotations"] >= 1
```

> If `annotations` requires non-null columns, set them per `schema.py` (e.g. a `kind`/`color` if `nullable=False`).
> Read the `annotations` Table before writing the seed and fill required columns.

- [ ] **Step 2: Run it — confirm it fails** (`ImportError: merge_repo`)

Run: `pytest tests/test_library_merge.py::test_merge_preview_reports_field_conflicts_and_counts -v`

- [ ] **Step 3: Create `app/backend/persistence/merge_repo.py` with `merge_preview`**

```python
"""Library merge + reversible un-merge (backlog #17/#16). Bound-param SQLAlchemy Core (rule #3); every table it
touches comes from the hardcoded ``merge_allowlist`` — never from request data. One transaction per operation
(the caller commits). The reversal snapshot stored on ``merge_operations`` is self-contained: un-merge replays
it without re-reading derived state.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Connection, and_, func, insert, select, update

from app.backend.persistence import merge_allowlist as al
from app.backend.persistence.schema import merge_operations, papers

# The paper metadata columns a merge snapshots (so un-merge restores A exactly) — the set build_paper_update touches.
_METADATA_COLUMNS = (
    "title", "abstract", "year", "venue", "item_type", "language",
    "publication_date", "doi", "first_author_family_name", "citation_key", "csl_json", "imported_source",
)

# Fields shown in the field-by-field picker → the papers column each reads from.
_PREVIEW_FIELDS = (
    "title", "year", "doi", "venue", "item_type", "abstract",
    "language", "publication_date", "first_author_family_name",
)


def merge_preview(conn: Connection, canonical_id: int, merged_id: int) -> dict[str, Any]:
    a = conn.execute(select(papers).where(papers.c.id == canonical_id)).mappings().first()
    b = conn.execute(select(papers).where(papers.c.id == merged_id)).mappings().first()
    if a is None or b is None:
        raise ValueError("both papers must exist")
    fields = []
    for name in _PREVIEW_FIELDS:
        va, vb = a[name], b[name]
        fields.append({"field": name, "value_a": va, "value_b": vb, "agree": va == vb})

    counts: dict[str, int] = {}
    for table_name, paper_col, _key in (*al.UNION_TABLES, *al.DEDUP_TABLES):
        counts[table_name] = _count(conn, table_name, paper_col, merged_id)

    warnings = _conflict_warnings(conn, canonical_id, merged_id)
    return {"fields": fields, "association_counts": counts, "warnings": warnings}


def _count(conn: Connection, table_name: str, paper_col: str, paper_id: int) -> int:
    from app.backend.persistence.schema import metadata

    table = metadata.tables[table_name]
    return int(
        conn.execute(
            select(func.count()).select_from(table).where(table.c[paper_col] == paper_id)
        ).scalar_one()
    )


def _conflict_warnings(conn: Connection, a: int, b: int) -> list[dict[str, str]]:
    from app.backend.persistence.schema import my_publication_decisions, reading_queue

    warnings: list[dict[str, str]] = []
    for table, label in ((reading_queue, "reading queue"), (my_publication_decisions, "My Publications")):
        both = conn.execute(
            select(func.count()).select_from(table).where(table.c.paper_id.in_([a, b]))
        ).scalar_one()
        if both and both >= 2:
            warnings.append({"kind": "membership", "detail": f"both papers are in the {label}; kept once"})
    warnings.append(
        {"kind": "derived", "detail": "the survivor's methods signals won't auto-recompute — re-run Methods to refresh"}
    )
    return warnings
```

- [ ] **Step 4: Run the test — confirm it passes**

Run: `pytest tests/test_library_merge.py::test_merge_preview_reports_field_conflicts_and_counts -v`

- [ ] **Step 5: `ruff format .`, commit**

```bash
ruff format .
git add app/backend/persistence/merge_repo.py tests/test_library_merge.py
git commit -m "feat(merge): merge_preview field diff + association counts (#17 t3)"
```

---

### Task 4: `merge_papers` core — metadata apply + union/dedup re-point + snapshot + hide B

**Files:**
- Modify: `app/backend/persistence/merge_repo.py`
- Test: `tests/test_library_merge.py`

**Interfaces:**
- Consumes: `merge_allowlist`, `metadata/paper_edits.build_paper_update`, `paper_lifecycle_repo.update_paper_metadata`.
- Produces: `merge_papers(conn, *, canonical_id, merged_id, resolved_metadata) -> int` (the merge_operation id).

The snapshot dict shape (written to `merge_operations.snapshot_json`):
```python
{
  "canonical_metadata_before": {col: value, ...},   # A's _METADATA_COLUMNS before the field-picker
  "repoints": [{"table": str, "id": int}, ...],     # rows whose paper_id moved B->A (restore: move back)
  "drops":    [{"table": str, "row": {col: value}}, ...],  # rows deleted for dedup/derived (restore: re-insert)
  "json_edits": [{"table": str, "column": str, "id": int, "before": Any}, ...],
}
```

- [ ] **Step 1: Write the failing test (union + dedup + hide B)**

```python
from app.backend.persistence.merge_repo import merge_papers
from app.backend.persistence.schema import annotations, merge_operations, paper_tags, tags


def test_merge_repoints_union_dedups_membership_and_hides_b(tmp_path):
    engine = _fresh_engine(tmp_path)
    with engine.begin() as conn:
        a = _add_paper(conn, title="A", csl_json={"title": "A"})
        b = _add_paper(conn, title="B", csl_json={"title": "B"})
        t1 = conn.execute(insert(tags).values(name="shared")).inserted_primary_key[0]
        t2 = conn.execute(insert(tags).values(name="b-only")).inserted_primary_key[0]
        conn.execute(insert(paper_tags).values(paper_id=a, tag_id=t1))
        conn.execute(insert(paper_tags).values(paper_id=b, tag_id=t1))  # collision -> drop B's
        conn.execute(insert(paper_tags).values(paper_id=b, tag_id=t2))  # unique -> re-point
        conn.execute(insert(annotations).values(paper_id=b, page=1, note="n"))  # union -> re-point

        op_id = merge_papers(conn, canonical_id=a, merged_id=b, resolved_metadata={"title": "A"})

        a_tags = set(conn.execute(select(paper_tags.c.tag_id).where(paper_tags.c.paper_id == a)).scalars())
        assert a_tags == {t1, t2}
        assert conn.execute(select(func.count()).select_from(paper_tags).where(paper_tags.c.paper_id == b)).scalar_one() == 0
        assert conn.execute(select(func.count()).select_from(annotations).where(annotations.c.paper_id == a)).scalar_one() == 1
        hidden = conn.execute(select(papers.c.deleted_at, papers.c.merged_into).where(papers.c.id == b)).mappings().one()
        assert hidden["deleted_at"] is not None and hidden["merged_into"] == a
        assert conn.execute(select(merge_operations.c.status).where(merge_operations.c.id == op_id)).scalar_one() == "active"
```

- [ ] **Step 2: Run it — confirm it fails** (`merge_papers` not defined)

- [ ] **Step 3: Implement `merge_papers` in `merge_repo.py`**

```python
def merge_papers(conn: Connection, *, canonical_id: int, merged_id: int, resolved_metadata: dict[str, Any]) -> int:
    from app.backend.persistence.schema import metadata

    if canonical_id == merged_id:
        raise ValueError("cannot merge a paper into itself")
    a = conn.execute(select(papers).where(papers.c.id == canonical_id)).mappings().first()
    b = conn.execute(select(papers).where(papers.c.id == merged_id)).mappings().first()
    if a is None or b is None:
        raise ValueError("both papers must exist")
    if a["merged_into"] is not None or b["merged_into"] is not None:
        raise ValueError("cannot merge an already-merged paper")
    if a["deleted_at"] is not None or b["deleted_at"] is not None:
        raise ValueError("cannot merge a trashed paper")

    snapshot: dict[str, Any] = {
        "canonical_metadata_before": {c: a[c] for c in _METADATA_COLUMNS},
        "repoints": [],
        "drops": [],
        "json_edits": [],
    }

    # (1) Apply the field-by-field resolved metadata to A (reuse the Details-editor merge — same validation surface).
    if resolved_metadata:
        from app.backend.metadata.paper_edits import build_paper_update
        from app.backend.persistence.paper_lifecycle_repo import update_paper_metadata

        update_paper_metadata(conn, canonical_id, **build_paper_update(a, resolved_metadata))

    # (2) Union tables: pure re-point (or drop on collision when a dedup key is given).
    for table_name, paper_col, key in al.UNION_TABLES:
        _repoint_or_drop(conn, metadata.tables[table_name], paper_col, canonical_id, merged_id, key, snapshot)
    # (3) Dedup tables: re-point, drop B's row on key collision with A.
    for table_name, paper_col, key in al.DEDUP_TABLES:
        _repoint_or_drop(conn, metadata.tables[table_name], paper_col, canonical_id, merged_id, key, snapshot)

    # (Task 5 adds derived / special / JSON walks here.)

    # Hide B: soft-delete (existing filters hide it) + mark merged.
    conn.execute(
        update(papers)
        .where(papers.c.id == merged_id)
        .values(deleted_at=func.current_timestamp(), merged_into=canonical_id)
    )
    op_id = conn.execute(
        insert(merge_operations).values(
            canonical_paper_id=canonical_id,
            merged_paper_id=merged_id,
            snapshot_json=json.dumps(snapshot, default=str),
            status="active",
        )
    ).inserted_primary_key[0]
    return int(op_id)


def _repoint_or_drop(conn, table, paper_col, a_id, b_id, key, snapshot):
    rows = conn.execute(select(table).where(table.c[paper_col] == b_id)).mappings().all()
    for row in rows:
        if key and _collides(conn, table, key, row, a_id, paper_col):
            conn.execute(table.delete().where(table.c.id == row["id"]) if "id" in table.c else _pk_where(table, row))
            snapshot["drops"].append({"table": table.name, "row": dict(row)})
        else:
            _update_paper_col(conn, table, paper_col, row, a_id)
            snapshot["repoints"].append({"table": table.name, "id": _row_identity(table, row)})


def _collides(conn, table, key, row, a_id, paper_col) -> bool:
    conds = []
    for col in key:
        value = a_id if col == paper_col else row[col]
        conds.append(table.c[col] == value)
    return conn.execute(select(func.count()).select_from(table).where(and_(*conds))).scalar_one() > 0


def _update_paper_col(conn, table, paper_col, row, a_id) -> None:
    conn.execute(_pk_where(table, row, update_values={paper_col: a_id}))


def _pk_where(table, row, update_values: dict | None = None):
    # Composite-PK-safe row targeting. Prefer an `id` PK; else match on the primary-key columns.
    pk_cols = [c.name for c in table.primary_key.columns]
    conds = [table.c[c] == row[c] for c in pk_cols]
    if update_values is not None:
        return table.update().where(and_(*conds)).values(**update_values)
    return table.delete().where(and_(*conds))


def _row_identity(table, row):
    pk_cols = [c.name for c in table.primary_key.columns]
    return {c: row[c] for c in pk_cols} if len(pk_cols) != 1 or pk_cols[0] != "id" else row["id"]
```

> Implementer note: simplify `_repoint_or_drop`'s delete to always use `_pk_where(table, row)` (drop the inline
> `table.delete()` branch) — the helper already handles both single- and composite-PK tables. `_row_identity`
> returns an int for `id`-PK tables and a dict for composite-PK tables; the un-merge (Task 6) branches on that.
> After writing, re-run `python tools/check_line_budget.py --list` — if `merge_repo.py` nears 600, plan to peel
> the private helpers into `merge_repo_ops.py` (do it only if actually over).

- [ ] **Step 4: Run the test — confirm it passes**

Run: `pytest tests/test_library_merge.py::test_merge_repoints_union_dedups_membership_and_hides_b -v`

- [ ] **Step 5: `ruff format .`, commit**

```bash
ruff format .
git add app/backend/persistence/merge_repo.py tests/test_library_merge.py
git commit -m "feat(merge): merge_papers core — union/dedup re-point + hide B + snapshot (#17 t4)"
```

---

### Task 5: `merge_papers` — derived-drop + special-case + JSON-scoped walks

**Files:**
- Modify: `app/backend/persistence/merge_repo.py`
- Test: `tests/test_library_merge.py`

**Interfaces:**
- Consumes: `DERIVED_DROP_TABLES`, `SPECIAL_TABLES`, `JSON_SCOPED`.
- Produces: extends `merge_papers` so the snapshot also carries derived drops, special-case drops, and json_edits.

- [ ] **Step 1: Write the failing tests (derived drop + findings review-preserve + JSON scope + dismissed pair)**

```python
from app.backend.persistence.schema import (
    dismissed_duplicate_pairs, open_science_signals, paper_findings, profile,
)


def test_merge_drops_derived_preserves_reviewed_finding_and_rewrites_json(tmp_path):
    engine = _fresh_engine(tmp_path)
    with engine.begin() as conn:
        a = _add_paper(conn, title="A", csl_json={})
        b = _add_paper(conn, title="B", csl_json={})
        conn.execute(insert(open_science_signals).values(paper_id=b, signal_type="data", source="oa"))
        # findings collision: same (source, content_key); B's is reviewed, A's is unreviewed -> keep the reviewed one
        conn.execute(insert(paper_findings).values(paper_id=a, source="s", kind="candidate", payload={}, content_key="k", review_state=None))
        conn.execute(insert(paper_findings).values(paper_id=b, source="s", kind="candidate", payload={}, content_key="k", review_state="confirmed"))
        conn.execute(insert(profile).values(starred_paper_ids=[b], research_domains=[]))

        merge_papers(conn, canonical_id=a, merged_id=b, resolved_metadata={})

        assert conn.execute(select(func.count()).select_from(open_science_signals).where(open_science_signals.c.paper_id == b)).scalar_one() == 0
        kept = conn.execute(select(paper_findings.c.review_state).where(paper_findings.c.paper_id == a, paper_findings.c.content_key == "k")).scalars().all()
        assert "confirmed" in kept  # the reviewed row survived on A
        assert conn.execute(select(profile.c.starred_paper_ids)).scalar_one() == [a]  # b -> a rewrite


def test_merge_drops_the_ab_dismissed_pair(tmp_path):
    engine = _fresh_engine(tmp_path)
    with engine.begin() as conn:
        a = _add_paper(conn, title="A", csl_json={})
        b = _add_paper(conn, title="B", csl_json={})
        lo, hi = sorted((a, b))
        conn.execute(insert(dismissed_duplicate_pairs).values(paper_id_low=lo, paper_id_high=hi))
        merge_papers(conn, canonical_id=a, merged_id=b, resolved_metadata={})
        assert conn.execute(select(func.count()).select_from(dismissed_duplicate_pairs)).scalar_one() == 0
```

- [ ] **Step 2: Run — confirm they fail** (derived rows not dropped; json not rewritten)

- [ ] **Step 3: Add the derived / special / JSON walk to `merge_papers`** (replace the `# (Task 5 adds …)` marker)

```python
    # (4) Derived caches: snapshot B's rows then drop them (A's stand; user re-runs to refresh).
    for table_name, paper_col in al.DERIVED_DROP_TABLES:
        table = metadata.tables[table_name]
        for row in conn.execute(select(table).where(table.c[paper_col] == b_id if False else table.c[paper_col] == merged_id)).mappings().all():
            snapshot["drops"].append({"table": table.name, "row": dict(row)})
            conn.execute(_pk_where(table, row))

    # (5) Special cases.
    _merge_findings(conn, canonical_id, merged_id, snapshot)
    _merge_my_pubs(conn, canonical_id, merged_id, snapshot)
    _merge_agent_writes(conn, canonical_id, merged_id, snapshot)
    _merge_dismissed_pairs(conn, canonical_id, merged_id, snapshot)

    # (6) JSON-scoped id rewrites B -> A.
    _rewrite_json_scopes(conn, canonical_id, merged_id, snapshot)
```

Then add these helpers (all bound-param; each records into `snapshot` for un-merge):

```python
def _merge_findings(conn, a_id, b_id, snapshot):
    from app.backend.persistence.schema import paper_findings as pf

    for row in conn.execute(select(pf).where(pf.c.paper_id == b_id)).mappings().all():
        clash = conn.execute(
            select(pf).where(pf.c.paper_id == a_id, pf.c.source == row["source"], pf.c.content_key == row["content_key"])
        ).mappings().first()
        if clash is None:
            conn.execute(pf.update().where(pf.c.id == row["id"]).values(paper_id=a_id))
            snapshot["repoints"].append({"table": "paper_findings", "id": row["id"]})
        else:
            # keep the REVIEWED row: if B's is reviewed and A's isn't, promote A's review from B's; then drop B's.
            if row["review_state"] is not None and clash["review_state"] is None:
                conn.execute(pf.update().where(pf.c.id == clash["id"]).values(
                    review_state=row["review_state"], review_reason=row["review_reason"], reviewed_at=row["reviewed_at"]
                ))
                snapshot["json_edits"].append({"table": "paper_findings", "column": "review_state", "id": clash["id"], "before": clash["review_state"]})
            snapshot["drops"].append({"table": "paper_findings", "row": dict(row)})
            conn.execute(pf.delete().where(pf.c.id == row["id"]))


def _merge_my_pubs(conn, a_id, b_id, snapshot):
    from app.backend.persistence.schema import my_publication_decisions as mpd

    b_row = conn.execute(select(mpd).where(mpd.c.paper_id == b_id)).mappings().first()
    if b_row is None:
        return
    a_row = conn.execute(select(mpd).where(mpd.c.paper_id == a_id)).mappings().first()
    if a_row is None:
        conn.execute(mpd.update().where(mpd.c.id == b_row["id"]).values(paper_id=a_id))
        snapshot["repoints"].append({"table": "my_publication_decisions", "id": b_row["id"]})
    else:
        if b_row["decision"] == "confirmed" and a_row["decision"] != "confirmed":
            conn.execute(mpd.update().where(mpd.c.id == a_row["id"]).values(decision="confirmed"))
            snapshot["json_edits"].append({"table": "my_publication_decisions", "column": "decision", "id": a_row["id"], "before": a_row["decision"]})
        snapshot["drops"].append({"table": "my_publication_decisions", "row": dict(b_row)})
        conn.execute(mpd.delete().where(mpd.c.id == b_row["id"]))


def _merge_agent_writes(conn, a_id, b_id, snapshot):
    from app.backend.persistence.schema import agent_writes as aw

    for row in conn.execute(select(aw.c.id).where(aw.c.target_paper_id == b_id)).mappings().all():
        conn.execute(aw.update().where(aw.c.id == row["id"]).values(target_paper_id=a_id))
        snapshot["repoints"].append({"table": "agent_writes", "id": row["id"]})


def _merge_dismissed_pairs(conn, a_id, b_id, snapshot):
    from app.backend.persistence.schema import dismissed_duplicate_pairs as ddp

    for row in conn.execute(
        select(ddp).where((ddp.c.paper_id_low.in_([a_id, b_id])) | (ddp.c.paper_id_high.in_([a_id, b_id])))
    ).mappings().all():
        lo, hi = row["paper_id_low"], row["paper_id_high"]
        other = None if {lo, hi} == {a_id, b_id} else (hi if b_id == lo else lo if b_id == hi else None)
        # Always drop the existing row (it involves B, or is the A-B pair itself); it's snapshotted for restore.
        snapshot["drops"].append({"table": "dismissed_duplicate_pairs", "row": dict(row)})
        conn.execute(ddp.delete().where(ddp.c.id == row["id"]))
        if other is None or other == a_id:
            continue  # the A-B pair (or a self pair) simply disappears
        nlo, nhi = sorted((a_id, other))
        exists = conn.execute(select(func.count()).select_from(ddp).where(ddp.c.paper_id_low == nlo, ddp.c.paper_id_high == nhi)).scalar_one()
        if not exists:
            conn.execute(insert(ddp).values(paper_id_low=nlo, paper_id_high=nhi))
            # the re-canonicalized pair is a NEW row; record it so un-merge deletes it back out
            snapshot.setdefault("inserts", []).append({"table": "dismissed_duplicate_pairs", "key": {"paper_id_low": nlo, "paper_id_high": nhi}})


def _rewrite_json_scopes(conn, a_id, b_id, snapshot):
    from app.backend.persistence.schema import metadata

    for table_name, column in al.JSON_SCOPED:
        table = metadata.tables[table_name]
        for row in conn.execute(select(table.c.id, table.c[column])).mappings().all():
            before = row[column]
            after = _replace_paper_id_in_json(before, b_id, a_id)
            if after != before:
                conn.execute(table.update().where(table.c.id == row["id"]).values(**{column: after}))
                snapshot["json_edits"].append({"table": table_name, "column": column, "id": row["id"], "before": before})


def _replace_paper_id_in_json(value, old_id, new_id):
    if isinstance(value, list):
        seen, out = set(), []
        for item in (_replace_paper_id_in_json(v, old_id, new_id) for v in value):
            marker = json.dumps(item, sort_keys=True, default=str)
            if marker not in seen:
                seen.add(marker)
                out.append(item)
        return out
    if isinstance(value, dict):
        return {k: _replace_paper_id_in_json(v, old_id, new_id) for k, v in value.items()}
    return new_id if value == old_id else value
```

> Implementer notes: (a) fix the copy-paste `if False else` in the derived loop — write it plainly as
> `select(table).where(table.c[paper_col] == merged_id)`. (b) The `snapshot["inserts"]` key (re-canonicalized
> dismissed pairs) is new — Task 6's un-merge must delete those back out; it's listed in the snapshot shape
> there. (c) `_rewrite_json_scopes` rewrites `summaries.scope_ref_json` structurally: a paper-scoped summary
> stores its id somewhere in that JSON — the recursive replace handles it whatever the nesting. (d) Watch the
> 600-cap: if `merge_repo.py` goes over, move the Task-5 special-case helpers to `merge_repo_special.py` and
> import them.

- [ ] **Step 4: Run both new tests — confirm they pass**

Run: `pytest tests/test_library_merge.py -k "derived or dismissed" -v`

- [ ] **Step 5: `ruff format .`, `python tools/check_line_budget.py --list`, commit**

```bash
ruff format .
python tools/check_line_budget.py --list
git add app/backend/persistence/merge_repo.py tests/test_library_merge.py
git commit -m "feat(merge): derived-drop + special-case + JSON-scope merge walks (#17 t5)"
```

---

### Task 6: `unmerge` — reverse the snapshot + the round-trip proof

**Files:**
- Modify: `app/backend/persistence/merge_repo.py`
- Test: `tests/test_library_merge.py`

**Interfaces:**
- Produces: `unmerge(conn, *, merge_operation_id) -> int` (returns the restored `merged_paper_id`).

Snapshot keys reversed: `canonical_metadata_before` (write back to A), `repoints` (move row's `paper_id` back
to B — `id` is int for id-PK tables, dict for composite-PK), `drops` (re-insert the row verbatim), `inserts`
(delete the re-canonicalized rows back out), `json_edits` (write `before` back). Then clear B's
`deleted_at`+`merged_into` and flip the op to `undone`.

- [ ] **Step 1: Write the round-trip proof test (the reversibility guarantee)**

```python
from app.backend.persistence.merge_repo import unmerge


def _snapshot_state(conn):
    """A comparable snapshot of the whole DB's paper-referencing rows, for byte-for-byte equality."""
    from app.backend.persistence.schema import metadata
    out = {}
    for name in ("papers", "annotations", "paper_tags", "open_science_signals", "paper_findings",
                 "dismissed_duplicate_pairs", "profile", "reading_queue", "my_publication_decisions"):
        table = metadata.tables[name]
        rows = [dict(r) for r in conn.execute(select(table).order_by(table.c.id if "id" in table.c else list(table.c)[0])).mappings()]
        # drop volatile timestamps so equality is about data, not clock
        for r in rows:
            r.pop("created_at", None); r.pop("updated_at", None); r.pop("reviewed_at", None)
        out[name] = rows
    return out


def test_merge_then_unmerge_restores_both_papers_exactly(tmp_path):
    engine = _fresh_engine(tmp_path)
    with engine.begin() as conn:
        a = _add_paper(conn, title="A", year=2023, doi="10.1/a", csl_json={"title": "A"})
        b = _add_paper(conn, title="B", year=2022, csl_json={"title": "B"})
        t1 = conn.execute(insert(tags).values(name="shared")).inserted_primary_key[0]
        conn.execute(insert(paper_tags).values(paper_id=a, tag_id=t1))
        conn.execute(insert(paper_tags).values(paper_id=b, tag_id=t1))
        conn.execute(insert(annotations).values(paper_id=b, page=2, note="keep"))
        conn.execute(insert(open_science_signals).values(paper_id=b, signal_type="data", source="oa"))
        before = _snapshot_state(conn)

        op_id = merge_papers(conn, canonical_id=a, merged_id=b,
                             resolved_metadata={"title": "A", "year": 2023})
        restored = unmerge(conn, merge_operation_id=op_id)
        after = _snapshot_state(conn)

    assert restored == b
    # B is fully live again; A's metadata restored; every association back where it started.
    assert after["papers"] == before["papers"]
    assert after["annotations"] == before["annotations"]
    assert after["paper_tags"] == before["paper_tags"]
    assert after["open_science_signals"] == before["open_science_signals"]
```

- [ ] **Step 2: Run it — confirm it fails** (`unmerge` not defined)

- [ ] **Step 3: Implement `unmerge` in `merge_repo.py`**

```python
def unmerge(conn: Connection, *, merge_operation_id: int) -> int:
    from app.backend.persistence.schema import metadata

    op = conn.execute(select(merge_operations).where(merge_operations.c.id == merge_operation_id)).mappings().first()
    if op is None:
        raise ValueError("merge operation not found")
    if op["status"] != "active":
        raise ValueError("merge operation is not active (already undone)")
    a_id, b_id = op["canonical_paper_id"], op["merged_paper_id"]
    snap = json.loads(op["snapshot_json"])

    # 1) restore A's metadata
    from app.backend.persistence.paper_lifecycle_repo import update_paper_metadata

    update_paper_metadata(conn, a_id, **snap["canonical_metadata_before"])

    # 2) move re-pointed rows back to B
    for entry in snap["repoints"]:
        table = metadata.tables[entry["table"]]
        paper_col = _paper_col_for(entry["table"])
        ident = entry["id"]
        where = (table.c.id == ident) if not isinstance(ident, dict) else and_(*[table.c[k] == v for k, v in ident.items()])
        conn.execute(table.update().where(where).values(**{paper_col: b_id}))

    # 3) re-insert dropped rows
    for entry in snap["drops"]:
        table = metadata.tables[entry["table"]]
        conn.execute(insert(table).values(**entry["row"]))

    # 4) delete re-canonicalized inserts back out
    for entry in snap.get("inserts", []):
        table = metadata.tables[entry["table"]]
        conn.execute(table.delete().where(and_(*[table.c[k] == v for k, v in entry["key"].items()])))

    # 5) restore json_edits
    for entry in snap["json_edits"]:
        table = metadata.tables[entry["table"]]
        conn.execute(table.update().where(table.c.id == entry["id"]).values(**{entry["column"]: entry["before"]}))

    # 6) B fully live again; 7) op undone
    conn.execute(update(papers).where(papers.c.id == b_id).values(deleted_at=None, merged_into=None))
    conn.execute(update(merge_operations).where(merge_operations.c.id == merge_operation_id).values(status="undone", undone_at=func.current_timestamp()))
    return int(b_id)


def _paper_col_for(table_name: str) -> str:
    if table_name == "agent_writes":
        return "target_paper_id"
    return "paper_id"
```

> Implementer note: `insert(table).values(**entry["row"])` re-inserts with the original `id` (SQLite allows an
> explicit PK). If any dropped table has a JSON column, `json.loads` already restored it to a Python object, so
> the re-insert value is correct. Confirm the round-trip test's `_snapshot_state` includes every table your
> merge touched in the test; if a later test exercises another table, add it there too.

- [ ] **Step 4: Run the round-trip test — confirm it passes**

Run: `pytest tests/test_library_merge.py::test_merge_then_unmerge_restores_both_papers_exactly -v`
Expected: PASS. **If it fails, the snapshot is incomplete — fix `merge_papers`, not the test.** This is the
reversibility gate.

- [ ] **Step 5: Run the whole merge suite, `ruff format .`, commit**

```bash
pytest tests/test_library_merge.py -v
ruff format .
git add app/backend/persistence/merge_repo.py tests/test_library_merge.py
git commit -m "feat(merge): unmerge snapshot reversal + round-trip proof (#17/#16 t6)"
```

---

### Task 7: Lifecycle guards + `merge_origin`

**Files:**
- Modify: `app/backend/persistence/repository.py` (Trash list filter; `purge_all_trashed` filter)
- Modify: `app/backend/persistence/paper_lifecycle_repo.py` (`purge_paper` guard)
- Modify: `app/backend/persistence/merge_repo.py` (add `merge_origin`)
- Test: `tests/test_library_merge.py`

**Interfaces:**
- Produces: `merge_origin(conn, paper_id) -> dict | None` (`{merge_operation_id, merged_from_title, merged_at}`).

- [ ] **Step 1: Write the failing tests**

```python
from app.backend.persistence import repository
from app.backend.persistence.merge_repo import merge_origin


def test_merged_away_paper_hidden_from_trash_and_not_purgeable(tmp_path):
    engine = _fresh_engine(tmp_path)
    with engine.begin() as conn:
        a = _add_paper(conn, title="A", csl_json={})
        b = _add_paper(conn, title="B", csl_json={})
        merge_papers(conn, canonical_id=a, merged_id=b, resolved_metadata={})
        trash_ids = {r["id"] for r in repository.list_papers(conn, only_deleted=True)}
        assert b not in trash_ids  # merged-away paper never shows as restorable trash
        from app.backend.persistence.paper_lifecycle_repo import purge_paper

        class _NoVec:
            def delete(self, *a, **k): ...
        assert purge_paper(conn, b, vector_store=_NoVec()) is False  # guarded: must un-merge first

        origin = merge_origin(conn, a)
        assert origin and origin["merged_from_title"] == "B"
```

> Check `repository.list_papers`' exact signature/keyword for the deleted view (it's the `only_deleted` param at
> `repository.py:262`). Adjust the test call to match.

- [ ] **Step 2: Run it — confirm it fails**

- [ ] **Step 3: Add the Trash filter in `repository.py`** (the `only_deleted` branch, line ~262)

Change:
```python
        .where(papers.c.deleted_at.is_not(None) if only_deleted else papers.c.deleted_at.is_(None))
```
to:
```python
        .where(
            and_(papers.c.deleted_at.is_not(None), papers.c.merged_into.is_(None))
            if only_deleted
            else papers.c.deleted_at.is_(None)
        )
```
(Confirm `and_` is imported in `repository.py`; if not, add it to the `from sqlalchemy import …` line.)

- [ ] **Step 4: Filter `purge_all_trashed`'s id-select in `paper_lifecycle_repo.py`**

Change its select (line ~82) from `.where(papers.c.deleted_at.is_not(None))` to
`.where(and_(papers.c.deleted_at.is_not(None), papers.c.merged_into.is_(None)))` (add `and_` to its imports if
missing — it already imports `and_`).

- [ ] **Step 5: Guard `purge_paper` in `paper_lifecycle_repo.py`**

In `purge_paper`, extend the pre-check to also read `merged_into`:
```python
    row = conn.execute(select(papers.c.deleted_at, papers.c.merged_into).where(papers.c.id == paper_id)).first()
    if row is None or row[0] is None or row[1] is not None:
        return False  # missing, not in Trash, or merged-away (un-merge first — never orphan the undo record)
```

- [ ] **Step 6: Add `merge_origin` to `merge_repo.py`**

```python
def merge_origin(conn: Connection, paper_id: int) -> dict[str, Any] | None:
    op = conn.execute(
        select(merge_operations).where(
            merge_operations.c.canonical_paper_id == paper_id, merge_operations.c.status == "active"
        ).order_by(merge_operations.c.created_at.desc())
    ).mappings().first()
    if op is None:
        return None
    title = conn.execute(select(papers.c.title).where(papers.c.id == op["merged_paper_id"])).scalar_one_or_none()
    return {"merge_operation_id": op["id"], "merged_from_title": title, "merged_at": op["created_at"]}
```

- [ ] **Step 7: Run the merge suite + the existing Trash/purge tests, `ruff format .`, commit**

```bash
pytest tests/test_library_merge.py tests/test_papers.py -q
ruff format .
git add app/backend/persistence/repository.py app/backend/persistence/paper_lifecycle_repo.py app/backend/persistence/merge_repo.py tests/test_library_merge.py
git commit -m "feat(merge): Trash/purge guards for merged-away papers + merge_origin (#17 t7)"
```

---

### Task 8: API router — preview / merge / undo / origin

**Files:**
- Create: `app/backend/api/routers/merge.py`
- Modify: `app/backend/api/app.py` (mount)
- Test: `tests/test_library_merge.py`

**Interfaces:**
- Endpoints: `GET /papers/{a}/merge-preview/{b}`, `POST /papers/merge`, `POST /merge/{op_id}/undo`,
  `GET /papers/{id}/merge-origin`.

- [ ] **Step 1: Write the failing endpoint test**

```python
from fastapi.testclient import TestClient
from tests.api_helpers import build_test_app  # confirm the helper name in tests/api_helpers.py


def test_merge_endpoints_happy_path_and_undo(tmp_path):
    app, engine = build_test_app(tmp_path)  # adapt to the project's helper (returns app + engine/db)
    with engine.begin() as conn:
        a = _add_paper(conn, title="A", doi="10.1/a", csl_json={"title": "A"})
        b = _add_paper(conn, title="B", csl_json={"title": "B"})
    client = TestClient(app)
    prev = client.get(f"/papers/{a}/merge-preview/{b}")
    assert prev.status_code == 200 and any(f["field"] == "title" for f in prev.json()["fields"])
    merged = client.post("/papers/merge", json={"canonical_id": a, "merged_id": b, "resolved_metadata": {"title": "A"}})
    assert merged.status_code == 200
    op_id = merged.json()["merge_operation_id"]
    origin = client.get(f"/papers/{a}/merge-origin")
    assert origin.json()["merged_from_title"] == "B"
    undo = client.post(f"/merge/{op_id}/undo")
    assert undo.status_code == 200 and undo.json()["restored_paper_id"] == b
    # negative: self-merge rejected
    assert client.post("/papers/merge", json={"canonical_id": a, "merged_id": a, "resolved_metadata": {}}).status_code == 422
```

> Use the project's existing app/DB test harness from `tests/conftest.py` / `tests/api_helpers.py` (mirror how
> `tests/test_papers.py` builds a client) rather than the sketch above if the names differ.

- [ ] **Step 2: Run it — confirm it fails**

- [ ] **Step 3: Create `app/backend/api/routers/merge.py`**

```python
"""Library merge + un-merge endpoints (backlog #17/#16). Thin wrappers over merge_repo; all mutation rides the
standard access-control / read-only middleware (merge + undo are writes -> 403 under CALLOSUM_READ_ONLY).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Connection

from app.backend.api.dependencies import get_connection
from app.backend.persistence import merge_repo

router = APIRouter()


class MergeRequest(BaseModel):
    canonical_id: int
    merged_id: int
    resolved_metadata: dict[str, Any] = {}


class MergeResponse(BaseModel):
    merge_operation_id: int
    canonical_id: int


class UndoResponse(BaseModel):
    restored_paper_id: int


@router.get("/papers/{canonical_id}/merge-preview/{merged_id}")
def preview(canonical_id: int, merged_id: int, conn: Connection = Depends(get_connection)) -> dict[str, Any]:
    if canonical_id == merged_id:
        raise HTTPException(status_code=422, detail="Choose two different papers to merge")
    try:
        return merge_repo.merge_preview(conn, canonical_id, merged_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


@router.post("/papers/merge", response_model=MergeResponse)
def merge(payload: MergeRequest, conn: Connection = Depends(get_connection)) -> MergeResponse:
    try:
        op_id = merge_repo.merge_papers(
            conn,
            canonical_id=payload.canonical_id,
            merged_id=payload.merged_id,
            resolved_metadata=payload.resolved_metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    conn.commit()
    return MergeResponse(merge_operation_id=op_id, canonical_id=payload.canonical_id)


@router.post("/merge/{op_id}/undo", response_model=UndoResponse)
def undo(op_id: int, conn: Connection = Depends(get_connection)) -> UndoResponse:
    try:
        restored = merge_repo.unmerge(conn, merge_operation_id=op_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    conn.commit()
    return UndoResponse(restored_paper_id=restored)


@router.get("/papers/{paper_id}/merge-origin")
def origin(paper_id: int, conn: Connection = Depends(get_connection)) -> dict[str, Any] | None:
    return merge_repo.merge_origin(conn, paper_id)
```

- [ ] **Step 4: Mount in `app/backend/api/app.py`**

Add to the router imports (with the other `from app.backend.api.routers import …`), then near the other
`api.include_router(...)` calls add — **before** `papers.router` so `/papers/{a}/merge-preview/{b}` and
`/papers/merge` win over `/papers/{paper_id}`:

```python
    api.include_router(merge.router)  # /papers/merge, /papers/{a}/merge-preview/{b} — before papers.router (#17)
```

- [ ] **Step 5: Run the endpoint test + confirm the route order (merge-preview not shadowed)**

Run: `pytest tests/test_library_merge.py -k endpoints -v`
Expected: PASS. Also confirm `GET /papers/5/merge-preview/6` doesn't 404 as `/papers/{paper_id}` — the
before-`papers.router` mount handles this.

- [ ] **Step 6: `ruff format .`, `python tools/check_line_budget.py --list`, commit**

```bash
ruff format .
python tools/check_line_budget.py --list
git add app/backend/api/routers/merge.py app/backend/api/app.py tests/test_library_merge.py
git commit -m "feat(merge): merge/preview/undo/origin API endpoints (#17 t8)"
```

---

### Task 9: Frontend — merge dialog + Merge action + undo affordances

**Files:**
- Create: `app/frontend/js/<next>_merge.jsx` (pick the next free numeric prefix; see existing chunk order)
- Modify: the library multi-select toolbar chunk (where bulk actions live) to add a **Merge** button enabled
  when exactly 2 are selected; the Detail pane chunk (`js/25_detail.jsx`) to show the "Merged from … — Un-merge"
  line via `GET /papers/{id}/merge-origin`.
- Build: `python tools/build_frontend.py`

**This task has no unit test (no browser automation in the repo). Its gate is the manual verification script.**

- [ ] **Step 1: Read the neighboring chunks to match conventions**

Read: `app/frontend/js/25_detail.jsx` (Detail pane + how it fetches), a modal/dialog chunk for the recipe
(e.g. an existing confirm modal), and the library toolbar chunk that renders bulk/multi-select actions. Use the
same `fetch` shim (`js/00_lib.jsx`), the same `.btn-*` classes (per `.claude/DESIGN.md` — read it before any
CSS), and the shared-IIFE function-hoist pattern (a new chunk's components are visible to callers without an
import, per the inc-208/222 precedent).

- [ ] **Step 2: Build the merge dialog component** (`MergeDialog`) in the new chunk

Behavior: given `paperA`, `paperB` ids, `GET /papers/{a}/merge-preview/{b}`; render:
- a header choosing which is the survivor (default A);
- for each `fields[]` entry with `agree === false`, a radio row (A value / B value) + an inline text edit; for
  `agree === true`, a read-only auto-filled row;
- the `association_counts` union line ("Combines N annotations · M tags · … onto the survivor");
- each `warnings[]` detail (incl. the derived-stale note);
- a **Merge** confirm → `POST /papers/merge` with `{canonical_id, merged_id, resolved_metadata}` (only the
  fields the user changed/picked, matching the Details-edit `edits` shape); on success show a toast
  "Merged → [title]. Undo" wired to `POST /merge/{op_id}/undo`.

Follow the honesty/DESIGN rules: destructive confirm uses the danger recipe; provenance/primary stays indigo.

- [ ] **Step 3: Add the Merge action to the library multi-select toolbar**

Enable it only when exactly 2 papers are selected (MVP scope). Clicking opens `MergeDialog` with the two ids.

- [ ] **Step 4: Add the Detail "Merged from … — Un-merge" affordance**

In `js/25_detail.jsx`, on load fetch `GET /papers/{id}/merge-origin`; if non-null, render a small line
"Merged from *[merged_from_title]* on [date] — **Un-merge**" whose button calls `POST /merge/{op_id}/undo` and
refreshes.

- [ ] **Step 5: Rebuild the frontend + line-budget check**

```bash
python tools/build_frontend.py
python tools/check_line_budget.py --list
```
Expected: build succeeds; no chunk over 600. If `25_detail.jsx` crosses the cap, extract the merge-origin line
into the new merge chunk (the inc-207 TagsRow precedent).

- [ ] **Step 6: Manual verification script** (record the result in the increment notes)

1. `uvicorn app.backend.api.app:app --port 8888` (do **not** touch a running instance; use a scratch DB).
2. Import/create two entries for the same paper (e.g. a preprint + published version).
3. Select both → **Merge** → confirm the field-by-field picker shows conflicts, pick per field.
4. Confirm merge → the merged-away entry disappears from the library; the survivor shows the union
   (annotations/tags/PDFs), and **opening a citation from the survivor still resolves the correct PDF + page**
   (coordinate-honesty invariant intact after re-point).
5. Open the survivor's Detail → **Un-merge** → confirm both entries return and the survivor's metadata reverts.

- [ ] **Step 7: `ruff format .` (no-op for JSX), commit**

```bash
git add app/frontend/js/ app/backend/api/frontend.py callosum-app.html
git commit -m "feat(merge): merge dialog + Merge action + un-merge affordances (#17 t9)"
```
(Commit whatever `build_frontend.py` regenerates — confirm the exact built-artifact path it writes.)

---

### Task 10: Gates + docs

**Files:**
- Create: `.claude/security-audits/2026-07-07_library-merge.md`
- Create: `.claude/qa-routes/route_<n>_library_merge.md` (+ any fixture per `.claude/QA-POLICY.md`)
- Modify: `app/backend/help/help_content.md`, `.claude/changes.md`, `.claude/docs/INCREMENT-BACKLOG.md` (+
  `-DONE.md`), `.claude/docs/increment-notes/INCREMENT-<N>-NOTES.md`, `.claude/CLAUDE.md` (feature paragraph +
  new modules)

- [ ] **Step 1: Security & data-safety audit** — write `.claude/security-audits/2026-07-07_library-merge.md`
  covering: single-transaction atomicity (inject a mid-merge failure → assert rollback: no `merge_operations`
  row, both papers untouched — add this as a test); un-merge exactness (the Task-6 round-trip is the evidence);
  table/column allowlist is constant, never request-derived (rule #3); no new external fetch / no new file
  write; the `merged_into` filter can't leak a merged-away paper (Task-7 tests); `merged_into` guards purge.
  Negative paths (self-merge, trashed/already-merged operands, double-undo) → honest 4xx. End with
  **Security Audit: PASS** (or RISK ACCEPTED BY USER).

- [ ] **Step 2: Add the atomicity rollback test** (referenced by the audit)

```python
def test_merge_rolls_back_on_failure(tmp_path, monkeypatch):
    engine = _fresh_engine(tmp_path)
    with engine.connect() as conn:
        a = _add_paper(conn, title="A", csl_json={}); b = _add_paper(conn, title="B", csl_json={})
        conn.commit()
    import app.backend.persistence.merge_repo as mr
    monkeypatch.setattr(mr, "_rewrite_json_scopes", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    with engine.connect() as conn:
        import pytest
        with pytest.raises(RuntimeError):
            merge_papers(conn, canonical_id=a, merged_id=b, resolved_metadata={})
        conn.rollback()
    with engine.begin() as conn:
        assert conn.execute(select(func.count()).select_from(merge_operations)).scalar_one() == 0
        assert conn.execute(select(papers.c.merged_into).where(papers.c.id == b)).scalar_one() is None
```

- [ ] **Step 3: QA route** — add `.claude/qa-routes/route_<n>_library_merge.md` per `.claude/QA-POLICY.md`
  declaring the 4 new API surfaces + the merge dialog / undo controls, asserting the honesty invariants
  (post-merge citations resolve; egress unchanged; signal-not-verdict N/A). Run
  `python tools/qa/build_surface_map.py check` — the new API surfaces must be covered (hard gate).

- [ ] **Step 4: Docs** — `changes.md` entry; move #17 + #16 from `INCREMENT-BACKLOG.md` to `-DONE.md`; write
  `INCREMENT-<N>-NOTES.md` (Implemented / key detail = the reversible snapshot + the low-blast-radius
  `deleted_at`+`merged_into` hiding / manual verification / pytest count); update `CLAUDE.md` (a merge
  paragraph + the new persistence/router modules); refresh the help corpus (a "Merging duplicates" section) and
  advance the `HELP-DOCS-SYNCED` marker.

- [ ] **Step 5: Experience pass (rule #11)** — dispatch the **corpus-builder** persona (the EndNote/Zotero
  migrant with visible duplicates) per `.claude/EXPERIENCE-PASS.md`: merge a preprint into its published
  version, confirm the union is right, confirm un-merge recovers. Record the finding in the increment notes;
  fix anything cheap, else file a UX follow-up.

- [ ] **Step 6: Full suite + format, then final commit**

```bash
pytest -q
ruff format .
python tools/check_line_budget.py --list
git add -A ':!www'
git commit -m "docs(merge): security audit + QA route + help/changes/increment + experience pass (#17/#16 t10)"
```

---

## Self-Review (completed against the spec)

- **Spec coverage:** re-point surface buckets 1–5 → Tasks 4–5 + allowlist Task 2; reversibility → Task 6;
  `merged_into` low-blast-radius hiding → Tasks 1/7; field-by-field picker → Task 3 preview + Task 9 dialog;
  API → Task 8; gates (security/QA/Experience) → Task 10. All spec sections map to a task.
- **Placeholder scan:** the only intentional deferrals are `<next>` (frontend chunk number) and `<n>`/`<N>` (QA
  route + increment numbers) — these are assigned at file-creation time by their task and are not logic gaps.
  Test harness helper names (`build_test_app`, `list_papers` signature) are flagged in-task to confirm against
  the real `tests/api_helpers.py` / `repository.py`.
- **Type consistency:** `merge_papers(*, canonical_id, merged_id, resolved_metadata) -> int`,
  `unmerge(*, merge_operation_id) -> int`, `merge_preview(conn, canonical_id, merged_id) -> dict`,
  `merge_origin(conn, paper_id) -> dict | None` — used identically across Tasks 3–10. Snapshot keys
  (`canonical_metadata_before` / `repoints` / `drops` / `inserts` / `json_edits`) are defined in Task 4, extended
  in Task 5 (`inserts`), and consumed in Task 6 — consistent.
- **Known implementer cleanups flagged in-task:** the `if False else` copy-paste (Task 5 step 3), the possibly
  unused `ForeignKey` import (Task 2), the `_repoint_or_drop` delete-branch simplification (Task 4). These are
  called out so a reviewer expects them.

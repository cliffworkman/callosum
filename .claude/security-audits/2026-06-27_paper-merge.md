# Security audit — non-destructive paper merge (inc 161)

**Date:** 2026-06-27
**Feature:** Merge duplicate papers into one surviving record (`POST /papers/merge`), launched from the Duplicates
modal and the library bulk bar. Engine: `app/backend/metadata/paper_merge.py::merge_papers`.
**Audit triggers:** a new API endpoint + a new data-consolidation write path spanning 3+ files (rule #1/§audit).

## Scope

The merge folds every "merged-away" copy's source data (attachments, chunks, annotations, notes, external
identifiers, tags, collection + manual-axis memberships) onto a chosen survivor, composes the survivor's scalar
metadata from the user's per-field picks, records a "Merged from…" lineage note, sets the primary attachment, and
soft-deletes the merged copies. Entirely local; no migration; no new dependency.

## Threat review

- **Input validation (boundary, rule #4).** `MergePapersRequest`: `survivor_id:int`, `merged_ids` capped
  `[1, 20]`, `metadata` a typed `MergeMetadata` with `extra="forbid"` (an unknown field → 422), `primary_attachment_id:int|None`.
  `merge_papers` re-validates regardless of the endpoint: every id must **exist and be live** (`deleted_at IS NULL`),
  ids must be distinct, the survivor must not be in `merged_ids`, and `primary_attachment_id` (if given) must belong
  to a paper in the merge set. All failures raise `MergeValidationError` → **422** before any write (fail-fast).
- **SQL injection (rule #3).** All reads/writes are SQLAlchemy Core bound parameters / table-object expressions
  (`update(...).where(table.c.paper_id == :v).values(...)`, `insert(...).prefix_with("OR IGNORE")`,
  `select(...).where(... .in_(all_ids))`). No string interpolation into SQL. The `_REPOINT_TABLES` /
  `_UNIQUE_ID_COLS` / `_ADOPT_COLS` are **module constants**, never request-derived.
- **UNIQUE-constraint safety (data integrity).** Soft-delete keeps the husk row, so its UNIQUE non-DOI identifier
  columns (`openalex_work_id`/`semantic_scholar_paper_id`/`zotero_*`) are **nulled first** to free them for the
  survivor (the husk's `csl_json` retains the values for audit). DOI is intentionally non-unique as of migration
  `0040_allow_duplicate_paper_dois`, so a duplicate DOI can mark records that need merging. Composite-PK
  tables (`paper_tags`/`collection_papers`/`cluster_node_papers`) are migrated with `INSERT OR IGNORE`; the
  no-per-paper-UNIQUE tables are re-pointed with a plain `UPDATE` (verified against the schema). `paper_external_identifiers`
  is globally UNIQUE on `(provider, identifier)`, so two rows can't share one → `UPDATE` cannot collide.
- **Data egress (invariant #3).** None. The merge reads/writes only the local DB; it makes **no** external call
  and routes no library text anywhere. Not behind (and does not touch) the Gemini egress gate.
- **Destructive-action safety.** No hard delete: merged copies are **soft-deleted** (restorable Trash husks that
  retain their `csl_json`). **No on-disk PDF is deleted** (attachments are re-pointed, files untouched). **No vector
  is deleted** (chunk embeddings follow their re-pointed chunk by id; the husk's paper-level embedding is left,
  excluded from retrieval per inc 66). The whole operation runs in one transaction (`conn.commit()` at the end of
  the endpoint) → all-or-nothing; a `ValueError` mid-way leaves the txn uncommitted.
- **File-path / SSRF / secrets.** No file paths are constructed, no URLs are fetched, no secrets are read or logged.
- **Resource caps.** `merged_ids` capped at 20; each migration is a bounded set of `UPDATE`/`INSERT` over one
  paper's rows. No unbounded loops or user-controlled iteration counts.
- **Supply chain.** No new dependency.

## Negative-path checks (from `tests/test_paper_merge.py`)

- `merged_ids=[]` / `survivor ∈ merged_ids` / non-existent id / **trashed** id → `MergeValidationError` (422). ✓
- composed DOI equal to an outside live paper's DOI → allowed, so the duplicate can be cleaned up by merge. ✓
- endpoint: self-merge → 422; duplicate-DOI merge → 200; happy path → 200 + merged copy in Trash, survivor live. ✓
- idempotent shared-tag merge does not violate the `paper_tags` composite PK. ✓
- the husk's DOI column and `csl_json["DOI"]` are preserved; non-DOI unique columns are freed for adoption. ✓

## Principles (rule #9)

The change touches **provenance + inspectability**, so the gate was run. The design *preserves* both: the lineage
note + the Trash husk keep the source records inspectable; the human drives every pick (survivor, fields, primary
PDF) — nothing is auto-decided; the fact/candidate distinction + egress posture are unchanged. The misaligned easy
path is the **existing** delete-the-redundant-copy (lossy); this merge is the aligned, union-preserving alternative.
No new claim/signal about the literature; no A-A veto in play (own-library consolidation — no accusation, no paywall
circumvention, no egress).

## Result

**Security Audit: PASS.** Local, bound-param, fail-fast-validated, non-destructive (soft-delete only, no file/vector
deletion), transaction all-or-nothing, no egress, no new dependency.

# Increment 262 — 600-line cap cleanup: split `routers/methods.py` + `persistence/schema.py` (backlog #47)

**Type:** infra / hygiene. Behavior-preserving refactor — no new features, no API/DB/schema changes, no migration.

## Context

Two `app/` files had drifted **over** the rule-#1 600-line hard cap through inc 261 while the CLAUDE.md
watch-list note stayed stale on both (inc 261 deliberately avoided landing new code in either — the CRediTer
router was a *new* file, not an addition to `methods.py`). Backlog #47 is the cleanup: split each back under the
cap following the established named precedents, proven by before/after test runs.

- `app/backend/api/routers/methods.py` = **619**
- `app/backend/persistence/schema.py` = **628**

## Implemented

### 1. `routers/methods.py` 619 → **450** (the inc-226 `paper_enrich.py` sibling-router pattern)

- **New `app/backend/api/routers/methods_retraction.py` (186):** the retraction endpoint cluster moved verbatim —
  `GET /papers/{paper_id}/retraction`, `POST /methods/retraction/run` + its `GET …/run/{job_id}` +
  `GET /methods/retraction/summary`, `GET|POST /methods/retraction/database[/refresh][/{job_id}]`, and the two
  background job runners (`_run_retraction_all_job`, `_run_retraction_db_refresh_job`) + their Pydantic models.
  The cluster was already self-contained: all shared state is reached via `request.app.state`
  (`retraction_jobs` / `retraction_db_jobs` / `retraction_checkers` / `retraction_watch_client`, all set up in
  `api/app.py`), so no cross-cluster coupling had to be threaded. The new router carries only its own scoped
  imports (`json`, `apply_retraction`/`detect_retraction`, `retraction_db_status`,
  `count_retraction_flagged`/`get_retraction_status`, the `retraction_watch.adapter`).
- **`app/backend/api/app.py`:** added `methods_retraction` to the router import block and
  `api.include_router(methods_retraction.router)` beside the `methods.router` include. Include order is
  irrelevant here — `/methods/retraction/*` and `/papers/{id}/retraction` overlap no other route.
- **`routers/methods.py`** keeps the statcheck / GRIM / effect-size / p-curve / bayes / completeness producers and
  loses the now-dead imports the move orphaned: `json` (used only by the retraction status endpoint), the
  retraction-only domain imports, and 2 of the 4 `signals_repo` symbols. **Also removed pre-existing dead code:**
  `import logging` + `_log = logging.getLogger("callosum.methods")` — `_log` was never referenced anywhere in the
  file (rule #5).

### 2. `persistence/schema.py` 628 → **558** (the inc-137 `schema_findings.py` table-group extraction)

- **New `app/backend/persistence/schema_summaries.py` (107):** the verification-output table group moved verbatim
  — `summaries`, `summary_sentences`, `citation_mappings`, `evidence_quotes`. It imports **only** `metadata` (+ the
  shared CHECK helpers) from `schema_base`, never from `schema`, so there is no circular import; `schema.py`
  re-exports the four names (`# noqa: E402,F401`) so existing `from …schema import summaries` paths keep working and
  importing `schema` still registers the tables on the shared `metadata`.
- **`persistence/schema_base.py`:** the `enum_check` / `non_empty_check` CHECK-constraint helpers and the
  `CITATION_MAPPING_STATUSES` value set moved here (added `CheckConstraint` to its sqlalchemy import). `schema.py`
  now imports the two helpers back (they are used across the papers/attachments/chunks/embeddings/jobs tables that
  stayed); `CITATION_MAPPING_STATUSES` is summaries-only, so it moved wholly with the group and is no longer
  imported into `schema.py`.

## Key technical detail

Relocating `enum_check`/`non_empty_check`/`CITATION_MAPPING_STATUSES` to `schema_base` (rather than importing them
from `schema.py` into `schema_summaries.py`) is the load-bearing choice. Both `schema.py` and the new
`schema_summaries.py` need those helpers; `schema_base` is the one module both already depend on for `metadata`, and
it imports nothing from the persistence package. Sourcing the helpers there gives one definition with **no import
ordering fragility** — had `schema_summaries` imported the helpers from `schema`, importing `schema_summaries` before
`schema` finished defining them would break. The `chunk_id` foreign keys in `citation_mappings`/`evidence_quotes`
reference `chunks` (still in `schema.py`) as lazy **string** FKs, which SQLAlchemy resolves against the shared
`metadata` regardless of which module defines a table first.

## Verification

Behavior-preserving, proven mechanically rather than by manual UI (no user-facing surface changed):

1. **Line counts (all < 600):** `methods.py` **450**, `methods_retraction.py` **186**, `schema.py` **558**,
   `schema_summaries.py` **107**, `schema_base.py` **34**.
2. **Import + `create_all`:** `import app.backend.persistence.schema` then
   `schema.metadata.create_all(create_engine("sqlite://"))` → all **47** tables register (the four summary tables
   among them) and every FK resolves; the four names are present as attributes on `schema`.
3. **`ruff format` + `ruff check .`** clean (the auto-fix pruned the now-unused `CITATION_MAPPING_STATUSES` import
   from `schema.py` and re-sorted the re-export block; CI runs `ruff format --check`).
4. **Focused subset** (`test_retraction`, `test_retraction_watch`, `test_statcheck`, `test_summaries`,
   `test_findings_review`, `test_health`) → **62 passed**.
5. **Full suite** (`pytest --ignore=tests/test_mcp_server.py`) → **1044 passed, 1 skipped** (unchanged — the
   refactor moved code without changing behavior; no test edits needed).

## Pytest

**1044 passed, 1 skipped** (unchanged from inc 261).

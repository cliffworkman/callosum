# Security Audit — Workbench SP2b: convert-all + stat-package exports (inc 258)

**Date:** 2026-07-03
**Scope:** One new endpoint (`POST /workbench/projects/{project_id}/convert-all`) + two new response shapes on the
existing export endpoint (`GET …/export?format=metafor|revman`) + a new pure module
(`app/backend/persistence/workbench_export.py`). Trigger: audit gate #1 (new API endpoint).

## What changed
- `convert_all` batches the already-audited per-row `convert` over every row of a project's `project_view`
  (reusing the cells already loaded in the view — no per-row extra query). Rows whose inputs are incomplete/invalid
  are left **honestly un-converted** (`set_converted(None)`) and named in an `incomplete` list — never a fabricated
  value. Returns `{total, converted, incomplete}` — **no pooled/summary estimate** (the load-bearing boundary).
- `workbench_export.py` adds `metafor_csv` (per-study `yi/vi/sei/ci` + moderators) and `revman_csv` (raw per-group
  study data per design). The pre-existing generic CSV body + `_csv_safe` moved here verbatim, with one correctness
  hardening (below). The router's export endpoint now dispatches `csv|metafor|revman` through `FORMATS` and keeps
  `audit` as JSON.

## Threat review
- **Input validation (rule #4).** `project_id` is a path `int`; `format` is checked against a 4-value allowlist
  (`csv|metafor|revman|audit`) → unknown format is **422**, never reaches the dispatch. No user string reaches SQL.
- **Parameterised SQL (rule #3).** Unchanged — all access is via `workbench_repo` SQLAlchemy Core bound params; the
  export module touches **no DB** (it is a pure `view -> str` transform).
- **Data egress (invariant #3).** None. The workspace is fully local — no external fetch, no LLM, no network. This
  slice adds no egress path. (QA route 65 asserts 0 genai-host requests.)
- **CSV / formula injection.** Every emitted cell passes through `_csv_safe`. It was **hardened**: it now
  neutralises a leading `=/+/-/@` **only when the value is not a plain number**, so a genuine formula-like string
  (`=DANGER()`, `-1+cmd`) is still `'`-prefixed, while a legitimate **negative number** (a negative Hedges' g, a
  negative mean-change) passes through unchanged — the old guard corrupted negatives into `'-0.59`, which would have
  made the metafor `yi` column non-numeric in R. Regression-pinned (`test_csv_escapes_formula_injection` still green;
  new tests assert a negative `yi` stays clean).
- **File-path safety.** The `Content-Disposition` filename is `extraction-{int}{-format}.csv` where `format` is from
  the allowlist and `id` is an int — **no user-controlled string** in the header → no header/filename injection.
- **Resource exhaustion.** `convert-all` iterates the project's rows once, doing O(1) arithmetic per row over cells
  already loaded in `project_view` (no N+1 query). Rows are user-created one-at-a-time via the UI, so the count is
  self-bounded; each `effectsize.convert` is bounded arithmetic (`MAX_N` caps inputs). No amplification.
- **Secret handling.** None involved.
- **Supply chain.** No new dependency (`csv`/`io` stdlib; scipy/effectsize already present).

## Negative-path checks (run)
- `POST /workbench/projects/999999/convert-all` (unknown project) → **404** (test).
- `convert-all` over a mixed project → the blank row is reported in `incomplete` and stays `converted: null`; the
  response has **exactly** `{total, converted, incomplete}` (no summary/pooled key) — test-pinned.
- `GET …/export?format=bogus` → **422** (existing test covers the allowlist).
- A design with no converter mapping → **422** (guarded like `convert_row`).
- Negative effect size / negative mean → exported as a clean number, not neutralised (test).
- Spreadsheet formula in a label/moderator (`=DANGER()`) → `'`-prefixed in every format (test).

## Result
**Security Audit: PASS.** Local-only, no egress, no new dependency; a thin batch over the already-audited SP1
converter + a pure CSV formatter with hardened (number-aware) injection neutralisation. The per-study boundary is
preserved — no pooling/aggregation is introduced.

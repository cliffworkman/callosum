# Security audit — Extraction workspace (inc 253, workbench SP2a-1)

**Date:** 2026-07-02
**Feature:** the meta-analysis extraction workspace — `persistence/schema_workbench.py` (ma_projects/ma_rows/ma_cells,
migration 0033) + `persistence/workbench_repo.py` + `routers/workbench.py` (11 CRUD/convert/export endpoints) + the
`45_workbench.jsx` "Extract" center-tab. Assemble a dataset from the library (template → rows → provenance-anchored
cells), convert each row via the SP1 converter, export a metafor/JASP CSV + a provenance audit JSON.

**Audit-gate trigger:** #1 (new API endpoints + request schemas) + #3 (a new file-write / DB-write path) + #5 (net-new
feature spanning >3 files, ~500 LOC) + a migration. **No** external fetch, egress, LLM, or new dependency.

## The load-bearing boundary — extract/structure/convert/export, never synthesize

The workspace inherits the SP1 converter's boundary and extends it to a stateful store: it **converts one study
(row) at a time and defines no endpoint that combines two rows.** There is no pooling / heterogeneity /
meta-regression / bias-inference / forest-plot code path — that is metafor/JASP/RevMan's job. **Export is data +
provenance, never a synthesized estimate.** Every value is **hand-entered by a human** (typed, or — SP2a-2 —
confirmed from a PDF selection); nothing is computed or inferred into a cell. The panel + the `route_65` QA route
assert this (no pool/aggregate/forest control).

## Threat review

- **Input validation / boundary (rule #4):** every request body is a Pydantic model with `extra="forbid"` + bounded
  fields (name ≤300, protocol ≤8000, value ≤500, quote ≤4000, bbox_json ≤2000, page ≥0). `design` is checked against
  the `DESIGNS` allowlist (422 otherwise). A cell PUT's `field_key` must be in the project's template (422 otherwise).
  A template PATCH is validated by `_validate_template` — field keys match `^[A-Za-z0-9_]{1,80}$`, types are an
  allowlist, and the design's **role columns cannot be removed or their role hijacked** (a fake role on a non-spine
  column → 422), so the deterministic convert hook can't be tampered.
- **Injection / SQL (rule #3):** all data access is SQLAlchemy Core bound parameters (`workbench_repo.py`); no
  string-built SQL. `field_key` reaches SQL only as a bound value (and only after the template allowlist check).
- **CSV formula injection:** the CSV export prefixes any cell whose first char is `= + - @` with `'` (`_csv_safe`),
  neutralizing spreadsheet formula execution; `csv.writer` handles comma/quote escaping. Test-pinned
  (`test_csv_escapes_formula_injection`).
- **Output encoding (XSS):** the frontend renders project/row/cell/converted values as React text nodes (no
  `dangerouslySetInnerHTML`); no XSS surface.
- **SSRF / external calls / egress:** NONE. Fully local — no network call, no LLM, no external fetch. The egress
  invariant (#3) is untouched; a `route_65` assertion fails the run on any genai-host request.
- **The `paper_id` no-FK column:** `ma_rows.paper_id` references `papers.id` but is a plain column (no FK) so a row
  survives a paper purge (the inc-216 `agent_writes.target_paper_id` pattern) — the dataset is the user's own
  extracted data. `project_view` tolerates a gone paper (title → None). Test-pinned
  (`test_cascade_delete_and_paper_survives_purge`).
- **Resource caps:** CRUD is O(1)/O(rows); no loop over user-sized external data, no recompute; convert is the SP1
  O(1) arithmetic wrapped fail-closed → 422. A project/row/cell count is user-scale (dozens); no pagination needed in
  SP2a-1.
- **Migration:** 0033 is additive + guarded (create-if-absent), no-op downgrade (0001's metadata drops the tables) —
  the 0021-0032 pattern. Applies cleanly (verified in the test run).
- **Supply chain:** no new dependency (scipy/SQLAlchemy already present).

## Negative-path checks (from `tests/test_workbench.py`, hermetic)

- Create with an unknown design → 422; a blank name → 422 (Pydantic min_length).
- Add a row with an unknown `paper_id` → 404.
- PUT a cell to a field not in the template → 422.
- Convert a row with empty/degenerate cells → 422 (the SP1 fail-closed, wrapped).
- Template PATCH: add a moderator column → 200; remove a role column → 422; a non-role column claiming a role → 422.
- CSV export neutralizes a leading `=` cell; a deleted project → 404; the `format` param off-allowlist → 422.
- A purged paper doesn't break `project_view`/export (no-FK column); DELETE project CASCADEs rows + cells.

## Verdict

**Security Audit: PASS.** Local, no egress/LLM/external-fetch/new-dependency; bound-param SQL; typed/validated +
allowlisted bodies; CSV formula-injection neutralized; the convert-spine (role columns) tamper-protected; the
extract-never-synthesize boundary structural + QA-asserted; additive/guarded migration.

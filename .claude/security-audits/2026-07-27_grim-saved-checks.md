# Security audit — saved per-paper GRIM/GRIMMER checks

**Date:** 2026-07-27
**Status:** complete — PASS

## Scope

Three new endpoints backing a small per-paper "saved checks" log for the METHODS "Data" (GRIM)
section (`app/backend/api/routers/methods_grim_saved.py`): `GET/POST /papers/{paper_id}/grim-checks`
and `DELETE /papers/{paper_id}/grim-checks/{check_id}`. The existing `POST /methods/grim` calculator
is untouched. This is the first time GRIM becomes paper-aware at all (previously it received no
`ctx`/paper id, so nothing could ever be attached to a paper).

## Principles-gate note (rule #9)

The easy/misaligned implementation would let the frontend POST its already-computed `grim`/`grimmer`
verdict for storage verbatim — trusting a client-asserted fact instead of the deterministic
substrate. The aligned design implemented here: **the save endpoint takes only the raw reported
inputs (mean/sd/n/items) and re-derives the verdict server-side**, calling `grim_test`/`grimmer_test`
identically to `POST /methods/grim`. A saved record can never drift from what the deterministic
function actually returns for those inputs — the computation is pure arithmetic, effectively free to
redo, so there is no cost trade-off pushing toward the misaligned shortcut. Verified directly:
`test_save_recomputes_server_side_and_matches_calling_grim_directly` calls `grim_test`/`grimmer_test`
independently and asserts the saved record matches exactly.

## Threat review

- **Input validation:** `mean`/`sd` are re-validated by `grim_test`/`grimmer_test` themselves
  (`ValueError`/`ArithmeticError` → 422, the exact same error path `/methods/grim` already uses);
  `label` is capped at 120 chars via pydantic `Field(max_length=120)` (the `paper_urls.py` precedent).
  `paper_id`/`check_id` are path ints, checked via `get_paper`/the delete's own rowcount.
- **Output encoding / injection:** parameterized SQLAlchemy Core throughout (rule #3); the stored
  `result_json` is a Pydantic-validated `GrimComputeResponse.model_dump()` — no raw user text is ever
  stored verbatim into a column read back as HTML/script.
- **Authorization scoping:** `delete_grim_check` requires `(paper_id, check_id)` together — deleting
  under the wrong `paper_id` 404s and leaves the real owner's row untouched (verified:
  `test_delete_removes_it_and_is_scoped_to_the_owning_paper`), so a client can't delete another
  paper's saved check by guessing a `check_id` and pairing it with an arbitrary `paper_id` — though
  note this app has no multi-user auth model (single-user local app); the scoping exists for
  correctness (no cross-paper data corruption), not as a security boundary between distinct users.
- **SSRF / external calls / data egress:** none — pure local computation + SQLite read/write. No LLM,
  no external API, untouched by the egress gate (invariant #3).
- **Resource caps:** no new unbounded loop or fan-out; each request does exactly one GRIM/GRIMMER
  computation (already bounded, the existing `/methods/grim` cost) plus one row insert/delete.
- **Supply chain:** no new dependency. One new table (`paper_grim_checks`, additive migration
  `0057`), no changes to any existing table.

## Negative-path checks

All verified by `tests/test_grim_saved.py` (5 passed):
- Empty saved list for a never-checked paper; 404 on all three routes for a nonexistent paper.
- A saved record's `grim`/`grimmer` fields match calling `grim_test`/`grimmer_test` directly on the
  same inputs (the deterministic-substrate proof).
- List is newest-first and strictly paper-scoped — a second paper's list never includes another
  paper's saved checks.
- Delete under the wrong `paper_id` → 404, real row untouched; delete under the correct pair → 204;
  a second delete of the same id → 404.
- `n=0`, a non-numeric mean, and an oversized (121-char) label all → 422, never a crash.

## Result

No exploitable issue or new sensitive boundary was found. The endpoints reuse GRIM's existing,
already-audited pure-computation path; the only new persistence is a small, correctly-scoped
append-only log with no cross-paper leakage.

**Security Audit: PASS**

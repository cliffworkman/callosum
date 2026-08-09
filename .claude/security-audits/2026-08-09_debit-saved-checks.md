# Security audit — DEBIT check + saved per-paper DEBIT checks

**Date:** 2026-08-09
**Status:** complete — PASS

## Scope

Four new endpoints, all mirroring the already-audited GRIM/GRIMMER pattern
(`.claude/security-audits/2026-07-27_grim-saved-checks.md`) exactly: the stateless
`POST /methods/debit` calculator (`app/backend/api/routers/methods.py`) and the paper-aware saved-checks
log (`app/backend/api/routers/methods_debit_saved.py`) — `GET/POST /papers/{paper_id}/debit-checks` and
`DELETE /papers/{paper_id}/debit-checks/{check_id}`. This audit exists because the change technically
crosses the net-new-feature trigger (a new endpoint set + a new table across 6+ files); the content below
confirms the mirroring is exact rather than re-deriving the threat model from scratch.

## Principles-gate note (rule #9)

Identical shape to the GRIM audit's finding: the save endpoint takes only the raw reported inputs
(mean/sd/n) and re-derives the verdict server-side via `debit_test`, identically to `POST /methods/debit`
— never trusting a client-asserted verdict. Verified directly:
`test_save_recomputes_server_side_and_matches_calling_debit_directly` calls `debit_test` independently
and asserts the saved record matches exactly.

## Threat review

- **Input validation:** `mean`/`sd` are re-validated by `debit_test` itself (`ValueError`/`ArithmeticError`
  → 422, the same error path `/methods/debit` uses); `n < 2` is explicitly rejected (a sample SD is
  undefined for n=1, which would otherwise divide by zero); `label` is capped at 120 chars via pydantic
  `Field(max_length=120)`, same as GRIM's. `paper_id`/`check_id` are path ints, checked via
  `get_paper`/the delete's own rowcount.
- **Output encoding / injection:** parameterized SQLAlchemy Core throughout (rule #3); the stored
  `result_json` is a Pydantic-validated `DebitComputeResponse.model_dump()` — no raw user text is stored
  verbatim into a column read back as HTML/script.
- **Authorization scoping:** `delete_debit_check` requires `(paper_id, check_id)` together, same as
  `delete_grim_check` — deleting under the wrong `paper_id` 404s and leaves the real owner's row
  untouched (verified: `test_delete_removes_it_and_is_scoped_to_the_owning_paper`). Same single-user-app
  caveat as the GRIM audit: this scoping is for correctness, not a security boundary between distinct
  users.
- **SSRF / external calls / data egress:** none — pure local computation + SQLite read/write. No LLM, no
  external API, untouched by the egress gate.
- **Resource caps:** no new unbounded loop or fan-out; each request does exactly one DEBIT computation
  (bounded — the mean's own GRIM-consistency check is the same bounded search already audited for GRIM)
  plus one row insert/delete.
- **Supply chain:** no new dependency. One new table (`paper_debit_checks`, additive migration `0071`),
  no changes to any existing table.

## Negative-path checks

All verified by `tests/test_debit.py` (8 passed) + `tests/test_debit_saved.py` (5 passed):
- Empty saved list for a never-checked paper; 404 on all three saved-check routes for a nonexistent paper.
- A saved record's `debit` field matches calling `debit_test` directly on the same inputs (the
  deterministic-substrate proof).
- List is newest-first and strictly paper-scoped.
- Delete under the wrong `paper_id` → 404, real row untouched; delete under the correct pair → 204; a
  second delete of the same id → 404.
- `n=0`/`n=1`, a non-numeric mean, and an oversized (121-char) label all → 422, never a crash.

## Result

No exploitable issue or new sensitive boundary was found. The endpoints reuse the already-audited GRIM
pattern's exact shape (deterministic recomputation, paper-scoped deletion, no egress, no new dependency);
the only genuinely new logic is the DEBIT arithmetic itself, which is pure local computation with no
external inputs beyond the same bounded numeric fields GRIM already validates.

**Security Audit: PASS**

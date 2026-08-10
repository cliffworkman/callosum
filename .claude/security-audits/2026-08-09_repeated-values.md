# Security audit — repeated-values checker + saved per-paper checks

**Date:** 2026-08-09
**Status:** complete — PASS

## Scope

`app/backend/api/routers/methods_duplicate_values.py` — a new endpoint set mirroring the already-audited
GRIM/DEBIT saved-checks pattern (`2026-07-27_grim-saved-checks.md`, `2026-08-09_debit-saved-checks.md`) almost
exactly: the stateless `POST /methods/duplicate-values` calculator and the paper-aware saved-checks log
(`GET/POST /papers/{paper_id}/duplicate-value-checks`, `DELETE /papers/{paper_id}/duplicate-value-checks/
{check_id}`). Written to confirm the mirroring, not re-derive the threat model.

## Principles-gate note (rule #9)

The value of this audit is less about a new trust boundary and more about a new *honesty* boundary: unlike
GRIM/GRIMMER/DEBIT, this heuristic has no peer-reviewed method behind it (confirmed via search — `scrutiny`'s
own docs call its `duplicate_count`/`duplicate_tally` "a blunt tool"). The result model deliberately carries no
`consistent`/`flagged` field, and the frontend deliberately renders no `cite-status verified/flagged` pill —
only a plain `value → count` list — so this tool cannot visually borrow the credibility of the validated checks
next to it (Principle #2, signal not verdict, applied to *presentation* as much as computation).

## Threat review

- **Input validation:** `values` is a bounded list (1–500 non-empty entries after stripping, enforced in
  `count_repeated_values` itself — `ValueError` → 422, same shape as GRIM/DEBIT); `label` is capped at 120
  chars via pydantic `Field(max_length=120)`, same as the sibling save endpoints.
- **Output encoding / injection:** parameterized SQLAlchemy Core throughout (rule #3); the stored `values_json`/
  `result_json` are JSON-serialized lists/dicts of plain strings and counts — no raw user text is interpreted
  as markup or executed.
- **Authorization scoping:** `delete_duplicate_value_check` requires `(paper_id, check_id)` together — deleting
  under the wrong `paper_id` 404s and leaves the real row untouched (verified:
  `test_delete_removes_it_and_is_scoped_to_the_owning_paper`), same posture as GRIM/DEBIT.
- **SSRF / external calls / data egress:** none — pure local computation (a `Counter` over a bounded list) +
  SQLite read/write. No LLM, no external API.
- **Resource caps:** the 500-value cap bounds the compute cost; the save path does exactly one insert.
- **Bypass surface:** no new dependency — the endpoint has no auth gate of its own (matches GRIM/DEBIT's own
  posture, all local-only tools with no sensitivity beyond normal library data).
- **Data exposure:** the saved record stores the user's own entered values verbatim (their own transcription of
  a paper they're reading) — no different in sensitivity from the mean/SD/N GRIM and DEBIT already store.

## Negative-path checks

All verified by `tests/test_duplicate_values.py` (8 passed) + `tests/test_duplicate_values_saved.py` (5 passed):
- Empty saved list for a never-checked paper; 404 on all three saved-check routes for a nonexistent paper.
- A saved record's `duplicate_values` field matches calling `count_repeated_values` directly on the same
  inputs (the deterministic-substrate proof).
- List is newest-first and strictly paper-scoped.
- Delete under the wrong `paper_id` → 404, real row untouched; delete under the correct pair → 204; a second
  delete → 404.
- Empty input, 501+ values, and an oversized (121-char) label all → 422, never a crash.

## Result

No exploitable issue or new sensitive boundary was found. The endpoints reuse the already-audited GRIM/DEBIT
pattern's exact shape; the only genuinely new consideration was presentation-honesty (no pill/verdict for an
unvalidated heuristic), addressed at the design level and confirmed by live Playwright verification.

**Security Audit: PASS**

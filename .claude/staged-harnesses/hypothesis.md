# Staged harness: Hypothesis property-based tests

**Checks:** property-based (generative) tests on the codebase's gnarliest *pure* functions — ones with real
edge-case surface that example-based unit tests tend to under-sample: `paper_edits` merge logic, the dedup
union-find, citation export formatting, and PDF quote-matching (`locate_quote`).

**Why deferred:** this isn't an all-or-nothing harness like ruff/pytest — it's per-target, added exactly when
one of those functions is being touched anyway, so the generative tests are written with fresh context on the
function's actual invariants rather than retrofitted in bulk from the outside.

**Activation trigger:** the next time any of these is touched:
- `app/backend/metadata/paper_edits.py` (merge logic)
- the dedup union-find (`app/backend/persistence/` — wherever `dismissed_duplicate_pairs`/merge candidates are
  scored and grouped)
- citation export formatting (`app/backend/citations/`)
- quote-matching / coordinate anchoring (`locate_quote`, `app/backend/pdf_processing/` or
  `app/backend/summarization/verification.py`) — this one matters most: it backs the coordinate-honesty
  invariant (CLAUDE.md invariant #2), so a property test here ("for any quote substring the extractor emits,
  locating it in the source text never returns a bbox outside the page bounds") is high-value once written.

## Draft config

No repo-wide config needed — Hypothesis tests live alongside the target's existing test file
(`tests/test_<area>.py`) using `@given(...)` strategies, not a separate harness file. Add `hypothesis>=6` to
the `dev` dependency group when the first property test is written; nothing else to wire globally (Hypothesis
tests just run as part of the normal `pytest` invocation once written).

## Activation steps
1. `hypothesis` → the `dev` dependency-group in `pyproject.toml`.
2. Write the property test(s) for the specific function being touched, in its existing test file.
3. No CI/pre-commit wiring needed — they run automatically as part of the existing `pytest -n auto -q` gate.
4. Update this registry's status to note which targets have been covered (this can stay partially active —
   e.g. "active for quote-matching, still drafted for the rest").

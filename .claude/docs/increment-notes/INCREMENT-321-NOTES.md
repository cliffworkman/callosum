# Increment 321 — LibreOffice adapter rework: Phase 2 (transactional refresh)

## Context
Increment 320 shipped Phase 0 (an empirical spike) and Phase 1 (a versioned mark-payload schema) of the P0
rework of callosum's shipped LibreOffice citation adapter (backlog #33/#34). Phase 0's spike confirmed
`XUndoManager` groups and reverts a multi-step mutation correctly in this LibreOffice version — the one
prerequisite Phase 2 needed before it could be trusted. This increment wraps `refresh()`'s write-back loop in
that mechanism.

## Implemented
`adapters/libreoffice/callosum_cite.py`:
- **`refresh()`** now routes its write-back through a new `_transactional_apply(doc, plan, bib_entries)` instead
  of looping + calling `_write_bibliography` inline. The render HTTP call is unchanged (still happens before any
  mutation begins, so a network failure there was always a no-op) — this only adds a rollback for failures
  *during* the mutation itself.
- **`_transactional_apply`**: wraps the per-mark `_replace_mark_text` loop + `_write_bibliography` in
  `doc.getUndoManager().enterUndoContext("Callosum refresh")` / `leaveUndoContext()`. On success, the whole
  group commits as one entry on the document's own Undo stack (a user's Ctrl+Z after a refresh now reverts the
  *whole* refresh in one step, not citation-by-citation). On any exception: the context is closed, `undo()`
  reverts the group in one call, and the result is checked against a pre-mutation snapshot — the roadmap's own
  "verify expected marks still exist" step. If the rollback itself didn't fully restore the prior state, that's
  raised as its own distinct `RuntimeError` (chained to the original) rather than silently re-raising the
  original error, since it would mean the document is now in a state nobody expected; if the rollback did
  restore correctly, the original exception propagates unchanged.
- **`_snapshot_marks(doc, names)`**: each named mark's current anchor text, keyed by name. Explicitly *not* the
  rollback mechanism (that's the UndoManager) — it's the verification oracle used before and after `undo()`.

## Tests
- `tests/test_libreoffice_adapter.py`: `test_snapshot_marks_reads_current_anchor_text`, using small duck-typed
  fake objects (`_FakeDoc`/`_FakeMarks`/`_FakeMark`/`_FakeAnchor`) that mirror the exact two-method UNO surface
  `_snapshot_marks` touches — safe to fake since the function itself is trivial (no risk of the fake diverging
  from real UNO semantics). `_transactional_apply` itself is deliberately **not** faked — it drives
  `_replace_mark_text` and `_write_bibliography`, both much more complex real-UNO-mutating functions, and this
  codebase's established convention (confirmed during Phase 0's research) is that real-document mutation logic
  is only ever verified against real UNO, never mocked in pytest. 15/15 tests pass.
- `adapters/libreoffice/selftest_uno.py`: a new **fault-injection** spike,
  `spike_transactional_refresh_rollback` — inserts 3 citations, does one successful IEEE-styled refresh (the
  known-good baseline), then monkeypatches the module-level `cc._replace_mark_text` to raise on its 2nd call and
  triggers a restyle to APA (a real, different render). Confirms the injected failure propagates out of
  `set_style`/`refresh`, and — critically — that **all 3 marks' text is back to the exact pre-refresh IEEE
  state** afterward, including the one mark that *had* already been rewritten to APA text before the injected
  failure hit. Run against real headless LibreOffice via `.local/lo_roundtrip/run_roundtrip.py`: **PASS.**

## Key technical detail
The three earlier design questions this needed answered were all resolved empirically in Phase 0, not assumed:
`enterUndoContext`/`leaveUndoContext`/`undo()` genuinely groups and reverts a multi-step mutation as one unit in
this LibreOffice version. This increment is the first real exercise of that mechanism under an actual partial
failure (not just the simple enter/mutate/leave/undo happy path Phase 0 tested) — the fault-injection spike
proves a mark that *had already been rewritten* before the failure still rolls back correctly, which is the
scenario that actually matters (a failure on mark 2 of 3 must not leave mark 1's already-applied change stranded).

## Manual verification
1. `pytest tests/test_libreoffice_adapter.py -q` — 15 passed.
2. `python .local/lo_roundtrip/run_roundtrip.py` — full real-LibreOffice round trip: `SELFTEST OK`, all four
   Phase-0 spikes still pass unchanged, plus the new Phase-2 rollback spike (before/after mark-text snapshots
   logged and confirmed identical).
3. `ruff format` / `ruff check .` — clean. `python tools/check_line_budget.py` — clean (348 files).
4. Full suite (`pytest -n auto -q`) — see this session's closing run for the final count.

## Gates
- **Security audit:** not triggered — no new endpoint, no request-schema change, no new file-write path; this is
  an internal mutation-safety mechanism using an existing UNO API, applied to an already-audited write path.
- **Principles/A-A (rule #9):** unchanged — this is a reliability/safety mechanism (never leave the document in
  a mixed state after a failure), not a claim/signal/judgment feature.

## Next
Phase 3 (backend locator/prefix/suffix/suppress-author/author-only passthrough through `citeproc_runner.js` +
a typed `CitationItem` Pydantic model) is the next natural slice — small, backend-only, and the mark payload
already carries these fields as of Phase 1 (currently always `None`/`False` since no UI sets them yet).

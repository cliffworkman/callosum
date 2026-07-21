# Increment 323 — LibreOffice adapter rework: Phase 4 (find the mark at the cursor)

## Context
Phases 0-3 (incs 320-322) established the versioned schema, transactional refresh, and backend passthrough for
per-occurrence cite properties. Every action built so far either inserts a brand-new citation mark
(`insert_citation`) or operates over *all* marks (`refresh`, `flatten`, `scan_citations_in_order`) — nothing
resolves "which ONE existing citation is the user pointing at right now." Edit Citation, Delete Citation, and
merge/split (Phases 5-6) all need exactly that lookup; this phase builds it once as a shared primitive.

## Implemented
`adapters/libreoffice/callosum_cite.py`:
- **`mark_at_cursor(doc)`**: reads the current view cursor's start position, then walks
  `scan_citations_in_order(doc)`'s already-decoded, already-filtered field list (reusing it rather than
  duplicating its decode/skip-unsupported logic) looking for the one whose `ReferenceMark` anchor contains that
  position — via `text.compareRegionStarts(anchor.getStart(), cursor) >= 0 and
  text.compareRegionStarts(cursor, anchor.getEnd()) >= 0`. Returns the same `{"citationID", "items", "_mark"}`
  shape a `scan_citations_in_order` field already has, so callers can treat "the mark at the cursor" and "a mark
  from the full scan" identically. Returns `None` if the cursor isn't inside any recognized citation mark
  (a foreign mark or one from an unsupported future schema version is excluded for free, since
  `scan_citations_in_order` already excludes both).

## Tests
Not pytest-testable in a meaningful way — `mark_at_cursor` touches `doc.getCurrentController().getViewCursor()`
and `text.compareRegionStarts`, both real-UNO-only operations with no faithful fake available (the same reasoning
that kept `_transactional_apply` out of pytest in Phase 2: faking this risks the fake diverging from real UNO
positional semantics, which is exactly the thing worth getting right). Verified instead by a new real-UNO spike,
`spike_mark_at_cursor` in `adapters/libreoffice/selftest_uno.py`: inserts 3 citations at fixed anchors, moves the
real view cursor into citation #2's own rendered range, and confirms `mark_at_cursor` resolves to citation #2's
`citationID` (not #1's or #3's) — then moves the cursor to plain body text and confirms it resolves to `None`.
Run against real headless LibreOffice via `.local/lo_roundtrip/run_roundtrip.py`: **PASS** on both cases.

## Manual verification
1. `pytest tests/test_libreoffice_adapter.py -q` — 15 passed (unaffected; no new pytest-testable surface here).
2. `python .local/lo_roundtrip/run_roundtrip.py` — full real-LibreOffice round trip: `SELFTEST OK`, all prior
   spikes (Phase 0's four, Phase 2's rollback) still pass unchanged, plus the new `mark_at_cursor` spike.
3. `ruff format` / `ruff check .` — clean. `python tools/check_line_budget.py` — clean.
4. Full suite (`pytest -n auto -q`) — see this session's closing run for the final count (unchanged from
   Increment 322's count — no new pytest cases this phase).

## Gates
- **Security audit:** not triggered — no new endpoint, no request-schema change, no new file-write path; a
  read-only lookup over the already-audited citation-mark scan.
- **Principles/A-A (rule #9):** unchanged — a positional lookup, not a claim/signal/judgment.

## Next
Phase 5 (the composer UI) is the natural next step and the biggest single chunk of the remaining P0 batch — a
unified live-search citation composer serving both Insert and Edit, built directly against the now-complete v2
schema + backend passthrough, with `mark_at_cursor` (this phase) resolving what Edit Citation should populate.
Alternatively, Phase 6 (Delete + merge/split, which also rides `mark_at_cursor`) could land first as a smaller
slice before tackling the composer.

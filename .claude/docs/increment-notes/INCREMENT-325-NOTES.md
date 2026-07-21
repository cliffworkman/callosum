# Increment 325 — LibreOffice adapter rework: Phase 7 (bounded bibliography)

## Context
This is the phase that closes the ORIGINAL verified finding that started this whole rework (backlog #33/#34):
`_write_bibliography` deleted from a single start-only bookmark to the document's literal end on every refresh,
silently destroying any user text placed after the bibliography. Phase 0's spike prototyped `TextSection` as the
bounding mechanism first and found it did **not** actually bound a rebuild safely (its own rebuild destroyed
text outside the section) — this phase ships the fallback that spike identified: a **bookmark pair**.

## Implemented
`adapters/libreoffice/callosum_cite.py`:
- **`BIB_BOOKMARK_END`**: a second bookmark marking the end of the managed range, alongside the existing
  `BIB_BOOKMARK` (start).
- **`_write_bibliography`** rewritten: when both bookmarks exist, the rebuild selects and clears **exactly**
  `[start, end]` — never `text.getEnd()`. Both fresh bookmarks are placed only *after* the new content is
  written (never both at the same collapsed position up front), sidestepping any "which side does a zero-width
  bookmark stick to" ambiguity entirely, since there's nothing to stick to yet when each is placed. A
  start-without-end (damaged/legacy) state is handled by rebuilding fresh at the start bookmark's position
  rather than guessing where "the end" might have been — a full user-facing repair/diagnostics command is
  Phase 9; this is just the safe fallback so a damaged document never crashes or corrupts.
- **`flatten()`** now removes both bookmarks (previously only the single start one).
- **`PREF_BIB_AUTO`** + **`bib_auto_enabled`/`set_bib_auto`**: a document preference (mirroring the existing
  style/locale preference pattern) that pauses the bibliography rebuild specifically — citations still update
  on every refresh; the bibliography block stays frozen until re-enabled. `_transactional_apply` checks this
  before calling `_write_bibliography`.
- **`refresh()`/`_transactional_apply`** gained an optional `bib_cursor` parameter: when given, the bibliography
  moves (or is created) at that position instead of its current location — used by the new "Insert bibliography
  here" action. An explicit `bib_cursor` always writes even while `bib_auto_enabled` is off — pausing the
  passive every-refresh rebuild shouldn't silently swallow a deliberate "put it here" request.
- New `_ACTIONS` entries (`insertBibliographyHere`, `toggleBibAuto`) + macro wrappers + `Addons.xcu` menu nodes.

**Deliberately out of scope for this pass** (a real scoping decision, not an oversight): a custom/suppressed
bibliography heading, and the full user-facing "detect and repair a missing/damaged bibliography" diagnostic
command — both noted in the roadmap's item 6 but not essential to the safety fix this phase exists to ship.
The repair command is Phase 9's job.

## Tests
Real-UNO spikes in `selftest_uno.py` (this is real UNO mutation logic, not meaningfully fakeable):
- **`spike_bounded_bibliography_preserves_trailing_text`** — reproduces the ORIGINAL failure sequence (cite,
  refresh creates a bibliography, type new text after it, refresh again) and confirms the trailing text now
  survives. This is the direct proof the verified bug is fixed.
- **`spike_insert_bibliography_here`** — moves the bibliography to a new cursor position; confirms it now
  precedes the surrounding text at the new location and nothing else was destroyed.
- **`spike_toggle_bib_auto`** — confirms the bibliography heading count stays at 1 while auto-rebuild is off
  even as a second citation is inserted (citations still update — `scan_citations_in_order` returns 2 marks —
  proving `refresh()` itself keeps running; only the bibliography write is skipped), then confirms re-enabling
  + a refresh brings the bibliography back.

All three passed; one harness-only fix was needed along the way: `toggle_bib_auto_interactive` always shows a
confirmation message box (unlike most interactive actions, which only message-box on a failure/edge case) —
calling it directly from the test (bypassing the real `.oxt` dispatcher, which sets `cc._DISPATCH_CTX` before
invoking an action) raised `NameError: XSCRIPTCONTEXT`. Fixed by having the spike set `cc._DISPATCH_CTX = ctx`
itself, exactly matching what `callosum_addon.py`'s real dispatcher does.

## Manual verification
1. `pytest tests/test_libreoffice_adapter.py -q` — 15 passed (unaffected; no new pytest-testable pure logic
   this phase — the bookmark-pair mechanics are real-UNO-only).
2. `python .local/lo_roundtrip/run_roundtrip.py` — full real-LibreOffice round trip: `SELFTEST OK`, all prior
   spikes (Phases 0/2/4/6) still pass, plus all three new Phase-7 spikes. (Two attempts hit a transient
   soffice-startup timeout unrelated to any code change — "nothing listening on UNO port 2003" — the third
   attempt started cleanly; noted here as an environment-flakiness observation, not a design issue.)
3. `ruff format` / `ruff check .` — clean. `python tools/check_line_budget.py` — clean.
4. Full suite (`pytest -n auto -q`) — see this session's closing run for the final count (unchanged from
   Increment 324's — no new pytest cases this phase).

## Gates
- **Security audit:** not triggered — no new endpoint, no request-schema change, no new file-write path; a
  document-internal mutation-safety fix over the already-audited bibliography write path.
- **Principles/A-A (rule #9):** unchanged — a data-safety fix + a user-controlled pause toggle, no new claim/
  signal/judgment.
- **README:** `adapters/libreoffice/README.md`'s "Use" section gained steps 12-13; the bibliography paragraph
  rewritten to describe the bounded-range guarantee instead of the old "keep your citations above it" caution.

## Next
Phase 8 (safe flatten — "Prepare submission copy") and Phase 9 (diagnostics/repair) remain before Phase 5 (the
composer, the largest remaining piece).

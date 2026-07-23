# Increment 360 — LibreOffice refresh progress and cancellation

## Context

P1 roadmap item #13's remaining performance controls were progress/cancellation and incremental rendering.
Writer refreshes already rendered before mutation and committed all writes in one verified UndoManager group, so
progress and cancellation could extend that transaction without weakening its all-or-nothing guarantee.

LibreOffice's published `XStatusIndicator` reports progress but has no cancellation callback. The Toolkit can
temporarily receive key events and yield to the main event loop, so large refreshes use Writer's native status
bar plus a scoped Escape-key listener. Small documents keep the prior silent fast path.

## Implemented

- Refreshes with at least 20 work units (roughly ten citations for a full citation+bibliography update) create a
  native Writer status indicator. Targeted refreshes count the full document render as work, so a large
  manuscript still reports progress even when only one citation will be written.
- Status text covers citation-data preparation, document-wide formatting, live-document validation, each
  targeted citation write, and bibliography write.
- A temporary `XKeyHandler` consumes **Esc** while progress is active. Each progress update yields to Writer,
  then raises `RefreshCancelled` if cancellation arrived.
- Cancellation before mutation is a no-op. Cancellation after one or more writes enters the existing
  `_transactional_apply` exception path: Writer closes and undoes the complete refresh group, then verifies every
  targeted mark has its original text.
- Component and macro dispatchers treat `RefreshCancelled` as an intentional stop rather than an error dialog.
- Yielding to Writer creates a concurrency boundary. The ordered mark name, citation id, and visible anchor text
  that produced the render request are therefore compared with the live document after rendering. Any mismatch
  rejects the stale response before write-back and asks the user to refresh again.
- Progress UI is best-effort. If a frame/status/toolkit service is unavailable, refresh behavior and rollback
  remain unchanged.
- Extension version bumped 0.9.0 → 0.10.0.

## Verification

- Targeted adapter/OXT/install suite: **86 passed**.
- `python adapters/libreoffice/run_roundtrip.py`: **SELFTEST OK** with the installed OXT and real Writer.
  The new 12-citation fixture proves the native status indicator and Escape listener resolve, injects
  cancellation after three citation writes and observes an exact full rollback, retains both pending flags, and
  proves a concurrent Writer citation edit causes stale-response rejection instead of overwrite.
- The same run completed every pre-existing LibreOffice spike.
- Full project suite: `1471 passed, 1 skipped in 680.47s (0:11:20)`.

## Gates

- **Principles / governance:** non-triggering. This controls deterministic formatting of the user's document and
  creates no literature claim, signal, ranking, recommendation, or worker assessment.
- **Security:** `2026-07-23_libreoffice-refresh-cancellation.md` is **PASS**.
- **QA:** no web API or frontend surface changed. Pure tests cover progress lifecycle/value bounds/cancellation,
  the no-UNO small-document path, and render-input signatures; real UNO proves native services and rollback.

## Manual verification debt

Cliff should install 0.10.0, refresh a large Writer document, confirm status text appears in the native status
bar, and press **Esc** during citation write-back. Formatting should return exactly to its prior state and any
pre-existing pending-refresh bar should remain. Prior menu/panel appearance click-through debt remains open.

## Next

Incremental rendering is the sole remaining #13 item. It must preserve document-wide citeproc correctness:
numeric renumbering, author-date disambiguation, and bibliography membership mean "incremental" cannot simply
send a cropped citation sequence. The next slice should cache/compare render results and write only fields whose
rendered output actually changed, while still rendering the full ordered document.

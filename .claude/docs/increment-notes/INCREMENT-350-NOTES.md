# Increment 350 — LibreOffice visible dirty-state indicator (P1 item #13)

## Context

Increment 349 added manual citation refresh mode, but a paused edit could leave old visible citation text without
a persistent on-screen cue. The roadmap names a visible dirty-state indicator separately. LibreOffice's
`XInfobarProvider` gives the document controller a native, persistent warning surface with extension action
buttons, avoiding a custom toolbar protocol or an in-document marker that might print.

## Implemented

- Added separate `CallosumCiteDirty` and `CallosumBibDirty` document properties. Defaults are clean; the flags
  persist with the document and distinguish exactly which surface needs work.
- Known Callosum mutations now maintain the flags:
  - paused automatic citation or bibliography updates mark only the skipped surface;
  - both paused mark both without making a render request;
  - successful full or partial refresh clears only the surfaces it actually wrote;
  - a render failure after a structured citation mutation conservatively marks both surfaces;
  - bibliography include/exclude changes mark bibliography pending if their immediate rebuild fails.
- A non-dismissible Writer **Callosum refresh pending** warning Infobar names citation formatting, bibliography,
  or both. Its fixed **Refresh pending** action reads the flags and updates exactly those surfaces, bypassing the
  automatic-mode settings without changing them.
- The Infobar is removed as soon as all known pending work is resolved. `dispatch()` restores it from persisted
  flags on the next Callosum action after a saved dirty document is reopened.
- Existing document diagnostics now reports pending citation/bibliography refresh state.
- Extension version bumped 0.5.0 → 0.6.0 and the `.oxt` rebuilt.
- Root/adapter README, served help, backlog, and project state updated.

## Scope boundary

This indicator covers states produced or observed by Callosum. Writer-only operations, such as moving a citation
with native cut/paste, are not automatically observed; users should still run a full refresh after those edits.
The persisted Infobar returns on the next Callosum action after reopen, not immediately at document-open. Both
extensions require a document-event listener and remain explicit #13 follow-ons. Selected/current-section
refresh, progress/cancellation, and incremental rendering also remain open.

## Verification

- `uv run pytest tests/test_libreoffice_adapter.py tests/test_libreoffice_oxt.py -q` — **67 passed**.
- `python adapters/libreoffice/run_roundtrip.py` — real headless LibreOffice + real seeded callosum server printed
  **`SELFTEST OK`**. The extended manual-mode spike proved citation-only and both-surface flags persist, the
  Infobar appears and disappears with state, fully automatic work stays clean, and **Refresh pending** resolves
  both surfaces while both automatic preferences remain disabled.
- `uv run pytest -n 4 -q` — **1433 passed, 1 skipped** in 573.41s.
- `uv run ruff check .` / `uv run ruff format --check .` — clean (**478 files**).
- `python tools/check_line_budget.py` — clean (**351 application-source files** within cap).
- `python tools/qa/build_surface_map.py check` — **260/260 API surfaces covered**; 21 unchanged frontend checklist
  entries, no new app browser surface.

## Gates

- **Principles / A-A:** non-triggering. This is deterministic document-formatting state and does not produce a
  claim, signal, ranking, or judgment about the literature.
- **Security:** triggered by the multi-file feature. Audit `2026-07-23_libreoffice-dirty-indicator.md` is
  **PASS**: two fixed scalar properties, fixed local action URL, no new host/endpoint/file path/dependency/secret.
- **QA:** the computed app API/frontend surface is unchanged. Unit tests cover all flag combinations and the
  fixed Infobar action; the required real-UNO harness proves the Writer controller behavior.
- **Experience pass (deadline writer revising a large manuscript, code/help-grounded because delegation was not
  available):** the warning is at the top of the document, names what is stale, cannot be dismissed while still
  stale, and carries the recovery action directly. The writer no longer has to remember which automatic mode was
  paused. The two event-listener limitations above were filed rather than hidden.

## Manual verification debt

Cliff should install 0.6.0 and visually confirm the Infobar copy, warning treatment, and **Refresh pending**
button in headed Writer. Headless UNO proves the real controller state and action behavior, but not the rendered
appearance. Earlier citations-panel and menu-command click-through debt remains.

## Next

Selected-citation refresh is the smallest remaining bounded #13 control. Current-section refresh needs a robust
definition of Writer section boundaries; document-event listening is a separate lifecycle slice.

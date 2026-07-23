# Increment 344 — LibreOffice adapter: "Citations in this document" panel (P1 item #12)

## Context
Cliff hand-verified the composer (Phases 5a/5b/5c) live in Writer — "a great start!" — closing the standing
manual-verification debt flagged across incs 329–332. While looking for what to build next, discovered
`INCREMENT-BACKLOG.md`'s #33/#34 entry was stale: it described the P0 correctness/safety batch (bounded
bibliography range, safe flatten, transactional refresh, the composer) as still "active now," when reading the
actual code confirmed all four were shipped and explicitly closed at inc 328. Corrected that entry, then asked
Cliff what to build next; he picked P1 item #12 from the word-processor roadmap: a panel listing every cited
work with occurrence count, missing/orphaned status, retraction status, and click-to-navigate.

## Implemented
- **`list_document_citations(doc, base)`** (`callosum_cite.py`, next to `diagnose_document`, its closest
  sibling): a read-only rollup of every unique cited work, in first-occurrence document order, reusing
  `scan_citations_in_order()`. For each: a rendered `csl_record_row` summary, occurrence count, orphaned flag
  (paper no longer in the library), retraction status (one call per unique paper to the existing, already-
  audited `GET /papers/{id}/retraction` — no new endpoint), and the first mark's anchor for navigation. Also
  adds `_paper_id_from_item`, centralizing the `"callosum-{id}"`-stripping idiom that was previously
  copy-pasted 3× — used here as its 4th call site, the other 3 left untouched (not a drive-by refactor).
- **New file `adapters/libreoffice/citations_panel.py`** (mirrors the `composer.py` split): one modal dialog,
  `run_citations_panel(entries)` — a live-filterable list (exact reuse of composer.py's `XTextListener`
  live-search pattern) plus a "Go to" button. Deliberately **modal, not a true persistent/live-refreshing
  panel** — every dialog in this codebase is modal, and building a non-modal always-open window would need
  new, unproven UNO lifecycle plumbing (an `XModifyListener`, something holding a reference so it isn't
  garbage-collected, since the `.oxt` dispatcher is a stateless per-click invocation). Ships the value (list,
  count, orphaned/retracted flags, filter, navigate) without that risk; the always-open version is a named,
  deliberately deferred later phase, not a silent scope cut.
- **Wire-up**: `_ACTIONS["citationsPanel"]`, `CallosumCitationsPanel` macro entry point, a new `Addons.xcu`
  menu item ("Citations in this document…", `m10`), `citations_panel.py` added to
  `tools/build_libreoffice_oxt.py`'s `ENTRIES` (verified: rebuilt the `.oxt` and confirmed the file is actually
  bundled, not repeating this session's earlier "No module named 'composer'" packaging miss). Extension version
  bumped 0.1.1 → 0.2.0 (a new feature). README documents the new menu action.

## Key technical detail
Caught one real bug before it shipped: the count label's live-updating text was initially set via
`count_lbl_ctrl.Label = ...` (direct control attribute) rather than `count_lbl_ctrl.getModel().Label = ...` —
the actual working pattern every other dynamic label in this codebase uses (`composer.py`'s
`assembly_lbl_ctrl.getModel().Label`). Caught by re-reading the established pattern before shipping, not by a
test — pytest can't exercise this UI code at all (it's UNO-only), which is exactly why the plan flagged manual
verification as required, not optional.

## Principles/A-A gate (rule #9)
Read-only document inspection (list/count/status/navigate) — no claim/signal/judgment about the literature
itself; the retraction flag relays an existing, already-verified FACT (the same `open_science_signals` row the
Review pane already surfaces), not a new judgment. No gate trigger.

## Tests
- `tests/test_libreoffice_adapter.py` (+4): grouping/counting/document-ordering, orphaned + retraction
  detection, non-fatal retraction-lookup failure, empty-document case — via a duck-typed fake doc
  (`_PanelDoc`/`_PanelMark`/`_PanelText`) faithful to `scan_citations_in_order`'s actual UNO surface
  (`getReferenceMarks().getByName()`, `getText().compareRegionStarts`), not just `diagnose_document`'s
  simpler `getElementNames()`-only fake.
- `tests/test_libreoffice_oxt.py`: `EXPECTED_ENTRIES` updated (a hand-maintained set — the newer
  auto-detecting regression test, `test_every_local_sibling_import_is_packaged`, already passed unprompted
  since `citations_panel.py` was correctly added to `ENTRIES` from the start).
- `adapters/libreoffice/selftest_uno.py` (+1 spike, `spike_list_document_citations`): real headless UNO —
  seeds a document with 3 citations across 2 papers (one cited twice), confirms document order, count,
  non-orphaned, non-retracted, and a real `ReferenceMark` handle in the result. Run via
  `python adapters/libreoffice/run_roundtrip.py` — `SELFTEST OK`.
- Full suite: `pytest -n auto -q` — clean (see the actual run for the count; no source outside
  `adapters/libreoffice/` + its tests touched).
- `python tools/check_line_budget.py`: unaffected (adapters/ is exempt from the cap; all files still small).

## Manual verification (flagged, not optional)
Per the plan and this project's own lesson from the composer (months of drift before Cliff's first click-
through): **Cliff should open the panel in real Writer against a real multi-citation document soon**, not let
it join the same backlog. The dialog's actual on-screen behavior (layout, the live filter, Go-to navigation)
has never been exercised outside the pure-logic tests + the read-only real-UNO spike above — composer.py's own
docstring already documents why this class of UI can't be spike-tested through `.execute()`'s blocking modal.

## Next
Deferred, named explicitly (not dropped): the true always-open/live-refreshing panel; metadata-conflict
detection (embedded mark CSL vs. current library record drift — no existing comparison logic anywhere in this
codebase); "citation groups containing the work" cross-reference detail. The rest of P1 (style manager, note
styles, bibliography editing controls, refresh/performance controls, portability, journal abbreviations,
accessibility) remains open per the roadmap doc.

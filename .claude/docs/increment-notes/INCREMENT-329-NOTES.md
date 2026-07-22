# Increment 329 — LibreOffice adapter rework: Phase 5a (the composer — live search + multi-item insert)

## Context
Phase 5 (the composer) is the last major piece of the P0 rework, previously deferred pending a context
compaction. Picked back up this session and scoped into sub-phases the same way the rest of the rework was:
**5a** (this increment) ships live-search + multi-item assembly + a real rendered preview, replacing the
original one-shot search+single-select "Add citation…" flow. **Not yet done**: per-item locator/prefix/suffix/
suppress-author/date fields (5b — the backend/schema already support these, from Phases 1/3; only the UI
doesn't yet), and Edit Citation / revert-manual-overrides (5c — reopening the composer on an existing citation).

Given live-search-as-you-type had zero precedent in this codebase (only one prior UNO listener implementation
exists at all — the `.oxt` dispatcher's `XJobExecutor` in `callosum_addon.py`), a real-UNO spike ran first
(matching Phase 0's own precedent for de-risking before designing) rather than guessing at UNO AWT behavior.

## Implemented
- **`adapters/libreoffice/composer.py`** (new file — kept separate from `callosum_cite.py`, already 1300+
  lines, since dialog construction is a distinct concern): `run_composer_dialog(doc, base) -> list | None`. A
  UNO dialog with a query edit box wired to a live `XTextListener` (search-as-you-type, no debounce timer
  needed — see the spike finding below), a results listbox, Add/Remove buttons (`XActionListener`) moving items
  into a persistent assembly listbox, a real rendered preview (a genuine round-trip through
  `POST /citations/render-document` on every Add/Remove — never simulated, per the Phase-3 constraint that some
  CSL styles silently reorder items), and Insert/Cancel. Returns the assembled paper ids in add-order, or `None`.
- **`callosum_cite.py`**: new **`insert_citation_items(doc, paper_ids: list, base, cursor=None) -> str`**
  generalizes the original single-item `insert_citation` (now a thin wrapper over this — every existing caller
  unaffected). Wraps ALL given papers' CSL records into ONE mark's `items` list. **`add_citation_by_search`**
  rewritten to open the composer and, if the user assembled + inserted, call `insert_citation_items`.

## The live-search spike (`selftest_uno.py::spike_live_search_listener`)
Empirically confirmed, against real UNO: a programmatic `edit_control.setText(...)` **does** fire
`XTextListener.textChanged` (UNO's own docs don't say either way for this control), and a synchronous local
search-and-listbox-refresh from inside that callback works with **no observed reentrancy problem** — the whole
round-trip took ~26-37ms across runs, fast enough that **no async debounce timer is needed at all** for a live
feel, since everything is localhost. This meaningfully simplified the design versus the original plan (which
assumed a timer-based debounce might be required). **What this spike does NOT prove** (and can't, headlessly):
whether a REAL human keystroke fires the same event the same way, and the actual felt responsiveness — that's
a manual check in real Writer, flagged explicitly rather than assumed.

## Tests
- **`selftest_uno.py::spike_insert_citation_items`**: bypasses the composer dialog entirely (which blocks on
  `dialog.execute()` — not spikeable headless, same limitation `_input_box`/`_suggest_listbox` have always had)
  and calls the new backend function directly, matching how every other action spike in this file works.
  Confirms exactly one mark for a 2-paper grouped insert (not two), the item order matches the call order, and
  the render reflects both sources — plus a regression check that the single-item `insert_citation` wrapper
  still behaves identically. Real, useful confirmation surfaced in passing: APA rendered the pair as `(Devlin &
  Chang, 2019; Vaswani & Shazeer, 2017)` — reversed from insertion order, exactly the already-known Phase-3
  finding that some CSL styles' own `<citation><sort>` overrides manual order, not a bug.
- No new pytest cases — `composer.py` has zero pure/decidable logic (everything needs a real UNO dialog); this
  matches `_input_box`/`_suggest_listbox`'s own established precedent of pytest-free, spike-plus-manual-only
  coverage. `tests/test_libreoffice_adapter.py` (25) + install/oxt (10) re-run clean — the `insert_citation`
  refactor is a non-regression.

## Manual verification
1. `pytest tests/test_libreoffice_adapter.py tests/test_libreoffice_install.py tests/test_libreoffice_oxt.py -q`
   — 35 passed (unchanged count; a refactor + a new module with no pytest-testable surface).
2. `python adapters/libreoffice/run_roundtrip.py` — `SELFTEST OK`, all prior spikes plus both new Phase-5a spikes.
3. `ruff format` / `ruff check .` — clean (one real catch: an unused `assembly_lbl` local, fixed).
   `python tools/check_line_budget.py` — clean (`adapters/` exempt regardless).
4. **NOT verified — flagged, not assumed**: the composer has never been driven by a real human in real Writer.
   Real keyboard-typing responsiveness, tab order, and the Add/Remove/Insert button flow all need a manual
   check before this is called done from an end-user's perspective. This is the same category of gap every
   dialog in this adapter has always had (no browser-automation-equivalent exists for LibreOffice dialogs).

## Gates
- **Security audit:** not triggered — no new endpoint, no new egress target (reuses `/papers`,
  `/papers/export`, `/citations/render-document` exactly as before), no file-write path, no auth change.
- **Principles/A-A (rule #9):** unchanged — the preview is a real, unaltered round-trip through the same
  rendering engine the final insert uses (never a client-side simulation), consistent with signal-not-verdict/
  inspectability-over-authority; no new claim/judgment surface.
- **README:** `adapters/libreoffice/README.md`'s item 1 rewritten to describe the composer; "Limitations"
  updated to name what's still missing (locator/prefix/suffix/suppress fields = 5b; Edit Citation = 5c).

## Next
**Phase 5b** (locator/label/prefix/suffix/suppress-author/author-only fields per assembled item in the
composer — the backend already accepts all of this via `CitationItem`, Phase 3) and **Phase 5c** (Edit Citation:
reopen the composer pre-populated from `mark_at_cursor`, plus "revert manual overrides" and "restore
style-defined sort") are what's left of the original Phase 5 scope. A manual, real-Writer verification pass on
5a is also still owed before it's fully "done" from an end-user standpoint.

# Increment 330 — LibreOffice adapter rework: Phase 5b (per-item locator/prefix/suffix/suppress-author)

## Context
Phase 5a (inc 329) shipped the live-search composer for multi-item insert but had no way to set any
per-occurrence field. The backend/schema have supported these since Phases 1 (mark-payload schema) and 3
(citeproc passthrough) — this phase is purely wiring the composer UI to what already exists server-side.

## Implemented
- **`callosum_cite.py`**: new **`CSL_LOCATOR_LABELS`** constant — the exact 19-value CSL locator-label
  vocabulary, duplicated (not imported) from `CSL_LOCATOR_LABELS` in `app/backend/api/routers/citations.py`,
  since the adapter runs under LibreOffice's own bundled Python with no access to the backend package; a
  comment flags the two must stay in sync (a fixed CSL-spec vocabulary, not something that drifts independently).
  **`insert_citation_items`**'s signature changed from `paper_ids: list` to `items: list[dict]` — each entry is
  `{"paper_id": ..., **optional per-occurrence overrides}`; omitted keys default via the existing
  `_normalize_item`. `insert_citation` (single-item) and `add_citation_by_search` updated to match — this is an
  in-session signature revision (Phase 5a shipped only last increment, not yet independently used), not
  backwards-compatibility debt.
- **`composer.py`**: assembly items are now dicts (`{"paper_id", "row", "record", **_ITEM_DEFAULTS}`, minus the
  adapter-internal `custom_override`) instead of 3-tuples. A new **"Options…"** button opens
  `_edit_item_options` — a small modal (locator-label dropdown using the exact `CSL_LOCATOR_LABELS`, a locator
  value field, prefix/suffix fields, and suppress-author/author-only checkboxes) for the currently-selected
  assembly item. **Suppress-author and author-only are mutually exclusive in the UI** (checking one unchecks
  the other via an `XItemListener` — they're contradictory CSL concepts, omit-vs-show-only-the-author, and
  citeproc's behavior with both set at once was never going to be tested/relied on). The assembly listbox now
  shows a compact `[...]` summary of any active override next to each item's row so the user can see at a
  glance what's set without reopening Options. The rendered **preview merges each item's current overrides
  into its cached CSL record** on every refresh — matching exactly what `insert_citation_items` does at actual
  insert time, so the preview is never stale relative to what gets inserted.

## Tests
- **`selftest_uno.py::spike_per_item_citation_overrides`** (new): confirms each override reaches the REAL
  citeproc-js render through `insert_citation_items` (not assumed from the backend's own test suite):
  - locator `{"label": "page", "locator": "12"}` → `'(Vaswani & Shazeer, 2017, p. 12)'`
  - prefix `{"prefix": "see "}` → `'(see Vaswani & Shazeer, 2017)'`
  - suffix `{"suffix": " (emphasis added)"}` → `'(Vaswani & Shazeer, 2017 (emphasis added))'`
  - suppress-author → `'(2017)'`
  - author-only → `'Vaswani & Shazeer'` (bare name, no year/parens)

  All five match the Phase-3 findings already recorded (prefix/suffix wrap INSIDE the parenthetical;
  author-only is bare, no year) — now proven through this adapter's own insert path, not just the backend.
- **`selftest_uno.py::spike_insert_citation_items`** updated for the new dict-based signature (regression-clean).
- No new pytest cases — same reasoning as Phase 5a: dialog construction has no pure/decidable logic.
  `tests/test_libreoffice_adapter.py` (25) + install/oxt (10) re-run clean.

## Manual verification
1. `pytest tests/test_libreoffice_adapter.py tests/test_libreoffice_install.py tests/test_libreoffice_oxt.py -q`
   — 35 passed (unchanged; a signature revision + composer UI additions, no new pytest surface).
2. `python adapters/libreoffice/run_roundtrip.py` — `SELFTEST OK`, all prior spikes plus the new Phase-5b spike,
   with the exact real-citeproc renders quoted above.
3. `ruff format` / `ruff check .` — clean. `python tools/check_line_budget.py` — clean.
4. **NOT verified — flagged, not assumed** (same open item as Phase 5a): no real human has driven the composer
   or the Options sub-dialog in real Writer yet. The mutex checkbox behavior, the label dropdown's default
   selection, and general layout/usability all need a manual pass.

## Gates
- **Security audit:** not triggered — no new endpoint/egress/file-write/auth surface; reuses the already-audited
  render/export endpoints exactly as Phase 5a did.
- **Principles/A-A (rule #9):** unchanged — the preview stays a real, unaltered round-trip; no new claim/
  judgment surface. The mutex UI behavior (suppress-author vs. author-only) is a usability guardrail, not a
  content decision made on the user's behalf.
- **README:** `adapters/libreoffice/README.md`'s item 1 + "Limitations" updated — locator/prefix/suffix/
  suppress-author are now described as shipped; "no suppress-date" and "no Edit Citation yet" spelled out
  explicitly rather than left implicit.

## Next
**Phase 5c** (Edit Citation — reopen the composer pre-populated from an existing citation via `mark_at_cursor`,
plus "revert manual overrides" and "restore style-defined sort") is the last piece of the original Phase 5
scope. A real-human manual verification pass on the whole composer (5a+5b) in actual Writer is still owed.

# Increment 331 — LibreOffice adapter rework: Phase 5c (Edit Citation) — closes the composer, closes Phase 5

## Context
The last piece of the original Phase 5 scope: reopening the composer on an EXISTING citation (add/remove/
reorder sources, edit per-item options), rather than only building brand-new ones. This closes out Phase 5
(the composer) in full, and with it the entire original P0 roadmap (backlog #33/#34) — every phase 0-10 plus
5a/5b/5c is now shipped; only a real-human manual verification pass on the composer remains open (flagged, not
assumed, in every one of the last three increments).

Along the way, resolved a design question left open by the roadmap: it lists "reorder items manually" and
"restore style-defined sorting" as paired required operations. Investigation found `decode_mark_name` already
returns a scaffolded-but-dormant `"sort"` field (from Phase 1, defaulting to `"auto"`) that nothing reads or
writes — and, more fundamentally, that CSL/citeproc-js has no per-request mechanism to override a style's own
`<citation><sort>` at all (it's baked into the style itself, not a runtime toggle). Building a "restore style
sort" action would therefore either be a no-op for the 4 styles that define one, or purely cosmetic for the 3
that don't — not a real, honest feature. Resolution: build "reorder manually" (it has real effect for styles
without their own sort, and the composer's preview — always a genuine round-trip — honestly shows when a
style's own sort overrides it anyway); do NOT build a separate "restore sort" action, since there is nothing
for it to meaningfully restore that the existing behavior doesn't already do by default.

## Implemented
`adapters/libreoffice/callosum_cite.py`:
- **`csl_record_row(record) -> str`**: formats a full CSL-JSON record (``author: [{family, given}]``,
  ``issued: {"date-parts": [[year]]}``) into the same row shape `build_search_rows` produces from a `/papers?q=`
  search hit — needed because an existing citation's decoded items only have the CSL shape, not a search hit.
- **`_build_records(items, base)`**: the CSL-fetch-and-merge loop extracted out of `insert_citation_items` so
  `edit_citation_items` can share it without duplicating the per-item logic.
- **`edit_citation_items(doc, field, items, base)`**: replaces an EXISTING citation's items in place — reuses
  the existing `_rewrap_mark_payload` helper (Phase 6) with the citation's OWN `citationID`/rnd, never minting
  a new one, since editing must not change a citation's identity.
- **`edit_citation_interactive(doc, base)`**: `mark_at_cursor` → reopen the composer pre-populated
  (`existing_items=field["items"]`) → `edit_citation_items` if the user clicked Update, else no-op on Cancel.
- New `_ACTIONS` entry (`editCitation`) + `CallosumEditCitation` macro wrapper + a new `Addons.xcu` menu node
  (`m02f`, "Edit citation…", grouped with the other existing-citation actions).

`adapters/libreoffice/composer.py`:
- **`_assembly_item_from_decoded(record)`**: rebuilds a composer assembly item from an existing citation's
  already-decoded item — separates the per-occurrence keys back out from the bare CSL record, so edit-mode
  assembly items have the identical shape a fresh `do_add()` produces (both feed the same preview/insert code
  unchanged).
- **`run_composer_dialog`** gained `existing_items: list[dict] | None = None`. When given: the assembly starts
  pre-populated, the dialog opens as "Edit citation" (title + button label "Update" instead of "Insert"), and
  the preview renders immediately on open rather than only after the first Add.
- **Manual reordering**: new Move ↑ / Move ↓ buttons (available in both Insert and Edit mode — same mechanism,
  no reason to withhold it from a fresh multi-item insert) swap the selected assembly item with its neighbor,
  refresh the row list + preview, and keep the moved item selected.
- **`_edit_item_options`** unchanged in shape (Phase 5b); reused as-is for editing an existing citation's items.

## Tests
- **`tests/test_libreoffice_composer.py`** (new file, 4 tests): a genuinely useful realization this phase —
  `composer.py` does no UNO imports at module level (only lazily, inside its dialog-building functions), so it
  loads fine under plain pytest. Added real pytest coverage for the pure helpers Phase 5a/5b had (incorrectly)
  assumed were UNO-only: `_item_overrides`, `_format_assembly_row`, `_assembly_item_from_decoded`.
- **`tests/test_libreoffice_adapter.py`** (+3): `csl_record_row` — family-name + issued-year formatting,
  defensive on missing fields, title truncation.
- **`selftest_uno.py::spike_edit_citation`**: confirms, against real UNO, that editing a citation to ADD a
  second item + set a locator keeps the SAME `citationID`/rnd (`'c1'` throughout) and the locator reaches the
  render; and that editing DOWN to fewer items also preserves identity. Bypasses the composer dialog itself
  (blocks on real user interaction — the same limitation every dialog-driven action in this file has).
- Full re-run: `pytest tests/test_libreoffice_adapter.py tests/test_libreoffice_composer.py
  tests/test_libreoffice_install.py tests/test_libreoffice_oxt.py -q` — **42 passed** (35 prior + 3 csl_record_row
  + 4 composer). Real-UNO roundtrip: `SELFTEST OK`.

## Manual verification
1. `pytest` (the four files above) — 42 passed.
2. `python adapters/libreoffice/run_roundtrip.py` — `SELFTEST OK`, all prior spikes plus the new Phase-5c spike.
3. `ruff format` / `ruff check .` — clean. `python tools/check_line_budget.py` — clean.
4. **NOT verified — flagged, not assumed, for the third increment running**: no real human has driven the
   composer (Insert OR Edit mode) in real Writer. Move ↑/↓, the Options sub-dialog's Clear button, and the
   edit-mode pre-population all need a manual pass before this is genuinely "done."

## Gates
- **Security audit:** not triggered — no new endpoint/egress/file-write/auth surface; reuses the already-
  audited render/export endpoints and the existing `_rewrap_mark_payload` mutation path exactly as Phase 6 did.
- **Principles/A-A (rule #9):** unchanged — no new claim/judgment surface. The decision NOT to build a
  "restore style sort" action is itself a small alignment note: building a control that looks actionable but is
  actually a no-op for most bundled styles would be a transparency regression (a button implying capability the
  tool doesn't have) — declined on exactly that basis, not just cut for scope.
- **README:** `adapters/libreoffice/README.md`'s "Acting on an existing citation" section gained item 9 (Edit
  citation…), renumbering 10-16; the macro-names list gained `CallosumEditCitation`; "Limitations" rewritten to
  describe Edit Citation as shipped and to explain the style-sort behavior plainly instead of promising a
  "restore sort" feature that was deliberately not built.

## Next
This closes Phase 5 (the composer) and, with it, the entire original P0 roadmap (backlog #33/#34) — every
phase from 0 through 5c and 6 through 10 has shipped. What remains, in order of what was flagged along the way:
1. **A real-human manual verification pass** on the composer (Insert and Edit) in actual Writer — the
   recurring open item across Phases 5a/5b/5c.
2. Whatever comes next is genuinely open — the P0 batch that has driven the last dozen increments is complete.

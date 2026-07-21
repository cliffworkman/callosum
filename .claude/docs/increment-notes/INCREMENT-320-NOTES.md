# Increment 320 — LibreOffice adapter rework: Phase 0 (empirical spike) + Phase 1 (versioned mark-payload schema)

## Context
A ChatGPT-5.6 competitive review (Zotero/Mendeley/EndNote/Paperpile/RefWorks/Citavi) of callosum's shipped
LibreOffice cite-while-you-write adapter (incs 106-108) was filed to
`.claude/docs/future-tracks/chatgpt5.6_future-tracks_wordprocessorpluginsroadmap.md` (+ `…competitivereview.md`)
this session and folded into backlog `#33/#34`. One claim — that `_write_bibliography` deletes from a bookmark to
the document's literal end on every refresh, silently destroying any user text placed after the bibliography —
was verified against the shipped code as a real, live data-loss hazard (A-A value A4).

The user chose to actively work the full P0 batch (roadmap items 1-8). Deep exploration (3 Explore agents) plus a
Plan agent that verified claims against the real citeproc-js source and bundled CSL style XML established this is
realistically **8-10 separate increments**, several requiring hands-on LibreOffice verification with **zero CI
coverage** of the UNO mutation path. The user confirmed starting with the two most foundational, bounded slices:
**Phase 0** (an empirical spike to de-risk open questions) and **Phase 1** (the versioned mark-payload schema).

## Implemented

### Phase 1 — versioned mark-payload schema (`adapters/libreoffice/callosum_cite.py`)
- `SCHEMA_VERSION = 2` / `SUPPORTED_VERSIONS = {1, 2}` + `_ITEM_DEFAULTS` (locator/label/prefix/suffix/
  suppress-author/author-only/custom_override, all defaulted to `None`/`False`) — named after citeproc-js's own
  `citationItems` properties, not the roadmap's parallel vocabulary, so there is zero translation layer between
  what a mark stores and what the backend/citeproc will eventually consume.
- `encode_mark_name` always stamps `"v": SCHEMA_VERSION` — every mark any code rewrites from here forward (a
  normal refresh, an insert, anything later) silently upgrades to v2; a caller-supplied `"v"` is overwritten, not
  merged.
- `decode_mark_name` branches on `payload.get("v", 1)`: v1 (no `"v"` key — every mark written before this
  increment) and v2 both normalize their items through the new `_normalize_item` (pure, no UNO) so every caller
  downstream sees one consistent shape regardless of source version. An **unsupported future version** (e.g. a
  document opened with an older adapter after a later schema ships) decodes as an explicit **inert-but-present**
  marker (`{"unsupported": True, "items": None}`) — never treated as foreign (which would let something else
  clobber it) and never guessed at.
- `scan_citations_in_order` skips unsupported marks (leaves them untouched in the document, excludes them from
  the render request) rather than erroring.
- **No change to `insert_citation`, `refresh`, or any dialog** — the still-single-item payload it builds today is
  already a valid (if minimal) v2 shape once `encode_mark_name` starts stamping the version; `_normalize_item`
  fills the rest with defaults on the next read. The composer UI to actually set locator/prefix is Phase 5.
- `tests/test_libreoffice_adapter.py`: 6 new tests — v1-mark defaults-filled decode, v2-mark preserves-set-fields
  decode, unsupported-version-is-inert-not-foreign, encode-always-stamps-current-version (incl. overwriting a
  caller's own stale `"v"`), and `_normalize_item`'s fill-only-missing-keys behavior. All 14 tests in the file pass.

### Phase 0 — empirical spike (`adapters/libreoffice/selftest_uno.py`, run via `.local/lo_roundtrip/run_roundtrip.py`)
Four new spike checks against a real headless LibreOffice + a real callosum server (this machine has LibreOffice
installed; the harness already worked end-to-end before this increment):

1. **Mark-size/scale + save/reopen fidelity.** 25 citations in one document (redundant full-CSL-record embedding
   is the roadmap's own architectural worry), saved to a real `.odt`, reloaded as a fresh doc object, every mark
   still decodes losslessly. **Result: PASS.** Mark names ran 413-434 characters for these two seeded papers
   (no abstract field); scales linearly, no truncation/corruption through a save/reopen round-trip.
2. **`XUndoManager` behavior.** Zero prior usage anywhere in this codebase; Phase 2 (transactional refresh) and
   Phase 8 (safe flatten) both depend on `enterUndoContext`/`leaveUndoContext`/`undo()` grouping + reverting a
   multi-step mutation in one call. **Result: CONFIRMED WORKING** in this LibreOffice version — a grouped
   mutation reverted to the exact pre-mutation text in one `undo()` call.
3. **Copy/paste duplicate-name behavior.** Copying a `CALLOSUM_CITATION`-named `ReferenceMark` within the same
   document and pasting it. **Result: Writer refused/dropped the name collision** — paste did NOT duplicate the
   mark. This narrows Phase 9's "duplicate citation IDs" diagnostic: within-document copy/paste is not a live
   hazard by itself (cross-document copy/paste remains untested and is a real open question for Phase 9).
4. **Bounded-bibliography prototype: `TextSection` vs `Bookmark`.** Wrapped a heading+entries block in a
   `com.sun.star.text.TextSection` and rebuilt it via the section's own anchor range (never `text.getEnd()`).
   **Result: FAILED** — the rebuild-in-place destroyed text placed *outside* the section, i.e. the same class of
   bug it was meant to fix. This is a genuine, valuable negative finding: `TextSection.getAnchor()` did not give
   the tight boundary assumed. **Phase 7 should evaluate the `Bookmark`-pair fallback (a second, end-of-block
   bookmark) rather than assuming `TextSection` is the answer** — this prototype does not clear it.

## Key technical detail — a live bug reproduced by accident, not contrived
The first version of spike #1 inserted each of the 25 citations at `text.getEnd()` on every iteration (mirroring
a natural "keep citing at the end of what I'm writing" workflow). Only **1 of 25** marks survived. Root cause:
`insert_citation`'s own auto-refresh appends the bibliography at document-end the first time it runs; every
*subsequent* "insert at the end" call therefore lands its new citation inside the bibliography's own
future-deletion zone, and the very next refresh's `cursor.gotoEnd(True); cursor.setString("")` silently destroys
it — exactly the hazard already found by static code reading, now reproduced live through a completely ordinary
sequence (cite → auto-refresh → cite again at the end → auto-refresh), not a contrived edge case. The spike was
rewritten to place all 25 citations at pre-existing in-body anchors laid down before any refresh runs (mirroring
how the pre-existing AAA/BBB round-trip test already avoids this trap) so it measures what it set out to measure.
This is independent, freshly-reproduced confirmation that Phase 7 (bounded bibliography) is not a nice-to-have.

## Manual verification
1. `pytest tests/test_libreoffice_adapter.py -q` — 14 passed (6 new).
2. `python .local/lo_roundtrip/run_roundtrip.py` — full real-LibreOffice round trip, twice (once catching the
   live bibliography-bug reproduction + a missing `import tempfile`, once clean): `SELFTEST OK`, all four spikes
   reported above.
3. `ruff format` / `ruff check .` — clean. `python tools/check_line_budget.py` — clean (348 files; `adapters/`
   isn't walked by the gate, confirmed).

## Gates
- **Security audit:** not triggered — no new endpoint, no request-schema field reaching the backend, no new
  file-write path; the payload-shape change is adapter-internal, additive, and backward-compatible (old marks
  keep decoding losslessly, no user action required). Phases 2+ (a `storeToURL` file-write path, new UNO
  mutation logic, a backend request-schema change) will need audit-gate treatment when they land.
- **Principles/A-A (rule #9):** unchanged from the plan's framing — this phase only adds an internal versioning
  mechanism; it makes no new claim/signal/judgment and doesn't touch egress/provenance.

## Next
Phase 2 (transactional-refresh mechanism, now validated as buildable — `XUndoManager` behaves as needed) is the
next natural slice, followed by Phase 3 (backend locator/prefix/suffix passthrough through `citeproc_runner.js`).
Phase 7's design should start from the Bookmark-pair approach, not `TextSection`, per this session's finding.

# Increment 322 — LibreOffice adapter rework: Phase 3 (backend per-occurrence cite passthrough)

## Context
Phases 0-2 (incs 320-321) established the versioned mark-payload schema and a transactional `refresh()` for the
LibreOffice citation adapter (backlog #33/#34). Since Phase 1, every citation mark already carries per-occurrence
fields (`locator`, `label`, `prefix`, `suffix`, `suppress-author`, `author-only`) — but they were only ever
defaulted to `None`/`False` and silently discarded before reaching citeproc-js. This phase closes that gap on the
backend: the exact chokepoint (confirmed during the original research against the live citeproc-js source) is one
line in `citeproc_runner.js` that built a `citationItems` entry as literally `{ id: String(it.id) }`, discarding
everything else.

## Implemented

### `app/backend/citations/citeproc_runner.js`
- New `buildCitationItem(it)`: forwards `locator`/`label`/`prefix`/`suffix` (only when actually set — `!= null`,
  never assigning `undefined`, since a JS object literal with an `undefined`-valued key is still enumerable and
  could confuse citeproc's own presence checks) plus `"suppress-author"`/`"author-only"` (only when truthy) onto
  the `citationItems` entry, alongside `id`. Used by the document-mode cluster-building map.
- Header docstring updated to document the new per-item wire fields.

### `app/backend/api/routers/citations.py`
- New `CitationItem` Pydantic model replacing the bare `dict[str, Any]` in `CitationCluster.items`:
  `model_config = ConfigDict(extra="allow")` so the real CSL bibliographic fields (title/author/issued/…) still
  pass through untouched, plus explicit fields `locator`/`label`/`prefix`/`suffix` (length-capped: locator 200
  chars, prefix/suffix 300 chars — free text from an eventual composer UI needs a boundary per rule #4) and
  `suppress_author`/`author_only` (Python attributes, aliased to the hyphenated wire keys `suppress-author`/
  `author-only` to match citeproc's own vocabulary and Phase 1's mark-payload keys exactly — no translation
  layer, one wire shape).
- `label` is validated against `CSL_LOCATOR_LABELS`, the fixed CSL 1.0.2 term list (confirmed against the bundled
  locale XML during the original research — no `"timestamp"` or generic `"other"` exists in CSL) — a clean 422
  instead of silently reaching citeproc-js, which would just render an unrecognized label oddly rather than
  erroring.
- `render_citation_document` now dumps clusters with `model_dump(by_alias=True)` so `suppress_author`/
  `author_only` serialize as the hyphenated wire keys `render.py`/`citeproc_runner.js` expect.
- `render.py` needed **no change** — its `item = dict(it)` shallow copy already passed extra keys through
  untouched; only the JS-side consumption line was the actual gap.

## Tests
`tests/test_citations.py` — 6 new tests, all asserting against **real citeproc-js output** (not assumed):
- `test_render_document_locator_and_label` — a page locator renders into the in-text citation.
- `test_render_document_prefix_suffix` — real output is `"(see Vaswani, 2017 (emphasis added))"`: citeproc wraps
  prefix/suffix *inside* the citation's own parenthetical group, around the cite itself — not appended outside
  the parens as I'd first assumed; the test was corrected against the actual rendered string.
- `test_render_document_suppress_author` — the author name is dropped from the in-text cite.
- `test_render_document_author_only` — real output is bare `"Vaswani"` (no parens, no year): citeproc's
  `"author-only"` renders *just* the author name, not a full "Vaswani (2017)" narrative form as I'd first
  assumed — it's the building block for a manual narrative construction (paired with a companion
  suppress-author cite for the date elsewhere), corrected in the test + its docstring to describe what it
  actually does.
- `test_citation_item_rejects_unknown_locator_label` — `"label": "timestamp"` → 422.
- `test_citation_item_locator_length_capped` — a 201-char locator → 422.

All 14 tests in `test_citations.py` pass (8 pre-existing + 6 new). `tests/test_libreoffice_adapter.py` (15
tests) unaffected. The real end-to-end LibreOffice round trip (`.local/lo_roundtrip/run_roundtrip.py`) still
passes fully — the mark payload already sends `locator: null`/`suppress-author: false`/etc. by default since
Phase 1, and the new `CitationItem` model accepts those defaults without any adapter-side change needed.

## Key technical detail — two assumptions corrected by running the real engine
Both `prefix`/`suffix` and `author-only` behave differently from a first guess, and the tests were written to
match the *actual* citeproc-js behavior rather than an assumption: prefix/suffix wrap inside the cite's own
parenthetical (not appended to the outside of the whole rendered string), and `author-only` is a bare
name-only render (not a full narrative "Author (Year)" form). This matters for Phase 5's composer, which must
preview via a real round-trip to `/citations/render-document` rather than simulate rendering client-side — a
requirement already flagged during the original research and now doubly confirmed by these two corrections.

## Manual verification
1. `pytest tests/test_citations.py tests/test_libreoffice_adapter.py -q` — 29 passed.
2. `python .local/lo_roundtrip/run_roundtrip.py` — full real-LibreOffice round trip: `SELFTEST OK`, all prior
   spikes (Phase 0's four + Phase 2's rollback) still pass unchanged.
3. `ruff format` / `ruff check .` — clean. `python tools/check_line_budget.py` — clean.
4. Full suite (`pytest -n auto -q`) — see this session's closing run for the final count.

## Gates
- **Security audit:** not triggered on its own merits (no new endpoint, an existing request-schema field just
  gained explicit typed sub-fields with length caps — tightening validation, not loosening it); the caps
  (locator 200 / prefix,suffix 300 chars) are new input-boundary protections, not new attack surface.
- **Principles/A-A (rule #9):** unchanged — this only makes existing per-occurrence metadata actually render;
  no new claim/signal/judgment, no egress/provenance change.

## Next
Phase 4 ("find the mark near the cursor" helper, needed by edit/delete/merge/split) or Phase 5 (the composer UI,
the biggest single chunk, built directly against the now-complete v2 schema + backend passthrough) are the next
natural slices.

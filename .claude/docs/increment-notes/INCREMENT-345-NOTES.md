# Increment 345 — LibreOffice adapter: bibliography editing (include uncited / exclude cited) — P1 item #11

## Context
Next slice of the LibreOffice P1 roadmap after the "Citations in this document" panel (P1 item #12, inc 344).
Cliff picked bibliography editing (roadmap item #11): including an uncited "further reading" work in the
bibliography, and excluding a specific cited work (e.g. a personal communication — cited in text,
conventionally omitted from the reference list).

Research (an Explore agent, plus reading `node_modules/citeproc/citeproc_commonjs.js` directly) found both
mechanisms are **real, pre-existing citeproc-js capabilities** — `engine.updateUncitedItems(idList)` and
`engine.makeBibliography({exclude: [{field, value}]})`, the latter's `field`/`value` matching genuinely
against ANY item property (confirmed in `CSL.getBibliographyEntries`'s `eval_spec(spec.value, item[spec.field])`)
— just never wired through this codebase. The render-document contract is fully stateless per call
(`INCREMENT-107-NOTES.md`), so which papers are excluded/included must live in the document itself.

## Implemented
- **Backend** (`app/backend/citations/`, `app/backend/api/routers/citations.py`): `RenderDocumentRequest`
  gains two additive, optional fields — `uncited_items: list[UncitedItem] = []` and
  `bibliography_exclude_ids: list[str] = []`. `render_document()` validates and forwards them;
  `citeproc_runner.js`'s document-mode block registers uncited items into `itemsById`, calls
  `engine.updateUncitedItems()` after `rebuildProcessorState`, and passes an `exclude` bibsection to
  `engine.makeBibliography()` when exclude ids are given. Verified directly against real citeproc before
  writing any tests: excluding a personal-communication-type item removed it from the bibliography while its
  in-text "(K. Jones, personal communication, 2021)" render was unaffected; an uncited item appeared in the
  bibliography with zero in-text citations.
- **Adapter persistence** (`callosum_cite.py`): two new document user-properties, `PREF_BIB_EXCLUDE`/
  `PREF_BIB_UNCITED` (JSON-encoded paper-id lists), via new `_get_id_list`/`_set_id_list` helpers generalizing
  the existing `_get_pref`/`_set_pref` pattern. `refresh()` threads both through: fetches CSL for uncited
  papers (skipping any that are also actually cited — no redundant double-registration), passes the exclude
  list's ids straight through.
- **`list_document_citations`** (the panel's data source) extended: uncited-include papers appear with
  `count: 0, uncited: True, mark: None`; every entry gains `excluded: bool`.
- **`citations_panel.py`** — the natural, already-built home for "manage what's in my bibliography" (matching
  Zotero/EndNote), not a separate dialog. Moves from read-only to read-write, flagged as a deliberate
  architecture shift: a **"Toggle bibliography exclude"** button (per-work, not per-occurrence) and an **"Add
  uncited work(s)…"** button that reuses `composer.run_composer_dialog` verbatim (zero new dialog code) —
  both persist + call `refresh()` + re-fetch the panel's own list in place.

## Key technical detail — a real bug found and fixed along the way
The bibliography-editing real-UNO spike surfaced a genuine, pre-existing bug in `_write_bibliography`'s
"replace in place" branch: `cursor.setString("")` on the bookmark-bounded range clears the block's *text* but
was observed to sometimes leave the (now zero-width) `BIB_BOOKMARK`/`BIB_BOOKMARK_END` bookmark *objects*
still registered. The next rebuild's fresh `start_mark`/`end_mark` then collided on name with the survivors —
LibreOffice silently auto-renamed the duplicate (`"...Copy 1"`) instead of erroring, so instead of one clean
managed range, the bibliography accumulated an orphaned stack of old blocks on every second-and-later refresh
once the new `_get_id_list` calls were added to every `refresh()` invocation. **Fixed** by explicitly
re-querying `doc.getBookmarks()` fresh and calling `text.removeTextContent()` on any surviving bookmark before
creating the new pair — the same explicit-removal pattern `_replace_mark_text` already uses for ReferenceMarks,
just not previously applied to these bookmarks. This is a real, previously-latent bug independent of the two
new features — reading the actual failure (not just re-running until green) was what surfaced it; a naive
retry or a weaker assertion would have shipped a silently-corrupting bibliography rebuild.

## Principles/A-A gate (rule #9)
No claim/signal/judgment about the literature — deterministic re-rendering of the user's own document/library
data in their chosen CSL style, per their own explicit include/exclude choices. No gate trigger.

## Tests
- `tests/test_citations.py` (+4): real endpoint tests (`TestClient`, real citeproc) — uncited item appears
  with no in-text citation, exclude removes a bibliography entry while its in-text citation is unaffected, a
  malformed uncited item → 422, and the additive-fields-are-optional backward-compatibility check.
- `tests/test_libreoffice_adapter.py` (+8): `_get_id_list` defaults/reads/defensive-on-corrupt-JSON;
  `list_document_citations`'s new `excluded`/`uncited` flags, including the "already cited, don't duplicate as
  uncited" edge case; `build_render_request`'s new optional kwargs. (`_set_id_list` itself needs a real
  `com.sun.star` import, like `_set_pref`/`set_bib_auto` before it — no pytest coverage possible, real-UNO only,
  matching this codebase's established split.)
- `adapters/libreoffice/selftest_uno.py` (+1 spike, `spike_bibliography_editing`): real headless UNO — cites
  p1, adds p2 as uncited, excludes p1, checks the bibliography SECTION specifically (isolated from the in-text
  citation, since the default APA style's in-text render also contains the author surname) at each step, plus
  `list_document_citations`'s `excluded`/`mark` fields. This is what caught the bookmark-survival bug above.
- Full suite: **1413 passed, 1 skipped** (up from 1402 by the 11 new tests) — run via `pytest -n 4 -q`; `-n auto`
  intermittently hit unrelated worker crashes (`node down: Not properly terminated`) under this machine's
  resource pressure from the many ML-model-loading workers `-n auto` spawns, resolved by reducing parallelism,
  not a regression from this increment's changes. `ruff check`/`ruff format --check`/line-budget clean.

## Gates
- **Security-audit addendum** to `.claude/security-audits/2026-06-21_citation-render-document.md` (request-
  schema change to an existing endpoint) — PASS, additive/capped/same posture as the original.

## Manual verification (flagged, not optional)
Same standing ask as the citations panel: **Cliff should click through both new buttons in real Writer** —
toggle-exclude and add-uncited — soon, not let it join the composer's own months-long verification gap. The
extension version bumped 0.2.0 → 0.3.0.

## Next
Remaining P1 roadmap items (real CSL style manager, note/footnote styles, more bibliography editing controls —
categories/chapter bibliographies/hyperlinked entries, refresh/performance controls, portability, journal
abbreviations, keyboard/accessibility) stay open, per `INCREMENT-BACKLOG.md`'s #33/#34 entry.

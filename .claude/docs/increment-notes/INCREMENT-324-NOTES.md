# Increment 324 — LibreOffice adapter rework: Phase 6 (delete / merge / split / open-in-callosum)

## Context
Phases 0-4 (incs 320-323) built the versioned schema, transactional refresh, backend cite-property passthrough,
and `mark_at_cursor` — the shared lookup for "which existing citation is this action about." This phase is the
first to actually USE that lookup for real user-facing actions: Delete Citation, merge/split (the parts of
"true grouped citations" buildable without a composer), and "Open in Callosum." Edit Citation itself (locators,
prefixes, suppress-author/date — anything needing a real editing UI) and "revert manual overrides" (nothing can
set an override without that UI) both stay deferred to Phase 5, the composer — a scoping decision, not an
oversight.

## Implemented

### `adapters/libreoffice/callosum_cite.py`
- **`delete_citation(doc, field)`**: removes a citation's mark AND its rendered text — unlike `flatten` (which
  keeps text as static). Runs `removeTextContent` then unconditionally `cursor.setString("")`, since this file's
  own comments describe `removeTextContent`'s effect on the wrapped text inconsistently across
  `_replace_mark_text` ("the text + cursor range survive") and `flatten` ("removing a ReferenceMark also deletes
  its wrapped text") — clearing explicitly is correct regardless of which is actually true.
- **`_rewrap_mark_payload(doc, mark, payload, rnd)`**: replaces a mark with a fresh one (new rnd + payload)
  wrapping a `PLACEHOLDER` — the shared primitive for merge/split, mirroring `_replace_mark_text`'s pattern but
  for an item-SET change rather than a re-render.
- **`merge_citations(doc, earlier, later)`**: combines two citations into one grouped citation at `earlier`'s
  position. `later` is deleted first (it comes after `earlier`, so removing it can't invalidate `earlier`'s own
  anchor). Known v1 limitation, documented: text/punctuation between the two originals isn't cleaned up.
- **`split_citation(doc, field)`**: reverses a grouped citation into that many single-item citations, joined by
  `"; "`. Known v1 limitation: a fixed separator, no composer yet to let the user choose.
- **`open_in_callosum(doc, base)`**: resolves the citation at the cursor via `mark_at_cursor`, extracts the
  first item's paper id (stripping the `"callosum-"` prefix `stamp_item_id` adds), and opens
  `{base}/?open_paper=<id>` via stdlib `webbrowser.open` — no new dependency. Known v1 limitation: for a grouped
  citation, only the first work opens.
- New `_ACTIONS` entries (`deleteCitation`, `mergeWithNext`, `mergeWithPrevious`, `splitCitation`,
  `openInCallosum`) + matching macro wrappers + `g_exportedScripts` entries + `Addons.xcu` menu nodes (all
  showing an honest message box when the cursor isn't on a recognized citation, or when there's nothing to
  merge/split).

### `app/frontend/js/40_app.jsx`
- A new mount effect reads `?open_paper=<id>` from the URL, validates it (`parseInt` + `Number.isFinite`), and
  calls the existing `openPdf({id: paperId})` — the same chokepoint every citation-jump/Files-list/axis-open
  action already uses, so an invalid id degrades exactly as it already does everywhere else. The param is
  stripped via `history.replaceState` immediately after use (one-shot; a refresh doesn't reopen it).

## Tests
- **Real-UNO spikes** in `selftest_uno.py` (delete/merge/split touch `doc.getUndoManager()`/live mutation and
  aren't meaningfully fakeable, matching the established split from Phases 2/4): `spike_delete_citation` (removes
  both mark and text, confirms the OTHER citation + all surrounding body text survives byte-intact),
  `spike_merge_and_split_citations` (merge → exactly the right two item ids in one grouped mark; split → reverses
  losslessly back to the same two single-item marks), `spike_open_in_callosum` (monkeypatches `webbrowser.open`
  to capture the URL instead of launching a real browser during the test; confirms the exact expected URL). All
  passed on the **first** real run — no design assumption needed correcting this phase (unlike Phase 3's
  citeproc rendering surprises).
- `tests/test_frontend_assembly.py`: `test_open_paper_deep_link` — asserts the parse/validate/open/strip
  sequence is present in the assembled bundle.

## Manual verification
1. `pytest tests/test_libreoffice_adapter.py tests/test_frontend_assembly.py -q` — 61 passed.
2. `python .local/lo_roundtrip/run_roundtrip.py` — full real-LibreOffice round trip: `SELFTEST OK`, all prior
   spikes (Phases 0/2/4) still pass, plus all three new Phase-6 spikes.
3. `ruff format` / `ruff check .` — clean. `python tools/check_line_budget.py` — clean.
4. `python -c "import xml.dom.minidom; xml.dom.minidom.parse(...)"` — `Addons.xcu` well-formed.
5. Full suite (`pytest -n auto -q`) — see this session's closing run for the final count.

## Gates
- **Security audit:** this phase crosses "3+ files / ~300+ LOC" on its own (5 files, ~345 lines). Added as a new
  Addendum to `.claude/security-audits/2026-06-21_libreoffice-adapter.md` covering the cumulative Phase 1-6
  surface (phases 1-4 were each individually sub-threshold and hadn't been written up yet). **PASS** — delete/
  merge/split are local UNO mutations only; `webbrowser.open`'s URL is built from a fixed local base + a
  digit-validated id (mirrors the already-audited `os.startfile`/`open`/`xdg-open` pattern in
  `2026-06-27_libreoffice-install.md`); the frontend deep-link validates its param and rides the existing,
  already-audited `openPdf` chokepoint.
- **Principles/A-A (rule #9):** unchanged — narrates/manipulates existing citation structure the user already
  created; no new claim/signal/judgment, no egress-posture change (the deep link stays on `127.0.0.1`/the user's
  own configured base).
- **README:** `adapters/libreoffice/README.md`'s "Use" section gained steps 8-11 + the macro-name list; the
  "Limitations (v1)" paragraph updated to reflect merge/split now covering part of "grouped citations."

## Next
Phase 5 (the composer UI) is the last major remaining piece and the biggest single chunk — a unified live-search
citation composer serving both Insert and Edit, letting the user actually set locators/prefixes/suffixes/
suppress-author/suppress-date and build true multi-item citations from scratch (not just merge two existing
ones). Phase 7 (bounded bibliography, Bookmark-pair per Phase 0's finding), Phase 8 (safe flatten), and Phase 9
(diagnostics/repair) remain after that.

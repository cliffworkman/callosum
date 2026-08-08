# Increment 460 — Evidence-aware Suggest-Citation composer (backlog #33/#34, P2 item #17)

## Implemented

Second item in the confirmed P2-leapfrog roadmap (#19 → **#17** → #20 → #21 → #18 → #22; see memory
`callosum-p2-leapfrog-roadmap`). Scope was confirmed as everything in the roadmap's #17 checklist except
filters (study-type/year/tag/collection — "study type" doesn't exist as a concept anywhere in callosum's
schema, confirmed by grep).

Research found the actual scope smaller than the roadmap's 10-item checklist implied: `/citations/suggest`'s
response already carried everything needed — full quote, page/section, the complete 3-way stance breakdown
(`stance.probs`), match score, `chunk_id`, `coordinate_precision` (always `"region"` for these matches).
**This increment touches zero backend Python.** It's entirely `adapters/libreoffice/` plus one small frontend
deep-link extension.

### `_suggest_dialog` reshape (`adapters/libreoffice/callosum_cite.py`)

- **Multi-select**: `MultiSelection = True` on the pick-list (was hardcoded `False` — no multi-select pattern
  existed anywhere in this codebase before). Confirm reads `getSelectedItemsPos()` (plural).
- **New "Details…" button** (enabled for exactly one selected in-library row) opens `_suggestion_detail_dialog`
  — mirrors `composer.py`'s established "Options…" → `_edit_item_options` modal pattern (there is no live
  inline detail-on-select pattern anywhere in this codebase; didn't invent one). Shows: the full quote, page/
  section, the 3-way stance breakdown (`_stance_breakdown_text`), a "why retrieved" line (`_why_retrieved_text`),
  a weak-evidence warning (`_is_weak_evidence`, reusing `VerificationConfig.retrieval_threshold`/
  `support_threshold` — 0.7/0.55 — the *same* numbers invariant #1 already uses), an editable page-locator field
  pre-filled from `page_start` (`_auto_locator`), and an "Open in PDF" button.
- **Insert behavior**: 1 row selected → unchanged single-citation path (now carrying evidence_* + locator). 2+
  rows selected → one grouped multi-item citation via the *already-existing* `insert_citation_items` (needed
  zero signature changes — confirmed unrecognized per-item keys pass straight through to `encode_mark_name`
  untouched). **v1 boundary**: multi-select insert must be all-library or all-beyond, never mixed (a
  beyond-library pick needs its own `save_beyond_library_item` round-trip first) — checked after the dialog
  closes with a message box, not by disabling Insert live.

### Evidence-audit record (mark payload)

New optional keys on `_ITEM_DEFAULTS` (default `None`): `evidence_chunk_id`, `evidence_page_start`,
`evidence_page_end`, `evidence_snippet`. `evidence_snippet` is capped at `EVIDENCE_SNIPPET_MAX` (150 chars) —
tighter than the server's own 400-char `QUOTE_MAX` — since the mark-name payload has no enforced size ceiling
anywhere in this codebase, and a grouped multi-source citation would otherwise multiply quote-sized text across
every item. Only populated from the Suggest flow; `insert_citation_interactive`/`add_citation_by_search` are
unaffected. **No `SCHEMA_VERSION` bump** — confirmed additive/backward-compatible (the version gate is a pure
allow-list membership check on `v`, and `_normalize_item` treats all supported versions identically via
`setdefault`, never stripping unknown keys).

### "Citations in this document" panel — making the record visible

`list_document_citations` (`callosum_cite.py`) gains an `evidence` field per citation (`{"page", "snippet"}` or
`None`), read from the first occurrence's item — mirrors exactly how `retraction_label` already flows through
this same function. `citations_panel.py` gets a `📎 evidence` row tag (`_format_row`) and a new **"View
evidence…"** button (`do_view_evidence`, following `do_toggle_exclude`'s exact single-selection pattern) that
shows the recorded page + snippet in a `_msgbox`. Recording evidence with no way to ever see it again would have
been inert — this closes that loop.

### "Open in PDF" deep-link extension (`app/frontend/js/40_app.jsx`)

The existing `?open_paper=<id>` one-shot effect now also reads `page`/`precision` query params and, when
present, builds a minimal target `{ id, paperId, page, precision }` — mirroring the *exact* existing
`armCapture` minimal-target precedent. No `bboxJson` needed (`precision` is always `"region"` for these
matches; `applyPdfCitationTarget` only needs `bboxJson` for `"exact"`).

## Key technical detail

**Evidence fields ride along harmlessly in a later render-document request, by design, not by accident.**
`_build_records` merges every non-`paper_id` key from an insertion item onto the fetched CSL record
unconditionally (`overrides = {k: v for k, v in it.items() if k != "paper_id"}`) — there is no whitelist
anywhere in this path (confirmed: `_normalize_item`/`encode_mark_name` don't strip unrecognized keys either).
This means `evidence_*` fields end up embedded in the same CSL item that eventually reaches
`POST /citations/render-document` on a refresh. Confirmed this is genuinely harmless rather than assuming it:
the backend's `CitationItem` Pydantic model uses `model_config = ConfigDict(extra="allow")` specifically because
CSL-JSON records legitimately carry many fields citeproc-js doesn't use — extra fields are silently ignored,
not rejected or misused. No privacy/egress implication either way, since render-document is a same-origin
localhost call, not external egress. Documented this in a code comment near `_ITEM_DEFAULTS` rather than
building stripping machinery for marginal benefit — consistent with the codebase's existing `custom_override`
field, which *is* explicitly stripped, but only inside `composer.py`'s own UI-assembly layer, not globally.

**A real bug was caught by the existing pytest suite, not manual review**: the "uncited further reading" branch
of `list_document_citations` constructs its own `seen[paper_id]` entry separately from the main citation-scan
loop, and initially missed the new `evidence` key entirely — `test_list_document_citations_includes_uncited_
work_with_no_mark` failed with a `KeyError` immediately on the first test run after the panel changes, caught
before this ever reached a real document.

## Housekeeping / gates

- **Security audit**: an addendum appended to `.claude/security-audits/2026-06-21_libreoffice-adapter.md` —
  triggered by criterion #5 (3+ files, meaningful LOC), not by any new external-facing surface. Zero new
  backend endpoint/egress/dependency; the deep-link extension mirrors the already-audited `open_in_callosum`
  pattern with the same input validation; the evidence record reuses an existing storage mechanism with a
  disclosed, empirically-verified size bound (the extended `spike_mark_size_and_reopen`).
- **QA route**: `.claude/qa-routes/route_42_cite.md` (the route covering `POST /citations/suggest`) gets a note
  that the LibreOffice adapter now also consumes this unchanged endpoint, and that its own UI is verified via
  the real-UNO harness, not this browser-driven route (no LibreOffice in that harness).
- `.claude/docs/INCREMENT-BACKLOG.md`: P2 item #17 marked **✅ CLOSED inc 460** within the #33/#34 entry; the
  confirmed roadmap order (#19 → #17 → #20 → #21 → #18 → #22) recorded inline, pointing at the
  `callosum-p2-leapfrog-roadmap` memory.
- `.claude/CLAUDE.md`: counter bumped to 460.

## Manual verification script

1. Open a real Writer document, place the cursor in a sentence, run Suggest citations.
2. Select 2+ in-library rows (Ctrl/Shift-click), open Details on one, confirm the full quote/stance breakdown/
   weak-evidence warning/locator/Open-in-PDF all render and work; confirm Open in PDF jumps to the matched page
   with the honest region-level note (no fabricated exact highlight).
3. Insert — confirm one grouped citation lands with both sources.
4. Open "Citations in this document" — confirm the 📎 evidence tag appears and "View evidence…" shows the
   recorded page + snippet for each Suggest-inserted citation.
5. Confirm no document mutation occurs from Details/View evidence alone (no Undo entry) — only Insert mutates.

## Verification

- `pytest tests/test_libreoffice_adapter.py tests/test_frontend_assembly.py -q` → **213 passed** (12 new pure/
  duck-typed adapter tests + 1 existing test updated for the new `_ITEM_DEFAULTS` shape + 1 existing deep-link
  test updated for the new call signature).
- `ruff format` + `ruff check`: clean on all touched files.
- `python tools/check_line_budget.py`: unaffected (`adapters/` is outside the line-budget tool's scope).
- `python tools/build_frontend.py`: rebuilt after the `40_app.jsx` edit; `test_built_artifact_is_in_sync` green.
- Real-UNO: `python adapters/libreoffice/run_roundtrip.py` — the extended `spike_mark_size_and_reopen` proves
  grouped, evidence-bearing citations (full-length snippets) round-trip losslessly through a real save/reopen.

## Rollback

Revert `adapters/libreoffice/callosum_cite.py`, `adapters/libreoffice/citations_panel.py`,
`adapters/libreoffice/selftest_uno.py`, and `app/frontend/js/40_app.jsx` to their pre-460 state (re-run
`tools/build_frontend.py` after). All changes are additive/backward-compatible; a partial revert (e.g. keeping
multi-select but dropping the evidence record) is also safe since they're independent pieces. No schema/
migration.

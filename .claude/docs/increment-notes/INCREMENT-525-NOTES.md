# Increment 525 — Word bibliography title/DOI links

**Date:** 2026-08-28
**Scope:** Word P1 bibliography item #11, fifth bounded slice: document-local external links in full and
heading-scoped bibliographies.

## User behavior

**Link bibliography titles/DOIs to the web** is an opt-in checkbox stored with the Word document. When enabled,
DOI or URL text already emitted by the selected CSL style becomes a normal external hyperlink. If the style omits
that identifier, the existing backend contract may instead identify one uniquely rendered single-source title
and link it to the source DOI (preferred) or URL. The setting applies to the full bibliography, categorized
layouts, and every heading-scoped bibliography block.

No bibliography text is added or changed. Disabling the checkbox refreshes the managed bibliography controls as
the same plain text, leaving hyperlinks in ordinary manuscript prose untouched. The optional Flatten metadata
cleanup removes this setting together with the other Callosum document preferences.

## Render-plan and offset contract

The backend already supplies `bibliography_links`, aligned one list per `bibliography_text` entry, so this
increment changes no renderer or endpoint. The Word pure layer now carries entry text, identity, and validated
link spans through category reordering and section projection. Generated plans record the exact paragraph index
of each entry after category headings, blank separators, and the section-level **References** heading.

Backend offsets are Python Unicode code-point positions; JavaScript string offsets are UTF-16 code units. The
adapter converts with `Array.from(entry)` before extracting anchor text, preventing astral characters earlier in
an author/title from moving the hyperlink onto a neighboring range.

## Word range seam and fail-plain behavior

Microsoft's production WordApi 1.3 exposes `Range.hyperlink`, but no production API slices a Range by exact
character indexes. After inserting authoritative plain text, Word therefore:

1. loads only the generated Content Control's paragraphs;
2. requires the planned paragraph at that index to equal the exact entry text;
3. searches only that paragraph for the exact backend-approved anchor;
4. applies the hyperlink only when exactly one range matches.

Zero or multiple matches stay plain. The pure layer independently rejects list misalignment, noninteger,
overlapping, zero/out-of-range, or over-20-per-entry spans; URLs over 2,048 characters, without a hostname, with
credentials/whitespace/control characters, or outside HTTP(S) also stay plain. This intentionally stricter
fallback is preferable to a plausible link on the wrong title or identifier.

HTML insertion was rejected: Microsoft's Range HTML contract does not promise cross-platform fidelity, and it
would make link transport responsible for visible bibliography formatting. Citeproc plain text remains the only
visible-output authority.

## Scientific, privacy, and architecture boundary

No prompt, provider, model, parser, scientific verification, citeproc behavior, citation order, entry text,
database, dependency, credential, permission, API schema, or automatic egress changed. This is explicit document
navigation metadata, not a scholarly claim, signal, score, or model output; the Principles gate is non-triggering.

Following a generated web link is a deliberate user action in Word. Callosum never fetches or preflights the
destination. The task pane remains same-origin, and the Word-on-the-web bearer token never enters settings,
receipts, document hyperlinks, or logs. Security audit `2026-08-28_word-bibliography-links.md` is **PASS**.

## QA and experience pass

The checkbox sits with the existing bibliography controls, states the external-web effect directly, and is a
native accessible checkbox. It initializes from the document setting, disables while saving/refreshing, restores
the exact previous setting on failure, and reports enabled/disabled/error state in the existing live status area.
No CSS or new dialog was needed. QA route 34 contains the desktop/web manual matrix; route 35 and the static Node
suite guard the fixed task-pane surface and zero-provider-host property. The website registry was reviewed; the
existing CSL/citation capability claim and screenshot remain accurate.

## Automated verification

- Word pure/static logic: **62/62** (`node --test adapters/word/taskpane_core.test.js`).
- Focused Word/access/citation pytest: **82 passed** in 196.37s.
- Focused Help pytest: **14 passed** in 22.00s.
- Full repository suite: **2563 passed, 3 skipped** in 1195.40s (19m55s;
  `pytest -n auto -q --tb=short`).
- JavaScript syntax passed for `taskpane.js` and `taskpane_core.js`.
- Scoped Ruff format/check, Bandit, Tach, 569-file line budget, QA surface map (430/430 gated API surfaces),
  website coverage review, targeted pre-commit, secret/private-path scan, and `git diff --check` passed.

Pure tests cover Unicode code-point conversion, URL validation, malformed/misaligned/overlapping/out-of-range
metadata, the 20-span cap, category paragraph indexes, section projection/link retention, and static Office.js
setting/search/single-match/cleanup wiring. Existing backend tests cover safe DOI/URL/title span construction.

## Honest verification boundary

No available agent can drive real Word. WordApi paragraph enumeration, `Range.search`, `Range.hyperlink`, toggle
save/reopen behavior, full/section link refresh, ordinary-link isolation, desktop Word, and Word-on-the-web are
**not yet live-verified**. Per the maintainer's request, these checks remain recorded here and will be folded into
one consolidated manual arc checklist after implementation work finishes.

## Manual Word verification owed

1. In APA or another identifier-printing style, enable links and confirm the exact DOI/URL text is clickable in
   the full bibliography without any visible-text change.
2. Switch to Nature or another style omitting the identifier; confirm the uniquely rendered title links to the
   source DOI/URL without adding text.
3. Create categories/custom order and two heading-scoped blocks; Refresh and confirm the same exact links follow
   their entries in the full and projected blocks.
4. Save/reopen, change style, edit bibliography text manually, add/remove citations, and Refresh; confirm text and
   links repair together.
5. Disable links; confirm managed bibliography links disappear while an ordinary-prose hyperlink is unchanged.
6. Exercise unsafe/credentialed/non-HTTP(S), malformed alignment, overlapping/out-of-range spans, repeated anchor
   text, transformed/multi-source titles, and astral Unicode before an anchor; confirm plain or exact placement,
   never a neighboring link.
7. Flatten with and without metadata cleanup; confirm rendered links/text remain static as chosen and the saved
   preference is removed only when requested.
8. Repeat the core enable/refresh/save-reopen/disable path in Word on the web.

## Next

Continue the Word parity arc with the smallest remaining independent bibliography/P2 slice. Do not expand this
increment into internal citation targets, grouped-citation navigation, a section manager, or provider behavior.

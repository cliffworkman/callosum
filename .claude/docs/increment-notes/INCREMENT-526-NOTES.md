# Increment 526 — Word evidence-aware Suggest details

**Date:** 2026-08-28
**Scope:** Word P2/leapfrog item #17: inspectable Suggest evidence, confirmed locator, source navigation, and a
bounded document audit record.

## Implemented

Each existing Word suggestion now has **Details…** without changing `/citations/suggest` or ranking. The panel
shows the complete returned matched passage, page/range, all three local-NLI probabilities, a plain-language
semantic-retrieval reason, and a warning when neither the established retrieval nor support signal is strong.
The page locator starts from the matched page/range and remains editable or removable before Add. **Open in PDF**
uses the existing Callosum `open_paper` deep link and honest region precision.

Adding the suggestion carries the confirmed locator plus a compact audit record into the existing citation
assembly and document Custom XML. Citation Edit/Update preserves it. **Citations in this document…** shows an
evidence badge and **View evidence…** for the first occurrence's recorded page plus snippet. Repeated Suggest-row
picks continue to create one grouped citation through the already-shipped composer.

## Key technical detail

The shared response already contains every needed field: quote, page range, match score, `stance.probs`, chunk,
attachment, and region precision. The Word layer adds no backend contract. Its pure helpers:

- clamp display probabilities and expose the full support/mention/contrast breakdown;
- reuse `VerificationConfig`'s established 0.70 retrieval / 0.55 support defaults rather than inventing a new
  weak-evidence bar;
- accept only positive integer identities in navigation/audit metadata;
- generate only a relative same-origin `open_paper` path with hard-coded region precision;
- normalize whitespace and cap the stored snippet at 150 characters (151 with ellipsis);
- allowlist the four `evidence_*` fields separately from both CSL metadata and author-editable citation options,
  so Edit round-trips provenance without exposing it as formatting state.

The full quote remains display-only. The UI states that adding a suggestion embeds the bounded snippet in the
Word document; shared documents therefore carry this inspectable provenance by design.

## Scientific / Principles boundary

The user still chooses a candidate, adds it to an assembly, and explicitly inserts the citation. The stance is a
signal beside its quote and probability breakdown, not a verdict. The similarity percentage is explained as why
the source surfaced, not correctness. The warning says to verify. Nothing auto-selects, auto-inserts, changes
rank, produces a new claim, or introduces a hidden composite score. Region evidence never becomes an exact
highlight. This strengthens, rather than relaxes, the existing AI-assist auditability standard.

No model, prompt, threshold, provider, egress, parser, citeproc, database, API schema, dependency, or ordinary
search-add behavior changed. Security audit `2026-08-28_word-suggest-details.md` is **PASS**.

## QA / privacy / experience

The detail action is secondary to the add row, reports expanded state, and uses native buttons/input. All
response-derived HTML is escaped; the later audit display uses `textContent`. Open in PDF is disabled without a
PDF attachment. Detail toggling performs no API/model work. State is bounded to one eight-result run and replaced
on the next Suggest. The existing local-first and Word-on-the-web bearer boundaries are unchanged.

## Automated verification

- Word pure/static logic: **67/67** (`node --test adapters/word/taskpane_core.test.js`).
- Focused Word/access/citation pytest: **82 passed** in 210.82s.
- Focused Help pytest: **14 passed** in 26.82s.
- Full repository suite: **2563 passed, 3 skipped** in 1298.42s (21m38s;
  `pytest -n auto -q --tb=short`).
- JavaScript syntax passed for `taskpane.js` and `taskpane_core.js`.
- Bandit, Tach, 569-file line budget, QA surface map (430/430 gated API surfaces), website coverage review,
  targeted pre-commit, secret/private-path scan, and `git diff --check` passed.

Pure tests cover full signal/detail formatting, threshold behavior, missing-signal fallback, auto/edited/removed
locator behavior, bounded evidence, deep-link validation, Custom XML assembly/edit round-trip, first-occurrence
audit extraction, and static details/PDF/evidence UI wiring.

## Honest verification boundary

No available agent can drive real Word. Detail focus/layout, locator editing, popup navigation, actual PDF page
arrival, Custom XML save/reopen, evidence-panel interaction, desktop Word, and Word on the web are **not yet
live-verified**. Per the maintainer's request, they remain recorded here for one consolidated manual checklist
after the Word arc finishes.

## Manual Word verification owed

1. Run Suggest on a selected sentence; confirm ranked order and compact rows are unchanged.
2. Expand several details and confirm full quote, page/range, three-way signal, retrieval reason, and correct
   weak-evidence warning. Collapse/reopen without document mutation.
3. Edit and remove the auto locator, add several suggestions, insert one grouped citation, then Refresh and
   Edit/Update; confirm each locator and evidence record stays source-local.
4. Use **Open in PDF**; confirm the same paper/page opens with region—not exact—positioning. Confirm it is disabled
   when no PDF attachment exists.
5. Open **Citations in this document…**; confirm the evidence badge and bounded page/snippet display for Suggest-
   added works, and no badge for ordinary search-added works.
6. Save/reopen, copy/paste, style-switch, note-style insert, Delete, and Flatten; confirm evidence follows only
   its citation and causes no unrelated mutation.
7. Repeat core detail/add/insert/audit/navigation behavior in Word on the web and confirm zero provider requests.

## Next

Continue with one bounded Word P2 item. Do not expand this increment into beyond-library search, a new filter
taxonomy, primary scientific verification, automatic insertion, provider behavior, or a redesigned PDF viewer.

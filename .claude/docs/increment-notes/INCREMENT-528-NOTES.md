# Increment 528 — Word citation-coverage audit

**Date:** 2026-08-29
**Scope:** Word P2/leapfrog item #18: local structural detection of long citation-free prose stretches.

## Implemented

The Word task pane now offers **Citation coverage audit…**, a read-only local scan mirroring the genuinely
missing part of Writer increment 463. It reports runs of at least three consecutive substantive paragraphs
(15+ words each) without a Callosum citation anchor. Headings, short transitions, table prose, the managed full
bibliography, and managed current-section bibliography blocks break a run. Results include document paragraph
numbers and bounded first-paragraph previews; at most 20 previews render.

Inline citations map through their containing Content Control paragraph. Citation controls inside Word's native
footnotes/endnotes map through the note's main-text `reference` range, so a note-cited paragraph is not falsely
called citation-free. WordApi 1.6 session-local paragraph identities make this a batched correlation rather than
a quadratic range-comparison loop; WordApi below 1.6 fails explicitly. The IDs never survive the `Word.run`.

## Scope correction found during audit

The handoff correctly warned that Word's existing **Document diagnostics…** already covers the integrity half.
Tracing the code confirmed it shares `checkPaperExistence(ids)`: a trash-aware per-id `/papers/export` presence
check followed by fresh `POST /methods/retraction/check-selected` for surviving papers. A second "integrity
preflight" button would have duplicated behavior and created drift, so increment 528 adds only the structural
coverage gap. No backend route or contract changed.

## Scientific / Principles boundary

This is a description of citation placement, not claim-level analysis. It never says prose is unsupported, that
a citation is missing, or that one should be added. Report copy explicitly calls each result a structural review
prompt. No NLI, LLM, embedding, prompt, provider, citation recommendation, or support threshold is involved.
That preserves Principles #2 (signal rather than verdict), #5 (the author is the filter), and #6 (a clean scan is
not a certificate). The easy-but-misaligned semantic classifier was deliberately rejected.

## Technical and security boundary

The scan reads only Word paragraph/control/note-reference metadata and runs one linear pure-JavaScript pass. It
makes no `callosumFetch` request and never mutates the document. Paragraph IDs are session-local; report text is
assigned with `textContent`; previews cap at 150 characters and stored results at 20. No text is persisted,
logged, placed in a URL, or sent to Callosum. Security audit `2026-08-29_word-citation-coverage.md` is **PASS**.

## Automated verification

- Word pure/static logic: **76/76** (`node --test adapters/word/taskpane_core.test.js`), plus JavaScript syntax
  checks for both task-pane files.
- Focused Word serving + Help/access-control slice: **35 passed**.
- Full repository suite: **2564 passed, 3 skipped** in 1414.25s (23m34s;
  `pytest -n auto -q --tb=short`).
- Ruff format/check, Bandit, Tach, the 569-file line budget, QA surface map (430/430 gated API surfaces), website
  review (69 routes/20 figures), managed changed-file pre-commit, secret/private-path scan, and `git diff --check`
  passed.

Pure tests cover exact/below-threshold runs, citation and short-transition breaks, headings/tables/managed-
bibliography exclusions, document paragraph numbering, preview/result bounds, note-reference/static UI wiring,
and the absence of a coverage-specific backend call.

## Honest verification boundary

No available agent can drive real Word. Native inline/note paragraph mapping, table/bibliography exclusion,
task-pane rendering, paragraph numbering, WordApi 1.6 gating, zero mutation, desktop Word, and Word on the web
are **not yet live-verified**. Per the maintainer's request, they remain recorded for one consolidated manual
checklist after the Word arc finishes.

## Manual Word verification owed

1. Create exactly two, then exactly three, consecutive 15+-word citation-free prose paragraphs; confirm only the
   latter is reported and the paragraph range/preview is correct.
2. Add an inline citation to a qualifying paragraph and confirm it breaks the run.
3. In a separate all-note-style document, insert a native footnote/endnote citation and confirm its main-text
   reference paragraph counts as cited.
4. Confirm headings, short transitions, table prose, the full bibliography, and current-section blocks do not
   create false stretches; create more than 20 stretches and confirm bounded disclosure.
5. Confirm the report remains neutral, the document is unchanged, and no backend/model/provider request occurs.
6. Confirm WordApi below 1.6 fails explicitly, then repeat the core scan in Word on the web.

## Next

Continue with one bounded remaining Word parity item. Do not turn placement structure into unsupported-prose
classification, duplicate Document diagnostics, add semantic/provider work, or infer that a citation is needed.

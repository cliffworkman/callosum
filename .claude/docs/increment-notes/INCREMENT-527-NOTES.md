# Increment 527 — Word open-science statement insertion

**Date:** 2026-08-29
**Scope:** Word P2/leapfrog item #21: author-controlled disclosure drafting, transient staging, and plain-text
insertion.

## Implemented

The Word task pane now has **Insert open-science statement…** for the same seven kinds shipped in Work →
Statements and LibreOffice: data availability, code availability, preregistration, funding, conflict of interest,
ethics, and AI use. Each kind exposes the same small set of canned starting phrases plus a bounded editable draft.
Choosing a phrase asks before replacing different text.

Opening the panel reads the existing `GET /statements/pending` map. **Stage for other editors** and **Clear
staged** use the unchanged POST contract, preserving the web/LibreOffice/Word handoff without backend work.
**Insert at cursor** writes the exact normalized draft at the end of the current selection as ordinary Word text.
It deliberately does not clear the staged copy, so repeated or cross-editor placement remains an explicit author
choice.

## Technical and security boundary

Pure helpers own the seven-kind allowlist, phrase registry, 4,000-character normalization, staged-response
normalization, and POST request construction. The Office.js layer keeps at most seven drafts in memory. It makes
one GET only when the panel opens and one POST only on Stage/Clear; insertion makes no request. Unknown/non-string
staged data fails soft. Stage/Clear never enters `Word.run`; Insert never creates a Content Control, Custom XML,
field, bookmark, or citation record.

Desktop remains same-origin loopback. Word on the web retains the explicit bearer-gated relay; its cloudflared
template adds only the exact `/statements/pending` path (no broad statement wildcard). No provider, model,
metadata source, dependency, persistence, new endpoint, or schema is introduced. Security audit
`2026-08-29_word-open-science-statements.md` is **PASS**.

## Scientific / Principles boundary

Funding, ethics, conflicts, availability, preregistration, and AI-use disclosures are facts only the manuscript
author can assert. The task pane states that Callosum neither infers nor verifies them. Canned text is a visible,
editable starting point; no phrase is silently selected or inserted. The author reviews the exact prose and clicks
Insert. This is deterministic assistance, not generative AI, scientific evidence, or a truth verdict. The
Principles gate is aligned with #3 (facts and candidates stay distinct) and #5 (the human is the filter): the
author supplies the fact and owns the decision. The misaligned easy path—inferring disclosures from library
metadata or silently applying boilerplate—is explicitly absent.

## Automated verification

- Word pure/static logic: **71/71** (`node --test adapters/word/taskpane_core.test.js`).
- Focused Word serving + statement/access/Help: **42 passed**.
- Full repository suite: **2564 passed, 3 skipped** in 1353.69s (22m33s;
  `pytest -n auto -q --tb=short`).
- JavaScript syntax, Ruff format/check, Bandit, Tach, the 569-file line budget, QA surface map (430/430 gated API
  surfaces), website review (69 routes/20 figures), managed changed-file pre-commit, secret/private-path scan, and
  `git diff --check` passed.

The full Python aggregate completed before the final Word-only draft-switch/placeholder correction. That
correction changed no Python/backend contract and was revalidated afterward by the complete 71-test Node suite,
the 42-test focused Python slice, JavaScript syntax, and every static gate above.

Pure tests cover all seven kinds, phrase identity, bounds, response allowlisting, clear request semantics, complete
UI wiring, replacement confirmation, local GET/POST staging, exact selection-end insertion, and the absence of a
Content Control/fetch in the insertion function.

## Honest verification boundary

No available agent can drive real Word. Task-pane focus/layout, staged-state transitions, exact insertion after a
non-empty selection, ordinary-text editability, Content-Control absence, save/reopen, desktop Word, and Word on
the web are **not yet live-verified**. Per the maintainer's request, these remain recorded for one consolidated
manual checklist after the Word arc finishes.

## Manual Word verification owed

1. Open the statement panel; traverse all seven kinds and confirm the expected starting phrases.
2. Stage different kinds from Work → Statements and Word; reopen/switch kinds and confirm exact local handoff.
3. Edit a staged draft, confirm the indicator changes, and reject/accept replacement by a canned phrase.
4. Select existing prose, insert a custom draft, and confirm exact text lands after—not over—the selection as
   ordinary editable text with no Content Control.
5. Clear staging and confirm document text remains; Close/Escape and empty drafts must mutate nothing.
6. Exercise the 4,000-character boundary and confirm no provider/model/network request beyond the Callosum route.
7. Repeat the core load/stage/insert/clear flow in Word on the web through the existing bearer-gated relay.

## Next

Continue with one bounded remaining Word parity item. Do not turn this authoring aid into generated disclosures,
fact inference, automatic verification, persistent manuscript metadata, a new provider surface, or live fields.

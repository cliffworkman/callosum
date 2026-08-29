# Increment 529 — Word saved-evidence insertion

**Date:** 2026-08-29
**Scope:** Word P2/leapfrog item #20, mirroring Writer increment 461 without changing scientific semantics.

## Implemented

The Word task pane now offers **Insert saved evidence…**:

1. search any live library paper;
2. load a privacy-minimized list of its author-saved highlights;
3. choose one highlight and inspect its complete normalized quote and saved note;
4. optionally type a claim and explicitly run the existing local three-way stance classifier;
5. choose quote-only, quote + citation, saved note + citation, or quote/note card + citation;
6. edit the page locator and insert at the end of the current main-story selection.

Quote-only is explicitly labelled **no citation** and inserts ordinary editable text. All cited formats reuse the
current Word new-citation function, including Custom XML storage, document-wide placement compatibility,
in-text/native-note behavior, citeproc Refresh, bibliography update, and short `callosum-<paper_id>` identity.
The payload adds only `evidence_annotation_id`, page start/end, and a whitespace-normalized 150-character snippet.

## Read-only Word evidence projection

The original plan was to call the existing `GET /papers/{id}/annotations` route directly. During security review,
that proved unsafe for Word on the web: Cloudflare path ingress cannot distinguish GET from POST, so allowing the
path would also make annotation creation reachable to a bearer-token holder. Increment 529 instead adds
`GET /integrations/word/evidence/{paper_id}`, a dedicated read-only projection of only four needed fields. The route
is bearer-gated, has no POST sibling, and the tunnel keeps `/papers/{id}/annotations` blocked.

## Scientific / Principles boundary

The stance model is optional and executes only after a click; typing never triggers inference. Its existing
support/mention/contrast probabilities are shown as a **signal, not a verdict**. Callosum does not choose a paper,
highlight, insertion format, or locator, and it does not generate a paraphrase: the “saved note” format uses the
author's own note, falling back visibly to the quote when absent. No prompt, provider, threshold, ranker, model,
parser, or verification contract changed. This preserves Principles #2 (signal), #3 (evidence versus author text),
#5 (human filter), and #6 (unavailable signal is not a certificate).

## Bounds and failure behavior

Quotes above 20,000 characters and notes above 4,000 fail before insertion rather than being silently truncated.
The read-only projection caps one paper at 200 returned highlights and rejects oversized rows explicitly.
Stance text is bounded to the endpoint's existing 4,000-character limit; locator and persisted snippet caps are 80
and 150. Picker response identities/shapes are normalized, and scholarly content uses escaped HTML or `textContent`.
Saved evidence must be inserted from the main story; note styles still create the native note at that main-story
position. Close/Escape, invalid content, missing highlights, failed export, stance unavailability, and placement
mismatch do not claim success. There is no cloud fallback or provider request.

## Automated verification

- Word pure/static logic: **82/82** (`node --test adapters/word/taskpane_core.test.js`), plus syntax checks for
  both task-pane JavaScript files.
- Focused Word/annotations/stance/access/Help slice: **56 passed**.
- Full repository suite: **2566 passed, 3 skipped** in 1028.49s (17m08s; `pytest -n auto -q --tb=short`).
- Ruff format/check, Bandit, Tach, the 569-file line budget, QA map (431/431 gated API surfaces), website review
  (69 routes/20 figures), changed-file pre-commit, secret/private-path scan, and `git diff --check` passed.

Pure tests cover annotation normalization, all four formats, quote fallback, explicit
oversize rejection, bounded/blank stance requests, annotation/page/snippet provenance, Custom XML round-trip,
static author-control wording, quote-only branching, main-story restriction, shared insertion, and Refresh. Python
tests cover the read-only minimized projection, absent paper, POST=405, bearer gate, and exact tunnel matches/
non-matches.

## Honest verification boundary

No available agent can drive real Word. The Office.js body-plus-citation placement, quote-only absence of a field,
native note behavior, save/reopen provenance, task-pane accessibility/rendering, cancellation, and real desktop/
web relay behavior are not live-verified. Per Cliff's request, QA route 34 retains these checks for one consolidated
manual verification pass after the Word arc.

## Next

After validation and shipment, the remaining planned Word parity lift is research-first Zotero field conversion.
Mendeley/EndNote conversion stays declined without a complete vendor payload contract.

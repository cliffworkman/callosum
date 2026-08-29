# Security audit — Word open-science statement insertion (increment 527)

**Date:** 2026-08-29
**Surface:** `adapters/word/` plus unchanged `GET`/`POST /statements/pending`
**Result:** **PASS**

## Trigger and boundary

The increment changes three or more files and moves user-authored disclosure text between Callosum and a Word
document, so the audit gate applies. It adds no route, persistence table, filesystem operation, dependency,
credential, model, prompt, provider call, scientific threshold, or production setting. The existing endpoint is
single-process, in-memory, and already shared with the web Statements workspace and LibreOffice.

## Input handling

- Statement kinds are selected from the same seven-value client allowlist the backend enforces.
- Drafts are trimmed and capped at 4,000 characters in pure adapter logic; the textarea has the same `maxlength`,
  and Pydantic independently rejects longer request bodies.
- Staged responses accept only object properties with allowlisted keys and string values. Unknown kinds,
  arrays, non-string values, and empty text are ignored. Empty POST text retains the existing clear semantics.
- Canned phrase labels/kinds are fixed source literals; generated `<option>` markup is still escaped. The draft
  itself is never interpolated into HTML: it enters a textarea via `.value` and Word via `insertText`.
- Replacing an existing different draft with a canned phrase requires an explicit browser confirmation.

## Document boundary and failure behavior

Insertion reads the final bounded textarea value and writes it at `selection.getRange(Word.RangeLocation.end)`.
It creates no Content Control, Custom XML Part, field, link, bookmark, hidden metadata, or executable content.
Selected manuscript prose is not overwritten. A failed Office sync reports an error and publishes no success.
Stage and Clear call only the transient endpoint and never enter `Word.run`, so they cannot mutate the document.
Conversely, Insert performs no fetch, so document success is not coupled to staging/server success.

## Egress, credentials, and privacy

Desktop requests are same-origin loopback. Word on the web continues through the explicit bearer-gated relay;
its ingress allowlist is extended by exactly `/statements/pending`, not a `/statements*` wildcard, and all other
app/settings/manuscript routes remain unreachable. `callosumFetch` adds the credential only as a request header. The token never enters statement text,
HTML, a Word document, staging response, log, or report. This increment makes no provider/model/metadata request.

Staged text is author-supplied manuscript disclosure content and remains in process memory until cleared or the
server restarts. It is not written to disk or telemetry. A user who inserts or shares the Word document is
deliberately persisting/sharing the visible prose itself; no hidden scholarly content accompanies it.

## Scientific and Principles alignment

These disclosures are author assertions, not inferable evidence. The UI says Callosum does not infer or verify
them, supplies phrases only as editable starting points, and requires an explicit Insert action. It creates no
quality score, truth verdict, hidden recommendation, automatic selection, or provider-generated prose. This
preserves the existing CRediT/open-science authorship boundary and the local-first contract.

## Resource bounds

The client holds at most seven staged strings, each capped at 4,000 characters. One GET occurs only when the
panel opens; POST occurs only on an explicit Stage or Clear click. There is no polling, retry loop, model work,
high-frequency persistence, or unbounded collection.

## Residual manual boundary

No available agent can drive Word. Panel layout/focus, exact selection-end placement, plain-text editability,
Content-Control absence, save/reopen, and the desktop/web relay paths remain on the consolidated maintainer
checklist. Node tests cover allowlists, bounds, clear semantics, UI wiring, exact Word insertion call, and the
absence of citation-control/fetch work inside insertion; Python tests cover route validation and same-origin
asset serving.

**Security Audit: PASS**

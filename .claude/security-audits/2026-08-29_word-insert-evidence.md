# Security audit — Word saved-evidence insertion (increment 529)

**Date:** 2026-08-29
**Surface:** Word task pane, read-only Word evidence projection, shared Word-on-the-web relay allowlist
**Result:** **PASS**

## Trigger and data boundary

The increment spans more than three files and lets scholarly highlight text enter Word, so the audit gate applies.
The author explicitly opens the panel, searches a paper, chooses one saved highlight, reviews the complete quote
and note, chooses a format, and clicks Insert. No highlight is selected automatically. The optional stance request
runs only on **Check stance**, through the already-shipped local NLI scorer; it makes no provider call and is labelled
a signal rather than a verdict.

Desktop Word uses same-origin localhost requests. Word on the web uses the existing explicit Remote-access opt-in,
Cloudflare tunnel, and bearer token. Highlight text and an optional claim therefore transit Cloudflare only in that
explicit web mode, never in ordinary desktop mode. The token remains in the Authorization header and is never placed
in a body, URL, document, log, or report.

## Read-only relay design

Cloudflare ingress rules match paths, not HTTP methods. Exposing the existing
`/papers/{paper_id}/annotations` path would also have exposed its POST mutation method to a valid tunnel token.
Instead, Word receives one dedicated GET-only projection at `/integrations/word/evidence/{paper_id}`. It returns only
`id`, `page`, `anchor_text`, and `note`; no attachment identity, bounding boxes, prefixes/suffixes, colors, source fields,
timestamps, paper metadata, or write method cross that seam. The route is not in the five static-asset exemptions,
so Remote access still requires the bearer token. The tunnel allowlist matches only decimal paper-ID path segments;
the original annotation path and the broader `/papers/{id}` path remain blocked.

## Input, output, and document bounds

- Evidence insertion rejects quotes above 20,000 characters and notes above 4,000; it never silently truncates the
  manuscript text being inserted.
- The read-only projection lists at most 200 highlights and rejects over-limit quote/note rows rather than
  returning an incomplete picker or an unbounded tunneled response.
- Stance request claim and passage are each capped at 4,000 characters by both client and existing API validation.
- Locators cap at 80 characters. Persisted evidence snippets normalize whitespace and cap at 150 characters.
- Paper and annotation pickers accept only positive integer identities; response shapes are normalized before use.
- Scholarly text is written with `textContent` or escaped before HTML assembly. No raw quote/note becomes markup.
- Quote-only is explicitly labelled **no citation** and creates no Content Control or Custom XML Part.
- Cited formats reuse the existing namespaced Custom XML citation payload and retain only bounded annotation/page/
  snippet provenance alongside CSL data. Runtime/model signals are not persisted as scientific findings.

## Mutation and failure behavior

All server/export/format validation needed for a cited insert occurs before the Office citation mutation. Evidence
insertion is allowed only from the main story, so a body quote cannot be ambiguously added inside a footnote while a
new note citation is created elsewhere. In-text and native-note citations share the existing placement checks,
Custom XML storage, Refresh, and bibliography lifecycle. Missing annotations, invalid formats, over-limit content,
failed export, unavailable stance inference, unsupported placement, Close, and Escape never publish a successful
result. There is no cloud fallback, provider retry, polling, background timer, filesystem path, or new dependency.

Office.js provides no native transaction/undo-context equivalent. The integration therefore retains the project's
existing build-before-mutate discipline but cannot claim one-step rollback. This limitation is recorded for the
consolidated manual Word verification checklist rather than hidden.

## Principles alignment

The feature preserves Principles #2, #3, #5, and #6: the model exposes a three-way signal, the quote remains source
evidence while the saved note remains author text, the author chooses every paper/highlight/format, and absence of a
stance result is not a certificate. Automatic stance calls, automatic evidence choice, provider-generated
paraphrases, and a hidden support verdict were explicitly rejected.

## Residual manual boundary

No available agent can drive Word. Real insertion position, native footnote/endnote creation, Refresh after body +
citation insertion, save/reopen provenance, task-pane rendering, cancellation, desktop no-egress observation, and
Word-on-the-web tunnel behavior remain not live-verified. They are recorded in QA route 34 for the consolidated
manual checklist requested after the Word arc.

**Security Audit: PASS**

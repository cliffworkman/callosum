# Security audit — LibreOffice document lifecycle observer (2026-07-23)

## Scope

Increment 359 adds a packaged LibreOffice document-event job and one in-process Writer modification listener per
open document. The observer restores persisted refresh state and compares Callosum-managed citation/bibliography
structure after document changes. No backend endpoint, dependency, secret, network host, or document content
export is added.

## Threat review

- **Egress / SSRF:** the lifecycle job and listener make no HTTP request. They cannot invoke citation rendering;
  only an existing explicit refresh command can contact the configured local Callosum endpoint.
- **Input / parsing:** only ReferenceMarks already accepted by the versioned `decode_mark_name` contract enter
  the citation signature. Bibliography reads are bounded by the existing start/end bookmark pair.
- **Mutation authority:** observer output is limited to the two existing `"0"`/`"1"` document properties and a
  fixed native Infobar. It never inserts, deletes, moves, or formats manuscript text.
- **Injection:** `Jobs.xcu` contains fixed event aliases and a fixed service implementation name. OXT tests parse
  the XML and require the job configuration and manifest entry.
- **State integrity:** listeners are keyed by Writer's runtime-unique document ID, deduplicated, and discarded on
  disposal. Re-entrant property-change callbacks are suppressed. Callosum commands retain their precise existing
  dirty-state accounting; changed state after an exception is conservatively reported as both surfaces pending.
- **Resource use:** each Writer modification performs a finite scan of recognized citation marks and the bounded
  managed bibliography. No polling, thread, timer, network retry, or unbounded queue is introduced.
- **Secrets / filesystem / supply chain:** no secret or new shipped filesystem path is accessed. `Jobs.xcu` is a
  static configuration entry in the existing OXT. No dependency changes.

## Negative-path proof

- A plain prose edit produces the same managed-structure signature and leaves both flags clean.
- A native citation move changes ordered mark structure and sets both flags plus the Infobar.
- Repeated lifecycle events attach only one listener for the document.
- Non-Writer models are ignored; listener and Infobar failures remain best-effort and cannot crash Writer.
- The installed real OXT restores a saved citation-only warning before any Callosum command runs.

## Result

**Security Audit: PASS**

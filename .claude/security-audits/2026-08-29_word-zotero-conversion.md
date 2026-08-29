# Security audit — Word Zotero field conversion (increment 530)

**Date:** 2026-08-29
**Surface:** untrusted Word fields/bookmarks, local library mutation, document mutation, Word-on-the-web relay
**Result:** **PASS**

## Vendor and platform contract

The parser is based on Zotero's current first-party Windows/Mac integration source, not a guessed community
format: inline citations use `ADDIN ZOTERO_ITEM CSL_CITATION {json}`, bibliographies use
`ADDIN ZOTERO_BIBL {json} CSL_BIBLIOGRAPHY`, and Bookmark mode uses `ZOTERO_BREF_…`. WordApi 1.5 supplies the
field code/result/delete surface. Prefixes are exact; unknown field types, malformed JSON, absent `itemData`,
oversized payloads, note fields, and Bookmark mode fail closed.

## Untrusted-input and resource bounds

- Field code is capped at 1 MiB and decoded without evaluation or HTML insertion.
- One citation may contain at most 100 items; one conversion at most 500 fields and 300 distinct works.
- Embedded items are canonically deduplicated before the existing backend cap is crossed.
- Only allowlisted per-item citation overrides survive; raw object prototypes or arbitrary fields do not become
  control properties. Scholarly strings remain data inside the existing namespaced Custom XML payload.
- A second full scan must have the exact same canonical field/bookmark snapshot before any document mutation.
- Zotero bibliography replacement requires exactly one valid inline bibliography and no note, Bookmark-mode, or
  malformed Zotero remainder. Unsupported material remains untouched.

## Network, credential, and egress boundary

Desktop conversion is same-origin localhost. Word on the web reaches the already-local
`POST /citations/zotero/resolve` through one exact Cloudflare ingress path and the existing bearer-token gate;
there is no wildcard route. The request contains only bibliographic metadata already embedded in the opened
document. The endpoint performs local identity matching or metadata-only creation and makes no provider/model
request, retry, fallback, or outward egress. The token remains an Authorization header and never enters a field,
descriptor, log, or document.

## Mutation and failure behavior

The author sees exact conversion/remainder counts and explicitly confirms after being told to save a copy. The
resolver runs before document mutation, all Custom XML parts are created before field deletion, fields are replaced
in reverse document order, and the existing Refresh/parser/bibliography lifecycle remains authoritative. A changed
snapshot fails before resolution or mutation. A resolver or validation failure leaves the Word document untouched.
Office.js offers neither save-as nor a native undo transaction: newly created metadata-only library rows can remain
if a later Office batch fails, and Word Undo cannot remove them. The dialog discloses both facts rather than claiming
atomicity. There is no cloud fallback.

## Residual platform boundary

No available agent can drive Word. Real Zotero field enumeration, result-range replacement, Content Control
placement, mixed unsupported content, save/reopen, and desktop/web behavior remain not live-verified. QA route 34
records them for Cliff's consolidated end-of-arc manual pass. Mendeley Cite and EndNote conversion remain declined:
no comparable complete/versioned vendor payload contract was established.

**Security Audit: PASS**

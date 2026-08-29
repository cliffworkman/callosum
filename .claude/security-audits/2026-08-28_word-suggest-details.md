# Security audit — Word evidence-aware Suggest details (increment 526)

**Date:** 2026-08-28
**Surface:** `adapters/word/` only; unchanged `POST /citations/suggest`, `/papers/export`, and same-origin
`?open_paper=` contracts.
**Result:** **PASS**

## Trigger and boundary

The increment changes three or more files and stores a small evidence locator in Word documents, so the audit
gate applies. It adds no API route, provider call, dependency, credential, permission, filesystem access, model,
prompt, scientific threshold, or production persistence outside the existing Word Custom XML payload.

## Input and output handling

- The shared endpoint already caps draft input at 4,000 characters, suggestions at 20 server-side (Word asks for
  eight), and returned quotes at 400 characters. The Word locator input is capped at 80 characters in the UI.
- Suggestion titles, quotes, reasons, page text, probabilities, labels, and stored evidence are escaped before
  HTML insertion. The later evidence display uses `textContent`, not HTML.
- Numeric paper/attachment/page/chunk identities must be positive integers before they enter generated navigation
  or audit metadata. Invalid/missing optional fields degrade to no link, no locator, or no evidence record.
- The weak-evidence indication reuses the established verification defaults (retrieval 0.70, support 0.55); it
  introduces no attacker-controlled expression, regular expression, or dynamic code.

## Navigation / SSRF / egress

`Open in PDF` constructs only a relative same-origin `/?open_paper=<integer>&page=<integer>&precision=region`
path. It requires the endpoint's positive PDF attachment identity, hard-codes region precision, and never accepts
an arbitrary scheme, host, filesystem path, or URL from suggestion content. It is a deliberate user click and
does not preflight or fetch anything itself.

In-library Suggest remains fully local (local embeddings + local NLI). No OpenAI, Anthropic, Gemini, metadata-
provider, or other external request is added. Word on the web continues through the existing bearer-gated relay;
the token stays in origin-local storage/request headers and never enters the detail HTML, deep link, document
payload, evidence record, logs, or report.

## Document data / privacy

The complete matched quote is displayed from the already-returned response but is not newly persisted. Only a
whitespace-normalized snippet capped at 150 characters (151 including the ellipsis), positive chunk/page fields,
and the confirmed locator join the citation's existing document-local Custom XML only on citation insertion. The
UI discloses this beforehand, and **View evidence…** makes it inspectable afterward. Because it is embedded in the Word file, the snippet
travels if the author shares that document; this is expected audit provenance, not hidden telemetry. No raw draft
sentence is persisted by this increment.

## Resource / failure behavior

State is bounded to the current eight suggestion responses and is replaced on every Suggest run. Detail toggles
perform no model/API request. Adding uses the existing one-paper export call, citation insertion, and refresh.
Missing/malformed signals fail soft; an Open-in-PDF action is disabled without a PDF attachment. Citation Edit
round-trips the exact allowlisted evidence fields rather than treating arbitrary CSL keys as UI state.

## Scientific / Principles alignment

This is an inspectability improvement to an existing model-backed signal, not a new judgment. Every stance
breakdown stays beside its verbatim matched passage and plain-language retrieval reason; region precision is
explicit; the weak-evidence message says **verify**; and nothing inserts until the author chooses Add and then
Insert. No hidden composite, paper-quality claim, correctness verdict, automatic selection, or ranking change is
introduced. It directly strengthens the ratified AI-assist auditability standard in the architecture log.

## Residual manual boundary

No agent can drive real Word. Popup/deep-link behavior, focus/layout, document Custom XML round-trip, save/reopen,
desktop Word, and Word on the web remain on the consolidated maintainer-manual arc checklist. Pure/static tests
cover normalization, bounds, exact persisted keys, edit round-trip, safe deep-link construction, and UI wiring.

**Security Audit: PASS**

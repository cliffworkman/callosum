# Security Audit — LibreOffice (UNO) citation adapter (inc 108)

**Date:** 2026-06-21
**Feature:** The first word-processor adapter — a drop-in LibreOffice Writer Python macro that places live
citation fields (ReferenceMarks carrying CSL-JSON), reads the ordered set, and writes back the in-text + bibliography
that callosum's `POST /citations/render-document` (inc 107) renders. Client-side code that ships into the user's
LibreOffice; **no change to the callosum server.**
**Files:** `adapters/libreoffice/callosum_cite.py` (the macro), `adapters/libreoffice/README.md`,
`adapters/libreoffice/selftest_uno.py` (headless round-trip harness), `tests/test_libreoffice_adapter.py`.

## Trigger
The future-track spec flags the **per-target field-injection path into live documents** as a security surface; a
new external component also warrants a review. Note what this is **not**: no new server endpoint, no new server
dependency, no new server fetch/ingestion path, no auth change. The render endpoint it calls was audited inc 107.

## Threat review
- **Field injection into the document.** The adapter writes the server's rendered citation/bibliography text into
  Writer ranges with `XText.setString` / `insertString` — i.e. **plain text**, never an HTML/RTF/ODF paste path.
  There is no markup interpreter on the write side, so a malicious-looking rendered string cannot inject document
  structure, macros, or fields. The server output is *already* sanitized (`render._safe_html` / `_to_text`, inc
  106/107); the adapter takes the **`text`** field (plain), not HTML. Defence-in-depth: even unsanitized text
  would be inert as `setString` content.
- **Untrusted input / boundary (rule #4).** Two inputs: (a) the user-typed paper id — coerced with `int()` before
  it reaches `/papers/export` (a non-numeric id raises and is shown in a message box, never executed); (b) the
  ReferenceMark name payload — `decode_mark_name` is **defensive**: wrong prefix/arity, bad base64, bad JSON, or an
  empty item list all return `None` and the mark is skipped (a corrupt or foreign mark — e.g. a real Zotero mark —
  never crashes a refresh and is never sent to the server).
- **SSRF / external calls / egress.** The macro talks **only** to a fixed `http://127.0.0.1:8080` base over stdlib
  `urllib` (no third-party HTTP client). The CSL-JSON it sends is the **user's own document/library data**, to the
  user's own local server. No remote host, no cloud, **no egress** (this is the local LibreOffice target — exactly
  why it is the first adapter; Google Docs, the cloud target, is fenced as opt-in and built last). The two
  `urlopen` calls carry `# noqa: S310` with a justification (fixed local base, not attacker-controlled).
- **Resource / DoS.** Bounded by the document: each refresh sends N clusters where N = citations in the document;
  the server already caps clusters/items/total (inc 107). HTTP calls use a 20s timeout. No unbounded loops (the
  `_new_rnd` counter and the scan both iterate the finite mark set).
- **Secret handling.** None — no keys, no tokens; the macro reads only the local library.
- **File-path safety.** The macro writes nothing to disk and builds no filesystem path; the only paths are the
  user's chosen Scripts/python install location (manual) and the dev self-test's temp profile (not shipped).
- **Code-execution surface.** The macro decodes base64→JSON only (`json.loads`, not `eval`/`pickle`); a crafted
  mark name can at worst produce a `None` (skipped) or a CSL dict forwarded to citeproc, which treats it as data.
- **Fail-safe UX.** Every macro entry point wraps its work in try/except and surfaces failures in a Writer message
  box — a server-down / bad-id / network error never crashes Writer or corrupts the document.

## Negative-path checks (concrete)
- Foreign/malformed/empty marks → skipped, not fatal (`test_decode_rejects_foreign_and_malformed`).
- Non-numeric / unknown paper id → `int()`/`fetch_csl` raises → message box, no document change.
- Unknown style id → `set_style` validates against `GET /citations/styles` and raises before any write.
- Internal `_mark` handles are stripped from the request body (`test_build_render_request_shape`) — only CSL-JSON +
  citationID reach the server.
- **End-to-end**: the headless UNO self-test (`selftest_uno.py`) drives a real LibreOffice through insert → render →
  restyle → flatten against a live callosum and asserts the position-aware output — confirming the write path is the
  plain-text path described above.

## Principles gate (rule #9)
Clears. The adapter **places**, callosum **renders** — no formatting (and thus no claim) originates in the adapter;
it **never auto-inserts** (every action is user-invoked); it is fully **local** (no egress). Credit-the-lineage is
honored: the Zotero `CSL_CITATION` field convention is credited as a *pattern* in the README + `THIRD-PARTY-NOTICES.md`.

## Result
**Security Audit: PASS** — client-side, local-only, plain-text writes, defensive decode, no new server surface, no
egress, no secrets, no file-path-from-input.

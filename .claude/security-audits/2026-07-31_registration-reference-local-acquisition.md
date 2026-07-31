# Security and privacy audit — registration references and local PDF attachment

**Date:** 2026-07-31
**Increment:** 426
**Status:** PASS

## Surface

Increment 426 parses registration identifiers from already-local article/supplement text and PDF URI annotations,
stores evidence rows, accepts a manually pasted identifier, lets a user reclassify an owned attachment, and imports a
browser-selected local PDF into the managed library as `role='preregistration'`.

It adds no registry provider, server-side URL fetch, redirect handling, search, credential, AI call, or automatic
action on panel open. Network discovery/acquisition remains out of scope.

## Threat review

- **Unexpected egress:** extraction and normalization are pure local operations. The pasted value is stored, never
  resolved. “Open externally” is an explicit user browser navigation, not a backend request. No paper text or metadata
  leaves the machine.
- **Arbitrary file upload/read:** the UI sends only bytes from a user-selected browser file. The upload endpoint is
  denied in read-only mode, through forwarded/tunnel requests, and from non-loopback clients. It does not accept a
  server filesystem path.
- **Resource exhaustion:** `Content-Length` is checked when valid and the streamed byte count is independently capped
  at 80 MiB. Oversized partial files are removed. PDF parsing happens only after the bounded write completes.
- **Content validation:** local uploads require `%PDF-`, must open with PyMuPDF, and must contain at least one page.
  Invalid content does not create an attachment or chunks.
- **Filename/path traversal:** the client filename contributes only a sanitized, length-bounded stem. Directory
  components and unsafe characters are removed; the destination is always a child of the configured managed library,
  with collision-safe suffixing. Temporary names are UUID-derived in the OS temp directory.
- **Partial failure:** the temporary file is removed in `finally`; if database ingest fails after the managed move,
  the managed file is removed and the transaction rolls back. Existing paper data is unchanged.
- **Cross-paper mutation:** attachment-role updates require both attachment id and owning paper id in the update
  predicate. Unknown/foreign attachments return 404. Role values are a five-value Pydantic allowlist.
- **Cross-document contamination:** the registration PDF enters the exact same extraction/chunk pipeline but carries
  canonical `preregistration` role. Increment 425's structural tests keep it out of article synthesis, search,
  summaries, transparency, and article processing state.
- **Reference confusion:** evidence records are not candidate/confirmed links. Provider/id normalization does not
  assert that the record belongs to the paper. Hidden PDF targets explicitly record that the URL was not printed.
- **Database input:** SQLAlchemy bound statements are used throughout. Stored strings are rendered by React as text;
  external URLs are opened only from normalized `http(s)` patterns.
- **Secrets/supply chain:** no credentials, cookies, auth sessions, new dependencies, or external executable are used.

## Negative-path evidence

- Context-free generic DOI/URL text is not classified as a registration reference.
- Registration language with no identifier returns `language-detected`, not a fabricated reference.
- Invalid manual text returns 422; invalid/oversized/non-PDF upload fails before persistence.
- A hidden “here” annotation retains the OSF target, visible text, nearby snippet, page, and non-printed status.
- Manual duplicate references are idempotent.
- An uploaded registration is attachment-scoped and stored with `preregistration` role.
- A role update cannot target an attachment belonging to another paper.

## Result

**Security and privacy audit: PASS.** The new write surface is local-only, bounded, validated, ownership-scoped, and
has no egress. Registry discovery and confirmed acquisition require a separate provider/SSRF/consent audit in the next
increments.

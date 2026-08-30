# Security audit — native Mendeley OAuth library import (backlog #57 Phase 6A)

**Date opened:** 2026-08-30
**Status:** **OPEN — bounded transport scaffold passed; OAuth activation blocked**
**Planned surface:** Mendeley OAuth 2.0 Authorization Code flow; paginated document/folder/file reads; bounded PDF
download and existing paper/PDF import paths.

This stub is opened before implementation, as required by the Phase 6 handoff. It is not a PASS and must not be
closed until the maintainer registers Callosum at `dev.mendeley.com` and the exact current authorization flow can
be exercised end to end.

## Required review before closure

- Exact current authorization/token endpoints, redirect URI, minimum scopes, state/PKCE/CSRF posture, callback
  host validation, token refresh/revocation, and provider error handling.
- Client secret and access/refresh token storage through the existing write-only credential boundary; no token in
  URL, argv, frontend state, logs, jobs, receipts, or errors.
- Explicit user consent before any Mendeley egress; personal-library-only scope unless a later audited increment
  deliberately adds groups.
- Hard page/document/folder/file/byte/time/retry/redirect bounds, HTTPS-only redirects, signed-download host
  validation, MIME/signature checks, filename/path traversal resistance, and partial-import failure behavior.
- Identity matching before paper creation; attachment deduplication; no silent overwrite; no provider fallback.
- Negative tests for denied/replayed callback, invalid state, expired token, pagination cycles, rate limits,
  redirect abuse, oversized PDFs, malformed metadata, and interrupted imports.

## Increment 537 partial evidence

- Fixed official HTTPS endpoints and version-1 Accept types; access tokens appear only in Authorization headers.
- Page size 500 with hard page, document, folder, file, body, URL, token, and code limits. Provider next links
  must remain HTTPS on `api.mendeley.com` and the exact starting resource; cycles fail closed.
- `/files/{id}` is not automatically followed. Only the documented HTTPS `downloads.mendeley.com` signed host is
  accepted by the scaffold. No file bytes are downloaded or ingested yet.
- OAuth and API errors exclude provider bodies, tokens, client secrets, and request details; secret-bearing
  dataclasses also redact their repr. HTTP is injectable; 16 focused tests passed without egress.
- No callback, state persistence, token storage, route, UI, importer, or live request exists, so this audit
  deliberately remains OPEN.

Fresh official documentation exposes a blocker requiring design evidence, not a workaround: authorization code
is a confidential-client-secret flow with no documented PKCE, while registration pins one redirect URI. A
distributed desktop binary cannot keep an embedded shared secret confidential and Callosum's ordinary backend
port may move. Activation requires app-registration/support evidence plus a defensible secret and redirect owner.

# Security audit — native Mendeley OAuth library import (backlog #57 Phase 6A)

**Date opened:** 2026-08-30
**Status:** **OPEN — implementation and live OAuth verification not started**
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

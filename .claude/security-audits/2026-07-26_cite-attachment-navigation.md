# Security audit — Cite attachment navigation and active PDF identity

**Date:** 2026-07-26
**Increment:** 392
**Status:** PASS

## Surface

- Existing `POST /citations/suggest` responses add an optional integer `attachment_id` sourced from the matched
  chunk's database-owned attachment.
- Existing Cite evidence clicks pass that id to the existing paper PDF route.
- The existing viewer displays the filename already supplied by that route's `Content-Disposition` header.
- No endpoint, parser, persistence, dependency, network destination, or executable surface is added.

## Threat review

- **Authorization and paper scope:** the serving route accepts only an integer and requires the selected attachment
  row to belong to the requested paper. A stale, unknown, or different-paper id fails closed.
- **Path handling:** no client path is accepted and no local path is returned. The route resolves its path solely
  from the database row. The UI displays only `path.name`, which the response already exposed as its inline
  filename before this increment.
- **Type confusion:** the citation engine returns an id only for records typed as PDF. A non-PDF matched source
  uses the primary-PDF fallback and drops the source page/coordinates rather than applying them to another file.
- **Attribution:** attachment provenance comes from the exact matched chunk chosen by deterministic retrieval,
  never from draft text, model output, or a client-supplied identifier.
- **Resource bounds:** citation suggestions remain capped at 20. The existing per-suggestion chunk metadata lookup
  now outer-joins one attachment row; no unbounded query or content read is introduced.
- **Information exposure:** the new API value is the same attachment primary-key integer already used by the Files
  list and PDF route. Filename display uses the same-origin response header; no checksum, directory, secret, or
  content is newly exposed.
- **Data egress / secrets:** all work is local and deterministic. No LLM, telemetry, provider call, secret access,
  or new external host is introduced.
- **Persistence / supply chain:** no write path, migration, subprocess, package, or downloaded asset is added.

## Negative-path evidence

- Backend coverage asserts the matched PDF id is retained and a non-PDF attachment id is omitted.
- Existing PDF-route tests cover non-PDF, unavailable, wrong-paper, and unknown attachment rejection.
- Frontend coverage asserts non-PDF fallback nulls its page target.
- Chromium coverage asserts the actual request carries the matched secondary id, the served filename is visible,
  region evidence draws no exact highlight, phone/toolbar overflow is zero, and console/page errors remain zero.

## Result

**Security Audit: PASS.** No unresolved finding or accepted risk.

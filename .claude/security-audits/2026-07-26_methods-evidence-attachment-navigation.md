# Security audit — attachment-aware Methods evidence navigation

**Date:** 2026-07-26
**Increment:** 388
**Status:** PASS

## Surface

- Existing statcheck, Bayesian, mixed-model, meta-analysis, and transparency responses add an optional integer
  `attachment_id` for evidence originating in a PDF.
- Existing frontend evidence clicks pass that id to the existing paper PDF route.
- No endpoint, persistence, parser, network path, or executable surface is added.

## Threat review

- **Authorization and paper scope:** the client supplies only an integer id. `GET /papers/{paper_id}/pdf` already
  requires the attachment row to belong to that paper; a different-paper or stale id fails closed.
- **Path handling:** no filesystem path is accepted from or returned to the client. The serving route resolves
  the local path from its database-owned attachment record and applies its existing availability checks.
- **Type confusion:** the common helper returns only records whose stored content or attachment type identifies
  a PDF. HTML and other supplementary-text ids are omitted instead of being sent to the PDF route.
- **Attribution:** attachment provenance comes from the matched chunk or statcheck result, not from user text.
  Exact quote location and region fallback retain the same source attachment, preventing coordinates from being
  applied to a different rendering.
- **Query bounds:** each endpoint performs one `IN` query over the already-bounded chunk/result attachment ids;
  there is no per-evidence query amplification.
- **Information exposure:** the only new response value is an attachment primary-key integer already used by
  the paper's Files list and PDF route. No local path, filename, checksum, content, or credential is exposed.
- **Data egress / secrets:** all work is local and deterministic. There is no LLM, telemetry, provider call,
  secret access, or new network destination.
- **Persistence / supply chain:** no write path, migration, dependency, subprocess, or downloaded asset is
  introduced.

## Negative-path evidence

- A multi-PDF API fixture places all relevant Methods evidence in a secondary PDF and asserts each evidence
  response retains that exact id.
- A non-PDF HTML evidence fixture asserts its attachment id remains absent.
- Existing PDF-route tests cover non-PDF, unavailable, wrong-paper, and unknown attachment rejection.
- Chromium smoke clicks a statcheck evidence row and asserts the actual request contains the secondary PDF id
  with a zero console/page-error budget.

## Result

**Security Audit: PASS.** No unresolved finding or accepted risk.

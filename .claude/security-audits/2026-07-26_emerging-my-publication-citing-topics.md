# Security audit — emerging My Publications citing topics

**Date:** 2026-07-26
**Increment:** 390
**Status:** PASS

## Surface

- New cache-only reads and explicit-refresh jobs for domain-scoped My Publications citing-topic snapshots.
- A bounded OpenAlex works query over server-resolved confirmed-publication identifiers and fixed date windows.
- A new local JSON snapshot table and dashboard evidence panel.
- No new external host, credential, LLM, file, parser, upload, subprocess, or executable surface.

## Threat review

- **Caller scope / object access:** callers submit at most eight membership-derived domain keys, never paper ids,
  labels, dates, topic ids, or URLs. The existing scope resolver validates keys against the current server-side
  decomposition before cache access or job creation. The all-publications scope is server-derived.
- **Identifier and date validation:** only `W\d+` source ids resolved from confirmed DOI-backed publications enter
  the adapter. The adapter rejects more than 50 source works and accepts only equal three-year windows between
  1900 and 2100. Users cannot author the OpenAlex filter or select clause.
- **SSRF / injection:** requests use the existing fixed OpenAlex works host/fetcher. The query contains only
  validated OpenAlex ids and computed ISO dates. SQLAlchemy bound expressions handle snapshot keys; React escapes
  all OpenAlex metadata and server-owned domain labels.
- **Egress / privacy:** ordinary GETs and scope switches are local-only. Explicit refresh sends public DOI/OpenAlex
  work identifiers plus fixed date filters to OpenAlex. It never sends domain labels, profile names, local paper
  ids, PDFs, abstracts, manuscript text, notes, credentials, or an LLM prompt.
- **Resource exhaustion:** at most 50 DOI-backed confirmed publications feed two three-year windows. Each window
  reads at most two 100-result cursor pages; at most six surfaced topics are stored, and each citing work has one
  primary topic. Strings/authors/source lists are bounded. Per-scope snapshots are capped at 16 and oldest-first
  pruned.
- **Coverage manipulation / misleading partials:** the two equal windows use the same result cap. Coverage exposes
  unresolved DOI-backed publications, missing primary topics, publication cap, and each window cap. A provider
  error or wholly unresolved DOI-backed scope raises, fails the job, and preserves the prior snapshot rather than
  overwriting it with a false empty result.
- **Cache integrity:** normalized provider results are keyed by a hash of sorted source work ids plus exact window
  years. Cached work/topic ids are revalidated through Pydantic/regex models on read. Malformed rows fail plain;
  deleted or no-longer-confirmed source publications are removed and visible counts/increase are recomputed.
- **Atomicity / races:** computation occurs outside a write transaction. A successful short write replaces only
  the selected scope; failure leaves its prior row intact. Concurrent same-scope refreshes are last-completed-wins
  over equivalent server-resolved inputs, while other scopes stay isolated.
- **Secrets / supply chain / files:** no secret is read, stored, returned, or logged. No dependency, filesystem
  path, archive, upload, subprocess, or arbitrary write is added.

## Negative-path evidence

- Malformed, unknown, and stale-looking domain keys return 422 before cache/job work.
- Invalid/oversized source ids and invalid windows make no provider request.
- HTTP/provider failure is distinct from a genuine empty 200 response and preserves the prior atomic snapshot.
- A DOI-backed scope where no own work resolves also fails rather than certifying an empty landscape.
- Invalid work/topic ids, malformed JSON payloads, deleted/unconfirmed sources, and stale evidence fail plain.
- Seventeen synthetic snapshot scopes retain only the newest 16.
- Fresh upgrade, model-drift, startup migration, and full upgrade→base downgrade paths pass.
- Chromium exercises the domain-keyed topic read, evidence expansion, local source link, mobile layout, and a
  zero console/page-error budget.

## Result

**Security Audit: PASS.** No unresolved finding or accepted risk.

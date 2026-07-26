# Security audit — domain-scoped My Publications citation gaps

**Date:** 2026-07-26
**Increment:** 389
**Status:** PASS

## Surface

- Existing local Citation gaps reads accept zero to eight research-domain keys.
- Existing explicit refresh accepts the same bounded key list and restricts the established OpenAlex graph walk.
- The single all-publications cache row becomes a bounded set of independently keyed JSON snapshots.
- No new provider, host, LLM, file, parser, or executable surface is introduced.

## Threat review

- **Caller scope / object access:** the client cannot submit paper ids or labels. Keys must match
  `domain:[0-9a-f]{20}`, are deduplicated, capped at eight, and must resolve to the current server-side profile
  decomposition. Unknown/stale keys return 422 before cache reads or job creation.
- **Identity stability:** keys hash sorted local membership ids, not mutable labels. Rename preserves scope;
  changed membership yields a new key. The hash is local routing identity, not authorization or a secrecy claim.
- **Egress / privacy:** only an explicit refresh sends the selected confirmed publications' public DOI/OpenAlex
  identifiers through the existing fixed-host adapter. Domain labels, profile identity, local paper ids,
  abstracts, PDFs, manuscript text, notes, credentials, and LLM prompts do not leave the machine. GET and scope
  switching are local-only.
- **SSRF / injection:** no URL or provider input is added. Existing `W\d+` validation and fixed OpenAlex adapter
  remain in force. SQLAlchemy bound expressions handle scope keys; React escapes labels and external metadata.
- **Resource exhaustion:** selecting domains can only narrow the existing 75-publication scan. Eight selected
  domains is the decomposition maximum; the established anchor/citing/candidate/string/evidence caps remain.
  Persistent scope combinations are capped at 16 and oldest-first pruned.
- **Atomicity / races:** refresh jobs receive an immutable, already-resolved scope. A successful short write
  replaces only that keyed row; failure preserves its prior snapshot. Concurrent same-scope refreshes are
  last-completed-wins over equivalent user-selected scope, while other scopes are isolated.
- **Migration / malformed cache:** migration 0053 preserves the legacy all-publications row, decodes SQLite JSON
  text before JSON insertion, and falls back to empty rebuildable cache values if legacy JSON is malformed.
  Response validation and read-time imported/dismissed/deleted-source filtering remain unchanged.
- **Secrets / supply chain / files:** no secret access/logging, dependency, filesystem path, upload, extraction,
  subprocess, or arbitrary write is added.

## Negative-path evidence

- Independent Domain A and Domain B fixtures prove each graph walk calls only the selected publications and
  retains only their source evidence; a two-domain request produces the canonical union scope.
- Malformed, unknown, and stale-looking keys return 422 before refresh/cache access.
- Seventeen synthetic scopes retain only the newest 16.
- Migration tests recreate the Increment-386 schema, preserve its all-publications candidate/coverage/timestamp,
  and pass zero model/migration drift.
- Existing failed-refresh, malformed-cache, source-deletion, import, dismissal, direct-citation, own-work,
  existing-library, and unconfirmed-member negative paths remain green.
- Chromium verifies the actual encoded domain-key request, selected state, scoped candidate/evidence, mobile
  wrapping, and zero console/page errors.

## Result

**Security Audit: PASS.** No unresolved finding or accepted risk.

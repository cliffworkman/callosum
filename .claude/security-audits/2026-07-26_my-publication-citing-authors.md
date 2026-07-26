# Security audit — My Publications authors citing your work

**Date:** 2026-07-26
**Increment:** 391
**Status:** PASS

## Surface

- Cache-only reads and explicit-refresh jobs for domain-scoped author-evidence snapshots.
- Bounded OpenAlex citing-work and own-work authorship queries over server-resolved confirmed-publication ids.
- A local JSON snapshot table and dashboard evidence panel with fixed OpenAlex and local-paper links.
- No new external host, credential, LLM, file, parser, upload, subprocess, or executable surface.

## Threat review

- **Caller scope / object access:** callers submit at most eight membership-derived domain keys, never paper ids,
  author ids, work ids, names, dates, filters, URLs, or SQL. The shared scope resolver validates keys against the
  current server-side decomposition before cache access or job creation. All-publications scope is server-derived.
- **Identifier/filter validation:** only `W\d+` ids resolved from confirmed DOI-backed publications enter the
  adapter. The user profile contributes one server-stored `A\d+` identity. At most 50 own-work ids enter fixed
  `cites:` and `openalex:` filters; callers cannot author filters, dates, paging, sorting, or selected fields.
- **SSRF / injection / links:** requests use the existing fixed OpenAlex works fetcher. Query values are validated
  ids and computed complete-year dates. SQLAlchemy bound expressions handle scope keys. React escapes all provider
  strings, and external hrefs are reconstructed from validated `A\d+`/`W\d+` ids under `https://openalex.org/`.
- **Egress / privacy:** ordinary GETs, scope switches, expansion, and local-paper selection are local-only. Explicit
  refresh sends public DOI/OpenAlex work ids plus fixed dates to OpenAlex. It sends no profile name, domain label,
  local paper id, PDF, abstract, manuscript, note, credential, or LLM prompt.
- **Resource exhaustion:** at most 50 confirmed DOI-backed publications feed two three-year windows of at most two
  100-result pages each. At most 25 stable author records per work and 12 surfaced authors are retained. Per-scope
  snapshots are capped at 16 and oldest-first pruned. Strings, ids, evidence lists, and integer fields are bounded.
- **Identity / no-accusation boundary:** candidates require one stable OpenAlex author id on at least two retrieved
  citing works covering at least two distinct own publications. The profile id and ids found on checked own-work
  authorships are excluded. The UI never infers fit, compatibility, availability, endorsement, or misconduct;
  "no coauthorship found" is explicitly limited to returned checked authorships and never asserted as historical
  proof. Missing work/authorship/author-id data and per-work/window/source caps remain visible.
- **Cache integrity / stale evidence:** normalized provider windows moved to a `v2` key before author ids were
  trusted. Cached ids are revalidated on read. Pydantic and regex validation discard malformed snapshot rows.
  Deleted or no-longer-confirmed source publications are removed at read time; both eligibility counts are
  recomputed, and the current profile author id is excluded again.
- **Atomicity / failure:** provider computation occurs outside a write transaction. One short successful write
  replaces only the selected scope. Provider failure or a wholly unresolved DOI-backed scope fails the job and
  preserves the previous snapshot; a genuine empty 200 result remains distinct and replaceable.
- **Secrets / supply chain / files:** no secret is read, stored, returned, or logged. No dependency, new host,
  filesystem path, archive, upload, parser, subprocess, executable, or arbitrary write is added.

## Negative-path evidence

- Invalid/unknown/stale-looking domain keys return 422 before cache or provider work.
- Invalid/oversized source ids and invalid profile author ids make no provider request.
- HTTP failure is distinct from an empty result; failed refreshes preserve the prior atomic scope snapshot.
- A DOI-backed scope where no own work resolves fails rather than certifying an empty landscape.
- Self and checked coauthor ids are excluded even when they meet both visible citation thresholds.
- Deleted source publications and a changed profile author id remove stale candidates at read time.
- Invalid author/work ids, malformed JSON, and malformed coverage fail plain.
- Seventeen synthetic snapshot scopes retain only the newest 16.
- Fresh upgrade, model-drift, startup migration, and full application tests pass.
- A headed disposable fixture confirms fixed OpenAlex links, numeric local-paper routing, and zero desktop/mobile
  horizontal overflow. The walkthrough exposed and fixed an older `[object Object]` local-source routing bug across
  all three prospection panels.

## Result

**Security Audit: PASS.** No unresolved finding or accepted risk.

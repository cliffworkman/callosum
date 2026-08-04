# Security audit — WIP Meta-Reference (reference-integrity + citation-concentration)

**Increment:** 447
**Date:** 2026-08-04
**Status:** COMPLETE — PASS

## Scope and trust boundary

This increment adds two new local-only WIP job families:

- `POST /wip/manuscripts/{manuscript_id}/reference-integrity/run`, `GET /wip/reference-integrity/run/{job_id}`,
  `GET /wip/manuscripts/{manuscript_id}/reference-integrity`, `POST /wip/reference-integrity/{reference_id}/review`
- `POST /wip/manuscripts/{manuscript_id}/citation-equity/run`, `GET /wip/citation-equity/run/{job_id}`

Both routers (`app/backend/api/routers/wip_reference_integrity.py`, `app/backend/api/routers/
wip_citation_equity.py`) carry `dependencies=[Depends(require_local_wip)]`, the same gate every other WIP route
uses — inherits read-only write blocking and the existing local-only trust posture. No new auth/session logic.

## Input validation and SQL

- `manuscript_id`/`reference_id`/`job_id` path params are FastAPI-typed (`int`/`str`); a non-existent manuscript
  or reference 404s before any detector work runs (`_require_manuscript`, the `wip_references` existence check
  in the review endpoint).
- Every query is SQLAlchemy Core with bound parameters — no string-built SQL anywhere in the two new router
  files, the new repo (`wip_reference_integrity_repo.py`), or the new schema module
  (`schema_wip_reference_integrity.py`). Table/column names are all Python identifiers, never request data.
- `WipReferenceReviewRequest.state` is a `Literal["dismissed", "confirmed_problem"]` — Pydantic rejects any
  other value before it reaches `set_reference_review_state` (which independently re-validates against
  `WIP_REFERENCE_REVIEW_STATES` as defense in depth, matching the Library-paper reviewer's own belt-and-braces
  pattern).

## Egress

- Both tools reuse the app's existing `crossref_client`/`openalex_client`/`retraction_checkers` — the identical
  egress posture the Library-paper reference-integrity and citation-equity tools already have (public
  bibliographic metadata lookups by DOI/title, cached). No new client, no new external host, no new dependency.
- What leaves the machine: a cited Library paper's own title/DOI/authors/year (already stored locally, already
  public bibliographic facts) — sent to Crossref/OpenAlex to verify identity and retraction status, and to
  OpenAlex to fetch reference-list structural metadata. **The manuscript's own text, its file path, its
  section content, and any unpublished prose never leave the machine** — the reference list itself is read
  from `wip_references` (a purely local link table the user built by hand via the References tab), never from
  the manuscript's file content.
- The Retraction Watch check reuses the existing local mirror (`retraction_db_status`, `app.state.
  retraction_checkers`) exactly as the Library path does — no new network call.

## Persistence and cross-space read

- Reference-integrity persists into two new, purely additive tables (`wip_reference_signals`,
  `wip_reference_reviews`), both scoped to `wip_manuscripts.id`/`wip_references.id` — never written from a
  Library-paper request path, and the reverse Library `reference_entities`/`reference_instances`/
  `reference_signals` tables are never written to from a WIP request path (`_propagation_signal_for` is a
  read-only `SELECT` against `reference_entities`, confirmed by reading the function — no `insert`/`update`/
  `delete` call touches a Library table anywhere in the new code).
- Citation-concentration remains fully ephemeral (no table, no migration) — identical posture to the existing
  Library-paper version.
- Cross-space propagation evidence exposes only what the Library-paper `flagged_sources_for_entity` already
  exposes to any authenticated local caller today (a citing paper's id/title and detector kinds for an active,
  non-dismissed signal) — no new information disclosure; a WIP manuscript sees the same shape of evidence a
  Library paper already would for the same shared reference.

## Negative paths (verified in `tests/test_wip_reference_integrity.py` / `test_wip_citation_equity.py`)

- Unknown manuscript id → 404 on both the run-start and the report-read endpoints, and on citation-equity's
  run-start.
- Unknown reference id on the review endpoint → 404 (`test_review_rejects_unknown_reference`).
- Zero "cited" `wip_references` rows → an honest empty report (`checked_count`/`references_total` = 0), never
  a 422 or a fabricated result (`test_run_with_zero_cited_references_is_an_honest_empty_report`, both files).
- A non-"cited" relationship state (`background-reading`, `to-cite`, etc.) is excluded from both the check run
  and the persisted/ephemeral report — verified directly
  (`test_run_flags_retracted_cited_reference_and_ignores_non_cited`).
- A per-reference detector exception is caught, recorded as a `provider_statuses` coverage entry, and does not
  abort the rest of the run (mirrors the Library-paper router's existing per-candidate exception handling).

## Status

Both new job stores (`wip_reference_integrity_jobs`, `wip_citation_equity_jobs`) are registered in
`JOB_LABELS`/`JOB_NAV_DEFAULTS`/`JOB_COMPUTE_KINDS` (`status.py`) — `Job.nav` receives only `{manuscript_id}`,
merged against a server-owned `{"workspace": "work", "tab": "meta-reference"}` destination by the existing
`_bounded_nav` allowlist. No result body, path, prompt, or secret enters `Job.nav`.

## Result

**Security Audit: PASS.** No new attack surface beyond the existing, already-audited Library-paper reference-
integrity/citation-equity egress posture; the only new capability is reading a purely local link table
(`wip_references`) as the detector input instead of a Semantic-Scholar/OpenAlex-discovered list, and writing to
two new tables scoped to WIP identifiers that a Library-paper request path cannot reach.

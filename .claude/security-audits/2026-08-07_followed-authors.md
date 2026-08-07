# Security audit: followed authors (gap-finder source, backlog #29)

Date: 2026-08-07

## Scope

A new lightweight OpenAlex-author subscription feeding gap-finder as a sibling module (inc 454). Triggers the
audit gate via CLAUDE.md's #1 (new API endpoints + a request-schema change) and #5 (net-new feature spanning
5+ files, well over 300 LOC). #2 (a new external fetch/integration) does **not** apply — this reuses the
already-audited `OpenAlexAuthorClient` (`2026-06-24_mypubs-citing.md`, `2026-07-26_my-publication-citing-
authors.md`); no new HTTP client, no new external host.

New surfaces:

- `alembic/versions/0069_followed_authors.py` — new tables `followed_authors`, `followed_author_candidates`
  (`persistence/schema_findings.py`, re-exported from `schema.py`).
- `app/backend/clustering/followed_authors.py` — pure compute (`compute_followed_author_candidates`), no I/O
  beyond the injected `author_client` and a read of `find_existing_paper_by_identity`.
- `app/backend/persistence/followed_author_repo.py` — repo layer (parameterized SQLAlchemy Core only).
- `app/backend/api/routers/followed_authors.py` — `GET/POST/DELETE /followed-authors`,
  `GET /followed-authors/candidates`, `POST /followed-authors/refresh` + `GET .../refresh/{job_id}`,
  `POST /followed-authors/add`, `POST /followed-authors/dismiss`.
- `app/frontend/js/30f_followed_authors.jsx` (new Discover tab) + a small quick-follow addition to
  `31d_mypubs_citing_authors.jsx`.

## Data egress

Two paths reach OpenAlex, both through the already-audited `OpenAlexAuthorClient`:

1. **Name/ORCID-follow** (`POST /followed-authors {name|orcid}`) — one bounded `resolve_author()` call. This
   sends only the name/ORCID the user typed, exactly the same shape `my_publications.py`'s own profile-linking
   flow already sends (same client, same audited call). Treated as inline-safe (not a background job), matching
   this codebase's existing precedent that `/gaps/add`'s single bounded Crossref lookup is inline.
2. **Refresh** (`POST /followed-authors/refresh`) — `fetch_author_works()` per targeted author, run as a
   background job (`followed_author_jobs` `JobStore`) so it never blocks the request thread; capped by the
   client's own existing ~1000-work/5-page fetch cap (unchanged, already audited).

Every other endpoint (`GET /followed-authors`, `GET .../candidates`, the direct-`author_id` follow path,
`DELETE`, `/add`, `/dismiss`) touches only the local SQLite DB — confirmed by `test_ordinary_reads_never_egress_
only_refresh_does` and `test_direct_follow_from_citing_authors_panel_makes_zero_resolve_calls` in
`tests/test_followed_authors.py`, both asserting against the fake client's `.calls` list rather than merely
reading the code. This is **not** the Gemini/LLM egress gate (invariant #3) — public OpenAlex journal/author
metadata, the same posture gap-finder's own OpenAlex calls already have.

## Input validation

- `author_id` is validated with `_AUTHOR_ID_RE = re.compile(r"^A\d+$")` at **every** entry point that accepts a
  bare OpenAlex id: the direct-follow path in `POST /followed-authors` and `DELETE /followed-authors/{author_id}`
  — both return 422 on a malformed id before touching the DB. Pinned by
  `test_malformed_author_id_and_oversized_name_are_rejected`.
- `display_name`/`name` are capped at `MAX_FOLLOW_NAME_LEN = 300` chars (`Field(max_length=...)` on
  `name`/`orcid`; an explicit length check + 422 on `display_name` in the direct-follow branch, since it's a
  plain `str | None` not itself field-capped). An oversized name is rejected, not silently truncated.
- The direct-follow path additionally requires a non-empty `display_name` — you cannot register a followed
  author with no human-readable label.
- `POST /followed-authors/dismiss` and `/add` reuse gap-finder's own existing validated shapes
  (`import_citing_work` already requires a DOI; a missing DOI raises 422, pinned by the existing gap-finder
  tests plus this feature's own `test_unfollow_is_idempotent_and_add_imports_a_candidate`).
- No endpoint accepts a file path, URL, or raw SQL fragment; every DB access goes through SQLAlchemy Core bound
  parameters (`followed_author_repo.py`) — no string-built SQL anywhere in the new code (rule #3).

## Resource caps

- `FOLLOWED_AUTHOR_MAX_CANDIDATES = 50` caps the persisted candidate rows per author per refresh (pinned by
  `test_compute_candidates_respects_max_candidates_default`, which also asserts the constant itself so a future
  change is deliberate, not accidental).
- The underlying `fetch_author_works()` fetch cap (~1000 works / 5 pages) is unchanged, existing, already-audited
  behavior in `OpenAlexAuthorClient` — this feature adds no new unbounded fetch.
- `replace_followed_author_candidates` is a delete-then-reinsert per author (not an unbounded append), so a
  repeatedly refreshed author's cache can never grow without bound.

## Cascade / orphan-row safety

`remove_followed_author` deletes the `followed_authors` row and cascades a delete of that author's
`followed_author_candidates` rows in the same call. `read_followed_author_candidates` additionally applies a
defensive `author_id IN (SELECT author_id FROM followed_authors)` filter at read time, so even a hypothetical
partial-failure cascade (e.g. a future refactor that reorders the two deletes) could never resurface a stale
candidate for an author the user no longer follows — pinned by
`test_repo_read_defensively_filters_stale_candidates_after_a_failed_cascade`, which simulates exactly that
partial-failure shape directly against the repo layer.

## Shared-state boundary (dismissal list)

`/followed-authors/dismiss` deliberately reuses gap-finder's own `profile.dismissed_gap_works` list
(`dismiss_gap`/`dismissed_gaps` in `profile_repo.py`) rather than introducing a second dismissal domain. This is
a considered design choice, not an oversight: a dismissal is about the *work* (identified by DOI/OpenAlex id),
not which generator re-derived it as a candidate, and gap-finder's own dismiss already treats it as
work-identity-scoped. Verified this doesn't let one source silently suppress genuinely different content from
another — the dismissal key is always the specific DOI/OpenAlex-work-id the user chose to hide, never an
author-level or source-level key, so dismissing one followed author's work has no effect on any other work.
Pinned by `test_dismiss_is_shared_with_gaps_dismissal_list`.

## Principles / A-A alignment (rule #9)

Directly resembles PRINCIPLES.md's gap-finder precedent (the same "candidates, not verdicts" framing already
established for backward/forward gap-finding): every surfaced work carries an **Add**/**Dismiss** pair, nothing
is auto-imported, and the persistent UI note explicitly discloses the v1 limitation — candidates are **not**
filtered or ranked by relevance to the user's research axes, only deduplicated against the library
(`FOLLOWED_AUTHOR_NOTE` in `followed_authors.py`, rendered verbatim in `30f_followed_authors.jsx`). The
misaligned/easier path here would have been to silently omit that disclosure (axis-relevance ranking simply
"not existing yet" without saying so) — declined per commitment #6 (silence is not a certificate): the note
says plainly that this machinery doesn't exist for this source, rather than letting the UI imply a filtered,
curated list. No opaque composite score anywhere (commitment #7) — `cited_by_count` is the work's own plain
OpenAlex citation count, shown as-is, never blended into a rank.

## Checks

- `pytest tests/test_followed_authors.py -q` — 13 passed (compute, repo idempotency/cascade/defensive-read,
  full endpoint lifecycle, zero-egress reads, direct-follow zero-resolve-calls, no-match 200, shared dismissal,
  malformed-input 422s).
- `pytest tests/test_gapfinder.py -q` — 13 passed, confirming the shared dismissal reuse introduced no
  regression in gap-finder's own behavior.
- `pytest tests/test_migrations.py -q` — 8 passed.
- `python tools/check_line_budget.py` — clean (495 files, all under cap).
- `python tools/build_frontend.py` + `pytest tests/test_frontend_assembly.py -q` — clean, 64 passed.
- `python tools/qa/build_surface_map.py check` — 382/382 API surfaces, 1625/1625 FE surfaces covered (new
  `route_87_followed_authors.md` declares all 7 new endpoints + both frontend files).
- Negative-path checks actually run (not just described): malformed `author_id` on follow and unfollow →
  422; oversized `display_name` → 422; missing `display_name` on direct-follow → 422; no-match resolution →
  clean `200 {status:"no-match"}`, never a crash; unfollow-then-unfollow-again → idempotent 204, not 404.

Result: **PASS.**

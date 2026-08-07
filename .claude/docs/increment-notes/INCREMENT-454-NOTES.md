# Increment 454 — Followed authors as a gap-finder source (backlog #29)

## Implemented

Backlog #29 ("gap-finder's followed-authors source") had been blocked for a long time on a "followed authors"
concept that didn't exist anywhere in the app. The original design doc
(`.claude/docs/future-tracks/opus4.8_future-tracks_gapfinder.md`) already specs it: follow an OpenAlex author,
fetch their works (cached/TTL), surface works absent from the library with the provenance "by [followed author]."
It's gap-finder's own second candidate-generator, after backward/forward citation-graph gap-finding (incs
135/137).

New tables `followed_authors` (the subscription list) and `followed_author_candidates` (the derived, per-author
candidate cache) — `alembic/versions/0069_followed_authors.py`, `persistence/schema_findings.py`. New compute
module `app/backend/clustering/followed_authors.py::compute_followed_author_candidates` (flat, deduped-against-
library, newest-first, capped at 50/author). New repo `app/backend/persistence/followed_author_repo.py`
(idempotent follow, cascading unfollow, a defensive read-time filter). New router
`app/backend/api/routers/followed_authors.py` mirroring `gaps.py`'s async-refresh-job shape: follow (by
name/ORCID via `OpenAlexAuthorClient.resolve_author`, or directly by an already-resolved `author_id` — zero
extra egress), unfollow, cache-only candidate reads, a per-author-or-all refresh job, Add (imports metadata via
the existing `import_citing_work`), and Dismiss (reuses gap-finder's own `dismiss_gap`/`dismissed_gaps`
persistence). New frontend tab `app/frontend/js/30f_followed_authors.jsx` (`FollowedAuthorsPane`) registered as
Discover's fourth sub-tab; a small quick-follow control added to `31d_mypubs_citing_authors.jsx` so an
already-resolved citing-author card can be followed with zero additional OpenAlex resolution.

## Key technical detail

**A sibling module, not a third `gap_candidates.direction`.** `GapCandidate` (`clustering/gapfinder.py`) has no
field for author provenance, and `direction` is a hardcoded two-way branch baked into the DB scope key, the
router's `Direction` Literal, and the frontend toggle across 4 files. Retrofitting followed-authors as a third
direction would have required a field the existing shape has nowhere to put, and would conflate two genuinely
different UX flows (a direction toggle vs. subscription management). Two new tables + a parallel router/pane
instead — cheap because the underlying idiom (cache table, refresh job, Add/Dismiss against the read-time-
filtered cache) is identical to gap-finder's own, just keyed by `author_id` instead of `(direction, axis_id)`.

**The disclosed v1 limitation: no axis-relevance ranking.** The design doc's aspirational language ("surface
works... relevant to axes") was never actually built even for backward/forward gap-finding — there, `axis_id` is
only an *input* scope filter (which of the user's own papers to pull citations from), never an output rank.
Followed-authors has no "which of my papers" input to scope from at all (a followed author's works come from an
external subscription, not derived from the library), so true axis-relevance filtering would need genuinely new
embedding-similarity machinery that doesn't exist for this purpose. v1 ships without it — `FOLLOWED_AUTHOR_NOTE`
states this plainly in the persistent UI note ("Not filtered or ranked by relevance to your research axes...
only deduplicated against your library") rather than silently shipping a flat list and letting the user assume
it's scoped. This is Principles commitment #6 (silence is not a certificate) applied to a *limitation*, not just
to a finding — the honest thing is to say what the feature does **not** do, not just what it does.

**The shared-dismissal-list decision.** `/followed-authors/dismiss` reuses gap-finder's own
`profile.dismissed_gap_works` (`dismiss_gap`/`dismissed_gaps` in `profile_repo.py`) rather than adding a new
column or table. A dismissal is about the *work* (its DOI/OpenAlex id), not which generator re-derived it as a
candidate — gap-finder's own dismiss already treats it as work-identity-scoped (it dismisses both the OpenAlex id
and the DOI together). One dismissal domain across both sources means a work dismissed via backward/forward
gap-finding also can't resurface via a followed author, and vice versa — proven directly by
`test_dismiss_is_shared_with_gaps_dismissal_list`.

## Housekeeping / gates

- **Security audit**: `.claude/security-audits/2026-08-07_followed-authors.md` — PASS. New endpoints + schema +
  a net-new feature over 300 LOC trigger the gate; no new external host (reuses the already-audited
  `OpenAlexAuthorClient`).
- **QA route**: new `.claude/qa-routes/route_87_followed_authors.md` (tier 2 external, mirroring route 41/gaps'
  shape) — covers follow (name/ORCID/direct-id)/unfollow, cache-only reads, refresh, Add/Dismiss provenance, the
  disclosed no-axis-ranking note, and the cross-source dismissal check. `build_surface_map.py check` confirms
  382/382 API + 1625/1625 FE surfaces covered.
- `.claude/docs/INCREMENT-BACKLOG.md`: #29 closed, moved to the shipped-breadcrumbs section.
- `.claude/CLAUDE.md`: gap-finder/literature-discovery narrative extended; counter bumped to 454.

## Manual verification script

1. Start the app against a seeded DB. Open **Discover → Followed Authors** — confirm the empty state + the
   persistent disclosure note.
2. Follow a real, moderately prolific author by name. Confirm the chip appears with the correct OpenAlex id in
   its tooltip.
3. **Refresh all** — confirm the progress indicator, the coverage summary line, and candidate rows each reading
   "by \<author\> (followed)" with title/year/Add/Dismiss.
4. **Add** one candidate → confirm it drops from the list and appears in the library (metadata-only, no PDF).
   **Dismiss** another → confirm it drops and stays dropped across a reload.
5. Go to **My Publications → Authors citing your work**, click **Follow** on a resolved author card → confirm it
   flips to "✓ Following" and the author now also appears in Followed Authors without a second name/ORCID
   resolution (the direct-id path).
6. **Unfollow** an author → confirm their candidates vanish immediately. Zero console errors throughout; zero
   requests to a `generativelanguage`/genai host.

## Verification

- `pytest tests/test_followed_authors.py tests/test_gapfinder.py -q` → **26 passed** (13 new + 13 pre-existing,
  confirming the shared dismissal reuse introduced no gap-finder regression).
- `pytest tests/test_migrations.py -q` → **8 passed**.
- `pytest tests/test_frontend_assembly.py -q` → **64 passed**.
- `python tools/check_line_budget.py`: clean (495 files, all under cap; new files well under: router 285 lines,
  compute module 80, repo 101, frontend pane 120).
- `python tools/qa/build_surface_map.py check`: 382/382 API, 1625/1625 FE surfaces covered.
- `ruff format` + `ruff check`: clean. `python tools/build_frontend.py`: clean.
- `alembic upgrade head` + migration tests: clean, zero drift on the two new tables.

## Rollback

Drop `followed_authors`/`followed_author_candidates` via a new down-migration if ever needed (the project's own
convention is no down-migrations by design — a `DROP TABLE` pair would need to be hand-written). Remove
`app/backend/clustering/followed_authors.py`, `app/backend/persistence/followed_author_repo.py`,
`app/backend/api/routers/followed_authors.py`, `app/frontend/js/30f_followed_authors.jsx`; revert the 3-line
`app.py` wiring, the `04b_workspaces.jsx` tab registration, and the quick-follow addition in
`31d_mypubs_citing_authors.jsx`. No other source's behavior is touched by any of this — the shared dismissal list
is read, never restructured.

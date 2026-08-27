# Increment 504 — Discover → Feed consolidation, Suggest modal, and toolbar cleanup

## Implemented

- **Consolidated the standalone Followed Authors tab into Feed.** Deleted `30f_followed_authors.jsx` and its
  `registerWorkspaceTab` registration (`04b_workspaces.jsx`). Feed's add-source dropdown gains a 5th,
  frontend-only **Author** option (`30e_feed.jsx`) that auto-detects a plain name vs. an ORCID iD (bare or a
  pasted `https://orcid.org/...` URL, `FEED_ORCID_RE`) and posts to the unchanged `POST /followed-authors`
  resolve endpoint — the backend's `followed_author` kind stays `user_addable=false`, so a raw OpenAlex id still
  can't be typed into the generic `/feed/subscriptions` endpoint. Unfollow needed no change (the existing
  bidirectional `feed_subscriptions` ↔ `followed_authors` sync already covered it).
- **Removed the now-dead gap-candidate machinery** the standalone tab's curated "what am I missing" view used —
  the user confirmed Feed's own un-deduped stream (badged "Followed," `in_library` known per item) is
  sufficient without it: `GET /followed-authors/candidates`, `POST /followed-authors/add`,
  `POST /followed-authors/dismiss`, `POST /followed-authors/refresh` (+ job poll), `compute_followed_author_
  candidates`/`FollowedAuthorCandidate`/`FOLLOWED_AUTHOR_MAX_CANDIDATES`/`FOLLOWED_AUTHOR_NOTE`
  (`clustering/followed_authors.py`), `replace_followed_author_candidates`/`read_followed_author_candidates`
  (`followed_author_repo.py`), the `followed_author_candidates` table (`schema_findings.py`), the
  `followed_author_jobs` JobStore + its three `status.py` nav/label/compute-kind entries, and the QA route
  `route_87_followed_authors.md`. A new migration `0077_drop_followed_author_candidates.py` physically drops
  the now-orphaned table — required because this project has a live `alembic check` drift test
  (`test_alembic_check_reports_no_model_drift`) that fails if the DB schema and the live ORM metadata disagree;
  simply deleting the Python `Table()` object (my first assumption) isn't sufficient here, since migration
  0069's own historical `op.create_table` DDL still runs on any DB reaching head. Also fixed the demo-snapshot
  pipeline that would otherwise break on this removal: `demo_extended_state.py`'s `DemoDiscoverState` dropped
  the `followed_author_candidates` field (schema version bumped 1→2), `tools/demo/capture_demo_extended_
  state.py` stopped calling the deleted endpoint, `demo/demo-runtime.js` dropped its fake-route handler, and
  the two checked-in static snapshots (`demo/extended-state-v1.json`, `demo/snapshot-v1.json`'s embedded copy)
  were hand-edited (not regenerated) to drop the field and bump the version — a minimal, targeted data fix
  rather than a full live-server recapture.
- **New `GET /feed/suggest-authors` endpoint** (`routers/feed.py` → `clustering/followed_authors.py`'s new
  `suggest_authors_to_follow`): a plain per-author paper-count tally across the live library, excluding the
  user's own name (a local last-name-token check, the `_family_tokens` convention already used in
  `my_publications.py`/`citation_equity.py`) and anyone already followed. A 5th local copy of the
  already-4x-duplicated CSL-JSON author-extraction pattern (not a shared refactor — out of scope).
- **Suggest redesigned into a 5-tab modal** (`30e_feed.jsx` + new `30g_feed_suggest.jsx`): Journal (unchanged
  library-frequency list), bioRxiv/medRxiv Categories (every fixed category shown, matched ones first with the
  matching axis/tag named as the reason — entirely frontend-composed, no new endpoint, since the fixed lists
  already ride `sourceMeta`), PubMed Search (suggestions from Discover→Search's `_discoverLoadSearchHistory()`
  + axes + tags, each labeled by source), and Author (the new endpoint). Suggest is now available regardless of
  the dropdown's current kind, always opening on Journal.
- **Followed-sources pill row capped to one visible line** with a real measured-overflow check
  (`ResizeObserver` comparing `scrollHeight`/`clientHeight`, not a guessed pill count) — a "…" button appears
  only when pills actually clip, opening `FeedSubsOverflowModal` (the same pills, unconstrained, with the
  existing × unfollow control).
- **Toolbar cleanup:** merged the two filter groups (All/Unread/Starred + a separate All/Highlighted) into one
  exclusive 4-way `.tags-srcfilter` toggle — All, Unread, Highlighted, Starred — removing the duplicate "All"
  button; scoped a width fix (`flex:0 0 auto; white-space:nowrap; padding:4px 12px`) to just this row so
  "Highlighted"/"Unread (N)" stop wrapping mid-word. Renamed "Auto-refresh on open" → "Auto-Refresh" and
  "Mark all read" → "Mark All Read" (Title Case).
- **Control-height + Title-Case DESIGN.md rules.** New `--control-h: 32px` token applied, scoped to the shared
  `.searchbar` container (Library header, WIP filters, Discover Search, Feed — the 4 remaining places that
  pattern appears): `.searchbar input`/`.searchbar .btn`/`.searchbar .lib-sort` (the select's radius also
  promoted from `--radius-sm` to `--radius`) now share one height, fixing a real 4-way mismatch (8px/6px/5px/3px
  vertical padding). Two new DESIGN.md §4 rules (Title Case; `--control-h`) plus two backlog items (#59, #60)
  for the full app-wide retrospective passes this increment deliberately didn't attempt.
- **Found and backlogged (not fixed) a separate, real bug** while live-verifying Author-follow:
  `OpenAlexAuthorClient._fetch()` (`integrations/openalex/author.py`) caches ANY response — including a transient
  fetch exception (`status_code=NULL`) — as permanently authoritative, so one Brotli-decode hiccup on a real
  OpenAlex response can make that author's name/ORCID unresolvable forever without a manual cache-row delete.
  Filed as backlog #61 (also flags a suspicious literal-backslash URL in `_fetch_by_orcid` for follow-up
  confirmation). Out of scope for this increment; deleted the one stale cache row in the local testing DB to
  complete live verification.

## Key technical detail

The alembic drift-check test is the reason a Python-only `Table()` removal wasn't enough: `metadata.create_all()`
(run once, by migration 0001, against whatever `Table` objects are importable at migration time) is what
actually created `followed_author_candidates` on every fresh test DB pre-removal — migration 0069's own guarded
`op.create_table` never ran end-to-end pre-removal, meaning `test_followed_authors_migration_upgrades_an_
existing_0068_database`'s "drop it, force the guarded path to run" simulation was only ever needed for the one
table whose Python object survives (`followed_authors`), not both. Post-removal, that same guarded 0069 DDL
now *always* recreates `followed_author_candidates` (since it's no longer in the live `create_all()` set),
which is exactly why an explicit forward-drop migration is the only way to keep a fresh-installed DB's real
schema and the live ORM metadata in agreement.

## Manual verification

Started the dev server on the real ~200-paper testing DB (`.local/validation-summarize/validation.sqlite`);
confirmed the auto-migration to `0077_drop_followed_author_candidates` ran cleanly on startup against real,
pre-existing data. Via Playwright: confirmed the Followed Authors tab is gone from Discover's sub-tab strip;
opened Suggest and exercised all 5 tabs against real library data (bioRxiv "neuroscience" correctly matched
first against 2 real axes + 5 real tags; PubMed Search surfaced a real prior search query first; Author ranked
20 real recurring co-authors by count with the seeded user's own name absent from the entire list); followed an
author by plain name (after clearing a stale error-cached OpenAlex response — see above) and confirmed the pill
appeared tagged "Followed"; opened the pill-overflow modal (10 real followed sources) and unfollowed the test
author from inside it, confirming `GET /followed-authors` no longer listed them; confirmed the merged
All/Unread (969)/Highlighted/Starred row no longer wraps and the add-source row (Journal dropdown, input,
Follow, Suggest, Refresh) and Search's own action row (Search/Clear ×/Recent searches/Clear history/Wanted/
Gaps/Overlooked/Saved for later) now render at one consistent height.

## Pytest

- Targeted (`test_feed.py`, `test_followed_authors.py`, `test_migrations.py`, `test_demo_snapshot.py`,
  `test_status.py`, `test_frontend_assembly.py`): **162 passed**.
- Full suite (`pytest -n auto -q`): **2531 passed, 3 skipped**.
- Opt-in Chromium E2E demo smoke test (`CALLOSUM_RUN_E2E=1 pytest tests/e2e/test_demo_static.py`): **1 passed**
  — this test builds and drives the real static demo bundle in a real browser; it caught a real bug (the new
  "…" overflow button shared the literal `.feed-sub` class, inflating the pill count by one) before this note
  was written, fixed by giving it its own `.feed-sub-more` class with the recipe restated rather than inherited.

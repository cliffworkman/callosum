# Increment 450 — Local usage instrumentation + "Your usage" dashboard (backlog #38A)

## Implemented

Backlog #38 ("Research-impact analytics") splits into two projects: Project A (local usage analytics,
zero-egress, buildable now) and Project B (a cross-user research signal, far-future, gated on N>1 users + an
accounts/hosting decision + a research-grade consent flow). This increment ships Project A's two near-term
stages — a local instrumentation seam and a personal dashboard — together, per the design doc
(`.claude/docs/future-tracks/opus4.8_future-tracks_researchimpactanalytics.md`).

**Five instrumented event types** — the design doc's own "tedium reduction" / "care-in-action" taxonomy — a
closed, reviewable set: `citation_export` (`papers.py::export_citations`, `citations.py::render_citations`;
count = papers exported/rendered), `duplicate_resolved` (`duplicates.py::dismiss_duplicates`/
`merge_papers_endpoint`; count = 1 per resolution decision, not the O(n²) pair count), `metadata_reresolved`
(`paper_enrich.py::reresolve_paper` always; `fill_metadata` only when fields were actually filled — a no-op
click isn't tedium-reduction), `quote_located` (frontend-fired from `37_cite.jsx`'s "Open source region," gated
on a genuine matched-source-region open, not the degraded "Open primary PDF" fallback), `flag_reviewed`
(`reference_integrity.py`/`wip_reference_integrity.py`'s review endpoints, shared event type for both Library
and WIP contexts).

New: `app/backend/persistence/schema_usage.py` (`usage_events` — `id`/`event_type`/`count`/`duration_ms`/
`created_at`, no payload column, no FK — the schema itself forecloses a content leak, not just a policy
statement), migration `0067_usage_events.py`, `app/backend/persistence/usage_repo.py` (pure repo),
`app/backend/usage.py` (`record_event()` — the single seam every call site routes through), new router
`app/backend/api/routers/usage.py` (`POST /usage/events`, `GET /usage/summary`, `GET /usage/export`,
`POST /usage/clear`), `app/frontend/js/35f_usage.jsx` (the new Settings card). `app_settings.py` gains
`usage_events_enabled` — the one flag in that file defaulting **True** (nothing here egresses, so this behaves
like any other local feature rather than the egress-consent pattern, per your explicit choice this session).

## Key technical detail

**`record_event()` deliberately takes the caller's already-open `Connection`, never its own transaction.** SQLite
runs in WAL mode with a 5s `busy_timeout` (`persistence/database.py`); WAL still allows only one writer. Four of
the six instrumented call sites already run inside an open write transaction (`run_write`'s `_do(conn)` closure,
or `with engine.begin() as conn:`). A `record_event()` that opened a *second* connection nested inside one of
those would contend for the same single-writer lock the outer transaction hasn't released yet — a real deadlock,
only resolved by the `busy_timeout` expiring into `database is locked`. This shaped the function's actual
signature before any code was written, not a fix applied after hitting the deadlock — see the module docstring's
explicit guardrail against a future "simplification" that reintroduces it. Two call sites (`export_citations`,
`render_citations`) are pure-read `Depends(get_connection)` handlers with no prior `conn.commit()` at all; each
gained one new explicit commit — ordinary plumbing, not a policy conditional.

**A real bug found by the new test suite, not by review.** `usage_repo.usage_summary()`'s first draft wrote
`dict(conn.execute(select(...).group_by(...)))` — this raises `TypeError: 'CursorResult' object is not
subscriptable` in this SQLAlchemy version; `dict()` needs the result materialized via `.all()` first
(`dict(conn.execute(...).all())`). Caught immediately by `tests/test_usage_events.py`'s first real endpoint run,
fixed before this ever reached a live server.

**Layering: the enabled-gate lives in one place, not six.** Every existing `stored_X_enabled()` gate check in
this codebase happens at the router/seam layer, never inside `persistence/`; `usage_repo.py` stays a pure repo
with no `app_settings` import, matching every other `*_repo.py`. The new top-level `app/backend/usage.py`
(sibling to `app_settings.py`) holds the actual gate + the closed `event_type` allowlist check — so a future
instrumented call site literally cannot forget to check the toggle, because the check isn't theirs to make.

**Principles/A-A gate (rule #9).** None of `PRINCIPLES.md`'s four worked examples apply directly — they're all
about claims *over the literature*; this produces a claim about the user's own usage, a genuinely novel case.
Principles #6 (silence isn't a certificate — the never-empty summary row per type, the honestly-stated
`duration_ms`-always-null limitation), #7 (no opaque scores — five separate labeled counts, never blended), and
#8 (inspectability — export/clear work unconditionally) apply directly regardless. A-A was additionally
consulted per CLAUDE.md's future-track trigger: A5 (local-first, trivially satisfied here), A4 (the local log
must be inspectable/exportable/deletable, non-negotiable per the design doc), A1 + the standalone
no-opaque-composite-score veto, and A3 — the dashboard's own copy names the Goodhart trap the design doc warns
against directly ("a count of actions, not a score — for tedious operations, doing them less is the win"),
rather than silently risking engagement-reads-as-flourishing.

## Housekeeping / gates

- **Security audit**: `.claude/security-audits/2026-08-05_local-usage-analytics.md` — PASS. The one feature in
  this project's audit checklist with genuinely zero external calls anywhere in it (confirmed by grep, not just
  asserted).
- **QA routes extended, not forked** — `route_35_settings.md` (the new card, its on-by-default exception to the
  page's usual off-by-default pattern, the no-payload assertion) and `route_42_cite.md` (the real `quote_located`
  trigger lives there, not in Settings).
- Help corpus updated (`help_content.md`); `HELP-DOCS-SYNCED` marker moved forward.
- Backlog #38 updated: Project A marked shipped, Project B's remaining gate stated explicitly so a future reader
  doesn't conflate "the buildable half is done" with "the whole future-track is done."

## Manual verification script

1. Open Settings → **Your usage**. Confirm the toggle is already **ON** and five count rows render, all at 0 on
   a fresh instance.
2. Perform a real instrumented action (e.g. Work → Cite → paste a matching sentence → "Open source region" on a
   real match, or "Copy BibTeX" from a paper card). Return to Settings and confirm the matching count increased.
3. Click **Export usage log** — confirm a JSON download containing only `event_type`/`count`/`duration_ms`/
   `created_at` per row, nothing else.
4. Click **Clear usage log** — confirm the counts reset to 0 and a deleted-count message appears.
5. Toggle **Track local usage** OFF, repeat step 2's action, confirm the count does NOT increase; confirm export/
   clear still work while off.

## Verification

- `pytest tests/test_usage_events.py tests/test_migrations.py -k usage_events -q` → **15 passed**.
- `pytest tests/test_papers.py tests/test_paper_merge.py tests/test_citations.py tests/test_metadata_multi_enrich.py
  tests/test_reference_integrity.py tests/test_wip_reference_integrity.py -q` → **204 passed** (including the 5
  new single-line instrumentation assertions in their own existing endpoint test files).
- `python tools/check_line_budget.py`: all application-source files within the 600-line cap.
- `python tools/qa/build_surface_map.py check`: 371/371 API, 1607/1607 FE surfaces covered.
- `alembic upgrade head` + `alembic check` on a scratch DB: clean, no drift.
- `ruff format` + `ruff check`: clean. `python tools/build_frontend.py`: clean;
  `pytest tests/test_frontend_assembly.py -q` → 64 passed.

## Rollback

Drop `usage_events` (additive migration; `0001` owns eventual metadata teardown); remove the new router mount +
`app/backend/usage.py` + `usage_repo.py`; revert the 6 instrumented call sites (each a 1-3 line addition, clearly
marked `# backlog #38A` in the diff); remove the settings-toggle wiring (4 points in `settings.py` +
`app_settings.py`); remove `35f_usage.jsx` + its `SettingsCard` + the one-line fire in `37_cite.jsx`. No other
feature's behavior is touched by any of this.

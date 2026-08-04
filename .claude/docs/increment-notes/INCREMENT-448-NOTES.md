# Increment 448 — SciELO + TOP Factor legitimacy signals (backlog #40 slice)

## Implemented

PUBLISHERS ("where to submit," Discover → Journals) shipped SP1a/SP1b with exactly **one** legitimacy source
wired in — DOAJ. A module constant, `LEGITIMACY_DEFERRED`, has named four still-missing sources since. This
increment wires in **two** of them: **SciELO** (a Latin-American/Iberian regional index) and **TOP Factor**
(Center for Open Science's per-journal transparency/openness rubric). The other two deferred bullets —
self-archiving/green-route (needs a Jisc-registered API key only the maintainer can obtain) and the remaining
regional indexes (AJOL/Redalyc/Latindex, none with a confirmed public API) — stay untouched. **This does not
close backlog #40** — see the updated backlog entry for everything still open.

Both external sources were verified live before planning, not assumed: SciELO's ArticleMeta API
(`GET https://articlemeta.scielo.org/api/v1/journal/?issn={issn}`, free, no auth) returns a bare JSON array —
empty `[]` for a non-indexed journal, one object per SciELO collection for a hit, using SciELO's legacy
ISIS-JSON field numbering (`v100`=title, `v310`=country). TOP Factor has no query API — a periodic bulk CSV
snapshot hosted on OSF (`https://osf.io/download/qatkz/`, ~4.2MB, confirmed real header with 9-10 named
categories, e.g. `Data citation`, `Study preregistration`, `Replication`, plus a `Total` sum column).

**SciELO** (`integrations/scielo/journals.py`, new) mirrors `integrations/doaj/journals.py`'s exact client
pattern: an injectable `Protocol`-typed fetcher, ISSN-regex validation before any request, `api_cache`-backed
caching, fail-closed (`None`) on any error. `ScieloJournal` carries `collections`/`codes`/`title`/`country` —
enough to show "Indexed in SciELO (scl, spa)" as inspectable evidence, never the full ISIS record. No cheap
pre-filter exists (a closed journal can still be SciELO-indexed), so every candidate gets one live call, bounded
by the existing `MAX_CANDIDATES=60` cap already applied upstream.

**TOP Factor** (`integrations/top_factor/adapter.py`, new) mirrors `integrations/retraction_watch/adapter.py`'s
exact download→parse→replace-locally pattern: `TopFactorClient.fetch_csv` (streaming, size-capped, follows OSF's
two redirects to the real file), `parse_top_factor_csv`, `download_top_factor_database`. New table
`top_factor_records` (`app/backend/persistence/schema_findings.py`, migration `0066_top_factor_records.py`) — one
row per journal, `categories_json` holding `[{"name","score","max","justification"}]` (this codebase's existing
`*_json` blob convention rather than an 18-column schema). New repo `top_factor_repo.py`
(`replace_top_factor_records`/`lookup_top_factor_record`/`top_factor_db_status`, the last a direct copy of
`retraction_db_status`'s `{count, retrieved_at}` shape). New router `methods_top_factor.py`
(`GET /methods/top-factor/database`, `POST .../refresh` + poll), mounted + wired into `app.py`/`status.py`
exactly like the Retraction Watch DB section of `methods_retraction.py`.

**The "never downloaded" honesty problem.** A per-journal `top_factor: None` is ambiguous — "no data for this
journal" vs. "the mirror was never downloaded at all." Resolved at the **report level**, not per-card:
`PublishersReport.top_factor_coverage` (`{count, retrieved_at}`, populated once per run from
`top_factor_db_status(conn)`) drives one report-level footer note when empty, rather than repeating the caveat on
every card. This never touches ranking or the candidate list — a display honesty caption only.

`build_profiles()` gained `scielo_by_issn`/`top_factor_by_issn` dict params (non-breaking defaults) plus a
keyword-only `top_factor_db_status`; the existing `_doaj_for()` per-ISSN helper generalized into a shared
`_by_issn(meta, table)` used for all three sources. `JournalProfile` gained `scielo_collections`/`top_factor`;
`legitimacy_signals` gained "Indexed in SciELO (...)" / "Has a TOP Factor transparency assessment" —
deliberately **not** the bare `Total` number, which lives only inside the frontend's "show the basis" `<details>`
block next to its category sub-scores (Principles #7, no opaque composite score). `LEGITIMACY_DEFERRED` narrowed
to drop both sources from the still-missing list.

**Frontend** (`08e_methods_publishers.jsx`): a `<details className="cite-equity-basis">` block per profile card
reusing `08b_methods_citation_equity.jsx`'s existing "show the basis" idiom — no new CSS. `35_settings.jsx`'s
`LocalMaintenanceSettings` gained a TOP Factor row mirroring the Retraction Watch row verbatim; adding it pushed
the file to 603/600 lines, so the whole function was extracted to a new `js/35e_maintenance.jsx` (131 lines) via
the established shared-IIFE function-hoist pattern (the inc-256 `35b_providers.jsx` precedent) — `35_settings.jsx`
is now 477 lines.

## Key technical detail

**SciELO's response shape required a `put_cached`-contract adapter.** `integrations/api_cache.py`'s `put_cached`
expects a dict payload; SciELO's real response is a bare JSON array (`[]` or `[{...}, ...]`). Wrapped as
`{"results": [...]}` before caching, unwrapped by `_scielo_from_results()` on read — an isolated shim inside
`journals.py`, not a change to the shared cache contract.

**TOP Factor's malformed-cell handling degrades honestly, never silently.** A malformed per-category score cell
is *omitted* from that record's `categories` list (never coerced to `0` — a fabricated zero would misrepresent
"this category wasn't assessed" as "this category scored zero"). A malformed `Total` cell is *derived* from the
sum of the successfully-parsed category scores rather than dropped or crashing the parse. A row with neither
ISSN nor EISSN is skipped outright (no null-keyed insert). All three paths are covered by dedicated tests in
`tests/test_top_factor.py` using a CSV built from `TOP_FACTOR_CATEGORIES` itself, so the test can't silently
drift from the real confirmed column names.

**A real Principles #7 violation found and fixed during live browser verification.** The first implementation
rendered `<summary>TOP Factor: {total} — show the basis (...)</summary>` — but a `<summary>` element is always
visible on an unexpanded `<details>`, so the bare `Total` number rendered on every TOP-Factor-rated card whether
or not a user ever expanded the basis block. Live Playwright verification against real downloaded TOP Factor
data (a real BioMed Central journal scoring 4/30) caught this directly in the rendered page text before any
manual code review would have. Fixed by moving the `Total` out of the `<summary>` entirely — the collapsed state
now reads only "TOP Factor — show the basis (N categories)" — and adding it as the last line *inside* the
expanded content, labeled "Total (sum of the categories above)" so it stays glued to its own inputs. Re-verified
live: the collapsed summary carries no number; the expanded block does, correctly computed and captioned.

## Housekeeping / gates

- **Security-audit addendum** appended to `.claude/security-audits/2026-07-01_publishers.md` ("Addendum — SP2")
  covering both new fetch paths (SciELO SSRF review — ISSN-regex-gated, constant HTTPS host; TOP Factor CSV parse
  bounds — size cap, row cap), the first schema/migration this tool has needed, and re-confirmation that every
  Principles/A-A veto (no composite score, no predatory label, gate-the-boost-never-the-listing, abstract never
  transmitted) still holds with the two new sources wired in.
- **Principles-alignment gate (rule #9):** touches commitment #7 (no opaque composite scores) most directly —
  worked example is **PRINCIPLES.md's PUBLISHERS section itself** (the project's own canonical "gate the boost,
  never the listing" case). Easiest misaligned path: show TOP Factor's `Total` as a small numeric badge on the
  card, exactly the "openness score" shape #7 exists to forbid. Declined — the total renders only inside the
  expanded per-category basis block, glued to its own inputs.
- **QA routes extended + one new route.** `route_60_publishers.md` gained new standing assertions (SciELO in the
  abstract-never-transmitted veto; TOP Factor's `Total` never bare), adversarial checks, and steps. New
  `route_85_top_factor.md` (next free number) mirrors `route_74_retraction_watch.md`'s structure for the
  Settings → Local Maintenance refresh flow.
- **A pre-existing QA hard-gate failure from inc 447 found and fixed in the same pass.**
  `tools/qa/build_surface_map.py check` failed with 4 uncovered API surfaces
  (`POST /manuscripts/{manuscript_id}/citation-equity/run`, `GET /citation-equity/run/{job_id}`,
  `GET /manuscripts/{manuscript_id}/reference-integrity`, `POST /manuscripts/{manuscript_id}/reference-integrity/
  run`) — unrelated to this increment's own changes. Root cause: `extract_api()` reads each route decorator's
  literal path string and does **not** prepend the owning `APIRouter(prefix=...)`, so the `/wip`-prefixed paths
  documented in `route_51_methods_citation_equity.md`/`route_68_reference_integrity.md`'s `api:` lines never
  matched the tool's actual (unprefixed) surface ids. `route_75_wip_workspace.md` had already independently
  discovered and worked around this by listing both the `/wip`-prefixed (readable) and bare (tool-matching)
  paths as two separate `api:` lines (the parser accumulates multiple `api:` lines). Fixed routes 51 and 68 the
  same way. `python tools/qa/build_surface_map.py check` now reports **367/367 API, 1601/1601 FE surfaces
  covered.**
- **Backlog #40 updated, not closed** — see `.claude/docs/INCREMENT-BACKLOG.md`.

## Manual verification script

1. Open **Settings → Local maintenance**. Confirm a "TOP Factor database: Not downloaded…" line + Refresh
   button. Click Refresh (live network) — confirm the count/as-of line updates from the real OSF CSV with no
   contact-email prompt.
2. Open **Discover → Journals**, run a topic likely to surface a SciELO-indexed and/or TOP-Factor-rated journal
   (e.g. a Latin-American public-health or social-science abstract). Confirm a hit shows "Indexed in SciELO
   (...)" and/or a "show the basis" block; expand it and confirm every category name/sub-score/justification
   renders, with `Total` appearing nowhere outside that expanded block.
3. Confirm a journal with neither signal still appears unchanged (gate-the-boost-never-the-listing preserved).
4. Confirm no `*score*` composite key or "predatory" string anywhere in the response/UI.

Live-verified end-to-end with real external data: a real TOP Factor CSV download (3,209 journals), a real
SciELO-indexed match ("Bulletin of the World Health Organization"), and real COS justification text rendering in
the expanded basis block.

## Verification

- `pytest tests/test_publishers.py tests/test_top_factor.py tests/test_migrations.py tests/test_status.py
  tests/test_frontend_assembly.py -q` → all passing (23 + 9 + 6 + existing status/assembly tests).
- `alembic upgrade head` + `alembic check` on a scratch DB: clean, no drift.
- `python tools/check_line_budget.py`: all application-source files within the 600-line cap.
- `python tools/qa/build_surface_map.py check`: 367/367 API, 1601/1601 FE surfaces covered (including the inc-447
  regression fixed above).
- `ruff format` + `ruff check` on every touched file: clean.
- `python tools/build_frontend.py`: rebuilt cleanly.
- Full suite: `pytest -n auto -q` (see the pytest-xdist local-flakiness memory note; CI's own `-n auto -q` run is
  the authoritative full-suite gate when local xdist flakes).

## Rollback

Drop `top_factor_records` (additive migration; `0001` owns eventual metadata teardown); remove
`methods_top_factor.py`'s router mount, `top_factor_db_jobs`/`top_factor_client` state in `app.py`, and the
`status.py` entries; revert `methods/publishers.py`/`routers/publishers.py` to their pre-inc-448 signatures;
remove `integrations/scielo/`, `integrations/top_factor/`, `35e_maintenance.jsx` (folding
`LocalMaintenanceSettings` back into `35_settings.jsx` minus the TOP Factor row). DOAJ-only PUBLISHERS behavior
is otherwise unchanged and requires no rollback.

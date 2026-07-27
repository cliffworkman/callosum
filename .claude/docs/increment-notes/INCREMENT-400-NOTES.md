# Increment 400 — cache statcheck results per paper, explicit Rescan

**Date:** 2026-07-27
**Status:** Implemented and verified live (Playwright, light + dark theme); 6 new backend tests
including byte-for-byte invariant-#2 fidelity; security audit PASS.

## Context

The METHODS "Statistics" per-paper check recomputed live every time a paper was selected — no
persistence, no visible "as of" timestamp, and the "Check statistics" button disappeared entirely
once done (the only way to re-check was navigating away and back, a silent full recompute). The user
suspected a published paper's statistics rarely change and asked for a cache with an explicit rescan
instead.

## Implemented

**Backend** — two new endpoints on a new sibling router `app/backend/api/routers/
methods_statcheck_cache.py` (split from `methods.py`, which was at 524/600 — rule #1), importing that
file's private compute/payload helpers directly (the inc-262/226 `methods_retraction.py`/
`paper_enrich.py` precedent):
- `GET /papers/{paper_id}/statcheck/cached` — reads the cache, never recomputes.
- `POST /papers/{paper_id}/statcheck/rescan` — runs the existing `_run_statcheck_for_paper` fresh,
  stores it, returns the same shape.

New table `paper_statcheck_cache` (`schema_findings.py`, migration `0056`): one row per paper,
storing the *verbatim* itemized `StatcheckResult`/`StatcheckCoverage` payloads (including
`bbox_json`/`coordinate_precision`) — the existing `open_science_signals` table (written by the
whole-library batch job) was confirmed insufficient, since it only stores a coarse
`{checked, inconsistent, decision_errors}` count for the library's "N flagged" chip, not the itemized
per-finding evidence a cached redisplay needs to be indistinguishable from a live run.

**Staleness** is a SHA-256 fingerprint over the paper's chunk set (`id:source_attachment_checksum`)
and attachment set (`id:checksum:availability`) — the exact inputs `_run_statcheck_for_paper` reads —
computed at cache-write time and re-derived at read time for comparison. A mismatch surfaces as a
passive `stale: true` flag; it never blocks the cached result from displaying and never
auto-triggers a recompute.

The "Check all papers" batch job's existing per-paper `persist()` closure now also warms this cache
(it already computes the full report per paper) — the "N flagged chip → auto-show" flow keeps
working with zero live recompute in the frontend, now sourced from the batch-warmed cache.

**Frontend** (`06_methods_statcheck.jsx`, `StatcheckPaper`): replaced the inc-140 auto-run-on-select
effect with a cache-fetch effect; the "Check statistics"/"Rescan" button is now **permanent** (never
disappears); an "as of `<date>`" line and, when stale, an amber `--flag`-token hint appear beside the
(still fully shown) cached result. The now-dead `ctx.methodsOpen` field was removed from `paneCtx`
(`40_app.jsx`) — it had exactly one consumer (the old auto-run's `active` prop), which this change
removed; the underlying accordion `methodsOpen` state itself is untouched (still needed directly by
`PaneAccordion`).

**A second 600-line-cap breach, unrelated to the frontend/router work**: adding the new table's
import to `schema.py` pushed it to 601/600. Split `jobs`/`job_errors` (a natural, cohesive pair, plus
their `JOB_STATUSES` constant) into a new `schema_jobs.py`, mirroring the `schema_findings.py`
precedent exactly — `schema.py` → 577 lines.

## Key technical detail

Fingerprinting the chunk/attachment *identity+checksum set* (not the extracted text itself) is
deliberately simpler and more conservative than WIP's own `wip_tool_runs.relevant_content_hash`
(which hashes normalized extracted text, so a byte-identical re-extraction reads as still-current).
Here, ANY reprocess — even one that happens to extract identical text — mints new chunk ids and thus
flips the fingerprint. A false "may be stale" is a safe, dismissible passive hint; a false "still
current" is the failure this exists to prevent (silence is not a certificate) — so erring toward
over-flagging is the correct trade-off, not a shortcut.

## Manual verification script

1. Select a never-checked paper — confirm "Check statistics" shows immediately with **no network call
   firing a recompute**.
2. Click it — confirm itemized results + "as of `<today>`"; the button now reads "Rescan" and **stays
   visible** (doesn't disappear).
3. Select a different paper, then reselect the first — confirm the identical cached result and "as
   of" date reappear instantly, no spinner, no recompute.
4. Confirm dark theme renders the new "as of"/stale-hint text correctly (muted `--ink-3` / amber
   `--flag`).
5. (Covered by pytest, not re-run live against production data this increment): reprocessing a
   paper's PDF should show the amber "may be stale" hint beside the unchanged old result on next
   open; Rescan clears it. Verified via `test_cache_flags_stale_after_content_changes_...` instead of
   a live reprocess, to avoid unnecessary reprocessing of real library data during manual QA.

All verified live via Playwright this increment; zero console errors throughout, in both themes.

## Pytest

`pytest tests/test_statcheck_cache.py -q` — **6 passed**: empty-before-any-check + 404s; rescan
computes/persists/overwrites a single row; `exact`- and `region`-precision results byte-identical
across a live run, an explicit rescan, and a subsequent cached read (the non-negotiable invariant-#2
check); a simulated reprocess flips `stale` while the returned results stay the old ones verbatim;
the library batch run warms the cache for both a flagged and a clean paper.
`pytest tests/test_statcheck.py tests/test_health.py -q` — 43 passed (the exhaustive
`test_api_exposes_only_read_only_get_routes` allowlist needed both new routes registered — a
**pre-existing blind spot** worth flagging: the test's own path-filtering logic silently skips any
route whose path isn't already in one of its allowlists, so a wholly new endpoint path isn't
automatically caught the way a new method on an *existing* path is; both new routes were added to the
correct lists anyway, matching the test's clear intent as a complete route inventory, even though its
current mechanism wouldn't have forced it). `pytest tests/test_frontend_assembly.py -q` — 53 passed.
Full suite before merge: see `changes.md`.

## Files changed

- `app/backend/api/routers/methods.py` (batch-job cache-warming addition; import)
- `app/backend/api/routers/methods_statcheck_cache.py` (new)
- `app/backend/persistence/statcheck_cache_repo.py` (new)
- `app/backend/persistence/schema_findings.py` (new `paper_statcheck_cache` table)
- `app/backend/persistence/schema_jobs.py` (new — `jobs`/`job_errors` split out of `schema.py`)
- `app/backend/persistence/schema.py` (re-exports; `jobs`/`job_errors` moved out)
- `app/backend/api/app.py` (mount the new router)
- `alembic/versions/0056_paper_statcheck_cache.py` (new)
- `app/frontend/js/{06_methods_statcheck.jsx,40_app.jsx}`
- `app/frontend/styles.css`
- `tests/{test_statcheck_cache.py (new),test_health.py}`
- `.claude/qa-routes/route_33_methods_statcheck.md` (extended)
- `.claude/security-audits/2026-07-27_statcheck-cache.md` (new — PASS)
- `callosum-app.html` (rebuilt)

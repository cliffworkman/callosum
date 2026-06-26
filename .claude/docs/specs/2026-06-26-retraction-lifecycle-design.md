# Retraction lifecycle — on-import auto-check + RW staleness nudge (inc 134)

**Goal:** Complete the retraction producer's lifecycle (the world-state design the future-track calls for): a
**new paper is auto-checked on import** (so a freshly imported retracted paper flags immediately, without waiting
for the user to re-run the batch), and the Retraction Watch database panel **surfaces its snapshot's age** so a
stale copy nudges a refresh.

## Why / gates

- Reuses the inc-131 checkers (Crossref + OpenAlex + the inc-132 RW mirror) — **no new external-fetch type/host**,
  **no new endpoint, no migration, no new dependency, no egress** (public DOI metadata, not the Gemini gate).
- The on-import check adds the (already-audited) retraction fetch to the import path — same posture as the inc-131
  batch; note it as an addendum to `2026-06-26_retraction.md`, no new full audit. No new claim type → Principles
  posture unchanged. No new end-user **surface** (an internal auto-check + a text nudge in the already-covered RW
  panel) → no new QA route; surface map stays 0-uncovered.

## Architecture

### 1. On-import auto-check (`methods/retraction.py` + the library jobs)

- New helper `auto_check_retractions(conn, paper_ids, *, checkers) -> int`: for each id, **guarded best-effort**
  (`try: apply_retraction(conn, pid, detect_retraction(conn, get_paper(conn, pid), checkers=checkers)) except
  Exception: continue` — a check failure for one paper never aborts the import); returns the count flagged
  retracted. Uses `app.state.retraction_checkers` (so it's consistent + test-injectable). The Crossref checker
  reads the **cache the enrich just populated** (free); the RW checker is offline; OpenAlex is one cached lookup
  — marginal for a handful of new papers.
- Hook A — **scan** (`routers/library.py::_process_scan_result`): after enrich + embed of `added_papers`, call
  `auto_check_retractions(conn, added_papers, checkers=retraction_checkers)` (a new `retraction_checkers` param,
  passed by `_run_scan_job` + `_run_watched_rescan_job` from `app.state.retraction_checkers`).
- Hook B — **citation import** (`routers/library.py::_run_import_job`): after embedding `created`, call
  `auto_check_retractions(conn, created, checkers=app.state.retraction_checkers)`.
- (Zotero import / single-PDF ingest are not async-job paths here; the library batch + per-paper refresh still
  cover them. Scan + citation-import are the "bring papers in" jobs that matter.)

### 2. RW staleness nudge (`08_methods_findings.jsx::RetractionDatabasePanel`)

Compute the snapshot age client-side from `retrieved_at` (days). When the mirror exists and is **older than 30
days**, append a subtle hint to the as-of line: `· N days old — refresh recommended` (styled muted/amber via an
existing token, not a loud warning). Absent mirror already says "not downloaded — refresh to enable…". No new
endpoint (reads the existing `GET /methods/retraction/database`).

## Honesty / Principles (unchanged, re-asserted)

- On-import writes the same FACT/signal as the batch — a registry record relayed verbatim, evidence-carried,
  non-accusatory; silence ≠ clean (a checked-clean new paper gets a `none` status). Best-effort: a check failure
  leaves the paper simply unchecked (honest), never blocks the import.
- The staleness nudge surfaces the snapshot date as a fact (world-state visibility), never implies the data is
  wrong — just old.

## Tests (hermetic — injected fake checkers)

- `auto_check_retractions`: over a mix (one flagged, one clean, one whose checker raises) → the flagged paper
  gets a FACT + `retracted` signal; the clean gets a `none` signal; the raising one is skipped (the others still
  apply); returns the flagged count.
- on-import via the **citation-import job**: import a citation with a DOI + an injected fake checker flagging that
  DOI (`app.state.retraction_checkers`) → after the job, the created paper carries the retraction FACT + signal.
- the scan hook: `_process_scan_result(..., retraction_checkers=[fake])` over an added paper flags it (unit, no
  real PDF — drive `_process_scan_result` directly with a crafted `scanned` dict + a pre-created paper).

## Verification

- pytest green (+ ~4); ruff clean; build + assembly + the **e2e suite** (run locally before push). Surface map
  unchanged (0 uncovered). Headed, no egress: a citation import of a known-DOI paper (with an injected fake
  flagging checker) → it shows the retraction FactMark without a manual batch; the RW panel shows a stale-age
  nudge for an old seeded `retrieved_at`. 0 console/page/genai.

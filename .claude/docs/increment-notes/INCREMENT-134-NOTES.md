# Increment 134 — Retraction lifecycle (on-import auto-check + RW staleness nudge)

## Implemented

Completes the retraction producer's lifecycle (the world-state design the future-track calls for): the producer
checked only on demand (the batch / per-paper), so a freshly imported retracted paper wouldn't flag until the
user remembered to re-run the batch. Two additions close that.

- **On-import auto-check.** New `methods/retraction.py::auto_check_retractions(conn, paper_ids, *, checkers) ->
  int` — a **guarded best-effort** detect+apply over a set of papers (each paper wrapped in `try/except` on top of
  `detect_retraction`'s per-source guard, so a source error / a missing row **never aborts the import**); returns
  the count flagged. Hooked into the two "bring papers in" async jobs (`routers/library.py`): the **scan** job
  (`_process_scan_result` gained a `retraction_checkers` param, passed by scan + watched-rescan) and the
  **citation-import** job, over the *new* paper ids, using `app.state.retraction_checkers`. The Crossref checker
  reads the cache the enrich just populated (free); the RW mirror is offline; OpenAlex is one cached lookup —
  marginal on an already-async job. A freshly imported retracted paper now flags immediately.
- **RW staleness nudge** (`08_methods_findings.jsx::RetractionDatabasePanel`): the panel computes its snapshot age
  from `retrieved_at` (`Date.now() - new Date(retrieved_at)`) and, past **30 days**, appends `· N days old —
  refresh recommended` (amber `--flag` — a status nudge; the data isn't wrong, just old). No new endpoint (reads
  the existing `GET /methods/retraction/database`).

## Key technical detail

**Best-effort, never blocks an import.** The auto-check is additive after the enrich+embed that the scan/import
jobs already do; its failure mode is "the paper is left unchecked" (honest — `silence ≠ clean` still holds via the
per-paper status), never a broken or 500-ing import. It reuses `app.state.retraction_checkers`, so it's consistent
with the batch + test-injectable (the import-job test injects a fake flagging checker and asserts the imported
paper carries the FACT). Zotero import / single-PDF ingest aren't async-job paths here; the batch + per-paper
refresh still cover them.

**No new gates.** No new endpoint, migration, external-fetch type/host, or dependency → reuses the inc-131 audit
(an addendum was added to `2026-06-26_retraction.md` for the on-import hook) and the established Principles
posture (no new claim type). No new end-user *surface* (an internal auto-check + a text nudge in the
already-QA-covered RW panel) → no new QA route; surface map stays 0-uncovered.

## Manual verification script

1. Import a citation (BibTeX/RIS/CSL-JSON) for a paper whose DOI a registry records as retracted → after the
   import job, the paper shows the **⚠ Retracted** FactMark + the library "N retracted" chip, **without** a manual
   batch run. (Unit-tested with an injected fake checker: `test_citation_import_auto_checks_retraction`.)
2. In the METHODS Review section, with a Retraction Watch snapshot older than 30 days, the RW database line shows
   "· N days old — refresh recommended".

Verified: the auto-check is unit-tested (`test_auto_check_retractions_best_effort` + the import-job test); the
staleness endpoint + render were confirmed live (`GET /methods/retraction/database` returns the count +
`retrieved_at`; the panel computes the age client-side); build + assembly + the **e2e suite** green locally.

## Pytest

**506** (504 → +2 `test_retraction.py`: `auto_check_retractions` best-effort [flagged / clean / missing-id
swallowed]; the citation-import job auto-checks + the paper carries the FACT). `ruff` clean. Surface map
unchanged (0 uncovered). `library.py` 284/600.

## Next

This completes the retraction arc end to end (inc 131 SP1 → 132 SP2 → 133 candidate-review wiring → 134 lifecycle).
Deferred: an on-import check for the **Zotero / single-PDF** paths; an automatic *cadence* refresh of the RW DB
(SP2/inc-134 = manual refresh + the now-visible staleness nudge). The broader backlog (discovery/gapfinder, a live
OS file-watcher, word-processor adapters, auth) is open.

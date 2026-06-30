# Increment 224 — retraction on-import / on-enrich for the remaining DOI-bearing paths (#31)

## Implemented

Completes the retraction on-import lifecycle (the #31 remainder). `auto_check_retractions(conn, paper_ids, *,
checkers)` (inc 134) was wired into the **scan** + **citation-import** jobs only; it now also fires on the three
remaining routes where a paper gains or corrects a DOI:

1. **OA-acquire job** — `app/backend/api/routers/acquisition.py::_run_acquire_job`: after `import_oa_pdf`
   Crossref-enriches the acquired paper, inside the same `engine.begin()` transaction →
   `auto_check_retractions(conn, [paper_id], checkers=app.state.retraction_checkers)`.
2. **`reresolve_paper`** (`routers/papers.py`) — after `enrich_paper_metadata_from_crossref(..., force=True)` and
   before `conn.commit()` (a corrected DOI can newly reveal a retraction).
3. **`fill_metadata`** (`routers/papers.py`) — after `enrich_paper_metadata_multi(...)` and before
   `conn.commit()` (gap-fill's Pass 0 can recover a missing DOI → now checkable).

All three reuse the existing hook fn + `app.state.retraction_checkers` (set in `app/backend/api/app.py:132`).
Best-effort by construction (the fn swallows per-paper errors → can't break the acquire/enrich).

## Key technical detail — the Zotero hook is moot

The backlog phrased the remainder as "Zotero / single-PDF import paths," but **there is no Zotero import route** —
`import_zotero_library` is only called by the validation harness + tests, so there's no app-state-bearing caller to
hook; a hook there would be dead code (rule #5). Skipped + recorded in the audit addendum. The DOI-bearing paths
that *do* have routes (OA-acquire + re-resolve + fill-metadata) are the real targets; `ingest_pdf_scaffold` has no
DOI and no route, so it's not a meaningful hook point either.

**Rule #1:** the three hooks + the import pushed `routers/papers.py` to exactly **600**; condensed the two new
hook comments to one line each → **598** (a split is a separate concern — papers.py is now the closest to the cap,
split before the next addition there). `acquisition.py` 148.

## Manual verification script

Backend-only; hermetic pytest (no network). New tests in `tests/test_retraction.py`:
- `test_reresolve_auto_checks_retraction` — seed a retracted-DOI + a clean-DOI paper, inject a graceful Crossref
  fetcher (404, never networks) + a fake retraction checker keyed on the DOI; `POST /papers/{id}/re-resolve` → the
  retracted paper carries the FACT, the clean one has none.
- `test_fill_metadata_auto_checks_retraction` — inject an empty `EnrichmentRegistry` (no source fetch) + the fake
  checker; `POST /papers/{id}/fill-metadata` → the FACT lands.
- `test_oa_acquire_auto_checks_retraction` — monkeypatch the acquisition module's `build_default_registry` (→ a
  fake resolver returning an `OaLocation`) + `download_oa_pdf` (→ a real minimal fitz PDF) + a graceful Crossref;
  `POST /papers/{id}/acquire-oa` → poll → the acquired paper carries the FACT.

## Pytest

**789** (+3). ruff clean. **QA surface unchanged** (161/161 API + 719/719 FE, 0 uncovered — no new route; the
behavior rides existing endpoints). `route_39_retraction.md` gained an on-import-lifecycle standing assertion.
Audit: **addendum 2** to `.claude/security-audits/2026-06-26_retraction.md` — **PASS** (no new fetch
type/host/endpoint/migration/dependency/egress; reuses the already-audited checkers + the same public DOI metadata
lookups, NOT the Gemini gate). **Principles non-triggering** — reuses the established retraction FACT producer (a
registry fact relayed verbatim, no new claim type, no-accusation boundary intact).

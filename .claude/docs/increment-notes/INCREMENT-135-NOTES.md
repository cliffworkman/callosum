# Increment 135 — Literature gap-finder (backward citation gap)

## Implemented

A new discovery capability (a long-wanted future-track): surface external works that **many of the user's library
papers cite but the library doesn't have** ("cited by N of your papers") — likely important references the user is
missing — as **candidates** to Add or Dismiss. The inverse of the inc-119 "who cites my work" feature: aggregate
each library paper's **`referenced_works`** (what it cites), not who cites it.

- **OpenAlex adapter** (`integrations/openalex/adapter.py`): `fetch_referenced_works(conn, ref) -> list[str]`
  (reuses the cached DOI→work fetch; reads the work's `referenced_works`, bare `W…` ids, capped `MAX_REFERENCED=500`,
  fail-closed) + `fetch_work_meta(conn, work_id) -> dict | None` (a candidate's title/DOI/authors/year by `W…` id —
  **validated `^W\d+$` before any fetch**, cached `work:<id>`, fail-closed).
- **`clustering/gapfinder.py`** — `GapCandidate` + `compute_gaps(conn, *, openalex_client, dismissed,
  min_citations=3, max_candidates=50) -> (candidates, coverage)`: for each live paper **with a DOI**, aggregate a
  `dict[ref_id, set[paper_id]]`; keep ids cited by >= `min_citations`; for the top `3*max_candidates`,
  `fetch_work_meta` → **exclude** no-DOI / already-in-library (`find_existing_paper_by_identity`) / dismissed; rank
  by count. Returns a coverage dict (`checked`/`total`/`note`). Pure over an **injected** client → hermetic.
- **Dismissals** (`profile.dismissed_gap_works`, **migration 0018** additive/guarded; `profile_repo.dismiss_gap`
  / `dismissed_gaps`): a JSON list of dismissed OA ids + DOIs, excluded by the job so a re-run doesn't resurface
  them. `dismiss_gap` inserts a minimal profile row if none (the gap-finder doesn't require a My-Pubs profile).
  **No `gap_candidates` table** — the computed list is the **ephemeral async-job result** (the p-curve model).
- **Endpoints** (`routers/gaps.py`): async `POST`/`GET /gaps/find` (`app.state.gap_jobs`; runs `compute_gaps` over
  `app.state.openalex_client`, excluding `dismissed_gaps`); `POST /gaps/add` (reuses inc-119 `import_citing_work`
  with a new `imported_source` param → `"gap-import"` — **metadata-only, deduped, into the general library**;
  the PDF stays the OA-acquire lane); `POST /gaps/dismiss`.
- **Frontend** (`36_gaps.jsx`): a **"Gaps"** library-header button → a modal (clones `26_wanted.jsx`): **Find gaps**
  → the candidate list (**"cited by N of your papers"** + title · authors · year) with per-row **Add** (→ "in
  library") / **Dismiss** (→ hidden) + the **coverage caveat** + an honest empty state. Tokens-only CSS.

## Key technical detail

**The count is evidence, not a rank.** "Cited by N of your papers" is a count over the user's **own** library's
citing — inspectable, never a global importance/quality score. The modal note states this explicitly, and
coverage is reported ("scanned M of N papers; the rest have no DOI; based on the references OpenAlex has —
partial"), so absence is honest (a missing work isn't "unimportant", just not surfaced). Add is **metadata-only**
(no PDF → the A-A no-paywall-circumvention veto holds). Principles gate run (audit §"posture"): aligned with
#1/#2/#3/#6/#7 + the A-A veto; **declined** a "must-read importance score" / a "papers you should read" leaderboard.

**Hermetic + offline by construction.** `compute_gaps` takes an **injected** `openalex_client`, and the adapter
fetches are cache-first — so tests use a fake client / fake fetcher, and the headed verify pre-seeds
`external_api_cache` (OpenAlex referenced-works + work-meta + the Crossref DOI for Add) so the **real code path**
runs fully offline. (A real OpenAlex run is the user's optional manual check.)

## Manual verification script

1. With ≥ `min_citations` (3) of your library papers citing the same external work that you don't have, open the
   **Gaps** button → **Find gaps** → the work appears as "cited by N of your papers".
2. **Add** it → it imports (metadata-only) into the library ("✓ in library"); idempotent. **Dismiss** another →
   it's gone and won't resurface on a re-Find. The coverage line states how many papers were scanned.

Automated equivalent: `.local/visual/drive_inc135_gaps.py` (deleted after) — pre-seeded the cache so the real
path ran offline; **PASS**, candidate + Add → in-library, 0 console/page errors, **0 genai hits**. (Op note: stray
uvicorns from repeated driver runs can hold a port + serve a stale app — use a free port + assert your own process
is alive; folded into `route_41`'s env note.)

## Pytest

**514** (506 → +8 `test_gapfinder.py`: `fetch_referenced_works` [+ no-field], `fetch_work_meta` [+ bad id],
`compute_gaps` [surfaces ≥N / excludes in-library + dismissed], `dismiss_gap` round-trip without a profile, the
find/add/dismiss endpoints + the dismiss-excludes-next-run). `ruff` clean; build + assembly + the **e2e suite**
green. Audit `.claude/security-audits/2026-06-26_gapfinder.md` **PASS**; QA `route_41_gaps.md` → surface **105/105
API + 522/522 FE, 0 uncovered**; migration head **0018**. **Watch:** `my_publications.py` at **594/600** (the
`import_citing_work` signature growth) — split before the next addition there.

## Next

This is the v1 backward gap-finder (library-wide). Deferred: axis-scoped gaps ("gaps for [axis]"); a persistent
`gap_candidates` cache table (v1 recomputes — cached OpenAlex makes the 2nd run fast); PDF acquisition of an added
gap (the existing OA-acquire button covers it). The broader discovery track (external search beyond your library)
remains open.

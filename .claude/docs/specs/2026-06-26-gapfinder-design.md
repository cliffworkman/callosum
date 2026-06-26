# Literature gap-finder (backward citation gap) — design (inc 135)

**Goal:** Surface external works that **many of the user's library papers cite but the library doesn't have**
("cited by N of your papers") — likely important references the user is missing — as **candidates** to Add or
Dismiss. The inverse of the inc-119 "who cites my work" feature: aggregate each library paper's
**`referenced_works`** (what it cites), not who cites it.

## Why / gates

- **Audit gate** — a new external-fetch *use* of the OpenAlex adapter (`referenced_works` + fetch-by-id). →
  `.claude/security-audits/2026-06-26_gapfinder.md`.
- **Principles gate** — a **discovery signal / a claim about what the user should consider**. Aligned (run
  inline): the output is **candidates, not verdicts** (the human Adds/Dismisses — facts-vs-candidates); each
  carries its **evidence** ("cited by N of *your* papers" — a count over the user's own library, not a global
  importance score); **coverage is stated** ("based on the references OpenAlex has for your library" — silence ≠
  "you have everything"); it is **not a quality rank** (the count is a fact about your library's citing, not a
  judgment of the paper). **Declined easy path:** a global "must-read importance score" / a ranked "papers you
  should read" leaderboard.
- Egress: **public OpenAlex metadata** (bounded, cached, on-demand) — the inc-81/119 posture — **not** the Gemini
  library-text gate.

## Architecture

### OpenAlex adapter (`integrations/openalex/adapter.py`)

- `fetch_referenced_works(conn, ref: PaperRef) -> list[str]`: reuse `_fetch_work(conn, ref)` (the cached DOI →
  work fetch), read `work.get("referenced_works")` (a list of `https://openalex.org/W…` URLs) → bare `W…` ids,
  capped (`MAX_REFERENCED = 500`), fail-closed (no work / no field → `[]`).
- `fetch_work_meta(conn, work_id: str) -> dict | None`: fetch a candidate by id (`/works/W…`, validate
  `re.fullmatch(r"W\d+", work_id)`, cache key `work:<id>` under `OPENALEX_PROVIDER`), parse
  `{openalex_work_id, doi, title, authors (≤8), year, cited_by_count}` (mirrors `author._work_from_obj`).
  Fail-closed → None.

### The gap computation (`app/backend/clustering/gapfinder.py`, new — injected client → hermetic)

- `GapCandidate` dataclass: `openalex_work_id, doi, title, authors: list[str], year, cited_by_in_library: int`.
- `compute_gaps(conn, *, openalex_client, dismissed: set[str], min_citations=3, max_candidates=50) -> list[GapCandidate]`:
  1. For each live paper **with a DOI**, `refs = openalex_client.fetch_referenced_works(conn, PaperRef(doi=…))`;
     accumulate `counts: dict[ref_id, set[paper_id]]` (a set so duplicate refs from one paper count once).
  2. Candidates = ref ids with `len(citers) >= min_citations`, sorted by citer-count desc, then id (stable);
     consider only the top `~3*max_candidates` to bound the metadata fetches.
  3. For each, `meta = openalex_work_meta`; **skip** if: no DOI; the DOI's **already in the library**
     (`find_existing_paper_by_identity(conn, doi=…)` not None); or the **OA id / DOI is dismissed**.
  4. Return up to `max_candidates` `GapCandidate`s (cited_by = the citer-count). Bound total OA fetches.
- Pure aggregation + injected `openalex_client` (with a fake fetcher) → tests run offline.

### Persistence — dismissals only (`persistence/profile_repo.py` + migration 0018)

- Migration **0018**: `profile.dismissed_gap_works` (nullable JSON — mirrors `dismissed_work_dois`, inc 85).
- `dismiss_gap(conn, key)` / `dismissed_gaps(conn) -> set[str]` (key = the OA id; store normalized). The gap job
  excludes dismissed candidates (so a re-run doesn't resurface them). **No `gap_candidates` table** — the
  computed list is the ephemeral async-job result (the p-curve model), so re-running just recomputes (cached OA →
  fast 2nd run).

### Endpoints (`app/backend/api/routers/gaps.py`, new)

- `POST /gaps/find` + `GET /gaps/find/{job_id}` — async (`app.state.gap_jobs = JobStore`); the job runs
  `compute_gaps` (with `app.state.openalex_client` + the dismissed set); returns the candidate list + a `note`
  (coverage caveat) + whether any paper lacked a DOI/OpenAlex match (honest "checked M of N papers").
- `POST /gaps/add {openalex_work_id, doi, title}` — import **metadata-only + deduped** into the **general**
  library (reuse the inc-119 `import_citing_work` flow: `find_existing_paper_by_identity` → `create_paper(...,
  imported_source="gap-import", openalex_work_id=…)` → Crossref enrich; idempotent). The PDF stays the separate
  OA-acquire lane (no paywall circumvention — A-A veto).
- `POST /gaps/dismiss {openalex_work_id, doi?}` — `dismiss_gap` (204).

### Frontend (`app/frontend/js/NN_gaps.jsx`, new — mirror `26_wanted.jsx` / the inc-119 citing modal)

- A **"Gaps"** button in the library header (`10_pdf_layer.jsx`, next to Wanted/Duplicates) → a modal: a
  **Find gaps** button (runs the async job, polls) → the candidate list (each: **"cited by N of your papers"** +
  title · authors · year) with per-row **Add** (→ in-library, disabled) and **Dismiss** (→ hidden) + the
  **coverage caveat** + the "checked M of N papers (the rest had no DOI / no OpenAlex match)" honesty line.
- Tokens-only CSS (read DESIGN.md).

## Honesty invariants (asserted in tests + the QA route)

- Candidates, never verdicts: nothing is auto-added; the human Adds/Dismisses.
- The count is "cited by N of **your** papers" — a fact about your library, never a global importance/quality rank.
- Coverage stated: only papers with a DOI + an OpenAlex match are scanned; the caveat + the "M of N" line make
  absence honest (a missing work isn't "unimportant", just not surfaced).
- Add is **metadata-only into the general library** (not My Pubs); the PDF stays the OA-only lane.

## Out of scope (v1 → later)

- Axis-scoped gaps ("gaps for [axis]"); a forward gap (works that cite many of your papers — that's inc-119's
  per-paper citing, not aggregated); a persistent `gap_candidates` cache table; PDF acquisition of a gap (the
  existing OA-acquire button covers an added paper).

## Tests (hermetic — injected fake OpenAlex client/fetcher, no network)

- `fetch_referenced_works`: a fake work body with `referenced_works` → bare ids, capped; no field → `[]`.
- `fetch_work_meta`: a fake `/works/W…` body → mapped; a bad id → None (no fetch).
- `compute_gaps`: a 3-paper library where 2 papers cite work X and 1 cites Y (min=2) → X is a candidate (cited_by
  2), Y excluded; a candidate already in the library (by DOI) excluded; a dismissed candidate excluded; the
  `min_citations` / `max_candidates` caps honored.
- endpoints: `POST/GET /gaps/find` (with an injected client → a candidate), `POST /gaps/add` (dedup/idempotent →
  in library), `POST /gaps/dismiss` (→ excluded on the next run); route-surface.
- migration head derived by tests (0018, inc 99).

## Verification

- pytest green (+ ~12); ruff clean; build + assembly + the **e2e suite** (run locally). QA route + surface map 0
  uncovered. Headed, **no egress**: inject fake gaps → the Gaps modal lists "cited by N" candidates → Add (→ in
  library) / Dismiss (→ hidden) + the coverage caveat. 0 console/page/genai. A real OpenAlex run is the user's
  optional manual check (needs network).

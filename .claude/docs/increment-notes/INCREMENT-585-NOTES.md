# Increment 585 — Bella's 3 end-user reports (#57/#58/#59), shipped in Desktop 0.5.9

Three GitHub-issue reports from real end-user testing (Bella), fixed together and released as 0.5.9.

## #59 — OA full-text acquisition: fall back across candidates on HTTP 403/404 (the bug)

**Root cause:** `ResolverRegistry.resolve()` returned only the **first** resolver's OA hit, and both callers
(`acquisition/wanted.py::run_recheck`, `routers/acquisition.py::_run_acquire_job`) downloaded that single
candidate — so a stale/forbidden URL from the primary resolver (OpenAlex) was a terminal dead end even when
arXiv/EuropePMC/etc. would return a working copy. **No fallback existed.**

**Implemented:**
- **`acquisition/fetch.py`** — `OaFetchError` now carries a **structured** `reason_code`
  (`http_error`/`not_a_pdf`/`oversize`/`redirect_error`/`unsafe_url`/`save_error`/`fetch_failed`) and
  `http_status`, so callers branch on machine-readable state, never by parsing the human message. A redirect
  hop to a non-https/IP target now raises `OaFetchError(reason_code="unsafe_url")` (a bad candidate) instead
  of a raw `ValueError` that would abort the cascade.
- **`acquisition/acquire.py` (new)** — `acquire_first_working(engine, registry, ref, *, download)` iterates
  the resolver cascade **lazily** (resolving the next resolver only after the current candidate fails),
  **dedups by `pdf_url`** (never re-fetches a known-bad URL), and returns a structured `AcquireOutcome`
  (`reason_code` ∈ `acquired`/`no_candidate`/`candidates_exhausted`, `candidates_tried`, `failures[]`).
  **Only `OaFetchError` triggers fallback** — any other exception propagates (never reclassified as
  exhaustion). Resolver priority is unchanged: the first candidate tried is exactly the one the old
  `resolve()` returned; later resolvers are consulted only on an expected download failure.
- **Both callers** now report three distinct non-error states — imported / **no OA candidate** / **candidates
  exhausted** (candidate(s) found but none downloadable, carrying the structured HTTP reason) — plus a 4th,
  unexpected-error state. `AcquireOaResponse.reason_code` is the machine-readable field; `run_recheck`'s
  summary gains an `exhausted` counter.
- **OA bright line untouched:** still only `OaLocation`s, still `download_oa_pdf`. This changes *which*
  candidate is chosen and *how* failure is reported — not OA eligibility or ranking.

**Tests:** `tests/test_acquisition_cascade.py` (7) — 403→fallback→success; all-403/404→structured exhausted;
duplicate-URL fetched once; resolver-priority preserved; unexpected exception not swallowed; failed attempts
leave no temp artifacts, only the success survives. `tests/test_wanted.py` updated for the new exhausted state.

## #58 — Add a paper by DOI (+ backend-orchestrated auto-OA)

**Reuse-first:** the MCP agent's `save_reference` already implemented DOI-add; extracted it into a shared
primitive so there is no DOI silo (the issue's constraint).
- **`metadata/doi.py`** — added canonical `normalize_doi(raw)` (bare / `doi:` / `https://doi.org/…` /
  `dx.doi.org` → bare lower-cased DOI, or `None` for non-DOIs). One normalizer for every DOI-add path.
- **`metadata/doi_add.py` (new)** — `add_paper_by_doi(conn, raw_doi, *, crossref_client, imported_source)`:
  normalize → dedup (`find_existing_paper_by_identity`) → Crossref resolve → create (or surface existing).
  Metadata-only; an unresolvable DOI creates **nothing** (fail honestly, no invented placeholder).
- **`routers/agent.py`** — `save_reference` refactored to call the shared primitive (behavior preserved).
- **`routers/acquisition.py`** — new `POST /papers/by-doi {doi, acquire_oa}`: creates the metadata record,
  then (opt-in, **backend-orchestrated**) starts the existing OA acquisition job on a newly-created paper and
  returns a **distinct** `acquire_job_id`. Metadata-import state and OA-fetch state are separate results — a
  failed PDF fetch never masquerades as a failed DOI import. Invalid/unresolvable → 422, nothing created;
  existing → surfaced, not duplicated.
- **Frontend:** `AddMenu` gets **Add with DOI…** (first item); new `28e_add_doi.jsx` modal (reuses the
  `axis-modal` recipe, no new CSS) with the honest explainer, a distinct OA-fetch status line, wired through
  `10_pdf_layer.jsx`/`03_library.jsx`/`40_app.jsx`.

**Real bug caught by the live smoke test (steering #1):** `app.state.crossref_client` defaults to `None` in a
running app (it's only set when injected, e.g. in tests), so every DOI would "fail to resolve" even though
Crossref is reachable. Fixed with an `or CrossrefClient()` fallback in the endpoint **and** the agent (mirrors
`paper_enrich._crossref`). The agent's DOI-save had the same latent None bug — now fixed too.

**Tests:** `tests/test_doi_add.py` (12) — normalizer forms/rejections; helper's 4 statuses; endpoint
created+distinct-OA-job / existing / invalid / unresolvable.

## #57 — Discoverable per-card delete

- **`10d_papercard.jsx`** — an **always-visible** `⋯` overflow menu per card (reuses the `.priority-pop`
  dropdown pattern — no new CSS) with **Move to Trash**. Keyboard-reachable + `aria-label`; Escape/outside-click
  close and return focus to the trigger; every handler `stopPropagation`s so it never selects/opens the card.
- **`03_library.jsx`** — one shared `trashPapers(ids)` primitive (confirm + soft-delete + selection/refresh
  cleanup); the bulk bar and the per-card menu both route through it, so single-item and batch can't drift.
  Reuses `DELETE /papers/{id}` (soft delete → Trash) — no backend change.

## Line cap (rule #1)

`40_app.jsx` was at the 600 cap; the #58 modal wiring tipped it over, so the six library add/import modal
renders moved to a new `40c_library_add_modals.jsx` (`LibraryAddModals`, shared-IIFE hoist).

## Live smoke test (release gate)

Ran the packaged flows against a fresh minimal DB via Playwright (Crossref reachable):
- **#57:** ⋯ always visible; Escape closes + refocuses trigger; click-isolated (card not selected); Move to
  Trash → confirm ("Move 1 paper to Trash…") → paper soft-deleted to Trash, library count 2→1.
- **#58:** Add with DOI is the first + Add item; URL-form + bare DOI normalized; real Crossref metadata
  resolved + created ("Why Most Published Research Findings Are False"); auto-OA started as a **distinct** job
  and **actually downloaded a real OA PDF** (paper got 1 attachment) — exercising #59's cascade end-to-end;
  re-adding surfaced "Already in your library — surfaced, not duplicated" (no re-fetch); garbage DOI → "That
  does not look like a valid DOI." (nothing added).

## Pre-existing issue found (NOT a regression; filed as a follow-up, not fixed in 0.5.9)

Trashing a paper that is currently **open** (its tab/citation preview mounted) leaves that preview calling
`POST /citations/render` with the now-trashed id → a benign `422 "No existing (non-trashed) papers to render"`
logged to the console. The backend correctly refuses; the paper is safely in Trash. This predates #57 (the
old bulk-delete path did the identical `setLibRefresh`/`setSelected`), is orthogonal to the delete affordance,
and fixing it (closing an open paper's tab on trash) is out of this patch's scope (steering #9).

## Gates

`tests/test_acquisition_cascade.py`/`test_doi_add.py`/`test_wanted.py`/`test_agent_writes.py` + affected
suites green (99+); frontend assembly 87; line budget OK; both ruff gates clean; QA route 56 (+40) extended
and `build_surface_map.py check` OK; security audit `2026-09-11_add-by-doi.md` PASS (the OA lane's structural
guarantees are unchanged, so #59 needed no new audit — same `OaLocation`/`download_oa_pdf` seam).

**Full-suite reconciliation** (`pytest -n 4`, 3030+ passed) surfaced five failures, all resolved:
- Two were mine: `test_retraction::test_oa_acquire_auto_checks_retraction` monkeypatched `acq.download_oa_pdf`
  (the router no longer imported it after the cascade refactor) → re-imported it and pass it explicitly to
  `acquire_first_working` so the router stays the injection seam; its fake `_Reg` also needed a `resolvers()`
  method for the cascade. `test_short_write_sweep` → updated `ALLOWED_RAW_COMMITS` (acquisition.py 0→1 for the
  by-doi endpoint's egress-mixed commit; agent.py 2→1 after the save_reference refactor).
- Two demo tests hit the changelog-drift review gate (my library-frontend edits are the first demo-watched
  source change since the inc-576 review, now 9 increments on) → recorded an explicit `--decline` on
  `demo/experience-coverage-v1.json`: the touched surfaces are demo-locked and change no showcased capability,
  and a full demo re-capture is out of scope for this patch (tracked, backlog #70).
- One (`test_website_how_it_works[demo/-target2]`) is a worktree-only env failure (unbuilt `dist-demo`); it
  passes once the demo is built, as CI does before pytest (`ci.yml`).

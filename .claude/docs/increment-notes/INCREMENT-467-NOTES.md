# Increment 467 — DEBIT consistency check (item #4 of the post-P2 backlog sequence)

## Implemented

Fourth item in the confirmed post-P2 backlog sequence (memory `callosum-next5-backlog-roadmap`). Backlog #44's
remaining "Increment 5" slice was originally phrased as "DEBIT/duplication analysis and perhaps a
collection-level z-curve" — research before design found the source doc
(`future-tracks/chatgpt5.5_future-tracks_integratinglakens.md`, item 5 "scrutiny") actually names three
**separate** things bundled under one increment number, not one feature. Disambiguated and scoped to
**DEBIT only** this increment (confirmed with Cliff):

- **DEBIT** (Heathers & Brown, 2019, "DEBIT: A Simple Consistency Test For Binary Data" — an unpublished OSF
  working paper, no DOI) tests whether a reported mean+SD+N for a **binary** (0/1) variable are mathematically
  consistent. Same deterministic, single-paper, user-entered, non-accusatory family as the already-shipped
  GRIM/GRIMMER (inc 127) — extends `app/backend/methods/grim.py` rather than a new file.
- **Duplicate-publication detection** and **z-curve** were deliberately *not* built here — duplicate-detection
  compares a paper's stats against *other papers/authors*, risking the APPROACH-AVOIDANCE standalone
  no-accusation boundary in a way DEBIT never does; z-curve is collection-level and needs LLM-assisted
  "focal statistic" extraction, which the source doc itself calls "more dangerous." Both filed as their own
  new backlog items (#54, #55), each flagged for its own Principles + APPROACH-AVOIDANCE pass.

### Backend

- `app/backend/methods/grim.py` — `debit_test()` + `DebitResult`. Reuses `grim_test` (binary data is the
  `items=1` case) to check the mean's own GRIM-consistency, then compares the reported SD against the
  theoretically-implied SD for binary data — `SD = sqrt(K(n-K) / (n(n-1)))` for the integer count K the mean
  implies — using the same rounding-tolerance treatment GRIMMER already applies to its own SD comparison.
- `app/backend/api/routers/methods.py` — `POST /methods/debit`, mirroring `POST /methods/grim` exactly (586
  lines total, still under the 600-line cap).
- New paper-aware saved-checks stack, mirroring inc 401's GRIM pattern file-for-file: `schema_debit_checks.py`
  (table `paper_debit_checks`, migration `0071`), `debit_checks_repo.py`, `methods_debit_saved.py`
  (`GET/POST /papers/{id}/debit-checks`, `DELETE /papers/{id}/debit-checks/{check_id}`), mounted in `app.py`.

### Frontend

`app/frontend/js/07_methods_grim.jsx` — a new `DebitSection` rendered as a second block within the existing
"Data" pane section (not a new tab), below `GrimSection`. Same form/save/list/delete shape as GRIM, with the
inc-401 paperId-reset fix (`useEffect` clearing the form/state on `paperId` change) applied from the start
rather than risking the same bug being rediscovered in new code. Credit block cites Heathers & Brown (2019)
with a link to the OSF page instead of a fabricated DOI; the section's one shared `<LakensCredit />` (DEBIT was
itself surfaced via Lakens' catalog) now renders once at the end of the whole Data section rather than once
per sub-tool.

## Key technical detail

For a binary (Bernoulli) variable with n observations and mean M = K/n (K the count of 1s), the sum of squared
deviations is exactly `K(1-M)² + (n-K)M² = K(n-K)/n` — pure algebra, no approximation — so the Bessel-corrected
sample SD is fully determined: `sqrt(K(n-K) / (n(n-1)))`. DEBIT computes this in closed form using the integer
K (never floating-point M directly) to avoid compounding rounding error, then compares against the reported
SD's own rounding-tolerance band (±half a unit in its last decimal place), matching GRIMMER's existing
treatment. `n < 2` is explicitly rejected (a sample SD is undefined for n=1) rather than silently dividing by
zero.

## Manual verification script

1. Open Methods → Data for any paper — confirm the new DEBIT mini-form (Mean / SD / N, no `items` field) below
   GRIM/GRIMMER.
2. Enter a consistent case (mean **0.500**, SD **0.527**, N **10**) → Check → confirm **consistent**.
3. Enter an inconsistent SD (e.g. **0.999** for the same mean/N) → confirm **impossible** with the binary-data
   caveat.
4. Save a check, confirm it appears in "Saved checks — this paper," switch to a different paper and back —
   confirm the form resets cleanly (no stale values) and the saved list is correctly paper-scoped. Delete it.
5. Confirm the credit block (Heathers & Brown 2019) links to the OSF page and "＋ add missing to library"
   imports a metadata-only paper without erroring on the missing DOI.

## Verification

Live-verified end-to-end via Playwright against the real 209-paper curated library (server restarted to pick
up the new backend code, since the dev server predates this session's edits and doesn't hot-reload):
- DEBIT compute (consistent + inconsistent cases), save, list, delete, and paper-switch reset all confirmed
  live via the real UI, with the saved record independently confirmed via `curl` at each step (never trusting
  the UI's own claim of success).
- The DOI-less "add missing to library" button successfully imported "DEBIT: A Simple Consistency Test For
  Binary Data" (Heathers & Brown 2019) as a metadata-only paper — confirmed via `GET /papers?q=DEBIT` — proving
  `find_existing_paper_by_identity`'s title/year/author fallback handles a DOI-less CSL-JSON record cleanly.
  The test paper was purged (`DELETE /papers/{id}/permanent`) after verification, matching this session's
  "clean up exactly what was created" convention.
- Zero console/page errors across every interaction (11 separate checks).
- `pytest tests/test_debit.py tests/test_debit_saved.py tests/test_health.py tests/test_grim.py
  tests/test_grim_saved.py tests/test_frontend_assembly.py -q` → **105 passed**.
- `python -m ruff check` / `ruff format --check` on every touched file → clean.
- `python tools/check_line_budget.py` → all files within the 600-line cap.
- `python tools/build_frontend.py` → clean build.
- `python tools/qa/build_surface_map.py check` → 0 uncovered API/FE surfaces (route 37 extended).
- `alembic upgrade head` against a fresh temp DB and against the real library DB (via server restart) both
  applied migration `0071_paper_debit_checks` cleanly.

**Tangential finding, not fixed (out of scope):** `alembic check` reports pre-existing drift on
`followed_authors.author_id`'s unique constraint (from inc 454, unrelated to this increment — confirmed by the
constraint name and table having nothing to do with DEBIT/GRIM/methods). Worth a small follow-up if it starts
blocking CI's own alembic-check gate; not introduced or touched here.

**CI caught a real line-budget miss.** The first push (commit `9288ca5`) failed CI's `lint-and-test` job: the
`schema.py` re-export line for `paper_debit_checks` pushed the file to 602 lines, 2 over the cap — the file was
already effectively at the ceiling before this increment, and the local `check_line_budget.py` run happened
*before* a later `ruff --fix` reorganized the import (both individually looked clean; the combination crossed
the cap and was never re-checked). Fixed by extracting `notes` + `annotations` (58 lines, a thematically
cohesive "user-attached paper content" pair) into a new `schema_annotations.py`, the same leaf-split pattern
this file has already used repeatedly (incs 137, 262) — `schema.py` 602→**556**. Re-verified: line-budget gate
clean, both ruff gates clean, 53 relevant tests (annotations + DEBIT + GRIM + health) passing. Lesson for next
time: re-run `check_line_budget.py` as the *last* step before committing, after any auto-fix tool has touched
a file near the cap — not just once mid-session.

## Security audit

`.claude/security-audits/2026-08-09_debit-saved-checks.md` — PASS. Mirrors the already-audited GRIM
saved-checks pattern (`2026-07-27_grim-saved-checks.md`) almost exactly; written explicitly to confirm the
mirroring rather than re-derive the threat model from scratch.

## Housekeeping

- `.claude/docs/INCREMENT-BACKLOG.md` / `INCREMENT-BACKLOG-DONE.md`: #44's DEBIT slice closed (moved to DONE
  per the new closure discipline); duplicate-publication detection and z-curve filed as new items **#54** and
  **#55** respectively, each flagged for its own Principles + APPROACH-AVOIDANCE pass before design.
- Memory `callosum-next5-backlog-roadmap`: item #4 closed; item #5 (Word/Docs parity kickoff) next.
- `.claude/CLAUDE.md`: counter bumped to 467; pytest count updated.

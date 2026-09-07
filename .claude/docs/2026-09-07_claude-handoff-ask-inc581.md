# HANDOFF — Ask query-planner + evidence-hygiene (inc 581), Rev 2

**For: a fresh Claude session (Cliff's alt account) continuing this arc. Paste this whole file as context.**
Last session ran low on usage mid-way through validation. Read `.claude/SCRATCH.md` first (shared
Claude↔Codex coordination + all DB/worktree locations), then this.

---

## What this is

Rev-2-approved implementation of a **bounded query planner + conservative H1a evidence-hygiene seam**
for **Synthesize → Ask**. A broad, multifaceted question ("synthesize the systems involved in X across
A, B, C…") used to embed as ONE vector, retrieve top-8, over-generate, and return "0 of 4 verified."
The fix: decompose into 3–6 facets, retrieve per facet, deprioritize (never delete) non-evidential
chunks via H1a, verify with the UNCHANGED verifier, assemble verified-first, and report honest per-facet
coverage. **Deadline: a real user demos this at lab meeting tomorrow.**

Design doc (read for full rationale + MUST/SHIP-IF/DEFER dispositions §20):
`.claude/docs/research/2026-09-07_ask-query-planner-next-day-scope.md`.
Frozen acceptance query: `.claude/docs/research/2026-09-07_ask-acceptance-frozen-query.md`.

## Current state: implementation COMPLETE on `main`, UNCOMMITTED, tests green, acceptance run pending

The working tree already contains all the code below (you don't need to re-write it). Verify with
`git status --short`. **Do NOT `git add` the pre-existing ` D .claude/docs/2026-08-*handoff*.md`
deletions — those are not mine.**

**New files:**
- `app/backend/summarization/query_planner.py` — `classify_breadth` pre-gate + `plan_query` (one
  egress-gated structured provider call) → `QueryPlan{scope, facets[3..6]{label,query}}`, strict
  validation, narrow fallback on any failure.
- `app/backend/summarization/faceted_pipeline.py` — `summarize_faceted`: `_load_article_pool` →
  `_faceted_retrieval` (ONE batched encode, per-facet vector search) → `_apply_hygiene_and_budget` /
  pure `_select_with_hygiene` (H1a deprioritization + dedup + per-paper(3)/per-facet/global(36) caps) →
  per-facet generation (existing generator) → ONE `_verify_candidates` → `_assemble` (verified-first,
  ≤3 verified/≤2 flagged per facet, 4-state coverage) → persist with coverage in `scope_ref_json`.
- `app/frontend/js/19c_facet_coverage.jsx` — `FacetCoverageStrip` (reuses `cite-status`/`synth-coverage`
  classes; green=supported, amber=unresolved; honesty caption).
- `tests/test_query_planner.py`, `tests/test_faceted_synthesis.py` — 27 pure-logic tests (all green).
- `.claude/research/ask_acceptance_newpath.py` — OLD-vs-NEW acceptance harness (mine).

**Modified:**
- `app/backend/summarization/pipeline.py` — extracted shared `_verify_candidates` +
  `_persist_verified_summary` (+ `_insert_summary` gained `extra_scope_ref`). Narrow path is
  behavior-preserving (proved: 41 existing summary tests green).
- `app/backend/persistence/chunk_structure_repo.py` — added `current_structure_roles(conn, chunk_ids)`
  (currentness-gated bulk role lookup; `{}` when absent/stale → hygiene no-ops).
- `app/backend/api/routers/summaries.py` — `_run_summarize_job` routes query-scope broad→`summarize_faceted`,
  narrow/sections/failure→existing `summarize_scope`; added egress-gated `_gated_complete` for the planner.
- `app/backend/api/routers/summaries_response.py` — optional `coverage: [FacetCoverageResponse]` from
  `scope_ref_json`.
- `app/frontend/js/20_synthesis.jsx` — renders `<FacetCoverageStrip>` (component moved to 19c for the
  600-line cap). `callosum-app.html` rebuilt.

**Verified this session:** 27 planner/faceted unit tests + `test_summaries.py` (17) +
`test_summarization`/`test_summarize_selected`/`test_frontend_assembly` (109) all pass. `ruff check`
clean, `ruff format` applied, line-budget OK (all <600). Cache key (`cache.py`
`synthesis_generation_cache_input`) includes `scope_ref`+`source_chunks` → the 6 per-facet calls don't
collide. `_gated_complete` means egress-off → planner falls back to narrow → question never leaves.

## IMMEDIATE NEXT STEPS (in order)

**1. Finish/redo the acceptance run (the background one likely died when the account switched).**
Corpus = a backfilled COPY of the demo library at `C:\Users\cliff\AppData\Local\Temp\ask_acceptance.sqlite`
(216 papers, `chunk_structure` backfilled, embeddings present — I made it; if gone, re-copy
`C:\Users\cliff\callosum-data\library.sqlite` and run
`python tools/backfill_chunk_structure.py --db-url "sqlite:///C:/Users/cliff/AppData/Local/Temp/ask_acceptance.sqlite"`).
Run (needs the Gemini key from `.env`; standing permission to use it):
```bash
CALLOSUM_ALLOW_DATA_EGRESS=1 python .claude/research/ask_acceptance_newpath.py --db-url "sqlite:///C:/Users/cliff/AppData/Local/Temp/ask_acceptance.sqlite" --out ".local/ask-acceptance-newpath.json"
```
Takes ~4–8 min (model load + 2 full pipeline runs + Gemini). Read `.local/ask-acceptance-newpath.json`.
**Compare NEW vs OLD** on: verified-synthesis usefulness, facet coverage, contributing-paper breadth,
evidence hygiene (`cited_evidence_role_distribution`), provenance, explicit gaps — **NOT raw claim
count.** OLD baseline (Codex, `...\callosum-codex-ask-baseline-20260907\.local\ask-next-day-acceptance\generation-summary.json`):
**7 claims → 2 verified / 5 flagged, 5 contributing papers**, pool included a references/table chunk.
NEW should show more verified claims across more facets/papers + cleaner cited evidence roles + coverage.

**2. Write the old-vs-new artifact:** `.claude/docs/research/2026-09-07_ask-acceptance-old-vs-new.md`
(the two metric columns from §11 of the design doc). If NEW under-covers facets because per-facet
generation over-generates (4–7/facet), consider the deferred **tier-3** change: a `claim_target=(1,3)`
in `integrations/gemini/generator.py::_prompt` (keep narrow default (4,7) byte-identical; the faceted
`scope_ref` can carry it). Only if clean.

**3. Live-verify on :8888 (the demo path):** `run-callosum.ps1` has **no `--reload`**, so **restart
the server** to load the new backend code (frontend already rebuilt). Ensure the demo DB has H1a for
hygiene — give Cliff / run:
```bash
python tools/backfill_chunk_structure.py --db-url "sqlite:///C:/Users/cliff/callosum-data/library.sqlite"
```
(cache-only/no-network/resumable; ~216 papers). Confirm provider = **Gemini** in Settings (Local AI is
`app_data_missing` on the dev server). Then in the UI run the frozen broad query and confirm: it routes
broad (facets planned), the coverage strip renders, verified claims lead, and the answer is materially
better than the old "0 of 4." Playwright MCP is available (ToolSearch `mcp__playwright__*`).

**4. Finish + commit.** Run `ruff format` on changed files, full `pytest -n auto -q` (retry `-n 4` if a
worker crashes — known flakiness). Write `INCREMENT-581-NOTES.md`. Commit to `main` (selective `git add`
of MY files only — do not touch the unrelated ` D` handoff-doc deletions). End-of-session commit+push is
the convention. Update `CLAUDE.md` (add the inc-581 Methods/Ask entry) if time.

**5. Deferred (per design §20, only if MUST-SHIP is solid):** tier-3 claim target, tier-4 flagged-claim
collapse UI, tier-5 per-citation `evidence_role` surfacing, H1b component provenance.

## Operational facts (also in SCRATCH.md — keep it updated for Codex)

- **:8888 demo DB** = `C:\Users\cliff\callosum-data\library.sqlite` (`run-callosum.ps1`), rev 0080,
  216 papers, covers the topic, `chunk_structure` = **0 rows** (backfill to enable hygiene).
- **Gemini** active in dev + desktop (egress on). Server needs **restart** for new code.
- **SCRATCH.md** is the shared Claude↔Codex handoff/coordination file — read + update it.
- Codex is producing the OLD baseline + a shared harness `ask_old_new_acceptance.py` in its worktree
  `...\callosum-codex-ask-baseline-20260907`; froze broad + 5 narrow queries at commit `7f47a1c`.

## Boundaries (standing)

- Don't touch the live **H1c-A3** worktrees/DBs or the **sealed H1c-A2** review packet.
- Read **copies** of any DB a Codex process may hold open (`baseline.sqlite`, `corpus.sqlite`); never
  mutate Codex's `baseline.sqlite`.
- Verifier thresholds are **untouchable**; hygiene is **deprioritize-not-delete**; no reconstructed
  evidence (H1c-A3 still validating); the ~7,500-PDF future corpus is out of scope.

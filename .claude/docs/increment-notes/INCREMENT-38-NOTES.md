# Increment 38 Notes — Axes increment 1: create & browse user-defined axes (supervised)

Exposed the already-built `app/backend/clustering/axis_scoring.py` engine as write endpoints + a
create/browse/score/correct UI. An axis is a named lens: the user writes a label + description, the
system embeds that text and scores every paper's similarity into three honest tiers (assigned ≥0.7 /
uncertain ≥0.5 / below-threshold, not stored). Supervised single-lens only — unsupervised clustering,
axis-as-synthesis-scope, and multi-pole axes are later increments.

## Endpoints added (`app/backend/api/routers/axes.py`)
- `POST /axes` `{label, description}` (label non-empty + ≤200; description ≤4000) → `create_axis`.
- `PATCH /axes/{axis_id}` (label/description) → `update_axis`; response carries recomputed `stale`.
- `DELETE /axes/{axis_id}` → `delete_axis` (CASCADE removes its nodes + assignments only).
- `POST /axes/{axis_id}/score` (202 + `{job_id}`) / `GET /axes/score/{job_id}` (poll) — async job.
- `POST /axes/{axis_id}/papers` `{paper_id}` (manual add) / `DELETE /axes/{axis_id}/papers/{paper_id}`.
- Extended reads (additive): `GET /axes` → `scored`/`stale`/`assignment_count`; `ClusterPaperResponse`
  → `status` (`assigned`/`uncertain`/`manual`) + `manual`.

## Key decisions
- **Async scoring** (mirrors the summarize job: `_AxisScoreJobStore`, `_run_axis_score_job`,
  `api.state.axis_score_jobs`). Scoring embeds the axis + the whole library + vector-searches → slow.
  **No LLM / no egress** — axis scoring is fully local (simpler than summarize).
- **`assignment_mode="absolute"`** passed to `score_axis` for the supervised single-lens path: the
  clean three-tier-by-threshold semantics (0.7/0.5) the product describes. The engine default
  `largest_gap` is a clustering heuristic reserved for unsupervised inc 2.
- **No migration.** Manual-vs-scored = `cluster_node_papers.confidence IS NULL` (manual) vs float
  (scored) — the column was already nullable; the scorer always writes a float. Staleness =
  `axis_score_state` reads the stored axis embedding's `(source_text_version, normalization)`,
  recomputes the current axis text-version with that normalization, compares (no embedding ⇒ unscored).
- **Re-score preserves manual adds** (the honesty contract — human overrides the embedding): the job
  snapshots manual paper_ids before `score_axis` (which wipes + rewrites scored assignments) and
  re-inserts (as NULL) any the recompute didn't re-assign. Rough edge: a scored paper the user manually
  *removed* may reappear after a re-score (a true exclusion-list is deferred).

## New reused-not-reimplemented helpers (`axis_scoring.py`, +~140 lines, file 545 total)
`delete_axis`, `ensure_axis_node` (public wrapper over `_ensure_cluster_node`), `add_manual_assignment`,
`remove_assignment`, `manual_assignment_paper_ids`, `restore_manual_assignments`, `axis_score_state`.
Scoring itself (`score_axis`/`_replace_axis_assignments`) is untouched.

## Frontend (`app/frontend/js/15_axes.jsx`, new; rebuilt to `callosum-app.html`)
New `AxesPanel` (a new ordered chunk between 10_ and 20_) owns the whole feature: "+ new" create form,
expand-to-browse (papers grouped/marked by tier with confidence shown honestly — assigned green,
uncertain amber, manual indigo-dashed with no score), a Score/Re-score action with a calm polling
progress state (mirrors `SynthesisPane`'s poll), an inline "+ add paper" library picker, per-paper
remove ×, inline edit, and delete-with-confirm. A stale axis shows an amber "description changed —
re-score" prompt. `Sidebar` (10_pdf_layer.jsx) now renders `<AxesPanel/>`; `App` (40_app.jsx) dropped
its old read-only axes state and passes `setSelected`/`selected` so clicking a paper opens its detail.
Build via `python tools/build_frontend.py`.

## Verification
- **pytest: 136 passed** (129 + 7 new axes tests; route-surface invariant updated). Hermetic via a
  dim-2 fake embedding model + `InMemoryVectorStore` driving cosine ≈ 1.0/0.6/0.0: a clearly-high paper
  → assigned, borderline → uncertain, far → below-threshold (not stored). Covers: tiers, stale-on-edit,
  re-score replaces + preserves manual, manual add/remove distinguishable, narrow cascade delete,
  graceful model-unavailable.
- **Live browser E2E** (`.local/axes_e2e/run.py`, real uvicorn + fake model + Chromium): create → score
  (1 assigned / 1 uncertain badge, far paper absent) → manual-add (manual badge) — **0 console errors**;
  screenshot confirmed the honest tiering. (Throwaway, gitignored.)
- Security audit: PASS (`.claude/security-audits/2026-06-17_axes-supervised.md`).
- No file under `app/`/`integrations/` exceeds 600 (axis_scoring 545, axes router 348, 15_axes.jsx 294).

## Manual check
Start the app → sidebar AXES → "+ new" → label + description → Create → expand → Score → watch the
calm progress, then see assigned/uncertain papers with confidence (far ones excluded) → click a paper
(detail pane) → "+ add paper" to manually add one (shows "manual") → edit description (axis goes
stale → "re-score" prompt) → Re-score (manual add preserved) → delete (confirm).

## Rough edges
- A scored paper the user manually removed can reappear on re-score (no exclusion-list yet).
- The in-process axis-score job store grows over process lifetime (same as the summarize job store).
- `_embedding_model`/`_vector_store` accessors are duplicated in `axes.py` (4 lines) rather than
  refactoring summaries' copies — a deliberate minimal-diff choice (a shared accessor is a future tidy).

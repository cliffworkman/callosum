# Increment 52 Notes — Suggest optimal axes (unsupervised discovery + coverage-with-diversity)

A blank axes panel is the new-user cliff. **Suggest optimal axes** mines the library's own embeddings
to propose a *diverse* set of candidate axes that **blanket the literature without duplicating each
other or the user's existing axes**, then lets the user curate + create the ones they like.

## Implemented

### Backend — `app/backend/clustering/axis_suggestion.py` (new; clustering + selection + LOCAL labels)
- `suggest_axes(conn, *, model, max_suggestions=6) -> list[SuggestedAxis]`:
  1. `< MIN_PAPERS` (6) → `[]`. Encode every paper in-memory (`paper_embedding_text` + `model.encode_texts`)
     and L2-normalize (numpy).
  2. `K = clamp(round(N/5), 2, 12)`; cluster with the (previously unused) `AgglomerativeAbstractClusterer`.
  3. Per cluster: centroid + representative papers (nearest the centroid). Singletons dropped.
  4. **Novelty** — drop clusters whose centroid is ≥ 0.6 cosine to ANY existing axis (`description or
     label`, encoded) → suggestions complement, never repeat.
  5. **Diversity (MMR-lite)** — greedily take the biggest clusters, skipping any ≥ 0.5 cosine to one
     already chosen, up to `max_suggestions`.
  6. **Local labels/terms** — c-TF-IDF over each cluster's papers (`tf·idf`, small stopword set): top ~6
     terms; label = top 1–2 terms title-cased.
- `apply_labels(suggestions, *, labeler)` — optional Gemini polish; **catches ANY failure per cluster
  (incl. `DataEgressDisabledError`) → keeps the local label**. Never raises → suggestion always works
  offline.

### Backend — Gemini + endpoint
- `integrations/gemini/axis_cluster_labeler.py` (new): `AxisClusterLabeler` protocol +
  `GeminiAxisClusterLabeler` — `label(*, titles, terms) -> {label, terms}`, **egress-gated before any
  genai import**, output JSON-parsed/deduped/capped (mirrors the term suggester). Exported from the package.
- `axes.py`: `_AxisSuggestJobStore` + `SuggestedAxisResponse`/`AxisSuggestJobResponse`; **`POST
  /axes/suggest`** (202 + job id) → `_run_axis_suggest_job` (clusters under one DB txn, then labels
  OUTSIDE it), **`GET /axes/suggest/{job_id}`**; `_axis_cluster_labeler` accessor. `app.py` injects
  `axis_cluster_labeler` + the suggest job store.

### Frontend — `17_axes_suggest.jsx` (new) + `15_axes.jsx`
- A **✨ Suggest** button in the axes controls row → `SuggestAxesModal`: POST then poll the job; render a
  card per suggestion = an **editable name** + **term chips selected-by-default** (these *define* the
  cluster — toggle off noise) + representative paper titles + a **Create axis** button (→ `POST /axes`,
  card marks ✓ created). Create several, then Done → the axes list reloads.
- CSS (token-only): `.axis-suggest`, `.suggest-item*` (reuse `.axis-modal*`/`.term-chip`/`.axis-input`/`.axis-btn`).

## Key technical detail
Local labeling is the always-available floor (offline, deterministic), so this endpoint **never 503s** —
unlike `/axes/suggest-terms` (which has no local fallback). Gemini is pure polish layered on top via
`apply_labels`, gated by the same `CALLOSUM_ALLOW_DATA_EGRESS` consent and degrading to local on any
failure. Suggestions are **ephemeral** (nothing persisted); the user creates axes through the existing
validated `POST /axes`, so re-suggesting after a create won't re-propose that now-covered theme.

## Manual verification script
1. Rebuild (`python tools/build_frontend.py`), restart uvicorn, hard-reload.
2. Click **✨** in the Axes panel → "Analyzing your library…" → cards appear (names + term chips +
   sample papers). Toggle a chip, rename, **Create axis** → ✓ created. Close → the axis is in the list.
3. Re-open ✨ → the theme you just created is no longer proposed (novelty filter). With
   `CALLOSUM_ALLOW_DATA_EGRESS=1` + a key, the names come back Gemini-polished; off → local terms.

## Verification
- **pytest: 179** (+5): returns diverse clusters; novelty filter; injected-labeler polish; egress-off →
  local (done, not 503); too-few-papers → empty. Route-surface invariant updated.
- **Live E2E** (`.local/suggest_axes_e2e/`, fake model, no network): ✨ → 2 curated cards → Create → axis
  appears in the list; **0 console errors**. Screenshot captured.
- **Audit:** `.claude/security-audits/2026-06-19_suggest-axes.md` → PASS.
- New module 143; `axes.py` 474; `17_axes_suggest.jsx` 91; `15_axes.jsx` 348 — all < 600. No new dependency.

## Backlog
Done: **suggest-optimal-axes**. Next queued: library multi-select + bulk delete (D, destructive → needs a
soft-delete/undo decision + plan); dedup (E); synthesis split (F); library merge (last); favicon
dark-swap; DESIGN.md `.btn-*` DRY; HELP viewer; SRI.

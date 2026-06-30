# Curated Axis (backlog A7) — design

**Status:** approved for implementation (brainstorm 2026-06-30).
**Design home:** `future-tracks/opus4.8_future-tracks_benchmarkrevisions.md` §A7 (decisions there are settled; this doc
is the per-item detail the backlog asked for).
**Scope:** decomposed into **SP1** (the curated-axis primitive, this spec's build target) + **SP2** (swap ↑/↓ for
drag-to-reorder — frontend-only follow-on, sketched at the end).

## Goal

An **axis populated by hand** rather than by keyword scoring — the bounded home for a genuinely arbitrary, ordered
working set ("the 12 papers for Aim 2, in citation order"). It stays an **Axis** (never a "folder"); the only
difference from a keyword axis is that its membership is hand-picked + hand-ordered instead of scored.

## Settled decisions (from §A7 — not re-litigated)

- Umbrella term stays **"Axis."** The curated variant is distinguished by a **subtle aesthetic cue** (a small icon by
  the label), never a loud "folder" label. Internally: *Curated* vs *Keyword* axis.
- A curated axis **hides the keyword + scoring UI** (cutoff flipper, Score button, 👁 hide-uncertain) and orders
  members **manually**; a keyword axis orders by fit.
- **Switching is bidirectional**, protected by the existing *manual-assignments-survive-re-score* guarantee, so a
  flip **never ejects hand-picked members**.
- **Flat for now** (no nesting; when nesting lands it is recursive *semantic* sub-axes, never manual folder-trees).
- **Tags are already pure labels** (free-form, filter + provenance + cosmetic color; no rating/score/container) — the
  coherence condition is already met; **no tag-side change**.
- **Reorder UX:** SP1 ships **↑/↓ buttons**; SP2 swaps them for drag-to-reorder (user decision, 2026-06-30).
- **Cue:** a small icon by the label (proposed **📌**; final glyph is the maintainer's call — a 1-char change).

## Architecture — `kind="curated"` + a `position` column (reuse the axis machinery)

A curated axis is a normal `axes` row with `kind="curated"`. Its members are the existing **all-`confidence IS NULL`
(manual)** rows on its single cluster node (`_ensure_cluster_node`), ordered by a **new nullable
`cluster_node_papers.position`**. Because **membership still lives in `cluster_node_papers`**, everything downstream
keeps working unchanged: the inc-63 synthesis scope filter (`GET /papers?axis_id=` subquery), the A6 drop-to-add
(`POST /axes/{id}/papers`), axis merge, the clusters endpoint, delete-cascade.

*Rejected:* a separate `curated_axis_members` table (forks membership → parallel plumbing in the clusters endpoint,
the A6 drop, the synthesis filter, merge) or a JSON `member_order` list on `axes` (denormalized; drifts from
`cluster_node_papers`; splits ordering from membership).

The "freeze" guarantee is **already built**: `axis_assignments.restore_manual_assignments` + the
`confidence IS NULL` = manual convention mean a curated axis is just the limit case — *all members manual, never
scored, with an explicit order.*

## SP1 — backend

### Migration (additive, guarded; the 0021 pattern)
- Add `position INTEGER NULL` to `cluster_node_papers` (schema.py Table + an `op.add_column` guarded by
  `inspect(bind).get_columns(...)`; no-op downgrade — 0001's `metadata.create_all` builds it on fresh DBs). NULL on
  keyword-axis rows (order stays `papers.id`); 0..n on curated members.

### Constants / kind
- `CURATED_KIND = "curated"` (alongside `MY_PUBLICATIONS_KIND`). `axes.kind` now ∈ {`standard`, `my_publications`,
  `curated`}. An allowlist (`CREATABLE_KINDS = {"standard", "curated"}`) gates the create/switch params (rule #3 — the
  kind value is never interpolated; `my_publications` is created only by its own resolver, never via these paths).

### Endpoints
- **`POST /axes`** gains an optional `kind` (default `"standard"`; must be in `CREATABLE_KINDS` else 422). A curated
  create is **label-only** (description optional, treated as a human note — it does NOT drive membership/scoring).
- **`PATCH /axes/{id}`** gains `kind` (in `CREATABLE_KINDS` else 422), implementing the bidirectional switch:
  - **Freeze (standard→curated):** read the axis's currently-**shown** members — *assigned* (`confidence >= cutoff`,
    `cutoff = axes.scoring_gain or DEFAULT_AXIS_CUTOFF`) **+ manual** (`confidence IS NULL`); demote all of them to
    manual (`confidence=NULL` via the existing upsert); assign `position` by their pre-freeze display order
    (assigned by confidence desc, then manual); **drop the below-cutoff (uncertain) rows** (they were never members —
    keeps *shown = frozen*, honoring A10). Set `kind=curated`. The description/terms are kept (so a later revert can
    re-score) but no longer drive membership. Idempotent (curated→curated is a no-op).
  - **Revert (curated→standard), warned in the UI:** set `kind=standard`; members are **kept** (the manual NULL rows
    survive); clear `position` (NULL); the axis is now *stale* (needs a re-score — fit order will replace manual
    order). Not blocked, not silent (the warning is a frontend confirm; the backend just performs it).
- **`PUT /axes/{id}/order`** `{paper_ids: [int, …]}` — set the manual order. Validates: the axis is curated (else
  422); `paper_ids` is **exactly** the set of the axis's current members (else 422 — no partial/foreign ids); writes
  `position = index` for each (bound params, rule #3). SP2's drag reuses this verbatim.
- **`POST /axes/{id}/papers`** (the A6 drop + manual add) — when the axis is curated, set the new row's
  `position = max(existing positions) + 1` (append at end); for a standard axis, `position` stays NULL (unchanged
  behavior). `add_manual_assignment` takes an optional `position`/`append` flag.

### Reads
- `repository.get_papers_for_cluster_node` (or the clusters endpoint) orders by `position` (NULLS last), then
  `papers.id` (stable tiebreak). Keyword axes (all `position` NULL) are unaffected (→ `papers.id`, as today).
- `AxisResponse` (kind already carried): for a curated axis report `scored=false, stale=false, scoring_gain` unused,
  `assignment_count` = member count, `uncertain_count=0`. `axis_score_state` short-circuits for `kind=curated`
  (never scored / never stale).
- `discovery/relevance.py` already excludes `my_publications`; extend the exclusion to `curated` (no query text → no
  axis-relevance highlight). Same one-line `kind NOT IN (...)` consideration anywhere axes are embedded/scored.

### Response models
- `ClusterPaperResponse` gains `position: int | None = None` (so the frontend can render + reorder). `AxisResponse`
  needs no new field (`kind` carries it).

## SP1 — frontend (`15_axes.jsx`, mirroring the `isMyPubs` pattern)

- `const isCurated = axis.kind === "curated";`
- **Hide** the `axis-rescore-row` (cutoff flipper + Score + 👁) for curated (exactly as `!isMyPubs` gates it today).
- **Cue:** a small icon prefixing the label (proposed 📌), mirroring the My-Pubs 📄 prefix.
- **Count badge:** a neutral style for curated ("N papers") — no scored-green / stale-amber (a curated axis has no
  scoring state). A small DESIGN.md note (a neutral badge variant).
- **Members:** rendered in **server (`position`) order** — for curated, skip the client tier-sort in `renderPapers`
  (which sorts assigned/uncertain/manual by confidence); render as returned. Each row gets **↑/↓** buttons (disabled
  at the ends) that compute the new id order and `PUT /axes/{id}/order`.
- **Drop-to-add** (A6) + **✕-remove** still work (append / `DELETE /axes/{id}/papers`).
- **Creation:** a small split on **"+ new"** → *Keyword axis…* (the existing `AxisEditModal`) / *Curated axis…* (a
  minimal name-only create → `POST /axes {label, kind:"curated"}`).
- **Switch:** a **Freeze** action on a keyword axis card (→ `PATCH {kind:"curated"}`, with a one-line "snapshots the
  current members, unlocks manual ordering" note) + a warned **Convert to keyword axis** on a curated card (a
  `window.confirm`: "needs search terms; replaces your manual order with fit order; members are kept" →
  `PATCH {kind:"standard"}`).

## Principles gate (run — aligned, non-triggering)

A curated axis is a **transparently human-authored, inspectable set** — "these are the papers I put here, in this
order." It strengthens, not strains, the charter: **#3 facts-vs-candidates** (a manual member is a human assertion,
visually + epistemically distinct from a scored candidate — exactly the existing manual/assigned/uncertain
distinction); **#9 defaults are the user's** (the user defines membership directly); **#7 no opaque score** (a curated
axis has *no* score at all). Freeze is an **explicit user act** (not an automatic drop of a signal); revert is
**warned, not silent** (#6-adjacent — no hidden loss). No A-A veto in play (no accusation / paywall / score). The
easier-but-misaligned path would be calling it a "folder" and letting it drift into a manual hierarchy — explicitly
declined (flat; the umbrella stays "Axis").

## Gates / acceptance (SP1)

- **No security audit** — a local additive column + local endpoints; no egress, no external fetch, no new dependency
  (the saved-searches / color-tags precedent).
- **Migration** head bumped (via `alembic_head()` in tests — never hardcode it).
- **QA route** — extend the axes route (`route_15_axes.md`) with: create-curated, freeze (members snapshot + uncertain
  dropped), reorder (↑/↓ → order persists), drop-to-add appends, revert (members kept / order lost / stale), and the
  honesty assertion (a curated axis shows no score/cutoff UI; never labeled "folder"). Surface map 0 uncovered.
- **pytest:** the freeze snapshot (assigned+manual kept, uncertain dropped, positions set); revert (members survive,
  position cleared, stale); `PUT /order` validation (422 on a foreign/partial id set, non-curated axis); add-to-curated
  appends; clusters returns position order; `axis_score_state` short-circuits for curated; create-curated 422 on a bad
  kind.
- **Acceptance:** a curated axis is creatable (name-only) + hand-populated (drop / manual-add) + manually ordered
  (↑/↓) + reorder persists; freeze and the warned revert both work with **no membership loss**; synthesis over a
  curated axis works unchanged (the inc-63 filter → select-all → summarize is membership-agnostic); the
  keyword/curated distinction is a subtle icon cue, never a "folder" label. Help corpus updated (`HELP-DOCS-SYNCED`).

## SP2 (follow-on, frontend-only) — drag-to-reorder

Replace the per-row ↑/↓ with HTML5 drag-to-reorder within the member list (the A6 drag primitive applied intra-list,
a new drop target = a list position), computing the new id order and calling the **same** `PUT /axes/{id}/order`. No
backend change. Its own small increment + QA-route step.

## Key code anchors (from the axes-subsystem map)

- `schema.py`: `axes` 306-319 (`kind` 315-316), `cluster_nodes` 321-332, `cluster_node_papers` 334-343 (composite PK,
  **no order column today**).
- `clustering/my_publications.py:42` `MY_PUBLICATIONS_KIND`; `_get_or_create_axis` 159-171 (the only kind-setter today).
- `axis_assignments.py`: `add_manual_assignment` 29-56, `restore_manual_assignments` 101-130, `axis_score_state`
  133-187, `manual_assignment_paper_ids` 80-98.
- `axis_scoring.py`: `score_axis` 149-191, `_replace_axis_assignments` 324-335 (DELETE-then-insert — why manual is
  restored after).
- `routers/axes.py`: `AxisResponse` 138-149, `ClusterPaperResponse`/`ClusterNodeResponse` 151-168, `_axis_cutoff` +
  the read-time tier split 347-382, `_cluster_paper_response` 532-550, the score-job freeze/restore orchestration
  419-429, `POST /axes/{id}/papers` 386, `DELETE …/papers/{id}` 403, `GET /axes/{id}/clusters` 348.
- `repository.get_papers_for_cluster_node` 588-600 (orders by `papers.id` — the read to extend).
- `15_axes.jsx`: `AxisItem` 59, the `isMyPubs` branch 60-71, the `axis-rescore-row` 156-167, the count badge 141-149,
  `renderPapers` client sort 89-114, the A6 drop handlers 117-124 + `dropPaper` 344-352, ✓/✕ routing 316-340.
- `14_axes_edit.jsx`: `AxisEditModal` 7 (keyword-oriented — a curated create bypasses its terms/suggest machinery).
- `discovery/relevance.py:54` (`kind != MY_PUBLICATIONS_KIND` — extend to exclude curated).

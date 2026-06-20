# Increment 44 Notes — Axis edit modal + title/term decoupling + click-to-open (backlog A + A′)

The first item off the post-inc-43 backlog. Consolidates the scattered axis forms into one **Edit Axis
modal**, makes the **title a cosmetic display name** (the *search vocabulary* is now a curated terms list),
and makes the axes panel a clickable library overview (clicking an article opens its PDF).

## Implemented

**Backend — `app/backend/clustering/axis_scoring.py` (one change, no migration)**
- `_axis_text` now embeds the **description only**, falling back to the label when the description is
  blank:
  ```python
  description = (axis["description"] or "").strip()
  return description if description else (str(axis["label"]) if axis["label"] else "")
  ```
  Going forward the modal always writes the vocabulary into the description (`prose\n\nRelated: <primary
  term>, <synonyms…>`), so the **title stops being the search query**. Legacy/label-only axes still score
  via the fallback. Staleness (`axis_score_state`) recomputes `_axis_text` → existing scored axes show
  stale → user re-scores (expected, no data loss). `POST /axes` / `PATCH /axes/{id}` / `POST
  /axes/suggest-terms` are reused unchanged — the frontend composes the description.

**Frontend — rebuilt `callosum-app.html`**
- **New `app/frontend/js/14_axes_edit.jsx` (`AxisEditModal`, 102 lines)** — one modal for create + edit:
  Title (cosmetic) · Description (prose) · **Terms** chips. "Search related terms" calls the inc-41
  suggester and appends suggestions **deselected by default** (the human opts in — model as aid, not
  crutch); **selected terms sort to the top**. Save composes the description and POSTs (create) or PATCHes
  (edit). Absorbs the old `AxisTermsModal`.
- **`app/frontend/js/15_axes.jsx` (448 → 357)** — "+ new" reveals a tiny **quick-name input**; Enter/`next →`
  opens the modal in create mode seeded with that name (title + first selected term). "edit" opens it
  prefilled (title=label; prose+terms parsed from the description). Removed `AxisCreateForm`,
  `AxisEditForm`, `AxisTermsModal`, the standalone "suggest terms" action, and the per-axis **`.axis-desc`
  preview** (terms live only in the modal). Collapsed `creating`/`editing`/`suggesting` state into one
  `editor`.
- **A′** — an axis paper's title click now calls `openPaper` → opens its PDF tab (and selects it). Threaded
  `onOpenPaper={openPdf}` App (`40_app.jsx`) → `Sidebar` (`10_pdf_layer.jsx`) → `AxesPanel`.
- `styles.css`: `.axis-quickname`; everything else reuses existing axis/modal classes.

## Key technical detail — what is embedded changed, not the schema

The decoupling is purely a change to **which stored text becomes the embedding query**: previously
`label + description`, now `description` (with a label fallback). No column, no migration — the terms
already live in the description via the inc-41 `Related:` convention; the modal just makes the primary
term the first entry and drops the title from the query. Proven by
`test_axis_scoring_keys_on_description_not_label` (label "anomalous" + description "borderline construct" →
the **borderline** paper is assigned, not the anomalous one) and the label-only fallback test.

## Manual verification script
1. `uvicorn app.backend.api.app:app --port 8080`; open `/` and **hard-reload** (frontend rebuilt; backend
   also changed → restart uvicorn).
2. "+ new" → type a name → Enter → the edit modal opens prefilled (name = title + one selected term).
3. "search related terms" → suggestions appear **unchecked**; tick the ones that fit (selected jump to
   top); add a custom term; Save.
4. The axis appears with **no description line** under it; expand → Score → confirm papers are matched by
   the **terms**, and renaming the title (edit) does **not** change scoring.
5. Click an article under the axis → its **PDF opens** in a tab.
6. Existing axes show "re-score" (stale) — re-score once.

## Verification
- **pytest: 147** (+2 decoupling/fallback tests; existing label-only + punctuation tests stay green via the
  fallback).
- **Live E2E** (`.local/axis_edit_e2e/`, fake model + suggester): quick-name → prefilled modal (title +1
  selected term) → search appends **deselected** chips (selected sorts top) → create → scored 2 papers →
  **no `.axis-desc`** → click paper opens a PDF tab (1→2). **0 console errors** through the local flow.
- **Security audit:** `.claude/security-audits/2026-06-19_axis-edit-modal.md` — **PASS** (no new
  endpoint/egress/ingestion/dependency surface).
- Line caps: `14_axes_edit.jsx` 102, `15_axes.jsx` 357, `axis_scoring.py` 598 — all < 600.

## Backlog
Item **A** + **A′** done (checked off in `.claude/docs/INCREMENT-BACKLOG.md`). NEXT per the queue:
**B** (tier-tag cleanup: remove ASSIGNED, ✓-confirm uncertain) + **C** (library focus-mode manual add),
then suggest-optimal-axes (now safe to build against the finalized axis model).

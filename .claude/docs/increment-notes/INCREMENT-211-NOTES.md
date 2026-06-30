# Increment 211 — A7 SP1: the Curated Axis primitive

## Implemented

The first build of backlog **A7 (Curated Axis)** — the last A-item, decomposed (design spec
`.claude/docs/specs/2026-06-30-curated-axis-design.md`) into **SP1** (this increment: the primitive + freeze/revert
+ ↑/↓ ordering) + **SP2** (drag-to-reorder, a frontend-only follow-on). A **curated axis** is an axis populated
**by hand** rather than by keyword scoring — the bounded home for an arbitrary, ordered working set ("the 12 papers
for Aim 2, in citation order"). It stays an **Axis** (never a "folder"); only its membership is hand-picked +
hand-ordered.

**Architecture:** a curated axis is a normal `axes` row with a third **`kind="curated"`**; its members are the
existing **all-`confidence IS NULL` (manual)** rows on its single cluster node, ordered by a new nullable
**`cluster_node_papers.position`**. Membership stays in `cluster_node_papers`, so synthesis (the inc-63 `axis_id`
filter), the A6 drop-to-add, and axis merge all keep working unchanged. The "manual survives re-score" guarantee
(`restore_manual_assignments`) means a curated axis is just the limit case — all-manual, never scored, with an order.

**Backend**
- **Migration 0028** — `cluster_node_papers.position INTEGER NULL` (additive + guarded + no-op downgrade; the 0021
  pattern). NULL on keyword axes → order stays `papers.id`.
- `axis_assignments.py`: `CURATED_KIND` + `CREATABLE_KINDS`; `append_member_position` (a new member → position
  max+1); `set_member_order` (validates the id set == current members, writes position by index); `freeze_to_curated`
  (snapshot assigned[≥cutoff]+manual → demote to manual + ordered, **drop the uncertain**, kind=curated);
  `revert_to_keyword` (members kept, position cleared, kind=standard); a curated short-circuit in `axis_score_state`
  (scored=False/stale=False/uncertain=0).
- `repository.get_papers_for_cluster_node` orders by `position` (NULLS last) then `papers.id`.
- `axis_scoring.create_axis(..., kind="standard")`.
- `routers/axes.py`: `kind` on `POST /axes` (allowlisted → 422) + `PATCH /axes/{id}` (the freeze/revert switch;
  standard↔curated only, never to/from my_publications); **`PUT /axes/{id}/order`** (422 on a non-curated axis /
  foreign id set); `POST /axes/{id}/papers` appends a position for curated; `ClusterPaperResponse.position`.
- `discovery/relevance.py` excludes `curated` (no query text → no axis-relevance highlight), like my_publications.

**Frontend** (`15_axes.jsx`, mirroring the `isMyPubs` pattern): `isCurated` hides the re-score row (cutoff/Score/👁);
a **📌** label cue; a neutral **`.is-curated`** count badge (quiet `--accent-soft` tint); members render in server
(`position`) order with per-row **↑/↓** (→ `PUT /axes/{id}/order`); drop-to-add + ✕-remove still work; a **📌**
toolbar button creates a curated axis by name; a **❄ Freeze** action on keyword cards + a warned **↩ Convert** on
curated cards. New CSS (`.axis-count-badge.is-curated`, `.axis-reorder`, `.axis-curated-hint`) — tokens only.

## Key technical detail

The freeze snapshot honors *shown = frozen* (A10): it keeps exactly the members the card displayed at its cutoff —
**assigned** (`confidence >= cutoff`) **+ manual** (`confidence IS NULL`) — demotes them all to manual, orders them
by their pre-freeze display order (assigned by confidence desc, then manual), and **drops the below-cutoff uncertain
rows** (they were never members). The reorder endpoint takes the full id list (not a move-delta), so SP2's drag
reuses it verbatim. Curated members render in server order *without* the client tier-sort (a curated row shows ↑/↓ +
title + ×, no tier/confidence — every member is a hand-pick, so the "manual" badge would be noise).

## Manual verification script

`HF_HUB_OFFLINE=1 python -m pytest tests/test_curated_axis.py -q` → 9 passed: the position column; manual-add
appends + ordered read; `set_member_order` writes + rejects a foreign id set; the order endpoint 422s on a
non-curated axis; freeze keeps assigned+manual / drops uncertain / orders / kind=curated; revert keeps members /
clears order / kind=standard; create-curated endpoint + bad-kind/my_publications → 422; PATCH freeze→revert keeps the
member. **Headed (no egress):** `.local/visual/drive_inc211_curated.py` — freeze a seeded axis → 2 members
(uncertain dropped) + 📌 + neutral badge + no scoring UI; ↓ reorder persists across reload; create a curated axis by
name; convert back → 📌 gone. 0 console/page/genai.

## Gates

- **pytest:** full suite green — **733 passed, 1 skipped** (+9 `tests/test_curated_axis.py`; `test_axes.py` updated
  for the additive `position` field).
- **ruff** check + format clean; frontend rebuilt; migration head **0028** via `alembic_head()`.
- **QA surface** — **145/145 API** (+1 `/axes/{id}/order`, claimed by the `/axes*` glob) **+ 689/689 FE, 0
  uncovered**; `route_15_axes.md` extended (curated step + the never-"folder" assertion).
- **No security audit** (a local additive column + local endpoints; no egress/fetch/dependency — the
  saved-searches/color-tags precedent). **No new dependency.**
- **Principles — aligned, non-triggering:** a curated axis is a transparently human-authored, score-free,
  inspectable set (#3 facts-vs-candidates; #7 no opaque score; #9 defaults are the user's); freeze is an explicit
  user act, revert is warned-not-silent; the declined easy path (a "folder" / manual hierarchy) stays declined
  (flat; the umbrella is "Axis"). **DESIGN.md** records the 📌 cue + `.is-curated` badge. **Help corpus** gained a
  "Curated axes" paragraph (`HELP-DOCS-SYNCED` → 211). Tags need no change (already pure labels).
- **Rule-#1:** `js/15_axes.jsx` ends at **551** (well under 600 — no split needed); `js/40_app.jsx` untouched (599).

## NEXT

**SP2 (frontend-only):** swap the per-row ↑/↓ for HTML5 drag-to-reorder within the member list (the A6 drag
primitive applied intra-list; reuses `PUT /axes/{id}/order`; no backend change) — its own small increment + a
`route_15` step. **This completes the A-list except SP2** (A9/A10/A8/A6/A5/A1/A3/A2/A7-SP1 all shipped). The
deferred **B-items** (MCP server, citation-context classifier, collaboration, OCR, mobile) remain larger, own design
passes.

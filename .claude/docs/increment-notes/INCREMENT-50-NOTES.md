# Increment 50 Notes — Axes manual-assignment cleanup (B) + library focus-mode add (C)

Two backlog items on the shared **manual-assignment** surface of the axes panel: (B) de-clutter the
tier tags + let the user **confirm** an uncertain paper, and (C) a **library focus-mode** to add the
papers the scorer missed. Manual = a human override stored as `confidence IS NULL`.

## Implemented

### Backend (`app/backend/clustering/axis_scoring.py`) — manual=NULL made authoritative + durable
The re-score flow deletes all assignment rows, re-inserts scored ones, then restores manual ids. Two
correctness fixes underpin B:
- **`add_manual_assignment` now upserts to NULL:** an existing *scored* row is `UPDATE`d to
  `confidence=NULL` (was a no-op). This is how **✓-confirm** works — `POST /axes/{id}/papers` on an
  uncertain scored paper demotes it to a manual (human-asserted) override.
- **`restore_manual_assignments` now forces NULL even when present:** a manual/confirmed paper that
  *also* re-scores above the floor is updated back to NULL instead of being skipped — so confirms
  **survive a re-score** (this also fixes a latent bug where a manual add that scored high silently
  reverted to scored). New tests cover both.

No new endpoint, route, migration, or egress; ✓-confirm + focus-mode Save reuse the inc-38
`POST`/`DELETE /axes/{id}/papers`.

### Frontend B (`app/frontend/js/15_axes.jsx`)
- `AxisTierBadge` renders **nothing for `assigned`** — the default good state is tag-free (just title +
  confidence). Tags now flag only non-default states: amber **uncertain**, dashed **manual** (honest
  human-vs-scorer provenance).
- `AxisPaperRow` shows a **✓** on uncertain rows → `confirmPaper` → `POST /axes/{id}/papers` → the row
  becomes manual. The × (remove) is unchanged.

### Frontend C (library focus-mode — staged, committed on Save)
- `40_app.jsx` owns the focus state: `focusAxis` `{id,label}`, `focusMembers` (fetched from
  `/axes/{id}/clusters` on enter), `focusPending` (paperId → "add"|"remove", staged). `saveFocus`
  loops the existing add/remove endpoints then bumps an `axisRefresh` nonce; `cancelFocus` discards.
- The axis card **＋** now calls `onEnterFocus` (threaded App→Sidebar→AxesPanel) and switches to the
  Library tab; the inc-38 in-card `AddPaperPicker` is **removed** (replaced by focus-mode).
- `PaperList` (center library) renders a **reminder card above the search bar** ("Adding to '<label>'
  · +N −M staged · Save/Cancel") and a per-row **+ add / ✓ in axis / ✓ staged / − staged** button
  (`onToggleFocusPaper`, `stopPropagation` so it doesn't select the row). `LibraryFrame` already
  spreads `libraryProps`, so the focus props flow through unchanged.
- `AxesPanel` reloads counts + the open axis's papers when `axisRefresh` bumps.
- CSS (token-only, per DESIGN.md): `.axis-confirm` (✓, green hover), `.focus-card` (reuses the
  `.axis-bulk-bar` accent recipe), `.paper-axis-add` (accent add → `.in` verified-green when a member).

## Key technical detail
`confidence IS NULL` is now the single, durable encoding of "human override." Both the immediate
confirm (`add_manual_assignment` upsert) and the post-re-score restore (`restore_manual_assignments`
force-NULL) guarantee it, so a confirmed/added paper can never silently revert to a scored tier.

## Manual verification script
1. Rebuild (`python tools/build_frontend.py`), restart uvicorn, hard-reload.
2. Score an axis → expand it: an **assigned** paper shows just its confidence (no tag); an **uncertain**
   one shows the amber tag + a **✓**. Click ✓ → it flips to **manual**. Re-score → it stays manual.
3. Click an axis **＋** → the Library shows the focus card; click **+ add** on a missed paper → **✓
   staged**, the count updates; **Save** → the paper joins the axis (manual); **Cancel** discards.

## Verification
- **pytest: 174** (+2: confirm-promotes-to-manual, confirmed-survives-re-score).
- **Live E2E** (`.local/axes_manual_e2e/`, deterministic fake model): no ASSIGNED tag; ✓→manual; focus
  card opens; staged add → Save → membership updated; **0 console errors**. Screenshot captured.
- **Audit:** `.claude/security-audits/2026-06-19_axes-manual-assignment.md` → PASS (no new surface).
- `15_axes.jsx` 386→332 (AddPaperPicker retired); `10_pdf_layer.jsx` 198→211; `40_app.jsx` 167→208;
  `axis_scoring.py` →537 — all < 600.

## Backlog
Done: **B** + **C**; the inc-38 `AddPaperPicker` is retired. Next queued: **B′** eyeball (hide
UNCERTAIN); suggest-optimal-axes; library multi-select + bulk delete (D); dedup (E); synthesis split
(F); library merge (last); favicon dark-swap; DESIGN.md `.btn-*` DRY; HELP viewer; SRI.

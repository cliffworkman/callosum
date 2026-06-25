# Design spec — "Statistics check" METHODS accordion section (inc 122)

**Date:** 2026-06-25 · **Status:** approved design → spec under review.
**Goal:** Relocate statcheck out of Settings (and the Details pane) into a dedicated **METHODS accordion section**
— the first real METHODS module on the inc-121 registry. Frontend-only; behavior + honesty posture preserved.

## 1. Decisions (from brainstorming)
- The METHODS pane gains a **"Statistics check"** section (`paneId:"methods"`, after DETAILS): DETAILS (order 10) ·
  STATISTICS CHECK (order 20).
- The section consolidates **both** statcheck surfaces — the **library-wide batch** (moved from
  `StatcheckSettings` in `35_settings.jsx`) **and** the **per-paper check** (moved from `StatcheckRow` in
  `25_detail.jsx`). Statcheck is removed from **both** Settings and Details.
- Removing `StatcheckRow` from `25_detail.jsx` relieves its pre-existing **625 > 600** rule-#1 violation.
- The library **"⚠ N flagged" chip** + the `?signal=statcheck-inconsistent` filter/banner stay **unchanged** (they
  are library affordances, not Settings).
- Name: **"Statistics check"** (matches today's label + the help corpus).

## 2. The new section — `app/frontend/js/06_methods_statcheck.jsx` (new chunk)

`registerPaneSection({ id: "statcheck", label: "Statistics check", paneId: "methods", order: 20, render })`.
A `StatcheckSection({ ctx })` component with two parts, top to bottom:

- **Library-wide (always available):** the `StatcheckSettings` body, verbatim — a "Check all papers" button →
  `POST /methods/statcheck/run` + poll `GET /methods/statcheck/run/{job_id}` (1.5s), the "N checked · **M** with
  inconsistencies" summary, and a **"Show flagged papers"** link → `ctx.onShowStatcheckFlagged`. On batch
  completion it calls **`ctx.onStatcheckRan()`** so the App refreshes the header chip count (see §4).
  The intro line (the "local, no AI … a list to review, not a verdict" caveat) moves with it.
- **This paper:** the `StatcheckRow` body, verbatim — when `ctx.selectedPaper != null`, a "Check statistics" button
  → `GET /papers/{id}/statcheck`, per-test rows (`r.raw` + `computed p = …` + a green/amber `.cite-status` pill,
  click → open the page via `ctx.onOpenPaper`), and the non-accusatory caveat. With no selection, a hint:
  "Select a paper to check its statistical reporting." The per-paper part needs the paper's **title** (for the
  page-open tab) + **chunk_count** (the `hasText` guard) — the section fetches `GET /papers/{id}` for the selected
  paper (the same lightweight call `DetailContent` makes) and passes them down.

Existing `.statcheck-*` / `.detail-statcheck` / `.settings-*`→ reuse; map any `.settings-*` classes used by the
batch block to the section's container (read DESIGN.md; tokens only, no new hex). The honesty caveats + the
non-ranking framing move **verbatim** (Principles posture preserved).

## 3. Removals
- `35_settings.jsx`: delete `StatcheckSettings` + its `<StatcheckSettings onShowFlagged=… />` render in
  `SettingsModal`, and drop the now-unused `onShowStatcheckFlagged` prop threaded into Settings.
- `25_detail.jsx`: delete `StatcheckRow` + its `<StatcheckRow … />` render in `DetailContent` (→ Details is pure
  bibliographic; re-measure: should drop well under 600).

## 4. App wiring (`40_app.jsx`)
- Add to `paneCtx`: `onShowStatcheckFlagged: showStatcheckFlagged` (existing handler) and a new
  `onStatcheckRan: () => api("/methods/statcheck/summary").then(r => { if (r.ok) setStatcheckFlagged(r.data.flagged || 0); })`.
- The inc-100 refresh effect was keyed on `settingsOpen` (the batch lived in Settings). Change it to a **mount-only**
  fetch (initial chip count); subsequent refreshes come from `onStatcheckRan` after a batch + the existing
  `showStatcheckFlagged` flow. (Keep the chip + signal-filter handlers as-is.)
- `SettingsModal` no longer needs `onShowStatcheckFlagged` (statcheck left Settings); the App keeps
  `showStatcheckFlagged` for the library chip + the section.

## 5. Backend / gates
- **No backend change, no migration:** every endpoint already exists — `GET /papers/{id}/statcheck`,
  `POST /methods/statcheck/run` + `GET …/run/{job_id}`, `GET /methods/statcheck/summary`,
  `signals_repo.store_statcheck`/`count_statcheck_flagged`.
- **Principles gate: non-triggering.** Statcheck's posture is preserved verbatim — counts never a composite score
  (#7), "prompt to look, not a verdict" + the no-accusation framing (#2, the A-A veto), inline-APA caveat ("a clean
  result isn't a clean bill", #6). This is a relocation, not a new claim/signal.
- **Rule #10 (QA):** recalibrate the routes referencing statcheck's old homes — `route_33_methods_statcheck.md`
  (now a METHODS-pane section, not Settings), and the statcheck touchpoints in `route_00` (Settings step),
  `route_30_detail_pane` (Details no longer has statcheck), `route_35_settings` (Settings no longer has it).
  Regenerate the surface map (FE checklist; no API change → gate stays green).

## 6. Files
- **New:** `app/frontend/js/06_methods_statcheck.jsx` (the section + registration).
- **Modify:** `35_settings.jsx` (remove StatcheckSettings), `25_detail.jsx` (remove StatcheckRow), `40_app.jsx`
  (paneCtx + refresh rewire), `styles.css` (only if a container class is needed; reuse existing), `.claude/DESIGN.md`
  (note statcheck as the first METHODS module under §5), `app/backend/help/help_content.md` (the "Checking
  statistics" section → new location), the QA routes above. Re-measure 25_detail.jsx (< 600 after removal).

## 7. Verification
- **pytest** (frontend-only — run it; the methods endpoints' tests are unchanged) green; `ruff` clean; rebuild
  `callosum-app.html`.
- **Headed Playwright (`:8097`):** the METHODS accordion shows **DETAILS · STATISTICS CHECK**; the Statistics-check
  section runs the library batch (summary + show-flagged → the library filter) and, with a paper selected, runs its
  per-paper check (per-test rows + caveat); **Settings no longer has** a Statistics-check block; **Details no longer
  has** a statcheck row; the library **"⚠ N flagged" chip refreshes** after a batch run.

## 8. Out of scope
Other METHODS modules (GRIM, p-curve, retraction), the findings/FACT-vs-CANDIDATE subsystem, any change to the
statcheck computation itself. Just the relocation of the existing surfaces into the METHODS section.

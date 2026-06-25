# Increment 122 — statcheck relocated to a METHODS "Statistics check" section

## Implemented

The first real **METHODS** module on the inc-121 pane registry. statcheck's two surfaces, previously split
across Settings and the Details pane, are consolidated into one dedicated METHODS accordion section.

- **New chunk `app/frontend/js/06_methods_statcheck.jsx`** — self-registers a METHODS-pane section
  (`registerPaneSection({id:"statcheck", label:"Statistics check", paneId:"methods", order:20})`, so it sits
  after DETAILS). It holds:
  - **`StatcheckLibrary`** — the library-wide batch, moved verbatim from `StatcheckSettings`: "Check all papers"
    → `POST /methods/statcheck/run` + poll `GET /methods/statcheck/run/{job_id}`, the "N checked · M with
    inconsistencies" summary, the "Show flagged papers" link. On completion it calls `ctx.onStatcheckRan()` to
    refresh the header chip.
  - **`StatcheckPaper`** — the per-paper check, adapted from `StatcheckRow`. The section only gets the paper id
    via `ctx.selectedPaper`, so it self-fetches `GET /papers/{id}` for the title + chunk_count, then runs
    `GET /papers/{id}/statcheck` on demand (per-test rows → page-open at region precision).
  - **`StatcheckSection`** — wraps both under "Whole library" / "This paper" eyebrows.
- **`40_app.jsx`** — added `refreshStatcheckChip` (a `useCallback` reading `GET /methods/statcheck/summary`);
  added `onShowStatcheckFlagged` + `onStatcheckRan` to `paneCtx`; rewired the inc-100 chip-refresh `useEffect`
  from `settingsOpen`-keyed to **mount-only** (the batch left Settings); dropped `onShowStatcheckFlagged` from
  the `<SettingsModal>` call site.
- **Removed** `StatcheckSettings` (`35_settings.jsx`) and `StatcheckRow` (`25_detail.jsx`) + their renders. The
  library **"⚠ N flagged" chip** + the `?signal=statcheck-inconsistent` filter/banner are unchanged.
- **QA (rule #10):** `route_33` now points `fe:` at `06_methods_statcheck.jsx` and reaches statcheck via the
  METHODS accordion; `route_30` dropped the per-paper statcheck step + its coverage (now route_33's alone);
  `route_32` clarifies statcheck rows live in the METHODS section. Surface check: 0 uncovered (88 API / 460 FE).
- Swept stray `app/frontend/js/*.jsx.tmp.*` atomic-write orphans (rule #5).

## Key technical detail

- **The section self-fetches the selected paper.** `paneCtx` carries only `selectedPaper` (the id), so
  `StatcheckPaper` does its own `GET /papers/{id}` for `title` + `chunk_count` (the `hasText` guard) rather than
  threading the full paper object — keeping the section self-contained (DETAILS already fetches the paper
  separately; the duplicate lightweight read is acceptable).
- **The chip refresh moved from `settingsOpen` to mount + `ctx.onStatcheckRan`.** The inc-100 effect refreshed
  the "N flagged" count whenever Settings closed (because the batch lived there). With the batch in the METHODS
  section, the effect now fires once on mount, and `StatcheckLibrary` calls `onStatcheckRan()` on batch
  completion to refresh it.
- **esbuild DCE:** the new section's components are referenced through the registered `render` closure (invoked
  at React render time), so they survive dead-code elimination once `PaneAccordion` renders the METHODS pane.
- **Honesty posture preserved verbatim** → **Principles gate non-triggering** (a relocation, not a new
  claim/signal): counts never a composite score (#7); "a prompt to look, not a verdict" + non-accusatory
  framing (#2 + the A-A no-accusation boundary); inline-APA caveat ("a clean result isn't a clean bill", #6);
  per-test rows open the page at `precision: "region"` (page-open, never a fake exact highlight). No backend /
  endpoint / migration / egress change.

## Manual verification script

1. Start the app (`:8097`, validation DB). The **METHODS** pane (right) accordion shows **DETAILS** and
   **STATISTICS CHECK**.
2. Open **Statistics check → Whole library** → **Check all papers**: it polls, then shows
   "N papers … · **M** with inconsistencies". If M>0, **Show flagged papers** narrows the library to the
   statcheck-inconsistent filter (banner shows); the library header **"⚠ N flagged" chip** reflects M.
3. Select a paper → **This paper** shows the paper title; **Check statistics** → per-test rows (verbatim stat +
   `computed p =` + green/amber pill) + the non-accusatory caveat; clicking a row with a page opens that page
   (region precision, no fake exact rect).
4. **Settings** → no "Statistics check" block. **Details** (DETAILS section) → no statcheck row.
5. DevTools network: **zero** requests to any `generativelanguage`/genai host; **0** console/page errors.

## Pytest

437 passed, 1 skipped (frontend-only increment; no backend/test code touched). `ruff` clean. Surface check
exit 0 (88 API / 460 FE, 0 uncovered).

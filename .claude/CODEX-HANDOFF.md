# Codex handoff — 2026-07-17 (≈3-hour window; Opus tags back in after)

You (Codex) are picking up **callosum** — a local-first, AI-assisted reference manager for scholarly PDFs. This is a
scoped handoff for a short unsupervised window. **Read `.claude/CLAUDE.md` in full first** — it is the authoritative
briefing (invariants, rules, commands, verification protocol). Everything below assumes you've read it.

## Ground truth / current state

- **Branch `main` is clean and pushed**, at commit `77fa7dd` (Increment **282**). **1237 pytest tests passing**
  (+1 skipped). Do NOT start on `main` — cut a feature branch (below).
- Recent increments (context): 279 overlooked-work lens (#37) · 280 workspaces two-level navigation (menu bar) ·
  281 short-write `run_write` sweep (the "database is locked" arc, complete) · 282 credit-the-lineage backfill (#8).
- Shell is **PowerShell** (Windows); a Bash tool is also available (POSIX). Dev server runs on **port 8888**
  (`uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8888`), not the default 8080.

## Hard rules for THIS session (read them twice)

1. **Work on a feature branch. Do NOT merge to `main` and do NOT push to `main`.** Commit incrementally on the
   branch and **leave it for review** — Opus will verify and merge on return. (Pushing the *branch* to origin as a
   backup is fine; merging to main is not.)
   `git checkout -b feature/workspaces-ux-polish`
2. **Verification is not optional and not to be claimed without running it.** Before you call anything done:
   - `python -m pytest` — the **full suite** (it takes ~24 min; run it, don't guess). Must be green.
   - `ruff check .` **and** `ruff format --check .` — CI runs **both**; both must pass. (Run `ruff format .` to fix.)
   - `python tools/check_line_budget.py` — the 600-line cap on `app/` + `integrations/` (`--no-verify` on commit
     skips the pre-commit hook, so run it yourself).
   - **After ANY `app/frontend/` edit:** `python tools/build_frontend.py` (rebuilds `callosum-app.html`), then
     `python -m pytest tests/test_frontend_assembly.py` must pass. Commit the rebuilt `callosum-app.html`.
3. **Do NOT touch the design invariants** (egress off-by-default gate; coordinate honesty exact/region/null;
   signal-not-verdict / no composite scores; evidence always shown). If a task seems to require it, stop and leave a
   note instead.
4. **Do NOT start #14 (permanent-delete-removes-the-PDF) or anything destructive / security-audit-gated.** Deleting
   user files needs a `.claude/security-audits/` gate + a confirmation flow — that's for the supervised session.
5. **No over-claiming.** If the suite didn't run, say so. If something is partial, say "partial." Opus will re-run
   the full suite + both ruff gates + read the diff against the invariants on return — accuracy now saves rework.
6. Keep diffs minimal (rule #7). Update `.claude/changes.md` + write an increment-notes file for real work (bump the
   increment number to **283**); keep `.claude/CLAUDE.md` current if you change architecture/conventions.

## The task: Workspaces UX polish (the inc-280 follow-ups)

Background: inc 280 replaced the center pane's flat tab strip with a **two-level navigation** — a **menu bar of
workspaces** *inside the center (Library) pane* (**Profile · Library · Discover · Extract** + right-aligned
**Help · Settings**) above per-workspace sub-tabs. Several tools **moved**: "Where to submit" → **Discover → Journals**;
"Funding Discovery" → **Discover → Funding**; "Effect-size converter" + "Meta-analysis reporting" → **Extract**;
Help/Settings → menu-bar center views (the `?`/`⚙` left the sidebar). Registry: `app/frontend/js/04b_workspaces.jsx`
(`registerWorkspace` / `registerWorkspaceTab` / `MenuBar` / `WorkspacePane`), mirroring `05_panes.jsx`. DESIGN note:
`.claude/DESIGN.md` §5.

Do these **in order**. **Task 1 is the safe, primary deliverable** (docs only). Only start Task 2 if Task 1 is done
+ verified and you're confident.

### Task 1 (PRIMARY — docs only, zero code risk): DESIGN.md §5 full rewrite

`.claude/DESIGN.md` §5 currently carries an **interim note** about the workspace menu bar (added inc 280) bolted onto
the older THEORY/METHODS accordion rubric. Rewrite §5 into ONE coherent section describing the **two navigation
dimensions**:
- **Menu bar = workspaces** (*what you're doing right now* — a mode you enter): Profile / Library / Discover / Extract
  + Help/Settings utilities. Outward-facing / generative / wide-output tools live here.
- **Side accordions = THEORY (left) / METHODS (right) = lenses on the current paper** (*evaluating the selected
  paper*): statcheck, Cite, Details, etc. Per-paper reasoning lives here.
- Fold the existing placement rubric ("place a tool by the user's COGNITIVE TASK") into this two-dimension model:
  *is it a mode (workspace) or a lens (accordion section)?* Keep the concrete recipes (the `.menubar` /
  `.workspace-*` tokens; sub-tabs reuse `.tags-srcfilter` + `.pane-tab` mount-but-hide; the accordion registry).
  Remove the "interim record / stage-4 task" framing — this rewrite IS that task.
- Keep it accurate to the shipped code (read `04b_workspaces.jsx` + `05_panes.jsx` + the §5 text before writing).
  **No CSS/code changes** — this is a documentation edit. Verification = it reads coherently + matches the code; run
  the full suite anyway to confirm nothing else drifted.

### Task 2 (OPTIONAL — small frontend; only if confident): a one-time "what moved" hint

For returning users re-finding a relocated tool, add a **dismissible, one-time** hint in the **Library** workspace
that points to where things moved.
- **Where:** at the top of the Library workspace body (`app/frontend/js/30c_frame.jsx::LibraryFrame`, above the
  frame-tabs or the list) — a thin banner, not a modal.
- **Copy (concise):** "New layout: 'Where to submit' + 'Funding' are now under **Discover**; 'Effect-size' +
  'Meta-analysis' under **Extract**; **Help** + **Settings** are on the menu bar." + a **Dismiss** (×) button.
- **One-time:** gate on `localStorage` key `callosum.workspaces-whatsnew` (reuse the existing `_loadLayout` /
  `_saveLayout` helpers from `04_layout.jsx`); once dismissed, never shows again. Show it only when NOT read-only.
- **Style:** reuse existing tokens/recipes (read `.claude/DESIGN.md` first, rule #8) — e.g. an `.axis-hint`-like
  neutral banner; **no new color semantics**, no new raw hex a token already names.
- **Verify:** `python tools/build_frontend.py`; add a small assertion to
  `tests/test_frontend_assembly.py` (the raw assembly contains the hint copy + the localStorage key); the assembly
  suite + full suite green. **Note in your handoff-back that the visual placement is UNVERIFIED** (no browser here) —
  Opus will eyeball it.

## When you're done (or the window ends)

- Leave the branch un-merged with clean commits. Append a short **"Codex session summary"** to the BOTTOM of this
  file: what you did, what you verified (with the actual pytest pass count + both ruff results), what's partial or
  unverified, and any blocker. Be precise — Opus reads this first on return and will re-verify against it.

---
## Codex session summary (fill this in)

Codex session summary — 2026-07-17

- **Branch:** `feature/workspaces-ux-polish`
- **Commits:** `c1bfa7f` (`docs: rewrite workspace navigation design`) plus this handoff-summary commit.
- **Done:** Task 1 complete. Rewrote `.claude/DESIGN.md` §5 into the two-navigation-dimension model: workspaces/menu
  bar = center-pane modes of work; THEORY/METHODS accordions = per-paper lenses. Preserved the shipped
  `04b_workspaces.jsx` / `05_panes.jsx` registry mechanics, placement rule, token recipes, mount-but-hide behavior,
  read-only hiding, and honesty/accessibility notes. Added `.claude/docs/increment-notes/INCREMENT-283-NOTES.md` and
  `.claude/changes.md` entry.
- **Not done:** Task 2 was not started. No frontend source, CSS, built HTML, or tests were changed for the optional
  one-time "what moved" hint.
- **Verification:** initial `python -m pytest` collection failed because the active Python environment lacked the
  optional `mcp` SDK. Installed `mcp_server/requirements.txt`, restored `starlette==0.45.3` to keep FastAPI in range,
  confirmed `tests/test_mcp_server.py` passes, then reran the full suite: **1237 passed / 1 skipped** in 18:50.
  `ruff check .` passed. `ruff format --check .` passed (`464 files already formatted`). `python
  tools/check_line_budget.py` passed (`all 342 application-source files within the 600-line cap`).
- **Unverified/partial:** no browser or frontend visual check applies to Task 1; no UI code changed. Optional Task 2
  would still need frontend build, assembly test update, full suite, and visual-placement caveat.
- **Blockers:** none. Pre-existing untracked files were left untouched: `.claude/funding-ui-pass-*.png` and `www/`.

Codex session summary update — Task 2 — 2026-07-17

- **Branch:** `feature/workspaces-ux-polish`
- **Commits:** adds the one-time workspace hint on top of `c1bfa7f` / `897c5ed`; see the final branch log.
- **Done:** Task 2 complete. Added a thin, dismissible Library workspace banner in `app/frontend/js/30c_frame.jsx`
  for returning users: "Where to submit" + Funding → Discover; Effect-size + Meta-analysis → Extract; Help +
  Settings → menu bar. Dismissal persists with `callosum.workspaces-whatsnew=1` via `_loadLayout` / `_saveLayout`.
  The banner is hidden unless `readOnly === false`, so it does not appear on read-only companions.
- **Files:** `app/frontend/js/30c_frame.jsx`, `app/frontend/styles.css`, rebuilt `callosum-app.html`,
  `tests/test_frontend_assembly.py`, `.claude/qa-routes/route_73_workspaces.md`,
  `.claude/docs/increment-notes/INCREMENT-284-NOTES.md`, `.claude/changes.md`, this handoff.
- **Verification:** `python tools/build_frontend.py` rebuilt `callosum-app.html`; `python -m pytest
  tests/test_frontend_assembly.py` **21 passed**; `python tools/qa/build_surface_map.py check` reported **0 uncovered
  API / 0 uncovered FE**; final full suite **1237 passed / 1 skipped** in 28:59; `ruff check .` passed; `ruff format
  --check .` passed (`464 files already formatted`); `python tools/check_line_budget.py` passed (`all 342
  application-source files within the 600-line cap`).
- **Unverified/partial:** visual placement is **UNVERIFIED** in-browser. Static/build/test coverage confirms the
  source and rebuilt artifact, but Opus should eyeball the banner above the Library tabs on desktop/mobile.
- **Blockers:** none. Pre-existing untracked files remain untouched: `.claude/funding-ui-pass-*.png` and `www/`.

Codex session summary update — Increment 285 — 2026-07-17

- **Branch:** `feature/workspaces-ux-polish`
- **Commits:** this increment's final commit is `feat: move discovery tools into search` on top of the earlier
  workspace-polish commits.
- **Done:** moved **Wanted**, **Gaps**, and **Overlooked** out of the Library header and into **Discover → Search** as
  primary buttons immediately after Search, preserving the existing app-level modals. Removed the standalone Discover
  **Feed** tab and embedded Feed below the Search contents/results. Updated the one-time layout notice, help corpus,
  DESIGN note, QA route, frontend assembly guard, increment notes, and rebuilt `callosum-app.html`.
- **Files:** `app/frontend/js/{04b_workspaces,09_placeholders,10_pdf_layer,30c_frame,30d_discover,30e_feed,40_app}.jsx`,
  `app/frontend/styles.css`, `callosum-app.html`, `tests/test_frontend_assembly.py`, `app/backend/help/help_content.md`,
  `.claude/DESIGN.md`, `.claude/qa-routes/route_73_workspaces.md`, `.claude/docs/increment-notes/INCREMENT-285-NOTES.md`,
  `.claude/changes.md`, this handoff.
- **Verification:** `python tools/build_frontend.py` rebuilt `callosum-app.html`; `python -m pytest
  tests/test_frontend_assembly.py tests/test_help.py` **35 passed**; `python tools/qa/build_surface_map.py check`
  reported **245/245 API** and **1143/1143 FE** covered; final `python -m pytest` **1237 passed / 1 skipped** in
  20:38 on the formatted tree; `ruff check .` passed; `ruff format --check .` passed (`464 files already formatted`);
  `python tools/check_line_budget.py` passed (`all 342 application-source files within the 600-line cap`).
- **Visual check:** Playwright desktop (`1440x1000`) confirmed Library no longer has Wanted/Gaps/Overlooked; Discover
  has Search/Journals/Funding only; Search shows Search/Wanted/Gaps/Overlooked as matching primary buttons; Feed is
  below Search. Playwright narrow (`390x844`) confirmed the action row wraps cleanly and Feed remains below Search.
- **Pending:** none after this commit is pushed.
- **Blockers:** none. Pre-existing untracked files remain untouched: `.claude/funding-ui-pass-*.png` and `www/`.

# Codex handoff — 2026-07-18 (session 3): Discover/Search/Synthesize IA + search sources & history

Picking up **callosum** with the maintainer (Cliff) **supervising live**. **Read `.claude/CLAUDE.md` in full first**
(invariants, rules, commands, verification, the four gates #8–#11). Everything below assumes you've read it.

## Git state — base on `feature/library-ux-polish`
- `main` has inc 283 (PDF section-labels) + the workspaces IA (284–287).
- **`feature/library-ux-polish`** (pushed) has inc 288–293 (Codex library-UX) + 294 (Reading-Queue priority strata +
  sync) + **295 (Feed: follow journals by title, Suggest-from-library, typeahead)**. This branch has the full current
  IA (Profile · Library · Synthesize · Discover · Work · Extract; Synthesize = Ask·Critique; Discover =
  Feed·Search·Journals·Funding). **Cut your branch from it:** `git checkout feature/library-ux-polish && git
  checkout -b feature/discover-search-synthesize`.

## Hard rules for THIS session
1. **Feature branch; do NOT push to `main` without Cliff's OK.** Commit incrementally; leave the branch for review.
2. **Verification is not optional and not claimed without running it:** full `python -m pytest` (~20 min) green;
   `ruff check .` **and** `ruff format --check .`; `python tools/check_line_budget.py`. After ANY `app/frontend/`
   edit: `python tools/build_frontend.py` then `pytest tests/test_frontend_assembly.py`; commit the rebuilt
   `callosum-app.html`.
3. **Gates (#8–#11):** read `.claude/DESIGN.md` before CSS (reuse tokens/recipes). **Principles (#9):** Search's
   contract is **"AI augments, never filters — the complete list is shown"** and Critical Read / Critique is
   **signal-not-verdict** — neither may regress. Add/extend a **QA route (#10)** per changed surface
   (`build_surface_map.py check` → 0 uncovered). Run the **experience pass (#11)** on each user-facing change.
4. **Do NOT touch the design invariants** (egress gate; coordinate honesty; signal-not-verdict; evidence shown).
5. **No over-claiming.** Report the real pytest count; say "partial"/"unverified" (esp. visual placement — flag what
   Cliff/Opus should eyeball). Minimal diffs; one increment-notes file + `changes.md` entry per increment (bump the
   number — next is **299**); keep CLAUDE.md current.
6. **Line-budget watch** (near-cap files you'll touch): `04b_workspaces.jsx`, `30d_discover.jsx`, `20_synthesis.jsx`,
   `40_app.jsx` — split with the shared-IIFE hoist precedent if one crosses 600.

---

## The list (group into a few increments)

### A. Search across selectable sources (a dropdown like the Feed's)
`GET /discovery/search` **already** fans out to a multi-source `SourceProvider` registry
(`app/backend/discovery/providers.py`) — Crossref + PubMed — and merges/dedups (results show `it.sources` pills). The
ask is to let the user **pick which source(s)**, not always-all.
- **Backend:** add an **optional `source` query param** to `GET /discovery/search` (`routers/discovery.py`) that, when
  set, restricts the fan-out to that provider; default = all (current behavior). Expose the provider list (a `kinds`/
  `source_meta`-style property on the registry, or a tiny `GET /discovery/sources`) — mirror the Feed registry's
  `source_meta` (`discovery/feed.py`).
- **Frontend (`30d_discover.jsx`):** add a source `<select>` in the searchbar (default **All**, then Crossref /
  PubMed / …) — reuse the Feed's `<select className="lib-sort">` recipe (`30e_feed.jsx`). Pass `&source=` to the
  fetch. **Keep the "AI augments, never filters — complete list shown" copy + the source pills** (Principles #9):
  choosing a source narrows *which providers are queried*, never AI-filters results.
- **QA:** extend the discovery search route for the `source` param.

### B. Re-separate Feed from Search — Discover = **Feed · Search · Journals · Funding**
Inc 285 embedded Feed *inside* Search. Undo that: Feed becomes its own Discover sub-tab again.
- `04b_workspaces.jsx`: register a **Feed** tab under `{id:"discover"}` (first, so the order reads Feed · Search ·
  Journals · Funding) via `registerWorkspaceTab` — render `<FeedPane .../>` standalone (the `embedded` prop on
  `FeedPane` was added in inc 285; render it un-embedded).
- `30d_discover.jsx`: remove the embedded-Feed block (the inc-285 in-Search Feed) so Search is just Search again.
- Keep the Wanted/Gaps/Overlooked launchers where they are (inc 285 put them in Search — leave unless Cliff says).
- **QA/help:** update `route_44_feed.md` / the workspace route + the help "menu bar" + Feed lines for the split.

### C. **Synthesize** workspace with **Ask + Critique** (move Critical Read in)
- `20_synthesis.jsx:567`: relabel the workspace `label: "Synthesis"` → **"Synthesize"** (match the active voice of
  Discover/Extract). Convert it from a single `render` into **two sub-tabs** via `registerWorkspaceTab({id:"synthesis"},
  …)`: **Ask** = the current `SynthesisPane`; **Critique** = Critical Read.
- Move Critical Read out of the METHODS accordion: `08x_methods_critical.jsx:158` is
  `registerPaneSection({id:"critical_read", paneId:"methods", order:40})` → change to
  `registerWorkspaceTab({id:"synthesis"}, {id:"critique", label:"Critique", order:20, hideInReadOnly:true, render})`.
  `CriticalReadSection` uses `ctx.selectedPaper` + `ctx.onOpenPaper` (in the workspace ctx) and
  `ctx.methodsOpen === "critical_read"` for its active-check — **adapt that** to the workspace's `active` 2nd render
  arg (the inc-280 MetaSection `methodsOpen` adapter is the precedent). Check `08y_critical_set.jsx` (the multi-paper
  "set critical review") — relocate/point it consistently.
- **QA/help/DESIGN:** update the workspace QA route, DESIGN §5 (Synthesize = Ask + Critique; METHODS loses Critical
  read), and the help menu-bar line.

### D. Clearable search history (recall previous results) — for **Search** and **Journals** — + clear an active search
New. NOTE: `saved_search_repo.py` is *named saved searches* (a different feature) — this is a lightweight **recent-
query history**.
- **Recall:** keep a per-surface recent-query history (start with `localStorage`, like `callosum.feedAutoRefresh`) —
  the last N queries; a small dropdown/list to **recall** (re-run) one, and a **Clear history** action. Apply to
  **Search** (`30d_discover.jsx`) and **Journals** ("Where to submit", `08e_methods_publishers.jsx` — its run
  inputs/results).
- **Clear active search:** a **Clear** (×) button on the active Search that resets the query + results list to empty.
- **Design choice to confirm with Cliff:** recall = *re-run the stored query* (simple, always fresh, tiny storage)
  vs *store & replay the actual past results* (literal "recall previous results", offline, but heavier). Recommend
  **re-run the query** unless Cliff wants stored results. Ask before building.
- **QA/experience:** history + clear are new controls → QA route + experience pass.

## When done / window ends
Leave the branch un-merged with clean commits (pushing the branch as backup is fine). Append a **"Codex session
summary"** to the BOTTOM of this file per increment: what changed, the **actual** pytest pass count + both ruff
results, what's partial/unverified (flag visual placements), any blocker. Opus re-verifies against it on return.

---

## Codex session summary — Group A Discover Search selectable sources — 2026-07-18

Branch: `feature/discover-search-synthesize`.

What changed:
- Completed handoff group A as Increment 296.
- Added `GET /discovery/sources`, returning registry-driven source metadata for the Search picker.
- Added optional `source=<kind>` to `GET /discovery/search`; omitted source preserves the prior all-provider fan-out,
  while a selected source queries only that registered provider. Unknown source kinds return 422.
- Extended `SourceRegistry` with `kinds`, `source_meta`, `get`, and `search_one`; Crossref/PubMed now expose display
  labels.
- Added a Discover → Search source dropdown using the existing `.lib-sort` recipe: **All sources**, **Crossref**,
  **PubMed**, and future registered providers.
- Preserved the honesty contract: source choice controls where to query, not AI filtering; the complete returned list
  is shown and source pills remain visible.
- Updated served help, route 43 QA coverage, security audit, increment notes, changelog, and rebuilt
  `callosum-app.html`.

Verification:
- `python tools\build_frontend.py` passed.
- `python -m pytest tests\test_discovery.py tests\test_frontend_assembly.py tests\test_help.py -q`: 65 passed.
- `python tools\qa\build_surface_map.py check`: API 248/248, FE 1141/1141, uncovered 0.
- `python -m pytest`: 1259 passed, 1 skipped in 1388.35s.
- `ruff check .`: passed.
- `ruff format --check .`: 464 files already formatted.
- `python tools\check_line_budget.py`: all 343 application-source files within the 600-line cap.

Partial/unverified:
- No browser smoke was run for the dropdown placement/state. Assembly/backend tests cover the data flow and labels;
  Cliff/Opus should visually spot-check Discover → Search with **All sources**, **Crossref**, and **PubMed**.
- Pre-existing uncommitted Feed/session-3 handoff changes were present before Group A started; I preserved them and
  kept Group A conceptually separate.
- Pre-existing untracked artifacts remain untouched: `.claude/funding-ui-pass-*.png` and `www/`.

Blockers: none.

---

## Codex session summary — Group B Feed restored as Discover sub-tab — 2026-07-18

Branch: `feature/discover-search-synthesize`.

What changed:
- Completed handoff group B as Increment 297.
- Re-separated Feed from Search inside Discover.
- Discover sub-tabs now render in this order: **Feed · Search · Journals · Funding**.
- `04b_workspaces.jsx` registers Feed as the first Discover tab and renders `<FeedPane .../>` standalone.
- `30d_discover.jsx` no longer embeds `<FeedPane ... embedded />` under Search results.
- Wanted/Gaps/Overlooked remain in Discover → Search as requested.
- Updated served help, DESIGN, route 44 Feed QA, route 73 Workspaces QA, placeholder commentary, frontend assembly
  guards, increment notes, changelog, and rebuilt `callosum-app.html`.

Verification:
- `python tools\build_frontend.py` passed.
- `python -m pytest tests\test_frontend_assembly.py tests\test_help.py tests\test_feed.py -q`: 57 passed.
- `python tools\qa\build_surface_map.py check`: API 248/248, FE 1141/1141, uncovered 0.
- `python -m pytest`: 1259 passed, 1 skipped in 1353.75s.
- `ruff check .`: passed.
- `ruff format --check .`: 464 files already formatted.
- `python tools\check_line_budget.py`: all 343 application-source files within the 600-line cap.

Partial/unverified:
- No browser smoke was run for the restored Feed sub-tab placement. Assembly tests cover registration/order and reject
  the old embedded Feed; Cliff/Opus should visually spot-check Discover shows **Feed · Search · Journals · Funding**
  and that Search no longer has Feed below its result list.
- Pre-existing untracked artifacts remain untouched: `.claude/funding-ui-pass-*.png` and `www/`.

Blockers: none.
---

## Codex update — 2026-07-18: Group C / Increment 298 complete

- Implemented **Synthesize** as the renamed center workspace label while preserving the internal `synthesis` id.
- Split Synthesize into registered sub-tabs: **Ask** for the existing synthesis pane and **Critique** for the single-paper Critical Read surface.
- Moved Critical Read out of the METHODS accordion; its active gating now comes from the workspace-tab `active` argument.
- Updated selection summarize to request **Synthesize → Ask** so a remembered Critique tab does not intercept summarize flows.
- Updated critical-set helper copy, served help, design notes, and QA routes for the new IA.
- Rebuilt `callosum-app.html`.

Verification:
- `python tools/build_frontend.py` — passed.
- Focused `python -m pytest tests/test_frontend_assembly.py tests/test_help.py tests/test_critical_review.py tests/test_critical_review_set.py -q` — 73 passed.
- `python -m ruff check .` — passed.
- `python -m ruff format --check .` — passed after formatting `tests/test_frontend_assembly.py`.
- `python tools/check_line_budget.py` — passed.
- `python tools/qa/build_surface_map.py check` — 248 API / 1141 FE, 0 uncovered.
- Full `python -m pytest -q` — 1260 passed, 1 skipped.

Handoff caveat:
- No browser smoke was run for the visual placement. Claude/Opus should eyeball the menu order and Synthesize tabs in the running UI, especially read-only behavior hiding **Critique**.

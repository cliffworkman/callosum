# Codex handoff — 2026-07-18 (session 4): continue the backlog

You (Codex) are picking up **callosum** with the maintainer (Cliff) **supervising live**. The loop that's working
well: you build a batch of backlog items; Opus reviews (build / tests / gates / invariants) and merges; Cliff steers.
**Read `.claude/CLAUDE.md` in full first** (invariants, rules, commands, verification, the four gates #8–#11).

## Base + git state
`main` is at **Increment 303** — it carries the whole recent run (workspaces IA · library-UX · reading-queue priority
strata · Feed-by-title · Discover/Synthesize · **fast pytest** · six misc UX fixes · mobile workspace switcher ·
navigation rubric cleanup). Cut your branch from it:
`git checkout main && git pull && git checkout -b feature/backlog-<short>`.

## The task — work `.claude/docs/INCREMENT-BACKLOG.md` top-down, but VERIFY first
The backlog's **"▶ AUTONOMOUS"** section is complexity-ordered (simplest first) — but it has **drifted**: several
items marked open are already shipped (e.g. **A5 "color tags" is done — inc 207** [`25b_tags.jsx` + `/tags/colors`];
the whole A1–A10 benchmark list is closed). So, per candidate:
1. **Pick** the next genuinely-open, autonomous-safe item (simplest first).
2. **Verify it isn't already shipped** — grep the code + `.claude/changes.md` + `INCREMENT-BACKLOG-DONE.md` before
   building. If it's already done, **mark it DONE in the backlog** (reconciling drift is real, valuable work) and
   move on. Don't rebuild shipped features.
3. **Build** the genuinely-open one as a single increment (bump the number — **next is 304**), honoring every gate.

### Concrete verified-open first picks
- **One-time workspace migration hint or alias** (inc-280 follow-up): returning users may still need a small hint for
  moved tools (Where-to-submit → Journals, Effect-size/Meta-analysis → Extract, `?`/gear → menu bar). Keep it light,
  dismissible, and browser-local if built.
- **Backlog verification cleanup:** A8 is closed-as-covered in inc 205, and A5 color tags shipped in inc 207. Do not
  rebuild either; their stale open bullets were reconciled in inc 303.
- **Reading-pane polish** (split-gated): a "fit page"/fit-height option, free-form note colors/labels, a
  scrollbar/minimap marker — but `30_viewer.jsx` is at the 600-cap, so **extract a low-coupling unit first** (the
  inc-176/182 pattern) before adding to it.
- Otherwise mine the AUTONOMOUS section + the method-track sub-items (backlog §§ ~265–745) for the next simplest
  un-shipped thing (verify-before-build each).

### Do NOT autonomously start these — leave a note for a supervised Opus/Cliff session
Anything gated or invariant-touching: **B1 SP2 — gated MCP writes** (own spec + the APPROACH-AVOIDANCE values pass +
per-write confirmation + a security audit); **RegCheck** (backlog "fraught — gated"); **#14
permanent-delete-removes-the-PDF** (destructive — security-audit + confirmation flow); anything that changes the
**egress gate / coordinate honesty / verification / signal-not-verdict** posture, or is **counsel-gated /
accusation-adjacent**. If a pick turns out to touch any of these, **stop and leave a note** rather than build.

## Hard rules for the session
1. **Feature branch; do NOT push to `main`.** Commit incrementally; leave the branch for Opus to review + merge.
2. **Verify with the NEW fast workflow (inc 300):** during dev run only the changed area's file —
   **`pytest tests/test_<area>.py -q`** (seconds), or **`pytest --testmon -q`** (auto-selects affected tests); before
   you call a change done, run the full suite **`pytest -n auto -q`** (~13 min, parallel) and it must be green. After
   ANY `app/frontend/` edit: `python tools/build_frontend.py`, then `pytest tests/test_frontend_assembly.py`, and
   commit the rebuilt `callosum-app.html`. Also `ruff check .` **and** `ruff format --check .`; `python
   tools/check_line_budget.py` (600-line cap).
3. **The four gates (#8–#11):** read `.claude/DESIGN.md` before any CSS (reuse tokens/recipes, no new hex);
   **Principles (#9)** for any claim/signal/judgment feature (read `.claude/PRINCIPLES.md` — signal-not-verdict,
   evidence shown, no opaque score); add/extend a **QA route (#10)** in the same increment per changed surface
   (`python tools/qa/build_surface_map.py check` → 0 uncovered); run the **experience pass (#11)** on each
   user-facing change; **credit-the-lineage** for any method-implementing feature.
4. **Security audit gate:** a new endpoint / external fetch / ingestion path / 3+-file feature opens a
   `.claude/security-audits/YYYY-MM-DD_<feature>.md` stub (end PASS or RISK ACCEPTED before done).
5. **No over-claiming:** report the real `pytest -n auto` pass count + both ruff results; say "partial"/"unverified"
   honestly (esp. visual placement — flag what Opus/Cliff should eyeball). Minimal diffs (rule #7). One
   increment-notes file + a `.claude/changes.md` entry per increment; keep `.claude/CLAUDE.md` current (bump BOTH the
   line-24 "Increment N / count" and the §"currently at N").

## When done / window ends
Leave the branch un-merged with clean commits (pushing the branch to origin as backup is fine). Append a **"Codex
session summary"** to the BOTTOM of this file per increment: what changed, the actual `pytest -n auto` pass count +
both ruff results, what's partial/unverified, any blocker, and **which backlog items you built vs. found
already-shipped (and marked DONE)**. Opus reads this first on return and re-verifies against it.

## Codex Session Summary — Increment 302 (2026-07-18)

- **Built:** top autonomous backlog item, mobile workspace switcher. `MenuBar` now takes the existing `mobile` flag; desktop still renders the horizontal workspace tab strip, while phone-width screens render a compact Workspace `<select>` grouped into Workspaces and Utilities. The bottom mobile nav remains only Library / Panels / Details.
- **Docs/coverage:** updated Help, DESIGN, route 73, route 00, frontend assembly guard, opt-in e2e smoke, backlog/DONE breadcrumbs, changelog, increment notes, and added `.claude/security-audits/2026-07-18_mobile-workspace-switcher.md` with PASS.
- **Verification:** `python tools/build_frontend.py`; `pytest tests/test_frontend_assembly.py tests/test_help.py -q` = 48 passed; `CALLOSUM_RUN_E2E=1 pytest tests/e2e/test_smoke.py -q` = 3 passed; `ruff check .`; `ruff format --check .`; `python tools/check_line_budget.py`; `python tools/qa/build_surface_map.py check` = 248 API / 1157 FE, 0 uncovered; `pytest -n auto -q` = 1264 passed, 1 skipped.
- **Environment note:** `pytest -n auto -q` initially could not run because `pytest-xdist` was absent. Installed `requirements-dev.txt`, then upgraded pytest/pluggy within the declared `pytest>=7.4,<9` range to satisfy the installed Playwright plugin. No repo dependency files changed.
- **Partial/unverified:** automated browser smoke covers the mobile dropdown switching and overflow. Human eyeball still recommended for real-content mobile proportions and desktop menu bar appearance.
- **Next backlog candidates:** inc 303 reconciled the DESIGN §5 rewrite and stale A8/A5 backlog drift. The one-time
  workspace migration hint is now the smallest user-facing follow-up. Reading-pane polish remains viable but requires
  extracting from `30_viewer.jsx` before adding features due the line cap.

## Codex Session Summary — Increment 303 (2026-07-18)

- **Built/reconciled:** docs-only navigation cleanup. `DESIGN.md §5` now states the canonical mode-vs-lens placement
  rule: center workspaces are broad modes of work; side panes are selected-paper lenses; THEORY/METHODS remain
  internal pane ids, not future product buckets.
- **Marked already-shipped:** A8 synthesis scope label is closed-as-covered in inc 205; A5 color tags shipped in inc
  207. Both stale open bullets were marked done in `INCREMENT-BACKLOG.md`, with breadcrumbs in
  `INCREMENT-BACKLOG-DONE.md`.
- **Verification:** docs-only, no frontend rebuild required; `ruff check .`; `ruff format --check .`; `python
  tools/check_line_budget.py`; `python tools/qa/build_surface_map.py check` = 248 API / 1157 FE, 0 uncovered;
  `pytest -n auto -q` = 1264 passed, 1 skipped.
- **Security:** no audit opened; no endpoint, egress, ingestion, dependency, secret, filesystem path, or shipped UI
  behavior changed.
- **Next backlog candidates:** one-time workspace migration hint/alias is the smallest remaining user-facing
  Workspaces-nav follow-up; reading-pane polish is next after a low-coupling extraction from `30_viewer.jsx`.

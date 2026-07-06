# Increment 264 — Autonomy harness: the 600-line-cap gate (backlog #20 ratchet step 1) + the drift it caught

**Type:** infra / harness (+ two behavior-preserving rule-#1 splits). The first piece of the autonomous-operation
safety layer: a fast, deterministic gate so neither a human nor an unattended loop can ship over-cap or lint-red.

## Context

The user chose to "lean on autonomy." The honest finding (see the survey plan): **hooks don't widen *what* can be
built autonomously — the backlog's `⛔ NEEDS CLIFF` cut line does. Hooks make the loop *safe*.** So step 1 is the
safety gate. Building it immediately proved its worth: on first run it caught **two files that had drifted over
the 600-cap** while the hand-maintained CLAUDE.md watch list stayed stale (`routers/axes.py` = 609,
`js/10_pdf_layer.jsx` = 604). A hard-blocking gate can't go green on a dirty tree, so clearing them *was* the
first job — exactly the mechanical, above-cut work the harness is for.

## Implemented

### 1. The gate
- **`tools/check_line_budget.py` (NEW):** fails (exit 1) if any `.py`/`.jsx` under `app/` or `integrations/`
  exceeds 600 lines (rule #1), printing the offenders; `--list` prints the 10 closest-to-cap files (the live
  watch list). Exempt by rule #1: `tests/`/`tools/`/non-code (never under `app/`/`integrations/`).
- **`tools/git-hooks/pre-commit` (NEW):** a plain, zero-dependency git hook running `ruff format --check .` +
  `ruff check .` + the line budget. Fast (~2–3s); the full pytest suite stays out (too slow for a commit hook).
  Installed via **`git config core.hooksPath tools/git-hooks`** (set locally; documented for fresh clones).
  Emergency bypass `--no-verify` (discouraged — CI still enforces).
- **`.github/workflows/ci.yml`:** a "Line budget" step after the ruff steps — the reliable backstop for a clone
  that didn't install the local hook.

### 2. The two splits it caught (behavior-preserving)
- **`routers/axes.py` 609→513:** the 14 request/response models + their field-cap constants (`AXIS_LABEL_MAX`,
  `AXIS_DESCRIPTION_MAX`, `DEFAULT_AXIS_CUTOFF`) → new **leaf** `routers/axes_models.py` (125). The leaf imports
  only pydantic/stdlib (nothing from `axes.py`), so `axes.py` re-imports the names with no cycle — the
  inc-137/inc-207 pattern. `datetime`/`Literal`/`Field` became unused in `axes.py` and were dropped (`BaseModel`
  stays for `AxisOrderRequest`).
- **`js/10_pdf_layer.jsx` 604→507:** the paper-card cluster (`ClipboardIcon`/`CheckIcon`/`PaperCopyButton`/
  `PaperCard`) → new `js/10d_papercard.jsx` (100). Plain function declarations that hoist across the shared
  esbuild IIFE, so `PaperList` + the My-Pubs tab call `PaperCard` unchanged — the inc-208/222 precedent. The
  rebuilt bundle is **byte-identical** (1,460,265 bytes), confirming zero runtime change.

## Key technical detail

The gate is the point, not the splits. A hand-maintained watch list in CLAUDE.md is a liability — it drifted
stale twice (inc 262 caught methods.py/schema.py; this caught axes.py/10_pdf_layer.jsx, both of which the prose
still listed as ~537/594). Moving the cap to a **computed check** wired into pre-commit + CI removes the drift
class entirely: `python tools/check_line_budget.py --list` is now the source of truth, and the CLAUDE.md watch
prose was retired.

## The autonomous loop (how to drive it, once the harness grows)

The gate makes a `/loop` over the **above-cut** backlog safe: each pass picks the top autonomous-eligible item →
plan → build → the pre-commit gate blocks a red commit → commit. The loop **stops at the cut line** (egress,
destructive paths, the Principles/values gate) and escalates. This increment is ratchet **step 1**; natural next
steps (each its own sign-off): a frontend-rebuild reminder hook (PostToolUse on `app/frontend/**`), the
`pre-commit` framework, and scheduling `tools/qa/supervisor.py` → the watched QA inbox.

## Verification

1. `tools/check_line_budget.py` — clean (282 files ≤600); pre-commit hook runs green on the tree.
2. `tests/test_axes.py` → 32 passed (the axes split); `python tools/build_frontend.py` clean + byte-identical
   bundle (the frontend split).
3. Full `pytest --ignore=tests/test_mcp_server.py` → **1055 passed, 1 skipped** (unchanged — behavior-preserving).
4. `ruff format` + `ruff check` clean.

## Pytest

**1055 passed, 1 skipped** (unchanged — no new tests; the splits are behavior-preserving and the tool script is
self-verifying).

# Increment 303 Notes — Navigation rubric rewrite + backlog reconciliation

Date: 2026-07-18

## Backlog Pick
- Picked the remaining top autonomous Workspaces nav follow-up after inc 302: rewrite `DESIGN.md §5` so the
  workspace migration has a canonical placement rule rather than an interim THEORY/METHODS note.
- Also reconciled two stale benchmark bullets encountered while checking the next item:
  - A8 was closed-as-covered in inc 205.
  - A5 color tags shipped in inc 207.

## What Changed
- `DESIGN.md §5` now starts with the mode-vs-lens rule:
  - Center workspaces are broad modes of work.
  - Side panes are selected-paper lenses.
  - `theory` and `methods` are internal pane ids, not product taxonomy for future placement decisions.
- The current center workspace map is listed explicitly: My Publications, Library, Synthesize, Discover, Work,
  Extract, Help, and Settings.
- The side-pane ordering guidance now says left pane / right pane instead of treating THEORY and METHODS as the
  primary user-facing architecture.
- `INCREMENT-BACKLOG.md` marks the DESIGN §5 rewrite shipped in inc 303, A8 closed-as-covered in inc 205, and A5 done
  in inc 207.
- `INCREMENT-BACKLOG-DONE.md` records the inc 303 reconciliation breadcrumbs.

## Verification Before Reconciliation
- A8: `.claude/changes.md` inc 205 explicitly says the requested synthesis scope label was already covered by the
  inc 145 pre-run scope note plus the inc 153 coverage readout, and that a literal "uncertain excluded" statement
  would be dishonest.
- A5: `.claude/changes.md` inc 207 documents the shipped color-tags work; code search confirmed `GET /tags/colors`,
  `POST /tags/{id}/color`, `TAG_COLORS`, schema color storage, frontend swatches, help text, and tag tests.

## Security
- No security audit opened. This is docs/backlog-only: no endpoint, egress path, ingestion path, dependency, secret,
  filesystem path, or shipped UI behavior changed.

## Experience Pass
- Persona: a future implementer deciding where a new tool belongs.
- Finding: transitional THEORY/METHODS wording still made side accordions feel like broad product buckets.
- Fix: the design guide now makes the decision hinge on the user's task: broad work mode versus compact selected-paper
  lens.

## Verification
- No frontend rebuild required; docs/backlog-only.
- `ruff check .` — passed.
- `ruff format --check .` — 465 files already formatted.
- `python tools/check_line_budget.py` — passed.
- `python tools/qa/build_surface_map.py check` — 248 API / 1157 FE, 0 uncovered.
- `pytest -n auto -q` — 1264 passed, 1 skipped.

## Revert
Restore the listed docs from git. No frontend rebuild is required.

# Increment 434 — Meta-Preregistration workspace relocation and consistency pass

**Date:** 2026-08-01
**Status:** implemented

## Outcome

The registration workflow now occupies a dedicated selected-paper workspace at **Synthesize →
Meta-Preregistration**, immediately after Critique. Transparency remains the local detector and source-evidence entry
point, with one compact handoff to the larger workflow. No registration links, versions, comparisons, or review state
changed shape.

## Architecture and interaction

- `registerWorkspaceTab` owns the new Synthesize tab at order 30; Critique remains order 20.
- App navigation sends the existing selected Library paper into that tab and does not retain a stale paper while a
  WIP manuscript is active.
- The tab reads paper/candidate/version/comparison state locally when opened. Discovery, acquisition, and comparison
  remain inside their existing explicit click handlers and gates.
- Transparency no longer mounts candidate, attachment, or crosswalk components. It retains preregistration-language
  detection, normalized reference evidence, source-page opening, and the workspace handoff.
- General UI structure reuses Settings primitives: cards, title/action rows, field labels, inputs, action rows,
  notices, a 14px card rhythm, and the standard radius. Candidate and paired-evidence cards retain only the semantic
  styling needed to express provenance, inspection flags, and two-document evidence.
- Desktop evidence remains side by side. At mobile width, evidence and source-control rows stack without losing an
  action or source.

## Epistemic and privacy boundaries

- This remains a crosswalk for human inspection, never a compliance/integrity/risk score or author judgment.
- “Not located” remains explicitly non-equivalent to absent.
- Opening Transparency or Meta-Preregistration performs no OSF/DataCite request, registration download, or comparison.
- No new external endpoint, payload, redirect, download path, content exposure, or credential behavior was added.

## Verification

- Frontend rebuilt with `python tools/build_frontend.py`.
- `tests/test_frontend_assembly.py tests/test_help.py`: **76 passed**.
- Dedicated real-browser consistency check: **1 passed** (tab order, computed Settings chrome equality, desktop/mobile
  overflow, mobile stacking, and zero console/page errors).
- Full parallel suite: **1779 passed, 1 skipped**.
- Ruff format/check, line budget, and diff hygiene: clean.
- Computed QA surface map: **351/351 API** and **1539/1539 frontend**, zero uncovered.

## Rollback

Revert Increment 434's frontend, tests, and documentation, then rebuild `callosum-app.html`. No database rollback is
needed. Preserve all registration links, immutable versions, comparison rows, evidence, notes, and review state.

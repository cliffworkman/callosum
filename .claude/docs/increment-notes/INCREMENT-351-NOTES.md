# Increment 351 — WIP manuscript workspace foundation and workflow

## Context

Library manages research inputs. WIP is now its sibling collection for unpublished research products, preserving
the existing frame and global workspace geometry.

## Implemented

- Additive migrations `0048` and `0049` for roots, manuscripts, files, activity, sections, tasks, and Library links.
- Bounded idempotent discovery, missing/restored identity, SHA-256 identity, one explicit primary file, trusted
  open/reveal, and remote/read-only denial.
- Permanent **Library · WIP** tabs, independent WIP browsing state, distinct badges/tokens, manuscript tabs/details.
- Open manuscript workspaces contain Overview, Structure, Tasks, Files, References, and Activity.
- A derived `researchContext` suppresses stale paper IDs and supplies WIP cues across all other workspaces.
- Served help, data contracts, design tokens, QA route 75, and the security audit were updated.

## Verification

- `pytest -n auto -q` — **1443 passed, 1 skipped**.
- Ruff/format, frontend build, 600-line budget, and QA map (**287/287 API surfaces**) pass.
- Headless Chromium at 1440x900 light/dark and 375x812: all six workspace views, no console/page errors, and no
  horizontal overflow.

## Scope boundary

Extraction-backed snapshots, check-run provenance/findings/staleness, richer reference search, dynamic-tab
persistence/reordering, and explicit moved-folder relinking remain later increments from the approved plan.

# Security audit — Axes manual-assignment cleanup + library focus-mode (increment 50)

**Date:** 2026-06-19
**Feature:** (B) drop the ASSIGNED tag + a ✓-confirm on uncertain axis papers; (C) a library
focus-mode to add/remove papers to an axis (staged, committed on Save). Files: `15_axes.jsx`,
`10_pdf_layer.jsx`, `40_app.jsx`, `styles.css`, `app/backend/clustering/axis_scoring.py`.

**Audit trigger:** gate #5 (a feature spanning 3+ files). **No** other trigger fires.

## Threat review
- **No new endpoint / route.** ✓-confirm and focus-mode Save both reuse the existing, already-audited
  inc-38 routes `POST /axes/{id}/papers` (validated: axis + paper must exist → 404 otherwise) and
  `DELETE /axes/{id}/papers/{paper_id}`. The route-surface invariant test is unchanged.
- **No new external fetch, no new file-ingestion path, no new auth, no new dependency, no migration,
  no egress.** Everything is local SQLite reads/writes through SQLAlchemy Core bound parameters.
- **Only backend change is internal logic** in `axis_scoring.py`: `add_manual_assignment` now upserts
  an existing scored row to `confidence=NULL` (the confirm), and `restore_manual_assignments` forces
  manual ids to NULL even when present (so confirms/manual-adds survive a re-score). No new input is
  accepted; `paper_id`/`axis_id` validation is unchanged. The `confidence` CHECK constraint
  (`NULL OR 0..1`) still holds (NULL is explicitly allowed).
- **Frontend** stages changes in React state and, on Save, loops the existing endpoints. A row button
  `stopPropagation`s so it can't trigger an unrelated select/open. No untrusted HTML is rendered.
- **Resource use:** focus-mode Save fires at most one request per staged paper (bounded by the library
  size); no unbounded loop. The library list is already paginated.

## Negative-path checks (run)
- `pytest` (174): existing manual-add + re-score tests still green; new `test_confirm_uncertain_paper_
  promotes_it_to_manual` (upsert) + `test_confirmed_uncertain_paper_survives_rescore` (the restore
  fix). Add/remove 404s on unknown axis/paper unchanged.
- Live E2E (`.local/axes_manual_e2e/`, fake model, no network): no ASSIGNED tag; ✓ promotes uncertain
  → manual; focus card opens; staged add → Save makes the paper a member; **0 console errors**.

## Result
**Security Audit: PASS.** No new attack surface — reuses validated endpoints; the only backend change
is internal upsert logic that keeps `confidence IS NULL` (= manual) authoritative and durable.

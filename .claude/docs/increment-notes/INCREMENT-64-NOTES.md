# Increment 64 Notes — Persistent "not a duplicate" dismiss (finishes inc-56 dedup)

The duplicate-detection scan (inc 56) flags likely-duplicate paper groups; you could open/delete/**dismiss**
a group, but a dismiss was **session-only** — re-running the scan re-flagged the same false positives (e.g. a
preprint + its published version that are legitimately two records). Now "not a duplicate" **sticks**.

## Implemented
- **Schema + migration `0006`** (idempotent, head `0005`→`0006`): `dismissed_duplicate_pairs` —
  `(paper_id_low, paper_id_high)` FK→papers (CASCADE), canonical `low < high` (CheckConstraint), unique. A
  pair is stored once regardless of order.
- **`repository.py`**: `get_dismissed_duplicate_pairs(conn) -> set[(low,high)]`; `dismiss_duplicate_pairs(conn,
  pairs)` (bound-param `INSERT OR IGNORE` — re-dismissing is a no-op).
- **`duplicate_detection.py::find_duplicate_groups`**: after the three layers assemble candidate `pairs` and
  **before** the union-find, drop any pair whose canonical `(min, max)` is dismissed. A dismissed pair no
  longer links its two papers → the group never re-forms (even if a stronger signal would otherwise connect
  them — "not a duplicate" is the user's adjudication).
- **`POST /papers/duplicates/dismiss`** (in `routers/duplicates.py`): body `{paper_ids}` (the group). Filters
  to existing live papers, requires ≥2 (else 422), stores **every canonical pair within the group** (so a
  ≥3-paper group never re-forms), commits, 204. Registered before `/papers/{paper_id}`.
- **Frontend** (`19_duplicates.jsx`): the dismiss button keeps the immediate session-hide AND fires
  `apiPost("/papers/duplicates/dismiss", { paper_ids })` (fire-and-forget). Tooltip → "Not a duplicate —
  won't be flagged again." Rebuilt `callosum-app.html`.

## Module split (rule #1, behavior-preserving)
Extending dedup pushed `routers/papers.py` to **636 lines** (> the 600 cap). The cohesive duplicates concern
(the dedup models + `_DedupJobStore` + the scan/status/dismiss endpoints + `_run_dedup_job`/`_embedding_model`)
was **moved verbatim** into **`routers/duplicates.py`** (157), bringing `papers.py` to **497**. `app.py`
imports `_DedupJobStore` from the new module and includes `duplicates.router` **before** `papers.router` so
`/papers/duplicates*` still wins over `/papers/{paper_id}`. No behavior change.

## Verification
- **pytest: 228** (+1 dedup-dismiss test): seed a shared-PMID pair → scan flags 1 group; dismiss → re-scan
  flags **0** (persistent); re-dismiss (any order) idempotent; <2 existing ids → 422. Migration-head asserts
  bumped to `0006`; route-surface invariant +`/papers/duplicates/dismiss`. The full suite stays green through
  the module split (the dedup endpoints now serve from `routers/duplicates.py`).
- **Live E2E** (`.local/dedup_dismiss_e2e/`): scan flags the pair → **dismiss** → close + reopen the modal
  (fresh scan) → **"No likely duplicates found."** (the dismissal persisted), 0 console errors; screenshot.
- Audit: `.claude/security-audits/2026-06-20_dedup-dismiss.md` — **PASS** (local-only, non-destructive,
  bound-param SQL, validated input).

## Backlog
**Persistent dedup-dismiss — DONE (inc 64).** Deferred (noted): a "manage dismissals" / **un-dismiss** UI
(today a dismiss is permanent with no in-app undo — low risk: it only suppresses a future flag, deletes
nothing); per-pair (vs whole-group) dismissal granularity.

# Increment 97 — statcheck as a library-wide lens

The patter's **carrot** (chores = inc 96). Turns inc-95's per-paper statcheck into a **library triage tool**:
batch-check every paper, persist a summary, and **filter the library** to "papers where a reported p-value
didn't recompute." Reuses the inc-95 engine unchanged; deterministic, local, no-LLM.

## Principles / values gate (rule #9 — aggregation is where it bites)
Persisting + aggregating a signal to a library surface risks reading as a rank / "bad papers" list. Honored:
- **#7 no opaque score + the *divergent* "scoring temptation":** the library view is a **FILTER**, not a rank —
  papers are **not** sorted/scored by inconsistency count; the persisted row stores a `status` + honest counts,
  **no composite "reproducibility score."**
- **#2 signal-not-verdict + the veto-level "no accusation":** framed "papers with reporting inconsistencies — a
  list to review, usually innocent (typos/rounding/one-tailed), not a verdict." No "unreliable/problem papers."
- **#3 facts / #8 inspectability:** the persisted summary is a deterministic FACT; clicking a flagged paper opens
  its inc-95 Details statcheck section (the per-test evidence). The row carries only the count/flag.
- **#6 coverage:** the batch reports "N papers with statistics checked of M total"; absence from the flagged list
  ≠ clean (inline-APA only). The declined easier path: a sortable score column + a "problem papers" ranking.

## Implemented
- **`app/backend/persistence/signals_repo.py`** (NEW; first reader/writer of the pre-built `open_science_signals`
  table — no migration): `store_statcheck` upserts **one summary row per paper** (`signal_type="statcheck"`,
  `source="statcheck"`, `status = inconsistent` iff any test flagged else `consistent`, counts in
  `evidence_snippet`) via `insert(...).prefix_with("OR REPLACE")` on the `(paper_id, signal_type, source)`
  unique constraint (idempotent re-runs); `get_statcheck_summary`.
- **`repository.py`** — `list_papers(signal=…)` + a `SIGNAL_FILTERS` allowlist (`"statcheck-inconsistent"` → a
  bound IN-subquery on `open_science_signals` where status='inconsistent'; unknown → ignored; rule #3),
  composing with the existing clauses; + `list_live_paper_ids` for the batch.
- **`routers/methods.py`** — async **`POST /methods/statcheck/run`** + `GET …/{job_id}` (JobStore
  `statcheck_jobs`); `_run_statcheck_all_job` iterates live papers → `run_statcheck` → `store_statcheck`, summary
  `{total, checked, flagged}`. **`papers.py`** — a `signal` query param on `GET /papers`.
- **Frontend** — Settings gains a **"Statistics check"** section (`StatcheckSettings`, mirrors `MyPubsSettings`):
  **Check all papers** → batch run → "N checked · M with inconsistencies" → a **"Show flagged papers"** link
  (`onShowStatcheckFlagged`) that sets `librarySignalFilter` + closes Settings. A new mutually-exclusive library
  **view** (`40_app.jsx`, clears trash/axis/tag/needs-review/focus like the others) + a clearable `.focus-card`
  banner (`10_pdf_layer.jsx`) with the non-accusatory copy. Rebuilt `callosum-app.html`.

## Key technical detail
The **batch run is the only persister; the per-paper GET (inc 95) stays read-only/live** — so the library facet
reflects the last batch run (re-run to refresh; a paper edited afterward is stale until then). A summary row is
stored for *every* live paper (even no-stats ones, as `consistent` with `checked:0`) so a re-run refreshes all
and the filter (status='inconsistent') stays correct; the snippet's `checked` count disambiguates "no stats"
from "all consistent." OR REPLACE means a row is never duplicated. No migration (the table existed since 0001).

## Manual verification script
1. Settings → **Statistics check → Check all papers** → "N checked · M with inconsistencies."
2. If M>0, **Show flagged papers** → the library shows only flagged papers + the banner; click one → its Details
   **Statistical reporting** section shows the offending tests; **clear** restores the full library.
   _(Visual check delegated to the user.)_

## Pytest
**408 passed, 1 skipped** (+3 in `test_statcheck.py`: `store_statcheck` OR-REPLACE upsert + status-flip + single
row; `list_papers(signal=…)` filter + unknown-ignored; the batch endpoint → `{total,checked,flagged}` → the
`?signal=` filter returns only the flagged paper + a 404). `ruff` clean; audit
`.claude/security-audits/2026-06-21_statcheck-library.md` **PASS**. No migration, no egress, no new dependency.

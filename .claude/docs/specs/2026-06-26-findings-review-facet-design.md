# Activate the candidate-review half — statcheck candidates + a unified "N to review" facet (inc 133)

**Goal:** Give the inc-130 candidate-review machinery (Confirmed / Accepted / Noted) real content + a library-wide
place to triage it. (1) the statcheck batch emits **candidate findings**; (2) a unified **"N to review"** library
chip + filter surfaces every paper with an unreviewed candidate (across all producers).

## Why / gates

- **Principles** — aligned, run inline. A statcheck candidate is *a prompt to look, reviewable* (the inc-95/97
  framing) — signal-not-verdict, no opaque score, no accusation. The facet is a **work-state queue** ("have I
  looked?"), not a quality rank. Declined: a "reproducibility score" / ranking. Coexists with the statcheck
  **signal** (a fact about the paper) — the signal persists regardless of review (fact vs work-state, principled).
- **No new endpoint, no external fetch, no migration** (reuses `paper_findings` + the existing batch + a query
  param) → no audit-gate trigger. Local, no egress, no LLM. Rule #10: update the QA routes.

## Architecture

### 1. statcheck → candidate findings (`methods.py::_run_statcheck_all_job`)

The existing batch already writes the **signal** (`store_statcheck`, inc 97) — keep it. Now it **also** emits a
candidate finding per paper via `upsert_findings(conn, paper_id, "statcheck", …)`:

- **flagged** (inconsistent + decision_errors > 0) → one candidate:
  `{kind:"candidate", tier:"primary", payload:{desc:"N statistical reporting inconsistencies (statcheck) — review",
    inconsistent, decision_errors, checked, page}}` where `N = inconsistent + decision_errors` and `page` = the
  page of the **first flagged** result (`report.results` — for the card's "show in paper" at region precision).
- **not flagged** → `upsert_findings(conn, paper_id, "statcheck", [])` (supersede any prior candidate — a paper
  that re-checks clean drops out of the review queue).

Idempotency falls out of `upsert_findings`'s `content_key`: same counts → same key → the review state is
**preserved** across re-runs; changed counts → a new (unreviewed) candidate re-surfaces; clean → superseded. So a
Noted paper stays Noted on a re-run with the same result, and doesn't nag.

The candidate uses the inc-130 contract verbatim — the Review-pane `FindingCard` (Confirmed / Accepted[reason] /
Noted + "show in paper · p.N") and the per-card "N to review" badge already render it; no UI work for the card.

### 2. The unified "N to review" library facet

- **Backend filter:** a new `finding` query param on `GET /papers` → `repository.list_papers(finding=…)` →
  `FINDING_FILTERS` allowlist (v1: `"needs-review"`) → a **bound IN-subquery** on `paper_findings` WHERE
  `review_state == "unreviewed"` (rule #3; mirrors the inc-97 `SIGNAL_FILTERS` block; composes with
  deleted/q/axis/tag). One value for now, extensible.
- **Frontend chip + filter (reuse `librarySignalFilter`):** `librarySignalFilter` already holds a special-view
  string (`"statcheck-inconsistent"` / `"retraction-retracted"`); add `"needs-review"` to it — **zero new
  view-state**, all the existing clear-other-views + banner + chip plumbing is reused. The `/papers` fetch maps
  the value: `if (librarySignalFilter === "needs-review") qs.set("finding","needs-review"); else if
  (librarySignalFilter) qs.set("signal", …)`.
- **The chip count** is computed **client-side** from the `findings_overview` the app already fetches into
  `findingsByPaper`: `findingsToReview = #papers with unreviewed_count > 0`. No new count endpoint. A
  **"📋 N to review"** header chip (mirrors the statcheck/retraction chips) → `showFindingsToReview` (sets
  `librarySignalFilter="needs-review"`, clears trash/axis/tag/needs-review/focus) → the filter view + a banner
  ("Findings you haven't reviewed yet — open each paper's Review section to Confirm / Note.").
- **Live refresh:** add `findingsRefresh` to the `/papers` fetch deps so reviewing a paper while in the
  needs-review view re-narrows it (the reviewed paper drops out); `onFindingsChanged` already bumps
  `findingsRefresh` → `findingsByPaper` re-fetches → the chip count updates too.

## Honesty invariants (asserted in tests + QA)

- A statcheck candidate is a **candidate** (reviewable), the statcheck **signal** is a fact — they coexist; the
  signal persists after the candidate is reviewed.
- The "N to review" chip counts the user's **unreviewed work**, never paper quality; it's a filter, not a rank.
- The candidate routes to its page at **region** precision (no fabricated exact highlight).
- statcheck stays non-accusatory ("a prompt to look") — the candidate `desc` says "review", not "bad".

## Out of scope (later)

- p-curve / GRIM emitting candidates (collection-level / per-value — not per-paper auto-scans; deferred).
- Folding statcheck's signal chip/filter INTO the unified facet (the coexist decision keeps both).
- Retraction facts in the needs-review queue (facts aren't reviewable — correctly excluded; `review_state=None`).

## Tests (hermetic)

- the batch writes a statcheck **candidate** for a flagged paper (payload desc/counts/page) + supersedes it when
  a re-check is clean; a clean paper gets **no** candidate; re-run preserves a reviewed candidate's state.
- `list_papers(finding="needs-review")` returns only papers with an unreviewed candidate; an unknown `finding`
  value → ignored (no filter); composes with deleted.
- endpoint: `GET /papers?finding=needs-review`; the statcheck batch end-to-end (run → the flagged paper appears
  in the findings overview unreviewed_count + the finding filter); route-surface unchanged (no new path —
  `finding` is a query param on the existing `/papers`).

## Verification

- pytest green (+ ~5); ruff clean; build + assembly; QA route(s) updated + surface map 0 uncovered.
- Headed, no egress: run the statcheck batch → a flagged paper shows "N to review" on its card + the header chip
  → click the chip → the filter narrows to it → open it → Review pane shows the statcheck **candidate** card →
  Confirm/Note it → it drops from the chip count + the filter view (live). 0 console/page errors, 0 genai.

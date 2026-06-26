# Increment 133 — Activate the candidate-review half (statcheck candidates + a unified "N to review" facet)

## Implemented

The inc-130 candidate-review machinery (Confirmed / Accepted / Noted cards) was built but **unexercised** — the
only producer (retraction, inc 131/132) writes *facts*, not *candidates*. This increment gives it content + a
library-wide place to triage it.

- **statcheck → candidate findings** (`methods.py::_run_statcheck_all_job`): the batch already wrote the
  **signal** (`store_statcheck`, inc 97) — kept. Now it **also** emits, per paper, a candidate via
  `upsert_findings(conn, paper_id, "statcheck", …)`: **flagged** (inconsistent + decision_errors > 0) → one
  candidate `{kind:"candidate", tier:"primary", payload:{desc:"N statistical reporting inconsistenc(y/ies)
  (statcheck) — review", inconsistent, decision_errors, checked, page}}` (the page is the first flagged result's,
  for the card's "show in paper" at region precision); **not flagged** → `upsert_findings(..., [])` (supersede any
  prior candidate, so a re-check-clean paper drops out). `upsert_findings`'s `content_key` idempotency means a
  re-run with the same result **preserves** a reviewed candidate's state (a Noted paper stays Noted, doesn't nag);
  a changed result re-surfaces as unreviewed.
- **The unified "N to review" facet.** Backend: a `finding` query param on `GET /papers` →
  `repository.list_papers(finding=…)` → `FINDING_FILTERS = {"needs-review": "unreviewed"}` → a **bound IN-subquery**
  on `paper_findings.review_state` (rule #3; mirrors the inc-97 `SIGNAL_FILTERS` block; composes with
  deleted/q/axis/tag). Frontend: a **"📋 N to review"** header chip (count of papers with `unreviewed_count > 0`,
  derived from the `/findings/overview` the app already fetches into `findingsByPaper`) → `showFindingsToReview`
  (reuses `librarySignalFilter` with the sentinel `"needs-review"` → the `/papers` fetch maps it to
  `&finding=needs-review` — **zero new view-state**, reusing all the clear/banner/chip plumbing) → a filter view +
  banner. The `/papers` fetch gained `findingsRefresh` as a dep, so reviewing a paper while in the queue
  **re-narrows it live** (the reviewed paper drops out; the chip count updates too).

The Review-pane `FindingCard` + the per-card "N to review" badge already render candidates (inc 130) — no card UI
work needed.

## Key technical detail

**Coexist, not replace (the user's call).** A statcheck **candidate** and the statcheck **signal** (inc 97/100)
are both kept, and the distinction is principled: the **signal** is a *fact about the paper* ("it has reporting
inconsistencies"), persistent regardless of review and surfaced by the "⚠ N flagged" chip + the
`signal=statcheck-inconsistent` filter; the **candidate** is the user's *work state* ("have I looked?"), surfaced
by the "📋 N to review" chip + the `finding=needs-review` filter. A flagged paper appears in both until you review
its candidate, then drops from the review queue but **stays** in the statcheck-flagged filter. (FACT vs
work-state — exactly the inc-130 contract.)

**Principles (run inline):** a statcheck candidate is *a prompt to look, reviewable* (the inc-95/97 framing) —
signal-not-verdict, no opaque score, non-accusatory (`desc` says "review", not "bad"); the facet is a work-state
queue, not a quality rank. Declined: a reproducibility-score / leaderboard. Retraction **facts** are correctly
excluded from the queue (`review_state=None`, not reviewable). **No new endpoint, no migration, no external
fetch, no egress** → no audit-gate trigger.

## Manual verification script

1. Seed an unreviewed statcheck candidate (or run the statcheck batch over a flagged paper). (See
   `.local/visual/drive_inc133_review.py`.)
2. Start the app (egress unset). A **"📋 N to review"** chip shows in the library header; the flagged paper's
   card shows its "N to review" badge.
3. Click the chip → the library filters to those papers (banner "To review …"); open one → METHODS → **Review** →
   the statcheck **candidate** card ("N reporting inconsistencies (statcheck) — review" + show-in-paper · p.N +
   Confirmed / Accepted / Noted).
4. **Confirm** it → the card flips reviewed and it **drops** from the chip count + the filtered view (live).

Automated equivalent: `.local/visual/drive_inc133_review.py` — **PASS**, 0 console/page errors, **0 genai hits**.

## Pytest

**504** (501 → +3 `test_findings_review.py`: the needs-review filter returns only unreviewed candidates [facts +
reviewed excluded; unknown value ignored]; the statcheck batch emits a candidate for a flagged paper [+ none for
a clean one] + the filter narrows to it; a reviewed candidate is preserved across a re-run). `ruff` clean. QA
surface **101/101 API + 510/510 FE, 0 uncovered** (`route_38` extended; the `finding` param rides the existing
`/papers`). No audit gate. methods.py at **492/600** — a `routers/retraction.py` (or statcheck) split is the next
time it grows. Verified headed + the **e2e suite** (incl. reading mode) green locally.

## Next

p-curve / GRIM are collection-level / per-value (not per-paper auto-scans), so they don't naturally emit per-paper
candidates — deferred. The retraction **producer-deepening** thread (on-import auto-check + a TTL/staleness nudge
for the RW DB) remains open. A future consolidation could fold the statcheck signal chip into the unified facet,
but the coexist model is the deliberate v1.

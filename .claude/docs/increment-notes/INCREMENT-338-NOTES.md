# Increment 338 — Backlog #23 (3/3): Bayesian auditor gets F1 chip + F4 persistence + F2 footer fix — #23 CLOSED

## Context
Third and last checker. Unlike LMM/meta-analysis (mechanical repeats of the same pattern), Bayes needed one real
design decision flagged at the end of increment 337's notes: the auditor emits TWO independent signals —
`BayesReport.not_reproduced` (a BF-recompute mismatch, statcheck-like) and `BayesCompleteness` (a reporting-
completeness checklist, LMM-like) — and the chip/candidate needs ONE combined "worth reviewing" definition.

## Implemented
- **Design decision:** `flagged = report.not_reproduced > 0 OR any completeness item is not-found/coherence-
  flag`, gated on `completeness.is_bayesian` (not `report.checked`, which has no gate of its own — a bare
  `t(df)=…, BF=…` could in principle appear without any Bayesian framing at all). One combined status
  (`"flagged"`/`"clean"`) rather than reusing `"incomplete"`/`"complete"` (not purely about completeness) or
  `"inconsistent"`/`"consistent"` (not purely about reproduction) — a deliberately generic pair of terms for a
  checker whose "worth reviewing" definition is inherently compound.
- `app/backend/persistence/signals_repo.py`: `BAYES_SIGNAL`/`BAYES_SOURCE` + `store_bayes`/`count_bayes_flagged`/
  `get_bayes_summary`.
- `app/backend/methods/bayes.py`: `apply_bayes(conn, paper_id, report, completeness)` — takes both report
  objects, combines them, writes the signal + (when flagged) a candidate describing which of the two triggered.
- **Structural move:** `GET /papers/{id}/bayes` was extracted from `methods.py` (531 lines, no headroom for
  another batch-endpoint block) into a new `app/backend/api/routers/methods_bayes.py` — the same inc-262
  `methods_retraction.py` precedent. `methods.py` dropped to 417 lines; the new file is 228 (well under the
  cap, plus the new batch endpoints). Persistence-on-ad-hoc-view (F4) + `POST /methods/bayes/run` +
  `GET /methods/bayes/run/{job_id}` + `GET /methods/bayes/summary` all land in the new file.
- `app/backend/persistence/paper_query_repo.py`: `SIGNAL_FILTERS["bayes-flagged"]`.
- `app/backend/api/app.py`: new `methods_bayes` router registration + `api.state.bayes_jobs = JobStore()`.
- Frontend: the same three-file chip wiring + `styles.css` (`.bayes-chip`, same amber `--flag` semantics).
  `08d_methods_bayes.jsx`: new `BayesLibrary` (whole-library batch, mirrors `LmmLibrary`/`MetaLibrary`).
  **F2 fix:** `<BayesCredit/>` moved from `BayesSection` into `BayesPaper`'s own render — Bayes already HAD an
  applicability gate, just expressed as a compound condition (`d.checked === 0 && !(d.completeness &&
  d.completeness.is_bayesian)`) rather than a single boolean; the credit now renders in the same branch as the
  actual result/checklist content, i.e. exactly when that compound condition is false.

## Key technical detail
Confirms the finding from increment 336's research: statcheck genuinely has no `is_x`-style gate (any paper
could in principle contain an APA-format statistic), while every OTHER sibling (retraction, transparency, LMM,
meta-analysis, and — now confirmed — Bayes) does have one, just sometimes expressed as a compound condition
instead of a single field. F2 was never "uniform across all four" as the backlog first framed it; it's uniform
across every checker that actually HAS an applicability concept, which turned out to be all of them except
statcheck.

## Tests
- `tests/test_bayes.py` (+7): the two-signal combination tested with **directly-constructed** `BayesReport`/
  `BayesCompleteness` objects (not real text) so each of "mismatch alone," "gap alone," "neither," "not
  Bayesian," and "reapply" is isolated rather than relying on one text sample that happens to trigger multiple
  signals at once (a real risk here, more than for LMM/meta, given two independent trigger paths) — plus the
  same ad-hoc-persists + batch+chip+filter end-to-end tests via real text.
- `tests/test_statcheck.py` + `tests/test_pcurve.py`: re-run after the `methods.py` extraction (both share
  `locate_quote_for_attachment`/statcheck internals with the file Bayes moved out of) — 34 passed, confirming
  the extraction is behavior-preserving.
- A direct `create_app(db_url="sqlite:///:memory:")` import smoke-check confirmed the new router registers
  cleanly (55 routes) before running the full suite.
- **Full suite** (`pytest -n auto -q`, the "before merging a multi-file change" gate, appropriate now that #23
  is fully closed): see the actual count below.

## Manual verification script
`.claude/qa-routes/route_59_methods_bayes.md` steps 9-11 (whole-library batch → chip → filter; credit
suppression on a non-Bayesian paper; a Critique candidate seeded purely by an ad-hoc view).

## Gates
- **Security audit:** `.claude/security-audits/2026-07-22_cross-method-auditor-consolidation.md` — PASS for
  all three checkers; the doc now closed as complete rather than left open for a future extension.
- **QA coverage:** `tools/qa/build_surface_map.py check` — API surfaces 100% covered (added the 3 new
  `/methods/bayes/*` endpoints + updated `route_59`'s frontmatter after the `methods_bayes.py` split).

## Backlog
**#23 closed** (`INCREMENT-BACKLOG-DONE.md`) — the full F1+F2+F4 build across all four originally-named
siblings (statcheck already had F1/F4 since inc 97/133; F2 doesn't apply to it). The statcheck-signal-vs-
review-queue "duality reads as two systems" UX nuance (a separate, lower-urgency backlog item) is unchanged —
now applies to five producers instead of two, worth reconsidering if it comes up again.

## Next
Backlog queue resumes at **#26** (CRediT builder UX: role presets + "and" formatting + discoverability) — the
next item in Cliff's explicitly-ordered 12-item decision queue.

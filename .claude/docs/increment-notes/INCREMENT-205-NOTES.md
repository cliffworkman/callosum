# Increment 205 — close A8 (covered) + remove the redundant THEORY → Discover placeholder

## Implemented

The third close-out of the wrap-up pass, bundling two trivial frontend-only items (the cheapest-first sequence).

**(1) A8 — synthesis scope label: closed as covered (no code).** A8 asked for a "summarizing N papers; uncertain
excluded" scope label at summarize time. On inspection the honest version is **already shipped**:
- **Pre-run** — the selection bar's summarize sets a `scopeNote` rendered in the Synthesis pane: *"Summary of **N
  selected papers** [· focused on '…'] [· capped at K chunks] from the library selection."* (`20_synthesis.jsx`,
  inc 145).
- **Post-run** — the inc-153 coverage readout: *"Drew from **M** of N selected papers · top K chunks · K contributed
  no cited passage."*

The literal "uncertain excluded" wording would be **dishonest in the general case** and is declined: `summarize_scope`
summarizes the **exact** `paper_ids` selected, regardless of certainty — it has no notion of an axis cutoff, and a
selection can come from an *unfiltered* view (where uncertain papers ARE selected). With **A10 (inc 204)** the
*filter* is now honest about what's selected (select-all from a hide-uncertain view yields an assigned-only set), so
the certainty boundary is enforced upstream at selection time — exactly where the user can see it. Closed as covered;
the reasoning is recorded in the backlog.

**(2) Remove the THEORY → Discover accordion placeholder** (Cliff's queued request). The inc-163 "Coming soon" stub
registered a THEORY → **Discover** section (Beyond library / Feed / Search tabs) in `09_placeholders.jsx`, but the
real features shipped as **center-pane tabs in the library frame** — Discover/Search (inc 184) + Feed (inc 188,
`30c_frame.jsx`). The placeholder was stale + duplicative. Removed the three `registerPaneTab` Discover blocks (per
the inc-163 convention: drop a stub in the increment its real feature lands); a comment records why. The METHODS
coming-soon stubs (Mixed-model / Bayesian / Meta-analysis / Citation equity) + the statcheck "More checks" tab + the
`ComingSoon` component are untouched.

Also folded in: a **ruff-format fix for `tests/test_papers.py`** — the inc-204 A10 test's `cluster_nodes` insert
needed wrapping; CI's `ruff format --check .` caught it (the inc-204 push went red on lint only — the suite was
green). Reformatted; no behavior change.

## Key technical detail

The Discover stubs were **inert** (`<ComingSoon>` — no controls/data), so removing them left the QA surface map
**unchanged** (136/136 API + 661/661 FE, 0 uncovered) — no route claimed `09_placeholders.jsx` (confirmed by grep),
consistent with inc-163's "the stubs add no interactive surface."

## Manual verification script

**Headed (no egress):** `.local/visual/drive_inc205_no_discover.py` — open the app, read the accordion section
headers: **no "DISCOVER"** (the placeholder is gone), "AXES" still present, and "MIXED-MODEL REPORTING" (a remaining
METHODS stub) still renders — i.e. the removal was surgical. 0 console/page/genai.

## Gates

- **pytest:** full suite unchanged — **713 passed, 1 skipped** (no new test; the Discover removal is covered by
  `test_frontend_assembly`, A8 is a doc-close).
- **ruff** check + format clean (incl. the A10 `test_papers.py` fix). Frontend rebuilt (`callosum-app.html`).
- **QA surface unchanged** — 136/136 API + 661/661 FE, 0 uncovered (removed inert stubs; no route change).
- **Audit:** none triggered (no endpoint/egress/migration/dependency). **Principles non-triggering** (A8 is a
  honesty-preserving *no-op-close*; the Discover removal deletes inert roadmap UI).
- **Help corpus** unchanged (it describes the real Discover tab, not the placeholder; `HELP-DOCS-SYNCED` stays at 204).

## NEXT (continuing the cheapest-first close-out)

**Inc 206 — A6 drag-and-drop a paper onto an axis** (a faster input for the existing manual-add path; rides
`restore_manual_assignments`; frontend, no migration). Then **A5** color tags/ratings + **A1** saved searches (each a
small migration + UI), **A3** full-text FTS5 search (migration + a security audit), and finally **A2** citation counts
+ **A7 Curated Axis** (its own design pass).

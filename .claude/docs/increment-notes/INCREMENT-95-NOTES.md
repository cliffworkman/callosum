# Increment 95 — statcheck: an inspectable, deterministic statistics-reporting signal

The patter's **carrot** (chores = inc 94). statcheck recomputes reported NHST p-values from a paper's extracted
text and flags reported-vs-computed disagreements — the project's verification ethos applied to the Methods
side. **Deterministic, local, no-LLM.** Track A of the open-science future-track.

## Principles / values gate (rule #9 — run before building)
statcheck is **PRINCIPLES Example 3** (recomputed stats; extract deterministically, show each beside its
passage, the model narrates — here there's *no model*) and **A-A names it as extending the determinism value
A6**. Honored: **#4/#3** (a recomputation is a deterministic FACT, no AI candidate); **#7 no opaque score** (the
*divergent* "scoring temptation" — show per-test results + transparent counts, **never a composite
reproducibility score**); **#8/#1** (each result carries the verbatim matched string + its page); **#6** (coverage
stated — inline APA NHST only; absence ≠ clean); **#2 + the veto-level "no accusation"** (inconsistencies are
reported-vs-computed facts, usually innocent — amber `--flag` "look at this", **never red**, no
misconduct/p-hacking labels). The declined easier path: a single open-science score + an "is this paper
trustworthy?" verdict.

## Implemented
- **`app/backend/methods/statcheck.py`** (NEW package `methods/` — room for GRIM/p-curve later). Pure,
  deterministic: anchored regexes for the five APA forms (t / F / r / χ² / z), `recompute_p` via `scipy.stats`
  (two-tailed t/r/z, one-sided F/χ²; `r`→t), and `_classify` with **rounding tolerance** (the reported stat's
  implied range → a p-range) + a **one-tailed fallback**, so correct reporting is **not** false-flagged.
  Classification: `consistent` / `inconsistent` / `decision-error` (significance flips at α=.05).
  `run_statcheck(chunks)` scans **per chunk** so each match carries its `page_start`; capped at `MAX_RESULTS`.
- **`app/backend/api/routers/methods.py`** (NEW concern-router) — `GET /papers/{paper_id}/statcheck` (sync,
  read-only): 404 if missing; no chunks → `checked: 0` (honest). Registered in `app.py`.
- **`requirements.txt`** — `scipy` made explicit (already present transitively via scikit-learn; genuinely needed
  for the t/F/χ² survival functions — `math` lacks the incomplete beta/gamma — so not hand-rollable like the
  inc-93/75 parsers).
- **Frontend** (`25_detail.jsx` + `styles.css`) — a **"Statistical reporting"** section with a **"Check
  statistics"** button (gated on the paper having extracted text), rendering per-test rows (verbatim match,
  computed p, a green/amber `.cite-status` pill) + a count summary + the non-accusatory coverage caveat; each
  row routes to its page via `onOpenPaper(paper, {page, precision:"region"})` (page-open, not a fake exact
  highlight — honors the coordinate honesty contract). Rebuilt `callosum-app.html`.

## Key technical detail
The recomputation's value is in **not** false-flagging: a reported statistic "2.10" is treated as the range
[2.095, 2.105) → a computed-p range, and the reported p (honoring `=`/`<`/`>` and its own decimals) is consistent
if it overlaps; for t/r/z a one-tailed reading is also tried before flagging. A `decision-error` is the stronger
tier — reported vs computed p land on opposite sides of α. Per-chunk scanning gives page provenance for free (a
stat split across a chunk boundary is a stated v1 miss). **No persistence** (on-demand, like inc-72 suggested-tags;
the pre-existing `open_science_signals` table + a library-wide facet are deferred to the findings subsystem).

## Manual verification script
1. Open a paper with a processed PDF + a Results section → **Statistical reporting** → **Check statistics** →
   tests list with reported/computed + consistent (green) / inconsistent / decision-error (amber) pills + a
   count summary + the caveat. Click a flagged row → the PDF opens at that page.
2. A metadata-only paper → "Process a PDF first…"; a paper with text but no APA stats → "No APA-format
   statistics found." _(Visual check delegated to the user.)_

## Pytest
**405 passed, 1 skipped** (+10 in `test_statcheck.py`: consistent / inconsistent / decision-error / rounding-not-
flagged / one-tailed-not-flagged / all five forms / no-stats / page provenance / `recompute_p` known values +
degenerate / the endpoint incl. no-chunks + 404). `ruff` clean; audit `.claude/security-audits/2026-06-21_statcheck.md`
**PASS**. No migration, no egress, no LLM; `scipy` made explicit (net-zero install).

# Increment 470 — z-curve (round 2, item #4, closes backlog #55)

## Implemented

Item #4 of round 2 (memory `callosum-next5-backlog-roadmap-round2`). Backlog #55 was spun off (inc 467) from
DEBIT's scope, flagged as needing its own design pass because the source doc
(`chatgpt5.5_future-tracks_integratinglakens.md`, item 7 "auto-zcurve") proposed something risky: *"It uses
Gemini to extract focal statistics and produce z-curve reports... more dangerous because 'focal statistic'
extraction is judgment-laden."* That's the exact misaligned path PRINCIPLES.md Example 3 warns about — a model
picking-and-pronouncing instead of a deterministic extraction.

**Research found the aligned path already exists and is proven**: `app/backend/methods/pcurve.py` (inc 126)
already solved this identical problem for p-curve, z-curve's simpler sibling. Instead of an LLM picking one
"focal" test per study, it reuses statcheck's existing exhaustive extraction of every inline NHST result and
discloses that deviation from strict methodology honestly in its own coverage note, already scoped
collection-level-only with UI copy stating it "never describes any single paper or author." Z-curve extends this
proven pattern — declining the design doc's LLM-assisted framing outright, same disposition as backlog #54's
declined salami-slicing branch. **Confirmed with Cliff**: build the full EDR/ERR mixture-model estimator (Bartoš
& Schimmack 2020's actual z-curve 2.0 method), not a smaller p-curve-on-the-z-scale stepping stone.

### Backend math (`app/backend/methods/zcurve.py`, new)

Deterministic, local, **no LLM, no egress**. Implements Bartoš & Schimmack (2022) Z-curve 2.0, **verified against
the reference `zcurve` R package's own source** (github.com/FBartos/zcurve, `R/tools.R` + `R/zcurve_EM.R` — pulled
and read directly, not derived from memory):

- 7 **fixed**-mean components (mu = 0..6, sigma = 1 — only their weights are EM-fit) as truncated folded-normal
  densities over the significance region `[a, b] = [1.96, 6]`; z-values above 6 are tallied separately
  (`prop_high`) rather than density-fit.
- The population-weight extrapolation (`pop_weights[k] = weights[k]/power2[k]`, renormalized) and the EDR/ERR
  formulas are lifted verbatim from `.get_pop_weights`/`.get_EDR`/`.get_ERR` in the R source.
- Bootstrap CIs with the published calibrated widening adjustment (+3pp for ERR, +5pp for EDR — a real, published
  part of the method, not an implementation guess).
- `low_reliability` fires below **N=300 significant results** — the reference implementation's own author-set
  threshold ("meant for large samples... might produce undercoverage and biased estimates" in small samples),
  far above p-curve's soft `MIN_RELIABLE=5`.

### Endpoint (`app/backend/api/routers/methods_zcurve.py`, new sibling router)

`methods.py` is at 586/600 lines — no headroom (the same wall inc-469 hit) — so this went straight into its own
file. Mirrors p-curve's `POST /methods/pcurve/run` / `GET /methods/pcurve/run/{job_id}` exactly: an async
`JobStore` job (`zcurve_jobs`, registered in `app.py`), capped selection (`MAX_ZCURVE_PAPERS=1000`), reuses
`run_statcheck` for extraction. Ephemeral — no persistence, no migration (a collection-level, selection-driven
check, not a per-paper saved record). `status.py` gained the standard 3-dict entries (`JOB_LABELS`,
`JOB_NAV_DEFAULTS`, `JOB_COMPUTE_KINDS`) for Status-popover visibility (invariant #5).

### Frontend (`app/frontend/js/29b_zcurve.jsx`, new)

A sibling to `PcurveModal`, not a tab inside it (GRIM/GRIMMER/DEBIT/repeated-values precedent: separate tools,
separate job lifecycles). A second "z-curve" bulk-action button sits next to "p-curve" in the library selection
bar (`10_pdf_layer.jsx`), wired through the same `useLibrary` state pattern (`zcurvePapers`/`setZcurvePapers`,
`bulkZcurvePapers`, mirroring `pcurvePapers` exactly in `03_library.jsx`/`40_app.jsx`).

## Key technical detail

**The Principles-gate finding that shaped the whole design**: EDR/ERR are quantitative *rate* estimates
("43% expected replication rate") — more verdict-shaped than p-curve's abstract right-skew statistic, and more
tempting to misread as describing the specific studies in a small curated set. Three concrete safeguards, named
before writing any frontend code: (1) a **hard, unmissable** reliability banner (`.zcurve-reliability-warn`, a
bolder amber treatment than p-curve's soft `.pcurve-warn`) below N=300 — expected to fire on nearly every
realistic personal-library run, which is the *honest* outcome per Principle #6 (silence is not a certificate; a
disclosed wide-uncertainty estimate is right, a quiet one wouldn't be); (2) CIs **always** rendered beside the
point estimate, never a bare percentage; (3) no per-paper or per-author breakdown of EDR/ERR anywhere — only the
aggregate + the already-precedented `included_tests` list.

**A real performance bug, caught by a stress test before shipping, not after**: the first EM implementation used
an absolute log-likelihood convergence criterion (`abs(ll - prev_ll) < 1e-9`). Total log-likelihood scales with
N, so for a few thousand observations the criterion was effectively unreachable — every fit silently burned its
full iteration budget. A synthetic 20,000-observation stress test (deliberately run to validate EDR/ERR recovery
on a *hard*, heterogeneous mixture) hung past two minutes and had to be killed. Fixed by switching to a
scale-invariant criterion (the largest per-component weight change between iterations), which also cut the
initial-fit iteration cap from 2000 to 500. After the fix, the same 20,000-observation/~7,000-significant-result
stress case completed in ~57s — bounded and acceptable for an async, Status-tracked background job.

**Numerical correctness was verified against reality, not assumed**: the power formula matches the reference
implementation's own documented component powers (.05/.17/.85/.98/.999/.99997 for mu=0,1,3,4,5,6) to 2-3
significant figures. Two synthetic-recovery checks: a homogeneous high-power population (true mu=4) recovered
EDR=0.974/ERR=0.975 against a true power of 0.979 — both essentially exact. A hard heterogeneous mixture (70%
near-null, 30% high-power) recovered EDR=0.292 with a 95% CI of [0.211, 0.397] that correctly bracketed the true
value of 0.349 (a known, expected known-limitation case for the method itself, not a bug — the CI covering the
truth is the correctness property that matters), and the hand-derived approximate ERR (0.834, from the known
per-subpopulation replication probabilities) matched the model's own output (0.839) closely.

## Manual verification script

1. In the Library, checkbox-select a batch of papers with statcheck-extractable stats → confirm a **z-curve**
   button appears next to **p-curve** in the bulk-action bar.
2. Click it → confirm the framing block ("never a score for these specific papers or their authors"), a running
   progress bar, then EDR/ERR each with a `95% CI [...]` beside it, an observed-discovery-rate comparison next to
   EDR, and an estimated null-component share.
3. With a realistic (small) selection, confirm the amber reliability warning appears prominently *before* the
   numbers ("z-curve needs at least 300 for a reliable estimate").
4. Expand "N included tests" → click one → confirms it opens the right paper/page (region precision, no fake
   exact highlight).
5. Click "add missing to library" on the credit block → confirm it adds the Bartoš & Schimmack (2022) paper
   (verify via `POST /library/credit/status`), then confirm the button flips to "✓ added to library."
6. Adversarial: empty selection → 422; fake job id → 404; a selection with no parseable stats → honest empty note.

## Verification

Live-verified end-to-end via Playwright against the real 217-paper curated library (server restarted to pick up
the new backend code):
- Selected 15 real papers → z-curve ran, producing EDR=59% [8-76%], ERR=62% [46-78%], observed discovery rate
  35%, null-component share 0%, over 76 significant results (of 218 extracted) — the reliability warning
  rendered correctly since 76 << 300.
- The included-tests list rendered with `z = 3.39`-style entries (confirmed distinct from p-curve's `p =`
  display, not a copy-paste leftover).
- Chased down and resolved a real-looking discrepancy during verification: a screenshot appeared to show the
  z-curve credit paper already "added" before any click — turned out to be a misread of the DOM (two separate
  credit lines stacked in the same block: the z-curve paper's own line correctly showed "not yet added"; a
  *different*, already-present Lakens-catalog review paper's line showed "added"). Confirmed via the authoritative
  `POST /library/credit/status` endpoint and a full 217-paper pagination scan before concluding it wasn't a bug.
  Then explicitly exercised the real add flow (click → poll → confirm present via the API) and cleaned up the
  test-added paper (`DELETE .../permanent`) afterward.
- Zero console errors across the entire session (initial load, selection, run, poll, expand, credit-add, cleanup).
- `pytest tests/test_zcurve.py tests/test_health.py -q` → **17 passed** (7 new + 10 existing route-allowlist
  cases).
- `python -m ruff check` / `ruff format --check` on every touched file → clean.
- `python tools/check_line_budget.py` (run as the last step before committing) → clean; the new sibling router
  file kept `methods.py` untouched.
- `python tools/build_frontend.py` → clean build; `pytest tests/test_frontend_assembly.py -q` → 64 passed.
- `python tools/qa/build_surface_map.py check` → 403/403 API + 1673/1673 FE surfaces covered (route 90 added).
- No migration needed — z-curve is fully ephemeral, matching p-curve's own persistence-free posture.
- `.claude/security-audits/2026-08-10_zcurve.md` — PASS, mirrors the p-curve audit's shape + records the
  convergence-criterion performance fix.

## Housekeeping

- `.claude/docs/INCREMENT-BACKLOG.md`: #55 closed in §4 → `INCREMENT-BACKLOG-DONE.md`.
- Memory `callosum-next5-backlog-roadmap-round2`: item 4 closed; item 5 (#37 equity/integrity wrap-up) next.
- `.claude/CLAUDE.md`: counter bumped to 470; pytest count updated.

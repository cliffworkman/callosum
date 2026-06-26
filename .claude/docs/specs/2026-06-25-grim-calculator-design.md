# Design spec — GRIM + GRIMMER data-consistency calculator (inc 127)

**Date:** 2026-06-25 · **Status:** approved design (brainstorming) → spec under review.

## 0. Context
The second of the GRIM/p-curve "data-detective" METHODS family the user asked for (after p-curve, inc 126;
surfaced via Daniël Lakens' automated-review catalog). **GRIM** (Brown & Heathers, 2017) checks whether a reported
mean of integer data is mathematically possible given the sample size and the number of scale items; **GRIMMER**
(Anaya 2016; Allard 2018 analytic) extends the check to the reported SD. The compute is trivial integer
arithmetic; the only hard part is *extraction* (associating a mean with its N + knowing the data is integer-scale)
— which is unreliable from PDF prose. **Decision (brainstorming): an assisted calculator**, not an auto-scanner —
the user enters a specific reported value to check, exactly how researchers use GRIM. Reliable, honest, no false
flags. Auto-suggest/auto-scan is a deliberate later option, not v1.

## 1. Decisions
- **Assisted per-value calculator** (no extraction): the user types the reported mean (and optionally SD), N, and
  items; the tool returns GRIM (and GRIMMER) consistency. **User-driven → inherently non-accusatory.**
- **GRIM + GRIMMER both** (the inputs overlap: M/N/items/decimals for GRIM, + SD for GRIMMER). GRIMMER via the
  Allard analytic algorithm. (If GRIMMER proves intractable in implementation, ship GRIM v1 + GRIMMER fast-follow
  — but the plan targets both.)
- **A new METHODS section** ("Data consistency (GRIM)"), self-registering on the inc-121 pane registry, order 30
  (after DETAILS=10, STATISTICS CHECK=20). It is a calculator — it does **not** read paper text — so it needs no
  `ctx.selectedPaper` and **zero `40_app.jsx` wiring** (which also avoids the standing 590/600 rule-#1 risk there).
- **Backend compute + endpoint** (not pure-JS) for testability + consistency with statcheck/p-curve and because
  GRIMMER's analytic algorithm deserves Python unit tests.

## 2. Backend — `app/backend/methods/grim.py` (new; pure, stdlib only, no scipy/numpy needed)
- `grim_test(mean: str, n: int, items: int = 1) -> GrimResult` — the reported mean is passed **as a string** so its
  decimal precision is read from it (GRIM depends on the reported precision). Algorithm: `D = decimals(mean)`;
  granularity `g = 1/(n*items)`; the achievable means are `K/(n*items)` for integer K; the reported mean is
  **consistent** iff some achievable value rounds (to D decimals, banker's-rounding matched to the field) to the
  reported mean. Return `GrimResult{consistent, reported_mean, n, items, decimals, granularity, nearest: [lo, hi]
  (the closest achievable values below/above), no_power: (n*items) >= 10**D, note}`.
- `grimmer_test(mean: str, sd: str, n: int, items: int = 1) -> GrimmerResult` — the **Allard (2018) analytic
  GRIMMER**: first GRIM-check the mean; then test whether an integer sum-of-squares exists consistent with the
  reported mean (rounded), SD (rounded), and N — i.e., reconstruct the achievable SD set and check the reported SD
  rounds to an achievable value. Return `GrimmerResult{consistent, reported_sd, decimals_sd, reason, note}`.
  (Exact algorithm finalized in the plan against known consistent/inconsistent test cases from the GRIMMER
  paper / the `scrutiny` reference.)
- **Validation/edge cases:** `n <= 0` or `items <= 0` → a clear error (422 at the endpoint); a mean/SD that won't
  parse → error; `no_power` true → consistency is reported but flagged "GRIM has no power at this N" (honest:
  absence of inconsistency ≠ a clean bill). Caps: items/n bounded to sane maxima (rule #4).

## 3. Endpoint — `POST /methods/grim` (`app/backend/api/routers/methods.py`)
- Request `GrimRequest{mean: str, sd: str | None, n: int, items: int = 1}`; Response
  `GrimComputeResponse{grim: GrimResultModel, grimmer: GrimmerResultModel | None}` (grimmer present iff sd given).
- **Sync, stateless, no DB, no egress** (mirrors the per-paper statcheck GET, but POST with the entered values).
  Bad inputs → 422. (`routers/methods.py` is ~243 lines; +~40 → ~285, under 600.)

## 4. Frontend — `app/frontend/js/07_methods_grim.jsx` (new METHODS section)
- `registerPaneSection({id:"grim", label:"Data consistency (GRIM)", paneId:"methods", order:30, render})`.
- A `GrimSection`: a compact form — **mean** (text, so decimals are read), **SD** (text, optional → enables
  GRIMMER), **N** (int), **items** (int, default 1, with a one-line "items = scale items averaged per score;
  leave 1 for a single integer measure") — and a **Check** button → `POST /methods/grim`. Renders:
  - GRIM: a green ✓ "consistent" or amber ✗ "impossible for N=… — nearest possible: lo / hi" pill; the granularity.
  - GRIMMER (when SD given): ✓/✗ with the reason.
  - The `no_power` note when applicable.
  - The **integer-scale caveat** ("GRIM/GRIMMER assume integer-scale data — counts or Likert-type items; they
    don't apply to continuous measures. An inconsistency is a prompt to look, not a verdict or an accusation.").
  - A **credit** block (Brown & Heathers 2017; GRIMMER: Anaya 2016 / Allard 2018) + a one-click **add to library**
    (bundled CSL-JSON → the existing `/library/import`, like p-curve inc 126).
- Tokens-only CSS (read DESIGN.md; reuse the statcheck/`.detail-*`/`.settings-*` recipes + `.cite-status`
  verified/flagged pills). **No `40_app.jsx` change.**

## 5. Gates
- **Principles (#9): aligned** — user-driven per-value (non-accusatory by construction); signal-not-verdict;
  nearest-possible values + granularity make it inspectable (#8); integer-scale + no-power caveats (#6 silence ≠
  certificate); no composite score (#7); the A-A no-accusation veto held (it never scans/ranks/labels papers or
  people). Declined easy path: an auto-scanner that flags means with guessed Ns.
- **Audit (#1 new endpoint / #5):** `.claude/security-audits/2026-06-25_grim.md` — input validation (n/items
  bounds, parse failures → 422), no egress, no DB, no external fetch, no SQL, bounded enumeration; credit-add
  rides the audited inc-93 import. PASS.
- **Rule #10 (QA):** new `route_NN_methods_grim.md` (assert calculator flow, the integer-scale caveat, no
  accusation/score, nearest-possible inspectability, the no-power state, 422 on bad input) + surface-map regen.
- **Credit-the-lineage:** in-context + add-to-library + a THIRD-PARTY-NOTICES entry under the methods-lineage
  section (GRIM: Brown & Heathers 2017; GRIMMER: Anaya 2016 / Allard 2018).
- **Help corpus:** a "Data consistency (GRIM/GRIMMER)" section; move the `HELP-DOCS-SYNCED` marker.

## 6. Verification (no egress — fully hermetic + headed)
- pytest: `grim.py` units — known GRIM-consistent vs impossible means (e.g., the canonical "M=5.19, N=28"
  examples), the decimals dependence, items>1, no_power at large N, GRIMMER consistent/inconsistent cases, bad
  inputs; the `POST /methods/grim` endpoint (happy + 422). Route-surface test (`test_health.py`) updated. `ruff`
  clean; rebuild `callosum-app.html`; surface check 0 uncovered.
- Headed Playwright: open the METHODS pane → Data consistency (GRIM) → enter a known-impossible mean → ✗ + nearest
  possible; a consistent one → ✓; SD → GRIMMER; add-to-library works; 0 console/page errors; 0 genai requests.

## 7. Out of scope
Auto-extraction / auto-scan (the deliberate later option); the findings subsystem; SPRITE / DEBIT (further
`scrutiny` checks). Just the assisted GRIM + GRIMMER calculator.

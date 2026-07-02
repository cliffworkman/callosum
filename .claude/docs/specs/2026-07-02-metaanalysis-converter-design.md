# Design — Meta-analysis extraction workbench, SP1: the deterministic effect-size converter

**Date:** 2026-07-02 · **Track:** Meta-analysis extraction workbench (`future-tracks/opus4.8_future-tracks_metaanalysisextractionworkbench.md`) · **Increment:** the workbench's SP1 (the first buildable slice).

## Context & decomposition

The workbench future-track doc scopes a deliberate **v1 = the extraction core from a user-defined *included set***
(deferring the screening/PRISMA front end, double-coding/IRR, and RoB instruments). Even that v1 has five distinct
pieces: a workspace surface, an extraction template, LLM-drafted + provenance-anchored + human-verified extraction (the
egress-requiring, highest-stakes heart), deterministic effect-size conversion, and a new export path.

Per this project's increment-first rhythm (245→246, 232→233), we slice v1. **SP1 = the deterministic effect-size
CONVERTER alone** — the safe, egress-free, standalone-useful core, and the trusted sink the extraction pipeline later
hands its verified data into. It reuses the auditor/methods pattern (statcheck/LMM/meta/transparency/Bayes), the Bayes
auditor (inc 241) being the closest precedent: a deterministic recompute with cited formulas, verified against a
reference. **Maintainer scope (AskUserQuestion):** converter-first + the fullest converter (core-3 + alternate inputs +
cross-metric).

## What SP1 is

A free-standing METHODS-panel calculator (the GRIM inc-127 / Bayes inc-241 shape — hand-enter the values; *reading* a
paper's stats is deliberately the LLM/SP2 job). Enter one study's reported statistics → a common meta-analytic metric +
its variance, with the **conversion path shown, the formula source cited, and every derivation choice recorded**.
Genuinely useful standalone (researchers do these conversions by hand / in spreadsheets constantly), and the safe
foundation the rest of the workbench builds on.

## The load-bearing boundary — convert, never synthesize (test-pinned)

Callosum **converts one study at a time — it never pools, models heterogeneity, meta-regresses, or does bias
inference.** Those are inferential statistics (metafor/JASP/RevMan territory, a stats environment Callosum will not
become). Enforced **structurally**: the endpoint takes a single study's inputs; there is **no code path that aggregates
across studies** (no cross-study loop, no pooling formula). Pinned by a static-import/shape assert — the module imports
no meta-analysis/aggregation library and exposes no `pool`/`combine`/`heterogeneity`/`meta_regress` function.

Secondary honesty (the auditable-decision boundary the doc flags): every output **shows its path + formula + assumptions**,
carries **no hidden composite**, and **records the per-study decision** — which SD-derivation was used (SE vs 95% CI vs
IQR), which continuity correction (zero-cell → Haldane–Anscombe), which cross-metric approximation (d↔r, OR↔d) — visibly,
never buried.

## Architecture (all new; nothing touched destructively)

1. **`app/backend/methods/effectsize.py` (NEW, pure — no I/O, no LLM):** the conversion functions + a frozen
   `Conversion` dataclass:
   `{metric, value, variance, se, ci_low, ci_high, path: list[str] (ordered steps), formula_source: str, caveats:
   list[str], choices: list[str] (the recorded per-study decisions)}` + `to_dict`. A `convert(family, inputs) ->
   Conversion` dispatch. Self-contained helpers; scipy only for the primitives (`scipy.stats.norm` for CIs, already in).
2. **`app/backend/api/routers/methods.py` → `POST /methods/effect-size`** (sync, stateless — mirrors `POST
   /methods/grim` / the Bayes read): body `{family: Literal["smd","correlation","binary","cross"], inputs: {...}}` →
   the `Conversion`. Degenerate/invalid inputs (n<2, negative SD, r outside (−1,1), a full zero row, etc.) → **422**.
3. **`app/frontend/js/08i_methods_effectsize.jsx` (NEW):** a METHODS section (`registerPaneSection`, order ~38,
   `hideInReadOnly`; reuses `.bayes-check-*`/`.method-credit`/`.lmm-*` — no new CSS if possible): a **family picker**
   (SMD / correlation / binary / cross-metric) → an input form (fields switch by family + by alternate-input mode) →
   a **result card** (metric name + value + variance/SE + a 95% CI + the ordered **path steps** + the **formula
   citation** + the **caveats** + the **recorded choices**) + a **credit block** with ＋ add methods sources to library.
4. **No LLM, no egress, no migration, no new dependency** (scipy already present).

## The math (standard formulas; each path-shown + source-cited)

- **SMD (continuous, 2 groups):** pooled SD `s_p = sqrt(((n1−1)s1² + (n2−1)s2²)/(n1+n2−2))`; Cohen's `d = (M1−M2)/s_p`;
  Hedges' `g = J·d`, `J = 1 − 3/(4(n1+n2)−9)`; `Var(d) = (n1+n2)/(n1·n2) + d²/(2(n1+n2))`; `Var(g) = J²·Var(d)`.
  (Borenstein et al. 2009, Ch. 4; Hedges 1981 for J.)
- **Alternate inputs (SMD):** `d` from `t` + Ns (`d = t·sqrt(1/n1 + 1/n2)`); `d` from a one-way `F` (2 groups:
  `t = sqrt(F)` then the t path); **SD derived from** SE (`SD = SE·sqrt(n)`), a **95% CI** (`SD = (upper−lower)·sqrt(n)
  /(2·z_.975)`), or **IQR** — for IQR, the default is the **normal-quantile rule** `SD ≈ IQR/1.349` (Cochrane Handbook),
  with **Wan et al. 2014**'s sample-size-adjusted estimator noted as the documented refinement/option. Each derivation
  is recorded as a `choice` (its citation carried) — the doc's flagged "which SD-derivation path" decision made
  explicit + auditable.
- **Correlation:** Fisher's `z = atanh(r)`, `Var(z) = 1/(n−3)`. (Fisher 1915.)
- **Binary (2×2 a,b,c,d):** `logOR = ln(ad/bc)`, `Var = 1/a+1/b+1/c+1/d`; `logRR = ln((a/(a+b))/(c/(c+d)))`,
  `Var = 1/a − 1/(a+b) + 1/c − 1/(c+d)`; risk difference + variance. A **zero cell** → the **Haldane–Anscombe** +0.5
  continuity correction (recorded `choice`, cited — Haldane 1940 / Anscombe 1956).
- **Cross-metric (flagged APPROXIMATIONS in `caveats` + recorded in `choices`):** `d↔r` (`r = d/sqrt(d²+a)`,
  `a = (n1+n2)²/(n1·n2)`; `d = 2r/sqrt(1−r²)`; Borenstein 7.x); `logOR↔d` via the Hasselblad–Hedges/Cox logistic-normal
  factor (`d = logOR·sqrt(3)/π`, `Var(d) = Var(logOR)·3/π²`).

Every `Conversion` reports its variance (and a 95% CI from it) so a study is analysis-ready for a downstream synthesis
tool; the tool itself never combines two of them.

## Honesty / Principles gate

- **Class:** the deterministic-recompute class (Bayes inc-241 / statcheck inc-95 / GRIM inc-127) — a per-value
  computation that carries its evidence (the formula + path + assumptions), not a judgment about the literature.
- **Principles touched:** #7 (no opaque composite — every output shows its path; nothing is a black-box score);
  inspectability-over-authority (the derivation/continuity/approximation *decisions* are shown + recorded, never
  buried); the **never-synthesize** veto (the doc's + the LMM/meta auditors' load-bearing line) — structural, no pool
  path.
- **Misaligned easy path (declined by construction):** a "run the meta-analysis / pool these studies" button; or
  hiding the SD-derivation / continuity-correction / cross-metric-approximation choice inside one number. SP1 has no
  aggregation surface and always surfaces the choice.
- **A-A:** no new veto in play (no accusation, no paywall, no reaching into other stores). The workbench's deeper A-A
  pass (mandatory-human-verification, LLM-not-a-coder) attaches to SP2's LLM extraction, not SP1.

## Gates

- **Security audit** (`.claude/security-audits/`): light — a new endpoint (#1) + a net-new feature (#5). Local,
  stateless, bounded/validated inputs, fail-closed (422 on degenerate), no egress, no external fetch, no new dependency.
- **QA (rule #10):** new `route_64_methods_effectsize.md` — the endpoint + panel + the never-synthesize / path-shown /
  choice-recorded / formula-cited assertions. Keep `build_surface_map.py check` 0-uncovered.
- **Experience pass (rule #11):** a meta-analyst persona converting a study's reported stats (means+SDs, a bare *t*, a
  2×2 with a zero cell) → confirm the path/variance/CI/choice are legible and the "this is an approximation" caveat is
  unmissable on cross-metric; the desire to "just pool these" is declined (no such control), pointed at metafor/JASP.
- **Credit-the-lineage:** Borenstein/Hedges/Higgins/Rothstein 2009 (*Introduction to Meta-Analysis*), metafor
  (Viechtbauer 2010), Fisher 1915, Hedges 1981, Wan et al. 2014, Haldane 1940, Anscombe 1956, Hasselblad & Hedges 1995
  — in-context (`formula_source` per conversion) + a one-click ＋ add methods sources to library; `THIRD-PARTY-NOTICES.md`
  credits the manifest.
- **Rule #1:** all new files well under 600. **No migration.**

## Tests / acceptance criteria (hermetic)

- **No aggregation code path** exists — a static assert: the module imports no meta-analysis/aggregation library and
  exposes no `pool`/`combine`/`heterogeneity`/`meta_regress` symbol; the endpoint accepts a single study only.
- **Each conversion matches a Borenstein et al. (2009) worked-example anchor** (baked into the tests, citeable to the
  textbook — the Bayes-vs-pingouin precedent): SMD (d + g + variances), correlation (Fisher z + variance), binary
  (logOR + logRR + variances), the alternate-input paths (d-from-t, d-from-F, SD-from-CI/SE/IQR), the cross-metric
  approximations (d↔r, logOR↔d).
- **Every result carries its path + formula_source + variance**; nothing is emitted without them.
- **Recorded choices** appear when a decision was made (SD-derivation, zero-cell continuity, cross-metric approx) and
  are absent otherwise.
- **Degenerate inputs → 422** (n<2, negative/zero SD where required, r∉(−1,1), a zero row in a 2×2 with no other cells).
- **Endpoint round-trip** per family; unknown family → 422.

## Scope — in / deferred

- **In (SP1):** the pure converter (core-3 + alternate inputs + cross-metric) + the `POST /methods/effect-size`
  endpoint + the METHODS panel + credit + the honesty surface (path/formula/choices/caveats). No migration, no egress,
  no dependency.
- **Deferred (SP2+):** the extraction **workspace** proper — a REVIEW/SYNTHESIS surface + a user-defined *included
  set* + an extraction **template** + **LLM-drafted, provenance-anchored, human-verified** extraction (the egress +
  heavy-A-A slice: mandatory human verification, LLM-never-an-independent-coder) + a persisted **dataset** that feeds
  *this* converter + **export** to metafor/JASP/RevMan + the audit log. Further deferred (per the doc): screening/PRISMA,
  double-coding/IRR, RoB instruments, figure extraction (point at WebPlotDigitizer, don't build).

## OUTPUT

A deterministic effect-size **converter** as a METHODS-panel tool: hand-enter one study's reported statistics → a
common meta-analytic metric (Hedges' g, Fisher's z, log OR/RR, risk difference) + its variance + a 95% CI, via standard
cited formulas, with the conversion **path shown**, the **formula source cited**, and every **derivation/continuity/
approximation choice recorded** — converting one study at a time, **never** pooling / modeling / doing bias inference
(structural + test-pinned). Local, no LLM, no egress, no migration, no new dependency. The safe trusted sink the
extraction workbench (SP2+) later feeds; credit-the-lineage to the conversion + synthesis tools it builds beside.

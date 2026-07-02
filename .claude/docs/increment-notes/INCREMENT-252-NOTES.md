# Increment 252 — Effect-size converter (meta-analysis workbench SP1)

The first buildable slice of the meta-analysis extraction workbench (`future-tracks/opus4.8_future-tracks_metaanalysisextractionworkbench.md`):
a deterministic **effect-size converter** as a METHODS-panel tool. Hand-enter one study's reported statistics → a
common meta-analytic metric (Hedges' g, Fisher's z, log OR/RR, risk difference) + variance + a 95% CI, via standard
cited formulas, with the conversion **path shown**, the **formula source cited**, and every **derivation choice
recorded**. The GRIM/Bayes assisted-calculator shape (hand-entry, per-value). Reading a paper's stats is deliberately
the LLM/SP2 job.

## Implemented

- **`app/backend/methods/effectsize.py` (NEW, pure — no I/O, no LLM):** a frozen `Conversion` dataclass
  (`metric, value, variance, se, ci_low, ci_high, path[], formula_source, caveats[], choices[]` + `to_dict`) + the
  conversion functions + a `convert(family, inputs)` dispatch. `NO_AGGREGATION = True` sentinel.
  - **SMD → Hedges' g:** `smd` (means+SDs+Ns → Cohen's d → Hedges' g via the J correction; Var(d)/Var(g)),
    `smd_from_t`, `smd_from_f` (two-group one-way F → t → g, caveated).
  - **SD derivations:** `sd_from_se` / `sd_from_ci` / `sd_from_iqr` (÷1.349, Cochrane; Wan 2014 noted) + the
    `sd_derivation` family (a value + its recorded choice).
  - **Correlation → Fisher's z:** `correlation` (atanh, Var 1/(n−3)).
  - **Binary 2×2 → log OR / log RR / risk difference:** `binary`; a zero cell → the Haldane–Anscombe +0.5
    continuity correction (recorded `choice`).
  - **Cross-metric (APPROXIMATIONS):** `d_to_r` / `r_to_d` / `logor_to_d` — each carries the "APPROXIMATION" caveat +
    the recorded cross-metric choice.
- **`app/backend/api/routers/methods.py`:** `POST /methods/effect-size` (sync, stateless — mirrors `POST
  /methods/grim`). `EffectSizeRequest {family: Literal, inputs: dict}` → `EffectSizeResponse` (the `Conversion` shape);
  `convert(...)` wrapped in `try/except (ValueError, KeyError, TypeError, ArithmeticError)` → **422**.
- **`app/frontend/js/08i_methods_effectsize.jsx` (NEW):** `registerPaneSection` id `"effectsize"`, order 38,
  `hideInReadOnly`. A family picker (SMD / SD derivation / Correlation / Binary / Cross-metric) + a per-family sub-
  selector → the input form → a result card (metric + value + variance/SE + 95% CI + the ordered **path** + each
  recorded **choice** + each **caveat** + the **formula source** + a **copy value + variance** button) + the standing
  "converts one study — never pools/models; hand off to metafor/JASP/RevMan" note + a credit block with ＋add-to-library.
  `app/frontend/styles.css` — `.es-*` (tokens only, mirrors `.grim-*`).

## Key technical detail

**The load-bearing boundary — convert, never synthesize (test-pinned).** The module converts a single study at a time;
it defines no pooling / heterogeneity / meta-regression / bias-inference function, and imports no meta-analysis /
stats-aggregation library. Pinned by `test_no_aggregation_code_path` (an AST scan + `NO_AGGREGATION is True`). The
endpoint takes one study's inputs; there is no code path that combines two `Conversion`s.

**Show-the-work honesty:** every result carries its ordered `path` steps + a cited `formula_source` + the recorded
per-study `choices` (SD-derivation / Haldane continuity / cross-metric approximation) + a 95% CI from the variance —
nothing is an opaque number. Cross-metric conversions always carry an "APPROXIMATION" caveat.

**Verification anchors:** hand-computed + scipy-checked Borenstein-et-al.-(2009)-formula anchors baked into the tests
(the Bayes-vs-pingouin precedent, citeable to the textbook — no metafor/R in-env): SMD (means+SDs → g 0.5924, Var(g)
0.04114), d-from-t/F (0.6455), SD-from-SE/CI/IQR (5.0 / 5.1021 / 5.0037), Fisher z (0.5493, Var 0.04), binary (log OR
0.9163 / log RR 0.6931 / RD 0.16667 + variances; zero-cell Haldane → log OR −1.5106), cross (d→r 0.2425, r→d 0.6290,
log OR→d 0.50518).

## Manual verification script

`.local/visual/drive_inc252_effectsize.py` (headed, no egress): seeds a paper → open METHODS → **Effect-size
converter** → SMD means 103/5.5/50 vs 100/4.5/50 → **Hedges' g = 0.592442** (Var 0.041143) + a 4-step path + the
Borenstein source; switch to **Binary** (10/20/5/25, OR) → **log OR = 0.916291**; switch to **Cross-metric** (d→r,
0.5/50/50) → **r = 0.242536** WITH the "APPROXIMATION" caveat; confirm no pool/aggregate control + the hand-off note +
the credit ＋add + a copy button. 0 console/page/genai. **PASS.**

## Gates

- **Audit `.claude/security-audits/2026-07-02_effectsize-converter.md` PASS** (local, stateless, deterministic
  arithmetic; bounded/validated inputs; fail-closed 422; no external fetch / egress / LLM / migration / new dependency;
  the never-synthesize boundary structural + test-pinned).
- **Principles + A-A (rule #9) — aligned** (the deterministic-recompute class — Bayes inc-241 / statcheck / GRIM: a
  per-value computation carrying its evidence; #7 no opaque composite [path shown]; the never-synthesize veto is
  structural; the misaligned "run the meta-analysis / pool these" button + hiding the derivation choice declined).
- **QA (rule #10):** new `route_64_methods_effectsize.md`; surface **183/183 API + 828/828 FE, 0 uncovered**.
- **Experience pass (rule #11, meta-analyst persona, inline):** the converter serves the meta-analyst (a bare t
  converts via the "t + group Ns" path; a zero-cell 2×2 records Haldane; cross-metric is flagged; the "just pool these"
  desire is declined). Fixed-cheap in-increment: a **copy value + variance** button (tab-separated, spreadsheet-paste)
  closing the extract loop (the inc-156 Cite-pane "vet-but-can't-extract" lesson). Filed to backlog: a value+variance
  copy is a bridge until SP2's dataset accumulates.

## Pytest

**971 + 12** hermetic `tests/test_effectsize.py` (full-suite count stamped after the run). The 12: SMD means / t+F
agree / degenerate-raise; SD derivations; correlation + out-of-range-raise; binary measures; binary zero-cell Haldane;
binary empty-raise; cross-metric + always-caveated; `convert` dispatch + unknown-family-raise; the no-aggregation AST
assert; the endpoint round-trip per family + degenerate/unknown → 422.

## NEXT (SP2+, deferred)

The extraction **workspace** proper — a REVIEW/SYNTHESIS surface + a user-defined *included set* + an extraction
**template** + **LLM-drafted, provenance-anchored, human-verified** extraction (the egress + heavy-A-A slice: mandatory
human verification, LLM-never-an-independent-coder) + a persisted **dataset** that feeds *this* converter + **export**
to metafor/JASP/RevMan + the audit log. Further deferred (per the doc): screening/PRISMA, double-coding/IRR, RoB
instruments, figure extraction (point at WebPlotDigitizer, don't build). Also filed: a copy-full-row / dataset
affordance once SP2's dataset exists.

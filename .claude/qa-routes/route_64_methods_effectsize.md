<!-- qa-coverage
api: /methods/effect-size
fe: 08i_methods_effectsize.jsx
-->

# ROUTE 64 - Methods: Effect-size converter (meta-analysis workbench SP1)

**Tier:** 1 local-stateful
**Goal:** Exhaust the assisted, per-value effect-size converter while preserving the load-bearing **convert-never-
synthesize** boundary and the show-the-work honesty. It is **user-driven, per-study** (the user types one study's
reported statistics) — it converts one study into a common metric + variance + a 95% CI; it NEVER pools, models
heterogeneity, meta-regresses, or does publication-bias inference. Local, deterministic, no AI, no egress.

## Environment

Clean seeded instance (`_TEMPLATE.md` -> Environment). **Egress UNSET** (the converter is local/no-LLM — assert no
genai-host request regardless). Register listeners before navigation.

## Standing assertions

- **Console-error budget = 0.** Any console `error` >= Medium; any `pageerror` >= High.
- **No uncompletable control.** Any visible control that cannot be completed through the UI is a bug.
- **Egress gate.** The converter is local; ANY request to a `generativelanguage`/Gemini/genai host is **Critical**.
- **Convert, never synthesize (Critical if violated).** No control pools studies, computes I²/τ²/Q, meta-regresses,
  or does funnel/Egger/publication-bias inference. There is no "run the meta-analysis / pool these" button. The panel
  states it converts one study and hands the dataset off to metafor/JASP/RevMan for synthesis.
- **Show the work / no opaque number (#7).** Every result shows its ordered **path** steps, cites its **formula
  source** (Borenstein et al. 2009, etc.), and records each per-study **choice** (SD-derivation / zero-cell
  continuity / cross-metric approximation) — nothing is a black-box score.
- **Cross-metric = an APPROXIMATION, unmissable.** A `d↔r` / `log OR→d` result carries a visible
  "This is an APPROXIMATION" caveat; it is never presented as an exact conversion.

## Adversarial checklist

- SMD with a zero SD / n<2 -> 422-class, no crash
- correlation r=2.0 (out of range) -> 422-class, no crash
- binary 2×2 with a zero cell -> the Haldane continuity correction is recorded (not a crash, not `inf`/`nan`)
- an empty 2×2 (0,0,0,0) -> 422-class
- unknown family via the API -> 422
- resize to `375x812`, no horizontal overflow

## Steps

1. Open the **METHODS** pane -> **Effect-size converter** section. Confirm the family picker (SMD / SD derivation /
   Correlation / Binary / Cross-metric) + the "converts one study — never pools/models; hand off to metafor/JASP/
   RevMan" intro.
2. **SMD**: means+SDs 103/5.5/50 vs 100/4.5/50 -> **Convert** (`POST /methods/effect-size`). Confirm **Hedges' g ≈
   0.5924** (Var ≈ 0.0414) + a 95% CI + the ordered path (pooled SD -> d -> J -> g) + the Borenstein formula source.
3. Switch the SMD sub-selector to **t + group Ns** (t=2.5, n1=n2=30) -> **d/g ≈ 0.6455** via the shown t path.
4. **Binary** (10/20/5/25, odds ratio) -> **log OR ≈ 0.9163** (Var ≈ 0.39) + the ln(ad/bc) path. Switch measure
   to risk ratio / risk difference and confirm each recomputes with its own formula.
5. **Cross-metric** (d→r, d=0.5, n1=n2=50) -> **r ≈ 0.2425** WITH the "APPROXIMATION" caveat + the recorded
   cross-metric choice.
6. **Correlation** (r=0.5, n=28) -> **Fisher's z ≈ 0.5493** (Var 0.04) + the Fisher 1915 source.
7. On a result, confirm a **copy value + variance** button (the extract loop — a tab-separated value+variance for a
   metafor/JASP row); confirm the standing **hand-off** note (converts one study; pooling/heterogeneity/meta-regression/
   bias belong to a synthesis tool) and the **credit** block (Borenstein/Hedges/Higgins/Rothstein 2009; Fisher 1915;
   Hedges 1981; Haldane/Anscombe; Wan 2014; Hasselblad & Hedges 1995) + a working **＋ add methods source to library**.
8. Adversarial: zero SD / n<2 / r=2.0 / empty 2×2 -> 422-class, no crash; confirm NO pool/aggregate control exists.

## Pass criteria

- The converter computes each family's metric + variance + 95% CI, with the path shown, the formula cited, and the
  per-study choices recorded.
- 0 console/page errors; **0 genai-host requests** (local).
- **No aggregation control** (no pooling / heterogeneity / meta-regression / bias inference); cross-metric results
  are flagged as approximations; nothing is an opaque score.
- Bad inputs fail closed (422-class); a zero 2×2 cell records the continuity correction; mobile viewport has no
  horizontal overflow.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_64_methods_effectsize.md` + `screenshots/` (see `_TEMPLATE.md`).

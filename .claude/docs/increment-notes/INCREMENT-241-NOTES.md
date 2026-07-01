# Increment 241 — Bayesian auditor SP1 (recompute default JZS Bayes factors; future-track #24)

With the competitive-benchmark A-list (A1–A10) and B-list (B1–B5) all done, the maintainer picked a new **METHODS
auditor** from the longer-horizon tracks. Two AskUserQuestion forks settled it: the **Bayesian auditor** (over the
LMM-reporting one — it has a genuine deterministic recompute, the truest fit to callosum's verify-everything thesis),
and **SP1 = the deterministic recompute only** (the Tier-2 completeness checklist deferred to SP2). The Principles
gate ran as I designed it — this is squarely the statcheck / p-curve / GRIM class (PRINCIPLES Example 3).

## What it does

For a paper that reports **default Bayes factors** for t-tests inline (e.g. `t(19) = 2.53, BF10 = 3.4`), recompute the
**default JZS Bayes factor** (Rouder, Speckman, Sun, Morey & Iverson, 2009) from the reported `t` + `df` and flag
where the reported value doesn't reproduce under the default prior. The Bayesian sibling of statcheck.

## The math (`methods/bayes.py`)

`jzs_bf10(t, n, df, r=0.707)` is the Rouder 2009 closed form via `scipy.integrate.quad` over the Cauchy prior on
effect size — the same closed form JASP and the `BayesFactor` R package use. **Verified against the pingouin/published
anchor**: `bayesfactor_ttest(3.5, 20, 20) = 26.743` (two-sample → n_eff = 10, df = 38) → our `jzs_bf10(3.5, 10, 38) =
26.744`. Plus monotonicity sanity (t ≈ 0 → BF < 1; large t → BF ≫ 1) and a degenerate-df → `None` (never a crash).
**No new dependency** — scipy is already an explicit dep (statcheck uses `scipy.stats`).

## The load-bearing honesty design (why the recompute is trustworthy, not false-flag-prone)

Two things the text doesn't tell us, handled honestly:

1. **The prior.** The reported BF used the *authors'* prior. We recompute under the **default** JZS prior (r ≈ 0.707).
   A mismatch is framed **"couldn't reproduce under the default prior"**, never "wrong" (#6 silence-≠-certificate;
   the A-A no-accusation veto).
2. **The design.** A bare `t(df)` doesn't reveal one-sample/paired (n = df+1) vs two-sample (needs the group sizes).
   So we recompute under **both** the paired and the two-sample-equal-groups interpretations and mark a BF
   **reproduced if it matches EITHER within a factor of ~2** (`LOG10_TOLERANCE = 0.3`) — **erring toward "reproduced,"
   the non-accusatory direction** (statcheck's one-tailed leniency). Only a BF matching *neither* is flagged.

**Extraction** anchors an inline `BF10/BF01/BF = value` (with optional scientific notation; BF01 inverted to BF10) to
the **nearest `t(df)` within a character window**. A BF with no adjacent t-stat is **not-checkable** — counted
invisible, never a guessed design.

There is **no composite score** (#7), the aggregate is transparent counts, and every row carries its evidence (the
verbatim match, the recomputed value, the assumed prior, the page — #4/#8).

## Surfaces

- **`GET /papers/{paper_id}/bayes`** (`routers/methods.py`): sync, read-only, mirrors `/statcheck` (reuses
  `get_chunks_for_paper` / `get_paper`; 404 unknown; a metadata-only paper → `checked: 0` honest-empty). The additive
  `prior_scale` is returned for inspectability.
- **METHODS panel `08d_methods_bayes.jsx`** (`registerPaneSection` order 32, `hideInReadOnly`, right after Statistics
  check): auto-runs when its section is the open one (the statcheck pattern); per-BF rows show `reported BF₁₀ = …` +
  `recomputed … (paired|two-sample)` + a reproduce/couldn't-reproduce pill; each row opens its page at **region**
  precision (page-open, never a fabricated exact rect — the coordinate-honesty contract); the default-prior + inline-
  only caveats; a Rouder-et-al. credit block with a one-click **＋ add to library**.

**Fully local — no egress, no LLM, no migration** (an ephemeral job result, like statcheck/p-curve/GRIM).

## Gates

- **Principles (#9) — aligned.** The statcheck class; declined the misaligned "Bayesian reproducibility score /
  pass-fail verdict / teaching BF>3 = significant" paths (the doc's central risk).
- **Audit `2026-07-01_bayes-auditor.md` PASS.** Local read-only; the only input is a path int + the paper's own text;
  bounded (`MAX_RESULTS = 500`) + wrapped parses fail-closed; no SQL written (reads via the audited repo); no
  SSRF/egress/secret; **no new dependency**; coordinate honesty preserved.
- **Credit-the-lineage.** Rouder et al. 2009 + the BayesFactor R package (Morey & Rouder) + the Lakens catalog
  credited in `THIRD-PARTY-NOTICES.md` + one-click library-addable.
- **QA (#10):** new `route_59_methods_bayes.md`; surface 174/174 API + 767/767 FE, 0 uncovered.

## Verification

pytest **894 passed, 1 skipped** (+10 hermetic `tests/test_bayes.py`, no network/model: the JZS two-sample anchor +
monotonicity/degenerate-df; `_normalize_bf10`; `run_bayes` extract-and-reproduce [paired] / two-sample /
gross-mismatch→flagged / scientific-notation + BF01 / a BF with no adjacent t → not-checked / no-BF-text → 0; the
endpoint reproduces + page + `prior_scale`, no-chunks→checked:0, 404). `ruff` + `format` clean; `test_frontend_assembly`
5/5.

**Headed-verified at desktop, 0 errors** (`.local/visual/drive_inc241_bayes.py` — seed a paper + a chunk with
`t(19) = 2.53, BF10 = 2.9`: open METHODS → Bayesian statistics → the section auto-runs → **"1 checked · 0 couldn't
reproduce"** + one row **"reported BF₁₀ = 2.9 · recomputed 2.8452 (paired)"** with a green "reproduces" pill + the
default-prior caveat → **＋ add to library** lands the Rouder et al. paper; 0 console/page errors, 0 genai-host
requests).

**The live spot-check on a real Bayesian paper is the maintainer's** (needs a paper reporting an inline t-test BF; the
math + contracts + a seeded round-trip are proven).

## SP2 (deferred)

The Tier-2 **completeness checklist** (prior stated? convergence diagnostics [R-hat/ESS]? a sensitivity/robustness
analysis? — presence/absence flags, never a verdict; BARG/WAMBS/JASP-guidelines) + more designs (correlation / ANOVA
default BFs). Spec: `.claude/docs/future-tracks/opus4.8_future-tracks_bayesianauditing.md`. Other new-auditor
candidate: the **LMM-reporting auditor** (#23).

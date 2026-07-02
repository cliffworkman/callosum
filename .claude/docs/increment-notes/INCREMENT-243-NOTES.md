# Increment 243 — Bayesian auditor SP3 (Pearson-correlation recompute; ANOVA declined as a finding)

The maintainer asked to **close out** future-track #24, and (AskUserQuestion) chose **"build all three"** remaining
threads: (1) correlation, (2) ANOVA, (3) the textual-coherence advisory flags. This increment is the "more designs"
recompute thread. Its honest outcome: **correlation shipped (verified); ANOVA declined as a finding** (unverifiable →
would fabricate false flags); the textual-coherence flags are the next increment (244).

## Correlation recompute (built + verified)

`run_bayes` now also recognizes an inline APA Pearson correlation reported with its Bayes factor
(`r(df) = …, BF10 = …`; df = n − 2, so n = df + 2) and recomputes the **default correlation Bayes factor**:
`methods/bayes.py::corr_bf10(r, n, kappa=1)` — the exact **Ly, Verhagen & Wagenmakers (2016)** / Wetzels &
Wagenmakers (2012, eq. 25) closed form via the Gaussian hypergeometric `scipy.special.hyp2f1` (+ `betaln`, `lgamma`),
under the default stretched-beta prior width κ = 1 (the JASP / BayesFactor default). **No new dependency** — scipy is
already an explicit dep.

**Verification (the load-bearing point).** `corr_bf10` was verified **exactly against `pingouin.bayesfactor_pearson`**
(the `ly` method — the same formula JASP and the BayesFactor R package use) at 7 points including negative r:
(0.6,20)=10.634, (0.5,30)=9.904, (0.3,50)=1.5555, (0.0,40)=0.19693, (0.8,25)=12721, (0.42,60)=37.389, (−0.5,30)=9.904.
pingouin is a **dev-only verification tool** — its anchor values are baked into `tests/test_bayes.py` as constants;
it is **not a runtime dependency** (the SP1 t-test-anchor posture).

**Extraction.** A new `_RSTAT` regex (`(?<![A-Za-z])r\(\d+\)=…`, leading-dot + negative r). `_scan_text` now collects
**both** t-test and correlation statistics and associates each BF with whichever is **nearest within the window**,
branching on type. A correlation `r(df)` is **unambiguous** (n = df+2 → a single recompute, `matched_design =
"correlation"`) — no paired/two-sample fork. The response gains an additive `computed_correlation`; the panel shows
`recomputed … (correlation)`; the `＋ add to library` credit now library-adds **both** source papers (Rouder et al.
2009 + Ly et al. 2016).

## ANOVA / regression — declined as a FINDING (not shipped)

The maintainer asked for ANOVA too. But the default Bayesian **ANOVA/regression** Bayes factor is **not faithfully
recomputable from `F(df1, df2)` + N alone** — it depends on the design (balance, cell sizes, the g-prior structure),
and there is **no in-env anchor** (pingouin has no ANOVA BF; no R BayesFactor). A candidate g-prior/R² recompute was
tested against the **only** available check — the J=2 → two-sample-t reduction against the *already-verified*
`jzs_bf10` (a one-way ANOVA with 2 groups is a two-sample t-test with F = t²) — and it **did not reduce** (ratios
0.63 → 0.52 across n, not 1.0), confirming an incorrect/unverifiable form.

Shipping an unverified statistical recompute would produce **false "couldn't reproduce" flags** — precisely the
accusation this whole design exists to avoid (rule #2: no "done" without verification; the A-A no-accusation veto).
Per the charter, **a feature that cannot be built to honor the principles is a finding about the feature, not a
reason to relax them.** So ANOVA/regression is deferred until a trusted anchor exists (R BayesFactor, or a validated
Rouder-2012 quadrature). The panel + docstring state this coverage limit honestly (silence≠certificate #6). This is
the aligned move — the same discipline the maintainer applied when *removing* the citation-equity geography signal
on principle (inc 229).

## Surface / gates

- Rides the **existing** `GET /papers/{paper_id}/bayes` additively (a `computed_correlation` field) — **no new API
  surface, no migration, no egress, no LLM, no new dependency.**
- **Principles (#9) — aligned:** a deterministic per-paper signal carrying its evidence (the statcheck / SP1 class);
  the ANOVA decline is itself the aligned action (honoring #2/#6 + the A-A veto over shipping an unverified recompute).
- **Audit — addendum 2 to `2026-07-01_bayes-auditor.md` PASS** (additive read-only field; verified recompute [exact
  pingouin anchor]; local/bounded/no-egress/no-dependency; ANOVA declined as an unverifiable/false-flag risk).
- **QA (#10):** `route_59_methods_bayes.md` extended (correlation ride the existing endpoint + panel); surface
  174/174 API + 769/769 FE, 0 uncovered.
- **Credit-the-lineage:** Ly et al. 2016 / Wetzels & Wagenmakers 2012 credited in `THIRD-PARTY-NOTICES.md` + one-click
  library-addable (alongside Rouder 2009).

## Verification

pytest **904 passed, 1 skipped** (+5 hermetic `tests/test_bayes.py`, no network/model: `corr_bf10` against the
pingouin anchors + degenerate [|r|>1 / n<3] → None; `run_bayes` correlation reproduce [r(58)=.42, BF10=37.4 → 37.39
(correlation)] / gross-mismatch → flagged / leading-dot + negative r / the nearest-statistic-wins branch [a far t +
an adjacent r → correlation]). `ruff` + `format` clean; `test_frontend_assembly` 5/5.

**Headed-verified at desktop, 0 errors** (`.local/visual/drive_inc243_correlation.py` — seed a paper + a chunk with
`r(58) = .42, BF10 = 37.4`: open METHODS → Bayesian statistics → the section auto-runs → **"1 checked · 0 couldn't
reproduce"** + one row **"reported BF₁₀ = 37.4 · recomputed 37.3886 (correlation)"** with a green "reproduces" pill →
**＋ add to library** lands **both** Rouder et al. 2009 + Ly et al. 2016; 0 console/page errors, 0 genai-host
requests).

## NEXT — inc 244 (the last #24 thread)

The fuzzier **textual-coherence** advisory flags (credible-vs-confidence mislabel; BF-direction error) as
clearly-demarcated **Tier-3 advisory** annotations (the future-track doc's Stage 3 — "advisory, requires expert
judgment," never mixed with the Tier-1/Tier-2 flags, conservatively gated). With inc 244, #24 is fully closed:
SP1 t-test recompute (241) · SP2 completeness checklist (242) · SP3 correlation recompute (243) · SP4 advisory flags
(244). ANOVA/regression remains a documented deferral.

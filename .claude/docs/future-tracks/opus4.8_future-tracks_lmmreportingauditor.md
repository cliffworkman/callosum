# Future track — LMM-reporting completeness auditor (METHODS panel)

**Disposition for CC:** Capture into the backlog + `.claude/docs/future-tracks/`. Do not build yet. Consumer-side
reading aid; the **reads-reported-text-only, never-runs-anything** constraint is load-bearing — it's what keeps
Callosum from becoming a statistics environment. Runs through the Principles gate (clears) + a light security
audit (core reads the paper-in-hand; lineage library-adds use the existing acquisition path; any LLM-assisted
detection sits behind the existing consent gate).

## One line
Audit a paper that uses a linear mixed model for whether it *reports* the things a careful reader needs to
evaluate it — random-effects structure, df method, convergence, ICC, R², estimation method, and (for longitudinal
designs with dropout) a missing-data sensitivity analysis — and flag, with grounded recommendations, what's
absent. It reads what the paper prints; it never runs a model.

## The load-bearing line: consumer-side, never producer-side
This fell out of the Troendle (2025) analysis directly. Methods like delta-based controlled-imputation MNAR
sensitivity analysis are *producer-side* — they need the raw longitudinal data and refit the model across an
imputation grid. Callosum has neither the data nor a reason to become a stats environment wrapping `mice`/`lme4`.
So this tool **never runs an LMM, an imputation, or a sensitivity analysis.** It audits the *reporting*: it reads
the methods and results and flags what a careful reader should look for and didn't find. Same move as the Bayesian
auditor's completeness tier; same FLAG-not-ADJUDICATE spine.

## The checks (each fires only when warranted — over-firing is the failure mode)
Each is a *reporting-completeness* flag with an inspectable basis and a grounded recommendation, not a verdict:
- **Random-effects structure** — is the structure specified (which grouping factors carry random
  intercepts/slopes)? Basis: the maximal-vs-parsimonious debate (Barr et al. 2013; Matuschek et al. 2017). Flag
  absence; don't adjudicate the choice.
- **Degrees-of-freedom / inference method** — Satterthwaite, Kenward-Roger, or asymptotic/Wald/LRT? Consequential
  for p-values, routinely unreported. Basis: Luke (2017). Flag if absent.
- **Convergence / singular-fit status** — did the model converge; was the fit singular? Basis: Bates et al.
  (`lme4`). Flag if unmentioned.
- **Estimation method** — REML vs ML (matters for LRTs on fixed effects). Flag if absent.
- **ICC** — reported where a multilevel structure is claimed? Fires only when clustering is asserted.
- **Marginal vs conditional R²** — variance explained reported, and which? Basis: Nakagawa & Schielzeth (2013).
- **Missing-data sensitivity (the Troendle-grounded flag)** — *scoped tightly*: fires only on a repeated-measures
  / longitudinal design with an LMM primary analysis and evident dropout/missingness. Did the paper report a
  missing-data sensitivity analysis (controlled/delta-based imputation, pattern-mixture, reference-based,
  tipping-point)? Basis: FDA ICH E9(R1) addendum + Troendle et al. (2025), Cro et al. (2020), Moreno-Betancur &
  Chavance (2016). Surfaces the regulatory/methodological recommendation; does not assert the paper is wrong.

## Veto-level lines
- **Reads reported text/tables only; never ingests raw data; never runs a model, imputation, or sensitivity
  analysis.** (The identity boundary.)
- **FLAG-not-ADJUDICATE** — surfaces absences + grounded recommendations, never a pass/fail verdict or a claim the
  analysis is wrong.
- **Tight scoping per check** — each flag fires only when its precondition holds (missing-data flag only on
  longitudinal+dropout; ICC only when clustering is claimed). A flag that fires on every LMM is noise.
- **Inspectable evidence** — each flag shows what it looked for and the passage it did/didn't find; the reader
  verifies. If LLM-assisted detection is used, it's consent-gated and every claim is shown against the source.
- **Recommendation-with-grounding, not opinion** — where a flag fires it cites the external basis; it never
  substitutes Callosum's judgment for the field's.

## Honest scope
The tool audits *reporting completeness*, not *analysis correctness*. A paper can report everything and still model
badly; it can omit an item and be fine. It flags what a careful reader should check, not what's wrong. Say so
plainly.

## Interpretation scaffolding (secondary, valuable)
When a paper *did* report an item, the tool can help the reader understand it — what a tipping-point/SIR
sensitivity analysis means, what Kenward-Roger does to df, what conditional vs marginal R² capture. Turns the
auditor into a literacy aid (mirrors the Bayesian-literacy framing) without ever computing anything.

## Credit-the-lineage (per the principle)
Each check cites its methodological basis in-context and offers the source to the library. Seed manifest:
missing-data sensitivity → Troendle et al. (2025, OA / public-domain — clean to add), Cro et al. (2020),
Moreno-Betancur & Chavance (2016), FDA ICH E9(R1); df methods → Luke (2017); random structure → Barr et al.
(2013), Matuschek et al. (2017); R² → Nakagawa & Schielzeth (2013); convergence → Bates et al. (`lme4`).

## Callosum-fit
METHODS panel (with PUBLISHERS, citation-equity, CRediT, statcheck, the Bayesian auditor). Reads the paper already
in the library (parsed text/tables). No new egress for the core checks; lineage library-adds use the existing
acquisition path; LLM-assisted detection sits behind the existing consent gate.

## Gates
- **Principles gate:** clears — consumer-side, flag-not-adjudicate, inspectable, grounded, honest scope.
- **Security audit:** light — reads the paper-in-hand; no new data path beyond existing acquisition + consent-gated
  LLM.

## Tests / acceptance criteria
- The tool **never** ingests raw data or runs a model/imputation/sensitivity analysis (asserted by test).
- Each check fires **only when its precondition holds** (missing-data flag does not fire on a non-longitudinal
  LMM; ICC flag does not fire absent a clustering claim).
- Every flag shows **inspectable evidence** (what was searched, the passage found/absent) and a **grounded
  recommendation** with citation; none is a pass/fail verdict.
- Detection precision/recall are tracked; the tool biases toward *flag-for-reader-verification* over assertion,
  and false fires are easily dismissed.
- Each check **credits its lineage** and offers the source paper to the library.

## OUTPUT
A METHODS-panel LMM-reporting completeness auditor: a consumer-side reading aid that reads a paper's reported
methods/results and flags — with inspectable evidence and grounded, cited recommendations, never verdicts —
whether it reports random-effects structure, df method, convergence/singular fit, estimation method, ICC,
marginal/conditional R², and (tightly scoped to longitudinal designs with dropout) a missing-data sensitivity
analysis grounded in FDA E9(R1) and Troendle et al.; it never ingests raw data or runs anything, credits each
check's lineage and offers the source to the library, and offers interpretation scaffolding when an item is
present.

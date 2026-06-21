# Future track — Meta-analysis extraction workbench (the systematic-extraction front end)

**Disposition for CC:** Capture + `.claude/docs/future-tracks/`. Broad; **scope a deliberate v1** (see Scope). The
most consequence-laden tool in the suite — its output flows into published meta-analyses, so the
**verify-everything / human-in-the-loop / never-synthesize** design is load-bearing, not decoration. Likely
warrants **its own workspace** (a REVIEW/SYNTHESIS surface), not a slot in the crowded METHODS panel — it's a
multi-step workbench, not a single-shot tool. Principles gate needs real scrutiny here (see Gates).

## What it is
A **systematic-extraction workbench**: the provenance-tracked data-collection front end of a meta-analysis /
systematic review, producing an **analysis-ready, fully-traced dataset for export** to a synthesis tool (metafor /
JASP / RevMan). It is the painful, error-prone middle of the pipeline — pulling clean, traceable data out of a
pile of PDFs — which no reference manager does well and which is Callosum-shaped because Callosum already holds the
papers, their parsed text, embeddings, a consent-gated LLM, and a provenance spine.

## The load-bearing boundary — extract, don't synthesize (same line as the LMM tool)
Callosum **extracts, screens, structures, and deterministically converts; it never pools, models heterogeneity,
runs meta-regression, or does publication-bias inference.** Those are inferential statistics — metafor / JASP /
RevMan territory, a stats environment Callosum will not become. The workbench produces the dataset + provenance and
**hands off.**

## The pipeline (components)
1. **Protocol layer (the entry point).** Record the question (PICO), inclusion/exclusion criteria, planned
   moderators, target effect-size metric; optionally link a PROSPERO/pre-registration. Everything downstream is
   auditable against this. This is what separates a real meta-analysis from "scrape a cluster and pool it" — making
   it the *entry point* is how the tool promotes rigor instead of greasing a garden-of-forking-paths synthesis.
2. **Cluster → screening queue (not an inclusion set).** Embeddings surface candidate papers from the library, but
   topical similarity is **not** meta-analytic commensurability. Candidates feed a title/abstract → full-text
   screening flow with recorded include/exclude reasons; the tool auto-maintains **PRISMA flow counts.** Discovery
   is automated; **inclusion is a human judgment against the protocol** — never imply that papers which cluster
   together can be pooled together (the apples-and-oranges error).
3. **Extraction templates.** User-defined extraction schema (N, means, SDs, design features, moderators, RoB
   items); per-study extraction forms.
4. **Assisted extraction with mandatory provenance + verification (the heart, and the danger).** Meta-analysis is
   garbage-in-garbage-out to an extreme degree — one mis-read SD or an SE-vs-SD confusion propagates into the
   pooled estimate and can flip the conclusion. So the consent-gated LLM **drafts** candidate values, but **every
   datum is anchored to its exact source location** (page / table / sentence, highlighted) and stays
   **unconfirmed until a human verifies it against the shown source.** The LLM proposes; the human disposes. The
   tool's value is making verification *fast and traceable*, **not removing the human.** Ambiguous/low-confidence
   extractions are flagged.
5. **Double-coding support (honestly).** Real extraction is double-coded by two independent humans with
   reconciliation + reported inter-rater agreement. The tool supports that and **resists treating the LLM as the
   second coder** — two correlated LLM passes aren't independent, and calling one a "coder" launders unreliability
   into a number. The LLM is a drafting aid for a human coder, full stop. Disagreements surfaced; IRR computed.
6. **Deterministic effect-size conversion.** Convert extracted stats → a common metric (Hedges' g, log OR,
   Fisher's z) + variances, using standard formulas — the natural escalation of the planned effect-size extractor.
   The **conversion path is shown, the formula source cited** (credit-the-lineage: Borenstein et al.; the metafor
   lineage), and the **per-study choice recorded** (estimating SD from a CI vs IQR is a *decision* that must be
   auditable).
7. **Risk-of-bias structuring (structure, don't adjudicate).** Provide standard instruments (RoB2 / ROBINS-I);
   record judgments + supporting quotes; **never auto-score** — same pattern as CRediT and the LMM auditor.
8. **Export, not synthesis.** A tidy **metafor / JASP / RevMan-ready dataset** with the full provenance trail, a
   **PRISMA diagram**, and an **extraction audit log** attached. Then hand off.

## Veto-level lines
- **Never pools, models heterogeneity, meta-regresses, or does bias inference** — extracts / structures /
  converts / exports only.
- **Every extracted datum is provenance-anchored and human-verified before it enters the dataset as trusted.**
- **The LLM drafts for a human coder; it is never an independent second coder.**
- **Clustering surfaces candidates; the protocol defines inclusion** — never imply commensurability.
- **Effect-size conversions are explicit, recorded, and formula-cited.**
- **Structure-not-adjudicate** for RoB and screening (record judgments + evidence; never auto-score).

## Why Callosum fits (and the prior art it must credit)
Callosum already holds the papers, parsed text, embeddings (clustering), a consent-gated LLM, and the
verify-everything provenance spine. Its edge is **local-first, library-integrated, provenance-anchored**
extraction welded to the papers you already manage — not a separate cloud silo you re-upload into.
**Prior art (credit-the-lineage, offer to library):** Covidence, Rayyan (screening); RevMan, metafor, JASP
(synthesis — the hand-off targets); WebPlotDigitizer / metaDigitise (figure extraction, which Callosum points to
rather than does); the PRISMA statement (Page et al. 2021); Cochrane RoB2 / ROBINS-I; Borenstein et al.
(effect-size conversion); and the (accuracy-anxious) LLM-assisted-extraction literature. Claim no novelty where
there's prior art; the differentiator is integration + provenance + local-first.

## Scope discipline — v1 = the extraction core, from an included set
This resolves the meta-analysis-vs-systematic-review scope tension: **v1 is the extraction workbench (the
meta-analytic core), not the systematic-review front end.**
- **v1:** start from a user-defined **included set**; a user-defined extraction template; **LLM-drafted,
  provenance-anchored, human-verified** extraction into the template; **deterministic effect-size conversion** with
  cited formulas; **export** to a metafor-ready dataset + provenance trail + audit log.
- **Defer:** the full screening / PRISMA front end (lean on Covidence/Rayyan or add later); double-coding / IRR
  (add once single-coder-with-verification is solid); RoB instruments; figure extraction (point out, don't build).

## Callosum-fit
Its own REVIEW/SYNTHESIS workspace (not the METHODS panel). Uses the library + embeddings + consent-gated LLM +
the provenance spine; new export path; credit-the-lineage manifest for the cited methods/tools.

## Gates
- **Principles gate (scrutinize carefully):** this is the highest-stakes tool for numeric propagation into the
  published record. The gate should specifically verify the **mandatory-human-verification**, **LLM-not-a-coder**,
  **never-synthesize**, and **clustering≠inclusion** properties — these are what make it safe. It clears *because*
  of them.
- **Security audit:** moderate — consent-gated LLM (existing), library/text ingestion (existing), the new export
  path (validate output). No new egress beyond the existing gates.

## Tests / acceptance criteria
- **No pooling / modeling / meta-regression / bias-inference** code path exists (asserted).
- **Every extracted datum carries provenance** (source location) + a verification state; nothing enters export as
  "trusted" while unverified.
- The **LLM is draft-only**; no path treats it as an independent coder; double-coding (when present) is between
  humans.
- Effect-size conversions use **standard formulas**, **show the path**, **cite the source**, and **record the
  per-study choice**.
- Clustering **surfaces candidates without asserting inclusion or commensurability.**
- Export yields a **metafor / JASP-ready dataset + provenance trail + audit log** (+ PRISMA diagram when screening
  is used).
- RoB / screening **structure judgments + evidence; never auto-score.**
- Cited methods/tools are **credited in-context and offered to the library.**

## OUTPUT
A meta-analysis extraction workbench in its own REVIEW/SYNTHESIS workspace: a protocol-first, provenance-tracked
data-collection front end that surfaces candidate papers by clustering (screening, not inclusion), extracts
structured study data via LLM **drafting that is provenance-anchored and human-verified before it is trusted** (the
LLM never an independent coder), converts to common effect sizes by **cited deterministic formulas with recorded
per-study choices**, structures RoB without adjudicating, and **exports an analysis-ready dataset + provenance
trail + audit log to metafor / JASP / RevMan** — never pooling, modeling, or doing bias inference itself; v1 scoped
to the extraction core from an included set, with screening/PRISMA, double-coding/IRR, and RoB instruments
deferred; full credit-the-lineage to the screening, synthesis, conversion, and reporting tools it builds beside.

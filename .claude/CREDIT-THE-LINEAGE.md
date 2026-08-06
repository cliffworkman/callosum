# Cross-cutting principle — Credit the lineage

*Captured into the values layer from the future-tracks inbox (2026-06-21). A cross-cutting principle, not a tool —
it applies across every Callosum tool that implements or builds on identifiable scholarly work (the generalization
of the tenzing-attribution decision), sitting alongside `PRINCIPLES.md` and `APPROACH-AVOIDANCE.md`. It is a
values-layer commitment; whether to elevate it to a hard rule-#9 gate trigger is the user's call (flagged, not yet
wired).*

## The principle
Any Callosum tool that implements, operationalizes, or is built on identifiable scholarly work or an existing tool
**must**:
1. **Credit that work in-context** — visible in the tool, not buried in a docs footnote.
2. **Offer the source paper(s) to the user's library** — active, one-click attribution via the acquisition path.

And where the lineage is a prior *tool*:
3. **Credit by citation + library-add, never by appropriating the tool's name.** A distinct name that credits the
   source honors it; reusing the source's name collides with it and reads as appropriation — the opposite of the
   intent.

## Why
A project organized around citation, credit, verification, and attribution that failed to credit its own
foundations would be self-refuting. The pattern is also dogfooding (it routes through Callosum's own
acquisition/library) and a genuine differentiator — most tools bury "based on X" in a docs footnote; surfacing it
in-context and making it actionable is uncommonly respectful.

## The lineage manifest (the mechanism)
Each tool declares a small **lineage manifest** — "this tool stands on X; here are the paper(s)" — surfaced
consistently (an "about / built on" affordance) and wired to offer each paper to the library. Lineages to seed:
- **statcheck module** → Nuijten & Epskamp (the package); Nuijten, Hartgerink, van Assen, Epskamp & Wicherts
  (2016, *Behavior Research Methods*).
- **CRediT statement builder** → tenzing (Kovacs, Holcombe, Aust, Aczel et al.); the open CRediT / NISO standard.
- **Bayesian auditor** → Kruschke (BARG, 2021); Vehtari et al. (R-hat / ESS, 2021); the BayesFactor lineage
  (Rouder, Morey et al.).
- **Citation-equity audit** → Lockhart, King & Munsch (2023); Dworkin et al. (2020); King et al. (2017).
- **PUBLISHERS** → DOAJ; SciELO; the TOP Factor (Center for Open Science); AJOL journal metadata
  (Alonso-Álvarez, 2025, Zenodo); NLM Catalog MEDLINE indexing (U.S. National Library of Medicine); Open Policy
  Finder.

## Acceptance criteria
- Every method-implementing tool surfaces its lineage **in-tool** and offers each source paper **to the library**.
- Where a tool's lineage includes a prior tool, the Callosum tool's **name is distinct** from it.
- The lineage manifest is a **consistent affordance** across the suite, not bespoke per tool.

# Cross-cutting principle - Credit the lineage

*Captured into the values layer from the future-tracks inbox (2026-06-21). A cross-cutting principle, not a tool -
it applies across every Callosum tool that implements or builds on identifiable scholarly work (the generalization
of the tenzing-attribution decision), sitting alongside `PRINCIPLES.md` and `APPROACH-AVOIDANCE.md`. It is a
values-layer commitment; whether to elevate it to a hard rule-#9 gate trigger is the user's call (flagged, not yet
wired). Extended on 2026-09-13 to cover contribution lineage inside Callosum's own product, research, and design
history: a provenance-centered platform should not make its own intellectual ancestry opaque.*

## The principle

**Credit the lineage.**

Callosum should preserve two related kinds of ancestry:

1. **Scholarly / tool lineage** - what prior scholarship, methods, standards, datasets, or software a capability
   stands on.
2. **Contribution lineage** - who introduced, challenged, tested, reframed, implemented, or materially changed an
   idea as it developed.

The shared commitment is:

> **Attribute ideas at the level of contribution, and preserve their ancestry as they change.**

A project organized around citation, credit, verification, and provenance would be self-refuting if it credited
external scholarship while obscuring the lineage of its own ideas and decisions.

## Scholarly and tool lineage

Any Callosum tool that implements, operationalizes, or is built on identifiable scholarly work or an existing tool
**must**:

1. **Credit that work in-context** - visible in the tool, not buried in a docs footnote.
2. **Offer the source paper(s) to the user's library** - active, one-click attribution via the acquisition path.

And where the lineage is a prior *tool*:

3. **Credit by citation + library-add, never by appropriating the tool's name.** A distinct name that credits the
   source honors it; reusing the source's name collides with it and reads as appropriation - the opposite of the
   intent.

## Contribution lineage

For material intellectual work on Callosum, preserve enough provenance to distinguish **who contributed what,
when, and in what role**.

Useful contribution roles include, where applicable:

- **Origin** - introduced the core idea or problem framing.
- **Elaboration** - materially extended or structured an existing idea.
- **Critique** - identified a substantive weakness, contradiction, risk, or failure mode.
- **Evidence** - introduced empirical, technical, legal, scholarly, or user evidence that changed the state of the
  idea.
- **Reframing** - changed the conceptual interpretation, justification, or boundary of the idea.
- **Implementation** - materially determined how an accepted idea was instantiated.
- **Disposition** - materially contributed to the decision to implement, defer, supersede, reject, or otherwise
  close a path.

These labels are descriptive aids, not a complete ontology. The goal is not to force every contribution into a
rigid taxonomy. The goal is to preserve enough ancestry that a later reader does not have to reconstruct material
intellectual history from memory.

### Attribute the contribution, not blanket ownership

Prefer:

```text
Cliff Workman - Origin
Proposed the core feedback-provenance concept.

Cliff Workman + ChatGPT - Elaboration
Developed local issue watching and update-time return.

Claude - Critique
Identified a substantive weakness in the justification.

Cliff Workman - Reframing
Distinguished the principle-level commitment from the empirical product hypothesis.
```

Over:

```text
Created by Cliff.
```

or:

```text
Created with AI assistance.
```

The unit of attribution is the **material contribution**, not the whole artifact.

### Do not launder attribution in either direction

Do not present a human-originated idea sharpened by a model as model-originated.

Do not present a model-originated contribution adopted by a human as solely human-originated.

Do not collapse critique, reframing, evidence, implementation, and origin into an undifferentiated `AI-assisted`
label when the distinction is materially recoverable.

Likewise, do not inflate routine editing, formatting, spelling correction, or mechanical transformation into
intellectual contribution merely because a human or model touched the artifact.

### Do not invent lineage to complete the record

If origin or contribution cannot be reliably reconstructed, say so.

```text
Origin not reliably reconstructed.
```

is preferable to confident but retrospective attribution.

When a model or system is materially involved, identify it when reliably known (for example, `ChatGPT` or
`Claude`). Include a specific model/version when it is readily and reliably available, but do not infer or invent a
version merely to satisfy a schema.

### Preserve ancestry as the idea changes

Where practical, contribution provenance should be chronological and append-oriented.

Conceptually:

```text
T1 - proposal
T2 - critique
T3 - reframing
T4 - evidence
T5 - implementation or disposition
```

Do not rewrite T1 so that it appears to have contained what was only learned at T3 or T4.

Issue comments, decision records, PR discussions, experiment receipts, and other contemporaneous artifacts are often
better provenance than silently rewriting an earlier artifact to match the current understanding.

### Attribution is not authorship adjudication

Callosum may preserve facts such as:

```text
Bella identified problem X.
Cliff proposed solution Y.
A model proposed alternative Z.
Vasiliki supplied evidence W.
```

That does **not** mean Callosum can determine:

- who deserves first authorship;
- whose contribution was most important;
- who morally owns an idea;
- how credit should be weighted.

Preserve ancestry. Leave normative judgments about authorship and deserved credit to the humans involved.

## Why

A project organized around citation, credit, verification, and attribution that failed to credit its own
foundations would be self-refuting.

For scholarly and tool lineage, the pattern is also dogfooding: it routes through Callosum's own acquisition/library
path. Most tools bury "based on X" in a docs footnote; surfacing it in-context and making it actionable is
uncommonly respectful.

For contribution lineage, the same principle applies inward. A provenance platform should not erase who originated
an idea, who challenged it, which evidence changed it, or how it reached its present form. Preserving that ancestry
builds trust precisely because the record can distinguish founder contribution, collaborator contribution, model
contribution, critique, and later revision without turning any one of them into mythology.

## The lineage manifest (scholarly/tool mechanism)

Each tool declares a small **lineage manifest** - "this tool stands on X; here are the paper(s)" - surfaced
consistently (an "about / built on" affordance) and wired to offer each paper to the library. Lineages to seed:

- **statcheck module** -> Nuijten & Epskamp (the package); Nuijten, Hartgerink, van Assen, Epskamp & Wicherts
  (2016, *Behavior Research Methods*).
- **CRediT statement builder** -> tenzing (Kovacs, Holcombe, Aust, Aczel et al.); the open CRediT / NISO standard.
- **Bayesian auditor** -> Kruschke (BARG, 2021); Vehtari et al. (R-hat / ESS, 2021); the BayesFactor lineage
  (Rouder, Morey et al.).
- **Citation-equity audit** -> Lockhart, King & Munsch (2023); Dworkin et al. (2020); King et al. (2017).
- **PUBLISHERS** -> DOAJ; SciELO; the TOP Factor (Center for Open Science); AJOL journal metadata
  (Alonso-Alvarez, 2025, Zenodo); NLM Catalog MEDLINE indexing (U.S. National Library of Medicine); Open Policy
  Finder.

## Contribution provenance records (internal mechanism)

Material Callosum ideas, critiques, evidence, reframings, implementation decisions, and dispositions should use the
lightest provenance record that preserves meaningful ancestry.

A reusable pattern is:

```text
## Provenance

YYYY-MM-DD | Role | Contributor(s)
What materially entered or changed at this point.
```

This can live in an issue comment, decision record, PR discussion, experiment artifact, or another durable location
appropriate to the work.

Do not create provenance capture tax for trivial changes. The standard is **material intellectual contribution**.
A useful test is:

> Would a later reader materially misunderstand where this idea came from or why it changed if this contribution
> were omitted?

If yes, preserve it.

## Provenance of this extension

```text
2026-09-13 | Origin | Cliff Workman
Observed that a provenance-centered platform should preserve proper attribution for its own product and intellectual
development, not only for external scholarly sources.

2026-09-13 | Elaboration | Cliff Workman + ChatGPT
Developed contribution-level attribution, chronological intellectual ancestry, symmetric human/AI anti-laundering
rules, the material-contribution threshold, and the distinction between attribution and authorship adjudication.

2026-09-13 | Precursor context | Issues #89 and #90
The need became visible while explicitly recording the ancestry of the feedback-provenance and issue-disposition
concepts after adversarial review sharpened their framing.
```

## Acceptance criteria

### Scholarly / tool lineage

- Every method-implementing tool surfaces its lineage **in-tool** and offers each source paper **to the library**.
- Where a tool's lineage includes a prior tool, the Callosum tool's **name is distinct** from it.
- The lineage manifest is a **consistent affordance** across the suite, not bespoke per tool.

### Contribution lineage

- Material intellectual contributions can preserve **who contributed what, when, and in what role** without
  requiring blanket ownership claims.
- Human-originated and model-originated contributions are not laundered into one another.
- Unknown or unreconstructable lineage remains explicitly unknown rather than being invented.
- Contribution history remains chronological enough that later reframing does not silently rewrite earlier states.
- Routine edits do not create provenance capture tax; the threshold is material contribution.
- Contribution provenance does not pretend to adjudicate deserved authorship or relative moral credit.
- A future reader can distinguish the major origins, critiques, evidence, reframings, and dispositions that shaped a
  material Callosum idea without needing private memory to reconstruct them.

# Future Tracks — Equity & Integrity Signals (HACKADEMIA-derived)

Capture document for a small residual of signals surfaced from the HACKADEMIA manifesto that are
**not already built, planned, or deferred** elsewhere in the backlog. Most of HACKADEMIA is either
already mirrored in Callosum's roadmap (its preregistration MVP = the prereg-deviation producer; its
p-hacking/GRIM/p-curve = the Methods producer set; its legal auto-resolver = Track D acquisition) or
is institution-facing activism (job-app automation, advisor/salary/stipend exposure, peer-review and
conference network mapping, the intervention-engine platform) that sits outside a reference manager's
scope. What follows is the genuine net-new.

**The connective thread (the equity import).** HACKADEMIA's equity commitment — *reduce the advantage
held by well-resourced institutions and well-connected researchers* — imports into a **reading** tool
in a specific, principled form: make the literature's own **prestige / credit / attention machinery
inspectable**, so that citation counts, journal standing, and who-cites-whom do not silently do the
user's thinking for them. The first three signals below are that idea instantiated. They are
**repointed** from HACKADEMIA's native output (public exposure, flagged-paper registries, indices)
to Callosum's: a **private, inspectable signal for the user's own judgment** — per `PRINCIPLES.md`,
never an accusation, never a score, never a verdict. The last two are integrity/forensic rather than
equity, are principle-fraught, and are recorded with that flagged explicitly.

**Cross-cutting gate.** Every item here must pass the `.claude/PRINCIPLES.md` alignment gate before
any build, and — because each is a citation/metadata-derived *signal* — must honor the same spine the
existing tracks commit to: show its evidence, stay decomposed and inspectable, and leave the decision
to the user. None may fold a weak signal into a composite score.

---

## Part 1 — Equity lenses

*Make the status machinery visible so prestige does not substitute for the user's judgment.*

### 1. Overlooked-work lens — the Matthew effect, inverted
*(HACKADEMIA T6.5, repointed from exposure to discovery)*

**What it is.** A discovery lens that surfaces papers highly relevant to an axis but **undercited
relative to their vintage or apparent quality** — the work the user is likely missing *because the
field overlooked it*, not because it is weak. Where the gap-finder follows citation **links** to the
user's set, this follows the **gap between relevance and attention**.

**Equity rationale.** This is the headline equity import. The Matthew effect (citation accruing to the
already-cited, prestige beget­ting prestige) is precisely the bias that buries good work from
lower-prestige authors and venues. A lens that actively surfaces under-attended but relevant work is a
direct counterweight to prestige bias in the user's own reading.

**Relationship to existing backlog.** **Net-new lens; reuses planned infrastructure.** It consumes the
**OpenAlex field/year citation percentile** already planned for the My-Publications dashboard
(`future-tracks/opus4.8_future-tracks_mypublications.md`) and the **OpenAlex adapter** (shared infra,
build-first). It is mechanically **distinct from the gap-finder**
(`…_gapfinder.md`): that surfaces relevant-but-absent papers via citation links; this surfaces
relevant papers whose *attention is low relative to expectation*. It can live as an additional
generator inside the gap-finder track or as a sibling discovery signal — open placement question.

**Dependencies.** OpenAlex adapter (field/year citation percentile, work metadata); axis embeddings
(to establish relevance); the discovery layer.

**Honest caveats.** "Expected citations" modeling is involved; a lighter, honest first version is
*"high axis-relevance × low citation percentile for its vintage = possibly overlooked,"* shown as a
ranked signal with its inputs visible, rather than a trained trajectory model. Low citations also
genuinely mean low quality often enough that the lens must surface, never assert — it points, the
user judges.

**Design rule.** A surfacing signal with visible provenance ("relevant to [axis]; Nth-percentile
citations for its publication year"). Augment, never filter; pull, not push. Never a "hidden-gem
score."

---

### 2. Citation credit-concentration signals — self-citation rate & reciprocal-citation clusters
*(HACKADEMIA T6.2, repointed from "citation laundering" exposure to inspectable signal)*

**What it is.** Two descriptive signals computed over the citation graph: a paper's **self-citation
rate** relative to a field baseline, and its membership in a **tight reciprocal-citation cluster** (a
set that cites itself heavily and the wider literature little).

**Equity rationale.** HACKADEMIA names "citation cartels that recirculate credit within established
networks." Citation counts read as quality signals; surfacing where a count is inflated by
self-citation or a closed mutual-citation loop lets the user see the credit machinery instead of
taking the count at face value — the same prestige-skepticism move as the overlooked-work lens, from
the other direction.

**Relationship to existing backlog.** **Net-new signal; reuses planned infra and slots into a planned
subsystem.** The citation graph it needs (`referenced_works` / `cited_by`) is the same one the
**gap-finder** and the shared **who-cites-this-set** engine build on the **OpenAlex adapter**. The
**theoretical-genealogy** candidate (`…_theorymethodsextension.md`) maps citation *lineage* but
computes neither of these metrics. The signals attach as a new **producer in the METHODS findings
subsystem** (`…_theorymethods.md`), emitting **candidate-class** findings (descriptive, not facts) and
optionally projecting as read-only **system-facts** filterable via the inc-71 tag mechanism (extend
the `system:{…}` provenance vocabulary).

**Dependencies.** OpenAlex adapter (citation edges); the who-cites-this-set engine; the findings
subsystem.

**Honest caveats.** Self-citation is **normal and legitimate** within an active research program — a
high rate is not misconduct. The signal is only defensible as a *rate against a field baseline*, shown
descriptively. Cluster detection has many false positives (subfields legitimately cite within
themselves); show the cluster and let the user read it.

**Design rule.** Strictly descriptive: the rate vs baseline, the cluster membership and who's in it.
Never an "integrity score," never an accusation.

---

### 3. Self-correction signal — positive integrity
*(HACKADEMIA T7.1, repointed to a per-work descriptive badge)*

**What it is.** A **positive** descriptive signal: this work is a registered **replication**, carries
an **author-issued correction**, or **engages a prior null**. The constructive complement to the
(planned) retraction signal.

**Equity / integrity rationale.** The incentive system rewards citation, not correction; epistemic
honesty is undervalued and invisible. Surfacing it gives the user a signal the literature's status
metrics suppress — and resists the failure mode where an integrity layer only ever flags the bad.

**Relationship to existing backlog.** **Net-new producer (positive valence); extends a planned
subsystem.** It is the positive analog of the **retraction producer** (Crossref Retraction Watch) in
the **findings subsystem** (`…_theorymethods.md`) and is adjacent to the **replication-status**
candidate (`…_theorymethodsextension.md`), but distinct: replication-status asks *"has this been
replicated?"*; this asks *"does this work participate in correction?"* Reuses Crossref relation types
/ OpenAlex metadata. Projects naturally as a **system-fact tag** (add `system:{replication|correction}`
to the provenance vocabulary in the Tags & keywords section).

**Dependencies.** The findings subsystem; Crossref/OpenAlex metadata (relation types); the
system-facts tag projection.

**Honest caveats.** Metadata coverage of corrections/replications/null-engagement is incomplete;
absence is not evidence of its opposite (the silence-is-not-a-certificate principle applies). Keep it
a descriptive badge that routes to the correction/replication record, never a "trustworthiness score."

**Design rule.** A descriptive, evidence-linked positive badge. No aggregation into a virtue index.

---

## Part 2 — Integrity / forensic signals (principle-fraught — record with discipline, or not at all)

*Net-new, but each sits close to the misaligned path the principles exist to rule out. Recorded with
the reframing baked in so a later build can't quietly ship the easy, score-or-accusation version.*

### 4. Analytic-flexibility surfacing — researcher degrees of freedom
*(HACKADEMIA T2.2)*

**What it is.** Surface the **specific disclosed analytic decision points** in a methods section — the
exclusion criteria, covariate choices, test selections, branch points — so the reader can judge how
much flexibility the design afforded.

**Relationship to existing backlog.** **Net-new candidate; distinct from prereg-deviation.**
Prereg-deviation (findings subsystem) asks whether a paper *departed from a plan*; this asks how large
the *analytic design space* was, independent of any plan. It would live in the **METHODS module pool**
(`…_theorymethodsextension.md`) and needs **GROBID section awareness** (shared infra already planned
for Track C section-scoping) to locate methods text.

**The principle hazard (why it's here, not in Part 1).** HACKADEMIA's framing is a composite
**"researcher freedom index"** — a textbook `PRINCIPLES.md` #7 violation. The **only** admissible
version **decomposes** into specific, inspectable decision points each tied to its passage, and **never
emits an index or a score**. The index is the easy implementation; that is exactly the warning.

**Honest caveats.** Identifying "analytic decision points" from prose is itself an LLM judgment and
will be noisy; it must be presented as *candidates pointing at passages* the user confirms, not as a
detected truth. High false-positive risk.

**Design rule.** Decomposed, passage-linked candidates only. No flexibility index, ever.

---

### 5. Stylometric inconsistency — a forensic sub-signal
*(sliver of HACKADEMIA T5.4)*

**What it is.** Within-paper stylistic discontinuity as a possible forensic signal, extending the
planned forensic-anomaly bundle.

**Relationship to existing backlog.** **Net-new sub-signal; extends a planned candidate.** It would
attach to the **forensic-anomaly signals** candidate (terminal-digit / Benford / image-duplication) in
the **METHODS module pool** (`…_theorymethodsextension.md`).

**The principle hazard.** This is the **noisiest and most accusation-adjacent** item in the entire
residual — it points at *people*, not statistics. It is the lowest priority, and there is a real case
that recording it at all risks a later blunt implementation. If kept, it is gated hard behind
**signal-never-accusation**, surfaced as a neutral "stylistic discontinuity detected here" pointer at
the spans, and never phrased as authorship suspicion.

**Open question (carried from the surfacing discussion).** Whether to keep this on the list at all, or
whether it sits too close to the misaligned edge to be worth the risk — a decision for the user.

**Design rule.** If built: a neutral, span-pointing signal. No authorship claim, no "ghost-author"
verdict.

---

## Summary — relationship to the existing backlog at a glance

| # | Signal | Net-new? | Builds on (existing backlog) | Slots into |
|---|--------|----------|------------------------------|------------|
| 1 | Overlooked-work lens | New lens | OpenAlex adapter; My-Pubs field/year percentile; axis embeddings | Gap-finder track *or* sibling discovery signal |
| 2 | Citation credit-concentration | New signal | OpenAlex adapter; who-cites-this-set engine | METHODS findings subsystem (producer) + system-facts tags |
| 3 | Self-correction (positive) | New producer | Findings subsystem (retraction analog); Crossref/OpenAlex metadata | Findings subsystem + system-facts tags |
| 4 | Analytic-flexibility | New candidate | GROBID section awareness; methods parsing | METHODS module pool — **decomposed only, no index** |
| 5 | Stylometric inconsistency | New sub-signal | Forensic-anomaly candidate | METHODS module pool — **flagged, open question** |

All five depend on the **OpenAlex adapter** (1–3 directly) or **methods-section parsing / GROBID**
(4–5), both already named as shared infra. None requires new external infrastructure — which is the
honest reason the residual is small and citation-graph-shaped: the one piece of new plumbing
HACKADEMIA leans on is the citation graph Callosum is already building for other reasons.

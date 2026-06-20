# Callosum — Principles

The organizing constraints that govern what Callosum is allowed to do. These are not style
preferences; they are the commitments that distinguish Callosum from a tool that produces fluent
text about the literature. They are demanding on purpose. Anything built on top of Callosum —
especially on the still-open THEORY side — should be answerable to them.

The throughline: **every AI output is an inspectable, grounded signal the user judges, never an
authority the user defers to.** The system's job is not to be right *for* you; it is to make being
right *yourself* cheap.

---

## The commitments

**1. Every claim carries its evidence.**
Any statement Callosum makes about the literature traces to specific source text the user can open
and check. The system's first job is not to produce a conclusion but to make the route from
conclusion to evidence short.
*Why:* a faithful summary and a confabulation are indistinguishable at the surface. Only the
evidence chain tells them apart — so the chain, not the prose, is the actual product.

**2. Signal, not verdict.**
Callosum does not render authoritative judgments. It produces an inspectable signal that points at
the evidence and leaves the decision to the user. "This claim is supported" is the wrong output;
"here are the passages bearing on this claim, with their stance — your call" is the right one.
*Why:* a confident-sounding verdict invites the user to stop looking. A pointer invites them to
look. The tool should make verification the path of least resistance, not the step that gets
skipped.

**3. Facts and candidates are different things, and never conflated.**
A deterministic fact (a registered retraction, a recomputed p-value, a shared identifier) is marked
as such and is stable. An AI-proposed candidate (a possible relevance, a possible claim-support, a
proposed cluster) is marked reviewable and is never auto-applied. They get different visual
treatment and different epistemic weight.
*Why:* the most dangerous error this kind of system makes is a model's guess wearing a fact's
clothing.

**4. The deterministic substrate is the source of truth; the model only narrates it.**
Where a non-model method exists — statistics recomputation, a citation lookup, structured metadata,
embedding similarity — that method produces the finding, and the model's role is at most to explain
it in prose. The LLM is the last component in the chain, never the first, and never the sole basis
for a claim.
*Why:* deterministic methods are inspectable and reproducible; raw model output is neither. Put the
trustworthy thing underneath and let the model describe it, not decide it.

**5. The human is the filter; the AI is the funnel.**
Callosum narrows, surfaces, and orders; the user judges. It is built to augment a comprehensive
human review, never to replace it — and specifically never to let the user quietly offload the
judgment it exists to support.
*Why:* a tool that drifts into being the decider trains its user out of the very expertise it was
meant to amplify.

**6. Silence is not a certificate.**
Every output bounds its own claim. The absence of a flag never means "clean" — it means "not
surfaced by these checks." Coverage is stated, not implied.
*Why:* the most consequential misreading of any integrity signal is treating "nothing surfaced" as
"nothing wrong."

**7. No opaque scores.**
Callosum does not fold signals into a hidden composite number that silently ranks a paper up or
down. Where a score exists, its inputs are visible, separable, and disableable.
*Why:* a composite score is where accountability goes to die — it lets a weak signal drive a strong
conclusion without anyone seeing the move.

**8. Inspectability over authority, always.**
At every surface, the user can ask "where did this come from?" and get a checkable answer. The
system earns trust by being auditable, not by being confident.
*Why:* confidence is cheap and a model has an endless supply of it. Auditability is the only thing
that separates a finding from a fluent guess.

**9. Defaults are the user's, not the author's.**
What Callosum prioritizes derives from the user's own corpus and is theirs to override; the
mechanisms are extensible so no single curator's — or model's — sense of what matters is imposed.
*Why:* a tool that quietly installs its builder's priorities is just a slower way of offloading
judgment to someone else.

**10. Local-first and provider-swappable.**
Deterministic and local methods are first-class; external and model calls are bounded, cached,
on-demand, and behind swappable interfaces. Capability should scale with available compute without
the architecture depending on any one provider.
*Why:* the discipline that keeps cost honest also keeps the system inspectable and portable — and
lets more compute buy more local capability rather than more dependence.

---

## The THEORY side, specifically

The THEORY layer reasons over the *content* of a corpus — what it claims, where it agrees and
conflicts, how its constructs are used, how its findings travel and mutate. It is the
highest-leverage part of Callosum and the least specified, and it is also where the commitments
above are hardest to keep, for a precise reason:

**Synthesis is the operation whose output most resembles authority.** A fluent paragraph about "what
the literature says" is the single most trust-inviting and least verifiable artifact a system like
this can produce. The better the prose, the more it invites the reader to skip the check. So the
THEORY contract is strict:

- **Retrieve, then attribute.** Every synthesized claim is generated *from* retrieved passages and
  carries them. No statement about the corpus exists without the spans it rests on, one click away.

- **Stance and evidence, with confidence.** When the system says papers support, contrast, or merely
  mention a claim, that stance comes from inspectable classification over retrieved text — shown
  with verbatim quotes and a visible confidence — never asserted in prose alone.

- **Surface disagreement; do not smooth it.** Where the corpus conflicts, show the conflict, grouped
  by position. A manufactured consensus is worse than an acknowledged disagreement, because it is
  the failure the reader cannot see.

- **An aggregate is a claim too.** A corpus-level statement — this construct is used inconsistently,
  this effect's variance is high, this theory is fragmenting — is held to the same standard as a
  per-paper one: it resolves to the specific papers and measurements behind it, and it states what
  it did and did not cover.

- **A candidate until the user accepts it.** A THEORY finding is proposed, not pronounced. The user
  confirms, edits, or rejects, and the system remembers the decision.

These constraints are demanding, and that is the point. They are what separate a system that
produces trustworthy signal from one that produces plausible text. Mining a corpus at scale
generates plausible-looking artifacts as a matter of course; the discipline above is how an artifact
is kept from being presented as a finding. Everything built on the THEORY side should be answerable
to it.

---

## Two paths: worked examples

The principles are easiest to apply against worked contrasts. Each example below implements the
*same* feature two ways — one that honors the principles, one that violates them. In every case the
misaligned path is the smaller, faster, more demo-friendly implementation. That is the point:
misalignment is rarely a mistake you stumble into. It is the path of least resistance, and it has to
be declined on purpose. When building a new feature — especially one with an AI component — find the
example it most resembles before writing code.

(Where an example names a module, it points at the real, principle-aligned implementation already in
the tree; read it before building the analogous thing.)

### Example 1 — Synthesizing across multiple papers *(extant)*

**Aligned (how Callosum does it):** retrieve the relevant chunks, generate the summary *from* them,
and pass every claim through local verification — embedding similarity to its cited source, an NLI
stance (support / contrast / mention), a verbatim quote, and a visible confidence. Claims that don't
verify are flagged, not dropped silently. Each citation routes to the exact passage. (The
verification layer + `pipeline.py`.)

**Misaligned:** hand the abstracts to the model, let it write a fluent synthesis paragraph, and
append citations after the fact (or let the model emit plausible-looking attributions). Ship the
prose.

**What each facilitates:** the aligned path produces a synthesis the reader can audit claim-by-claim,
and can trust *because* they don't have to. The misaligned path produces a better-reading paragraph
in a fraction of the code and tokens, and looks identical to the aligned one at a glance.

**The risk:** the two outputs are indistinguishable on the surface and divergent underneath
(principle 1). The misaligned summary states things its sources don't support — not occasionally, but
as a structural property of unconstrained generation — and appends citations that *look* like
grounding without being checked (violates 1, 2, 8). A reader under time pressure accepts it, and the
unsupported claim now propagates with a citation attached, which is worse than no citation: it
travels with borrowed authority.

### Example 2 — Detecting duplicate records *(extant)*

**Aligned (how Callosum does it):** deterministic layered matching — shared identifiers, then
canonical title+author+year, then embedding similarity above a fixed threshold — unioned into groups,
each shown with a confidence and the reason it matched. **Flag-only:** the user resolves each group,
nothing merges automatically, and "not a duplicate" dismissals persist. (`duplicate_detection.py`,
`19_duplicates.jsx`.)

**Misaligned:** ask the model "are these the same paper?" for each candidate pair and auto-merge the
ones it answers yes to.

**What each facilitates:** the aligned path gives a reviewable signal with a visible reason and keeps
every destructive action in the user's hands. The misaligned path is less code, catches messy cases
the deterministic layers miss (a preprint vs its published version), and "just cleans up the library"
without bothering the user.

**The risk:** the model's yes/no is an unverifiable verdict driving a destructive, far-reaching
operation — a merge re-points PDFs, annotations, citations, and axis assignments. One false positive
silently destroys data the user wanted (violates 3, a guess treated as fact; 4, model as source of
truth; 5, judgment offloaded). "Bothering the user" *was* the feature: the duplicate call is exactly
the judgment the user must own, because only they know the preprint and the published version are
both worth keeping.

### Example 3 — Surfacing effect sizes *(hypothetical; planned)*

**Aligned:** extract the reported effect sizes and their context deterministically; show each beside
field benchmarks and the passage it came from; let the user read the distribution. The model, if used
at all, only narrates what the extraction found.

**Misaligned:** roll the effect sizes — plus sample sizes, p-values, journal prestige — into a single
composite "evidence strength" score per paper and rank the library by it; or have the model read each
paper and pronounce whether the effect "is real."

**What each facilitates:** the aligned path lets the user see that an effect is large but estimated
from tiny samples — the judgment that actually matters. The misaligned path produces a clean, sortable
number and a confident verdict: far more impressive in a demo, far easier to act on.

**The risk:** the composite score is where accountability dies (principle 7) — a weak input (prestige)
silently moves a strong output (rank), and no one can see the move. The "is it real" verdict is a
signal masquerading as a judgment the tool isn't entitled to make (principle 2). Both replace the
user's reading with the tool's (principle 5). And a sortable score *invites* the user to stop at the
number — the failure is built into the affordance.

### Example 4 — Answering "what does the literature say about X" *(hypothetical; THEORY frontier)*

**Aligned:** retrieve the passages bearing on the question; classify each as supporting / contrasting
/ mentioning over the retrieved text, with verbatim quotes and confidence; present a structured map
that *surfaces the disagreement* — these papers say X, these say not-X, here are the spans — proposed
as a candidate the user confirms or edits.

**Misaligned:** pass the question and the abstracts to the model and return its prose: "The literature
broadly supports X, though some studies note exceptions." Ship that as the finding.

**What each facilitates:** the aligned path gives the user the actual state of the corpus, conflict
included, every position checkable. The misaligned path gives a fluent, authoritative-sounding answer
that reads like a settled review and takes a tenth of the work.

**The risk:** this is the most dangerous misalignment in the system, because synthesis prose is the
artifact that most resembles authority (principle 2 and the THEORY contract). The model smooths
genuine disagreement into a false consensus — and the smoothing is invisible: the reader cannot see
the conflict that was flattened, so cannot know to look for it (principle 6). An ungrounded "the
literature supports X" is indistinguishable from a grounded one until you check, and the misaligned
version gives you nothing to check (1, 8). On the THEORY side this is not an edge case — it is the
default output of the easy implementation, which is exactly why the contract is strict.

---

## Using this document

Before implementing any feature that produces a claim, signal, or judgment about the literature: name
the principles it touches, name the misalignment it is most at risk of — usually the easier
implementation — and make the aligned design choice explicit before writing code. If a feature cannot
be built to honor these principles, that is a finding about the feature, not a reason to relax them.

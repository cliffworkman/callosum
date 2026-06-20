# THEORY / METHODS Pane — Future Module Candidates

Record of "fits-the-principle" candidates for the THEORY and METHODS panes. These are a
pool, not a build list. Each is written as a self-contained Claude Code prompt in the same
format as the THEORY/METHODS build prompts.

Shared assumptions (all candidates):
- DEPEND ON the THEORY/METHODS build: the module registry (panel sections as self-registering
  units), and for METHODS the findings subsystem (upsert_findings, FactMark, FindingCard, the
  review workflow, tiers, the coverage/scope mechanism) and EVALUATE's consolidation. If those
  are absent, report and stop.
- Reuse, do not fork: the existing highlighter / quote-routing (20_synthesis.jsx + openCitation
  in 40_app.jsx), the embeddings/vector store, app/backend/clustering/abstract_clustering.py and
  the axis machinery, app/backend/summarization (generators + verification) for any grounded LLM
  call, the crossref adapter pattern for new adapters, and the existing card/detail components.
- Principle gate every candidate already passes: verdict becomes pointer; the AI does
  retrieval/extraction/computation and the judgment lands on a checkable output or on the user;
  absence is never rendered as a clean verdict; LLM touches are grounded and verified, never
  freelanced.

================================================================================
## THEORY PANE CANDIDATES
================================================================================
THEORY tools render as registered sections in the THEORY pane, operate over the library, and
route to passages via the existing highlighter. They surface and organize what the literature
says; they do not adjudicate it.

--------------------------------------------------------------------------------
## Disagreement map
Goal: For a selected claim or topic, surface where library papers CONFLICT, grouped by stance,
each item routing to the exact passage. Maps the landscape; adjudicates nobody.

DEPENDS ON: THEORY pane + module registry, the embeddings/vector store, summarization +
verification, the highlighter.
APPROACH: (1) Retrieve passages relevant to the claim across the library via vector search.
(2) Classify each retrieved passage's stance (supports / qualifies / contradicts) — a grounded
LLM call over the retrieved passages ONLY, run through the existing verification step so every
stance tag traces to its exact quote. (3) Render stance-grouped clusters; each item click-routes
to the passage.
LLM ROLE: stance classification over retrieved passages, verified and anchored; cached
(content-addressed over claim + retrieved-passage versions + model + prompt version). No
free-form synthesis.
CONSTRAINTS: it maps disagreement, never declares who is right; a stance with no verifiable quote
is dropped, not shown.
TESTS: a claim with known opposing papers groups them by stance with working anchors; an
unverifiable stage tag never renders.

--------------------------------------------------------------------------------
## Construct-usage glossary
Goal: For a selected term, show how it is defined/used across the library — the variants side by
side with quotes. Built for definitional precision.

DEPENDS ON: THEORY pane, vector store, summarization + verification, highlighter.
APPROACH: retrieve definitional/usage passages for the term; extract each paper's usage (grounded
extraction, verified to the quote); present the variants with per-paper anchors.
LLM ROLE: extraction over retrieved passages, verified and anchored; cached.
CONSTRAINTS: extract observed usages; do NOT synthesize a single "correct" definition.
TESTS: a term used differently across papers yields distinct, anchored usage entries.

--------------------------------------------------------------------------------
## Claim-to-evidence map
Goal: For a user-entered claim, show which library papers bear on it and how (support / qualify),
routed to the supporting passages.

DEPENDS ON: vector store, verification, highlighter.
APPROACH: retrieve passages relevant to the claim; classify bearing (supports / qualifies /
uninformative), grounded and verified; render the supporting/qualifying set with anchors.
LLM ROLE: bearing classification over retrieved passages, verified; cached.
CONSTRAINTS: surfaces what bears on the claim; does not rate whether the claim is true.
TESTS: a claim with known supporting and qualifying papers separates them with anchors.

--------------------------------------------------------------------------------
## Theoretical genealogy
Goal: Trace an idea's evolution across the library chronologically — who built on whom — via the
citation graph plus content.

DEPENDS ON: an OpenAlex adapter (BUILD — integrations/openalex is currently a README stub; needs
references + citing-works for a DOI, following the crossref adapter pattern with external_api_cache
caching), the library, embeddings.
APPROACH: build the citation subgraph among library papers (plus key external nodes); order by
year; label edges with a content-derived relation (builds-on / refines / challenges) as a grounded
LLM label over the ACTUAL citing-context sentences, verified. Render a timeline/graph routing to
papers and the citing passages.
LLM ROLE: edge-relation labeling over real citing-context sentences, verified; graph construction
otherwise deterministic.
CONSTRAINTS: OpenAlex is paid/rate-limited — cache aggressively, build on demand; an unlabeled edge
is shown as a bare citation link, never a guessed relation.
TESTS: a known lineage renders in order with content-grounded edge labels and working routes.

--------------------------------------------------------------------------------
## Conceptual gap surfacing
Goal: Surface topics adjacent to your axes that the library UNDER-covers, framed as coverage
description.

DEPENDS ON: the axes (15_axes.jsx), embeddings, clustering, and an external source
(OpenAlex/Semantic Scholar) for adjacent literature.
APPROACH: compute the library's topic coverage (axis/embedding density); compare against adjacent
external literature to find thin regions; present "dense on X, thin on the X–Z interface," routing
to the sparse region and to representative adjacent papers.
LLM ROLE: minimal/none — embedding density + external counts.
CONSTRAINTS: describe coverage; the "worth chasing" judgment is the user's. Never imply a thin
region is a flaw.
TESTS: a library deliberately thin in one adjacent area surfaces that area as a coverage gap.

--------------------------------------------------------------------------------
## Quote bank
Goal: Collect quotes tagged by claim/axis/paper as you read, building a structured evidence base
for writing.

DEPENDS ON: the existing highlighter/annotation system, the axes.
APPROACH: a THEORY-pane collector where selecting text saves a quote with its exact location plus
tags (claim, axis, paper); browse / filter / export. Grounded by construction — the user's own
quotes.
LLM ROLE: optional auto-tag SUGGESTION (grounded, user-confirmed before applying).
CONSTRAINTS: a data/UX tool reusing existing annotation; suggested tags are never auto-applied.
TESTS: saving a selection persists the quote with location + tags; filtering by axis returns it;
export round-trips.

--------------------------------------------------------------------------------
## Operationalization extractor  [SEAM CASE — construct = theory, measure = methods]
Goal: For a construct, extract how each paper OPERATIONALIZED (measured) it.

DEPENDS ON: vector store, verification, highlighter.
SEAM NOTE: construct is THEORY, measurement is METHODS. Place by dominant use (lean METHODS), or
treat as the first dual-registered module if both panes genuinely want it — decide per DESIGN.md.
APPROACH: for a construct, retrieve methods/measures passages; extract the operationalization
(instrument, scale, task) grounded, verified, anchored; present per-paper.
LLM ROLE: extraction over retrieved passages, verified.
CONSTRAINTS: extract the stated measure; do not judge construct validity.
TESTS: papers measuring the same construct differently yield distinct, anchored operationalizations.

================================================================================
## METHODS PANE CANDIDATES
================================================================================
METHODS tools emit FACTS or CANDIDATES into the findings contract and render via FactMark /
FindingCard. Most are deterministic computations; LLM use, where present, is grounded extraction
only. All respect the bounded-claim / coverage rule: absence is never "clean."

--------------------------------------------------------------------------------
## GRIM / GRIMMER / SPRITE consistency checks
Goal: Deterministic consistency checks on reported means/SDs given sample size — emit reviewable
CANDIDATES.

DEPENDS ON: the findings subsystem (candidates, FindingCard), paper text.
APPROACH: extract reported means/SDs/Ns and the response granularity where inferable; run GRIM
(is the reported mean possible given N and integer-scale granularity), GRIMMER (SD consistency),
optionally SPRITE; emit CANDIDATES (tier=primary — high-confidence arithmetic) stating the
inconsistency as evidence with a text anchor.
LLM ROLE: none.
CONSTRAINTS: static given the text — run on import / re-extraction, idempotent; coverage note
records the integer-scale + extractable-N assumptions; whether an inconsistency matters is the
user's review.
TESTS: a known GRIM-inconsistent mean yields a primary candidate with anchor; a clean paper yields
none but records coverage.

--------------------------------------------------------------------------------
## Sample-flow consistency
Goal: Do the participant Ns add up across recruited / excluded / analyzed? — emit a CANDIDATE on
mismatch.

DEPENDS ON: findings subsystem, paper text.
APPROACH: extract the participant-flow numbers (recruited, excluded-with-reasons, analyzed),
grounded and verified; check arithmetic consistency; emit a primary candidate stating the mismatch
with anchors to each number.
LLM ROLE: grounded extraction of the flow numbers, verified; the arithmetic is deterministic.
CONSTRAINTS: bounded coverage (only where a flow is reported); never imply a clean flow when none
was parseable.
TESTS: a paper whose Ns do not reconcile yields a primary candidate; a consistent flow yields none.

--------------------------------------------------------------------------------
## Reporting-checklist presence
Goal: Detect study type and surface the relevant reporting checklist (CONSORT / PRISMA / STROBE /
ARRIVE) with which items are detectably present.

DEPENDS ON: findings subsystem, paper text.
APPROACH: classify study type (grounded); map to the checklist; detect each item's presence via
text-mining. POSITIVE-detection only (like transparency: present = reliable, absent = unknown);
emit detected items as informational FACTS plus the checklist reference.
LLM ROLE: study-type classification (grounded), verified; item detection is text-mining.
CONSTRAINTS: absence of an item = not detected, NOT missing; surface this in coverage; render
descriptively, never as a compliance score.
TESTS: an RCT surfaces CONSORT with detected items present; a differently-phrased item is not
flagged as "missing."

--------------------------------------------------------------------------------
## Citation stance (via Scite MCP)
Goal: Is the paper's key claim SUPPORTED or DISPUTED downstream? — surface counts routing to the
disputing work.

DEPENDS ON: findings subsystem, the connected Scite MCP.
APPROACH: query Scite for the paper's citation classifications (supporting / mentioning /
contrasting); surface as a FACT mark ("cited 40x; 3 contrasting") with click-through to the
contrasting citations.
LLM ROLE: none — Scite supplies the classification.
CONSTRAINTS: bounded meaning (the stance is Scite's, with its own error profile — state the source);
world-state signal, so cache with a TTL and refresh on a cadence, like retraction.
TESTS: a paper with known disputing citations shows the contrasting count routing to those works.

--------------------------------------------------------------------------------
## Effect-size extraction + benchmark context
Goal: Extract reported effect sizes and place them against reference benchmarks — informational,
not a verdict on importance.

DEPENDS ON: findings subsystem, paper text.
APPROACH: extract reported effect sizes (d, r, eta-squared, OR) grounded, verified, anchored;
attach reference benchmarks (e.g., Cohen's conventions) as a REFERENCE LOOKUP band, not a
freelanced "small/large." Emit as informational facts (the extracted ES + the benchmark band).
LLM ROLE: grounded extraction of the effect sizes, verified.
CONSTRAINTS: the benchmark is reference context, never a judgment of practical importance; that
stays with the user.
TESTS: a reported d=0.2 surfaces with its anchor and the conventional band, with no
importance-verdict attached.
PAIRS WITH: Statistical power / design sensitivity (below) — contrasts the extracted effect against
the design's minimum detectable effect.

--------------------------------------------------------------------------------
## Statistical power / design sensitivity
Goal: Surface a LEGITIMATE power signal for an already-published study as DESIGN SENSITIVITY —
never observed/post-hoc power. Pairs with effect-size extraction: it adds the design side and shows
design-capability against the relied-on effect.

DEPENDS ON: findings subsystem; reuses the statcheck APA-NHST extraction (test + df), the
sample-flow extraction (N), and effect-size extraction (the effect to contrast). Mostly a
SYNTHESIZER of those extractions plus a deterministic power computation (statsmodels-style) —
little new parsing, no LLM judgment.

HARD REFUSAL: do NOT compute observed / post-hoc power (power from the study's OWN observed effect).
It is a monotonic transform of the p-value, carries no new information, and is a known error
(Hoenig & Heisey, "The Abuse of Power"). Decline it explicitly with a one-line note on why — the
refusal is a teaching moment.

APPROACH (three legitimate pieces):
1. Minimum detectable effect size (MDES): given the extracted N, test, and alpha, the smallest
   effect the design could reliably detect at conventional power. Deterministic; never uses the
   observed effect. Present it AS A CONTRAST with the extracted effect: "design could reliably
   detect d >= 0.62; the effect interpreted as meaningful is d = 0.34." The juxtaposition is the
   value; the user draws the conclusion.
2. Power-analysis consistency check (statcheck-for-power): if the paper STATES an a-priori analysis
   ("N=64 for 80% power to detect d=0.5"), recompute it and flag an inconsistency if the stated N
   does not yield the stated power. A reviewable CANDIDATE.
3. Power for an EXTERNAL effect (where available): power to detect a meta-analytic / prior effect
   estimate — legitimate because the effect comes from outside the study. Needs an external
   estimate (sparse); wire to the replication / benchmark sources.

EMITS: MDES and the design-sensitivity numbers as informational FACTS, anchored to the reported N
and test; the power-analysis consistency check as a CANDIDATE; observed power is declined, not
emitted.
LLM ROLE: none for the computation; the one judgment-prone step (reading the design/test) is already
handled, grounded and anchored, by the statcheck extraction.
CONSTRAINTS: state the alpha assumption when unstated (do not silently pick .05); conventional power
(80%) is a convention, not a law — make it adjustable or show a small power-across-effect curve so
no single number reads as a cutoff; the MDES-vs-effect contrast is design-capability-as-fact, NEVER
accusatory (there are legitimate reasons to interpret a small effect).
TESTS: a study with a small N surfaces an MDES well above its relied-on effect, shown as a contrast
with anchors and no "underpowered" label; a stated power analysis whose N does not match its target
yields a candidate; a request for observed power is declined with the teaching note.

--------------------------------------------------------------------------------
## Replication status
Goal: Does this finding have a registered/published replication (success/failure)? — surface known
replications as facts.

DEPENDS ON: findings subsystem, external sources (replication databases, OSF registrations,
OpenAlex).
APPROACH: look the paper/finding up in replication resources; surface located replications as FACTS
with links and outcome where stated.
LLM ROLE: none (lookup), or grounded extraction of a stated outcome, verified.
CONSTRAINTS: sparse data — "no replication found" = not located, NOT "unreplicated"; bounded
coverage; cache/TTL.
TESTS: a finding with a known replication surfaces it with a link; one without yields a "none
located" coverage note, not "unreplicated."

--------------------------------------------------------------------------------
## Corpus p-curve  [COLLECTION-LEVEL]
Goal: Over a SELECTED library subset, does the body of work show evidential value? Present the
p-curve for the user to interpret. (The grounded, valid rescue of "detect p-hacking.")

DEPENDS ON: the METHODS infra, the ported statcheck APA-NHST extractor (reuse it), and a
library multiselect (checkbox-subset, like the My-Publications selection).
APPROACH: extract the focal/test p-values across the SELECTED set (reuse the statcheck extraction),
run a p-curve analysis (right-skew test), and present the curve plus the right-skew result as a
grounded statistical OUTPUT. Collection-level only — never single-paper.
LLM ROLE: none.
CONSTRAINTS: present the distribution; the interpretation (evidential value vs concern) is the
user's. Requires a valid, user-chosen analysis set; state the selection it ran on. NEVER label a
paper "p-hacked."
TESTS: a set with right-skewed p-values shows evidential value; a flat/left-skewed set shows the
curve without any accusatory label; the analyzed set is stated.

--------------------------------------------------------------------------------
## Forensic anomaly signals (terminal-digit / Benford / image-duplication)
Goal: Surface deterministic integrity-anomaly SIGNALS as reviewable candidates — the signal, never
the accusation.

DEPENDS ON: findings subsystem, the paper PDF (figures) and extractable numeric tables.
APPROACH: terminal-digit and Benford analysis on extractable numeric tables (deterministic);
optionally image-region duplication detection on figures (pixel analysis). Emit CANDIDATES stating
the anomaly as evidence with an anchor (the table region or the figure regions). Tier by signal
strength.
LLM ROLE: none.
CONSTRAINTS: HIGH-STAKES framing carries this entire feature — always "here is a statistical
anomaly, you judge," NEVER "fraud" or "fabrication." The label stays with no one but the user, and
even the user is given only the signal, not a conclusion.
TESTS: a table with anomalous terminal digits yields an anchored candidate framed as an anomaly;
no output ever uses accusatory language.

================================================================================
## NOTES FOR LATER
================================================================================
- OpenAlex adapter is the shared dependency for genealogy, gap-surfacing, and replication — build
  it once (citation graph + works), cache in external_api_cache, on-demand.
- Citation-stance reuses the connected Scite MCP rather than a built adapter.
- p-curve and corpus tools need a library multiselect; align it with the My-Publications selection
  mechanism so there is one selection model.
- The statistical power / design-sensitivity tool is a SYNTHESIZER — it reuses the statcheck,
  sample-flow, and effect-size extractions and adds only a deterministic power computation, so build
  it after those three; its hard refusal of observed/post-hoc power is the entry's most important
  line.
- The operationalization extractor is the test case for whether DESIGN.md's "place by dominant use"
  resolves seam tools or whether a small dual-registration is worth allowing.
- Every candidate already passes the where-did-the-judgment-go gate; that gate is the entry test
  for any future addition to either pane.

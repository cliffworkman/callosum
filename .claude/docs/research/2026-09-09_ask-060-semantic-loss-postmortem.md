# Ask 0.6.0 — Semantic-loss postmortem & next-experiment design

**Date:** 2026-09-09
**Type:** Architectural postmortem + next-experiment design. Analysis only — no code, no inference,
no 0.7.0 edit, no `R_0_6` freeze, nothing staged or committed.
**Primary source:** `callosum-final-060-20260909-131923/REPORT_FINAL_060.md`
(PROTOCOL SHA256 `d123ea05…`, REPORT SHA256 `d504b244…`), branch
`experiment/ask-cli-staged-synthesis`, HEAD `6b4b8d9`.
**Corroborating source:** `experiments/ask_cli_revised/{qwen.py, synthesis.py, ledger_renderer.py}`
(the built worker/renderer contracts); calibration lineage Runs 0.5 / 0.6 / 0.6a / 0.6b;
the 0.7.0 prereg summary in `.claude/SCRATCH.md`.

> **Epistemic discipline for the whole document.** Everything below is bounded to **one frozen
> experimental condition**: a single 0.6.0 receipt over two positive-corpus questions
> (q_aib, q_depr) plus one negative control (q_builtenv). A passed boundary is **demonstrated on
> this receipt**, never promoted to a universal reliability claim. The following distinctions are
> load-bearing and are preserved throughout, never smoothed:
> - quotation fidelity ≠ proposition fidelity
> - ancestry ≠ fidelity ≠ retrieval utility
> - verification ≠ responsiveness ≠ completeness
> - request preservation ≠ evidence usefulness
> - model failure under one arrangement ≠ global model incapacity
> - preserving nodes ≠ preserving edges
> - null / mixed / uncertain evidence is **evidence structure** (kept distinct), not disposable
>   prose qualification

---

## 1. EXECUTIVE VERDICT

The 0.6.0 experiment is **complete**, and its verdict — *IMPROVED BUT NOT READY — RESPONSIVENESS
LIMIT REMAINS* — is correct and well-earned. It should not be reinterpreted as an incomplete
experiment because a chat handoff was truncated; the receipt is whole.

What the receipt changes about our understanding: the dominant historical bottleneck
(evidence-selection output starvation) was **isolated and resolved on this receipt** by
structured-output enforcement, and request preservation and terminal provenance held. With those
two large, previously-confounding failures removed, the remaining loss is now **localizable** rather
than diffuse. The clearest remaining destructive boundary is **claim formation** — the stage that
takes an *exact* source span (verifier quote-confidence 1.0) and emits a free-paraphrase "claim."
That stage loses information in two distinct ways that the report's aggregate numbers bundle: a
**mechanical** way (152/328 ungrammared truncations that fail to `None`, deleting the span's
evidence) and a **representational** way (the paraphrase changes subjects, populations, direction,
reverses nulls, and imports neighboring assertions). The single most important sentence in the whole
receipt is: **all 148 candidate quotes are exact-source matches at confidence 1.0, and manual review
still found the derived propositions unsound.** Quotation fidelity is not proposition fidelity.

The recommended next step is a **small, isolated, model-fixed claim-representation experiment** on
the frozen claim-formation input packets. It does not attempt a rebuild, does not touch retrieval or
thresholds, does not attribute anything to model size, and does not produce `R_0_6` — it produces a
**candidate** claim/evidence representation whose only job is to answer one question cleanly: *does
replacing a generative rewrite with a source-preserving representation change semantic fidelity, with
the model held fixed?*

---

## 2. WHAT 0.6.0 ACTUALLY ESTABLISHED

Bounded to this frozen receipt:

- **Request preservation — DEMONSTRATED PRESERVED ON THE FROZEN 0.6.0 RECEIPT.** 22/22 live units,
  26/26 deterministic; original-question text/SHA, stable IDs, offsets, full parent context, all 12
  operations, and exact specialist identity (`anomalous is bad bias`) survive; no generated candidate
  answer masquerades as a request. This is a demonstrated property of the current pipeline on this
  input set, not a universal guarantee.
- **Structured-output starvation — RESOLVED ON THE FROZEN RECEIPT for evidence-selection.** Stage A
  50/50 required structured treatments completed (0 truncation, 0 parse failure, 0 structurally
  invalid); live Stage B selection 256/256 whole, schema-valid, non-truncated. Historically
  selection truncated 46/50. The intervention was narrow and specific: selection calls now carry an
  OpenAI-compatible `response_format` / `json_schema` (name `calibration`, `strict: true`, item enum
  = the exact offered span IDs, empty array allowed). The report's own guard applies: *"no claim of
  universal reliability."* Valid JSON is **not** proof of useful span choice — of 78 AIB selected
  occurrences, 62 were nonresponsive to the source-unit focus.
- **Retrieval was corpus-sensitive on the two positive questions.** AIB reached actual
  anomalous-is-bad construct evidence (amygdala↔prosociality/dispositions in chunks 34974/35111;
  explicit vs slight/nonsignificant implicit bias in 35068). Depression surfaced substantive LLD,
  serotonin, amyloid, glucose, gray-matter, and cognitive material — **including null/uncertain
  findings.** Built-env retrieved only other-domain material; the user confirmed **after freeze** that
  the library contains no built-environment literature (a negative control — see §11).
- **Terminal renderer held its provenance guarantees on this receipt.** 14/14 emitted proposition
  IDs and spans resolve against both sealed span catalogs and the read-only source DB; zero
  renderer-added scientific claims or aggregates; all 22 unresolved units remain visible. It exposes
  upstream defects rather than laundering them into fluent prose.
- **Deterministic invariants and regression tests pass.** 16 revised Ask CLI tests, the revised and
  original selfchecks, calibration + Run06/06a/06b selfchecks, and the 15/15 Cliff adjudication
  checks. These establish deterministic invariants, **not** live semantic success.

---

## 3. UPDATED LOSS PIPELINE

The pipeline, as actually built (`qwen.py`): decompose → obligations (natural-language, no IDs) →
nominate papers → within-paper retrieval → **context gate** (`accept/before/after/both/discard`, cap
48, **ungrammared**, fallback `accept`) → **evidence-selection** (span-IDs only, cap 96, **grammared
this run**) → **claim-formation** (free paraphrase of one exact quote, cap 192, **ungrammared**,
fallback `None`) → obligation-map → local NLI verifier (ret 0.70 / quote 1.0 / support 0.55 /
contra 0.55) → recovery (one literal re-query) → constrained `verbatim-ledger-v1` renderer.

Where information is lost **now**, ranked, with failure class un-bundled:

| # | Boundary | What is lost | Failure class |
|---|---|---|---|
| 1 | **Selected span → claim** | 152/328 claim calls truncate (fail to `None`) → the exact span produces no proposition; and even when a claim forms, meaning mutates | **mechanical** (truncation→None) **+ representational** (paraphrase mutation) |
| 2 | **Context gate → offered evidence** | 246/354 gate calls truncate (fail OPEN to `accept`) → context-growth judgment never exercised, fragments pass on; separately, genuine `discard` drops useful nulls | **mechanical** (truncation→accept) **+ semantic** (discard), bundled in the report |
| 3 | **Verification → responsiveness** | verifier confirms claim↔source support but accepts semantically unsound and non-responsive claims (EBQ subject error 0.8914; generic caption 0.9375) | **verification-policy** |
| 4 | **Relationships** | brain→behavior / brain→attitude edges exist in retrieved spans but never reach verified support; nodes survive, edges do not | **representational** |
| 5 | **Qualifications/nulls** | retrieved null/mixed/uncertain findings never survive to verified output (a null reversed into a decrease) | **representational** |
| 6 | **Recovery** | one literal re-query returns the same hits, duplicates every initial verified record (7 duplicates) | **mechanical/architectural** |
| — | Request → referent | (preserved on this receipt) | — |
| — | Selection envelope | (resolved on this receipt via grammar) | — |
| — | Terminal renderer | (held guarantees on this receipt) | — |

The central reframing: the two boundaries that dominate the remaining loss (gate, claim) are **both
ungrammared** and therefore both mix a large *mechanical* (format-starvation) loss with a *semantic*
loss. Selection just demonstrated that the mechanical half of exactly this failure class is
removable. We cannot cleanly attribute either boundary's *semantic* contribution until its mechanical
truncation is removed the same way.

---

## 4. CONTEXT-GATE POSTMORTEM (Boundary A)

**What job it is intended to perform.** `context_gate` returns one of `accept / before / after / both
/ discard` for a retrieved packet against one subquestion. `accept` = the packet already contains a
complete relevant claim, stop growing; `before/after/both` = grow context to make the current
material interpretable; `discard` = even with context this text won't yield a helpful claim (its
prompt names abbreviation lists, headings, bibliographic metadata, keyword lists, unrelated
discussion).

**It bundles at least three tasks:** (1) **noise control** (discard obvious non-evidence), (2)
**context-window budgeting / sufficiency** (grow vs stop), and (3) implicitly **relevance**. These
are not one task. Noise control is largely a *deterministic* judgment (is this a running header, a
reference list, a keyword line?). Sufficiency/growth is a genuine reading judgment. Relevance shades
into responsiveness, which the pipeline never judges cleanly (§6).

**Why destructive exclusion is dangerous here.** `discard` is irreversible: once the gate drops a
packet, no downstream stage can reconsider it. The receipt shows the concrete harm — the gray-matter
null passage **28044** was discarded by the gate, and null evidence is exactly what depression
qualification retention needed (§8, §13).

**But the report's headline number is bundled and must be un-bundled.** "Context gate → offered
evidence: DEMONSTRATED LOSS; 246/354 truncations" conflates two very different events:
- **Mechanical truncation (246/354).** The gate is ungrammared with a 48-token cap; a 1.5B rambles
  past 48 tokens without closing valid JSON, so the call truncates. On truncation the code fails
  **OPEN** to `_FROZEN_GATE_FALLBACK = {"action": "accept"}`. This is **not a direct deletion** — the
  packet is *kept*. What is lost is the *growth decision*: a packet that needed `before`/`after`
  context is accepted as-is, a fragment, which then feeds claim drift downstream. Only ~108/354 gate
  calls (31%) actually produced a model action at all.
- **Semantic discard.** Among the calls that *did* return a valid action, genuine `discard` decisions
  removed useful material (28044). This is a real judgment error, distinct from truncation.

**Consequence for interpretation.** We currently **cannot assess the gate's semantic judgment**,
because 69% of its calls never produced one — they truncated to `accept`. Any claim that "the gate's
judgment is wrong" is premature. The gate's *first* problem is that its judgment is mostly not being
exercised.

**Could deterministic/ranking machinery reduce the destructive model judgment?** Yes, plausibly, for
the noise-control half. Callosum already ships an instrumented deterministic classifier — H1a
`chunk_structure.evidence_role` (`scientific | bibliographic | structural | unknown`, inc 577) — that
targets exactly the categories the gate's `discard` prompt enumerates. Delegating discard to the
deterministic classifier (with `unknown` treated as first-class and *never* auto-excluded, per the
inc-577 rule) would remove most destructive model discard while leaving the genuine reading judgment
(grow-or-stop) to the model.

**Could gating become non-destructive?** Yes. A retain-and-rank policy — keep all candidates, mark
priority/relevance, allow downstream reconsideration — would eliminate the irreversible-loss hazard
entirely, converting the gate from a *filter* into a *scorer*. The "not selected but retained" state
is the researcher's own instinct ("this may matter; I'm not ready to discard it," §12).

**Is model strength the binding issue?** No evidence yet. The binding issues visible on this receipt
are (a) the format/output-cap starvation (the same class grammar fixed for selection) and (b) the
gate's *information contract* itself (destructive + bundled tasks). Neither is a capacity claim.
**Do not remove the gate and do not keep it as-is by default** — its contract should be redesigned
(deterministic noise control + non-destructive growth scoring), and only then, with reliable output,
can its residual judgment quality be measured.

---

## 5. CLAIM-FORMATION POSTMORTEM (Boundary B) — the headline

**The finding, stated precisely.** All **148 candidate quotes are exact-source** (verifier
quote-confidence 1.0). Manual review of the derived paraphrased claims nonetheless found unsupported
additions, changed subjects, changed populations, imported neighboring assertions, qualification
loss, altered scope, and nonpropositions (84/148 occurrences explicitly labeled UNSUPPORTED). The
exact-quote guarantee is real and the propositions built on it are still unsound. **A codec can be
syntactically lossless and semantically lossy.**

**Why the current stage loses information — two mechanisms.**
- **Mechanical (evidence deletion).** `form_claim` is ungrammared with a 192-token cap; 152/328 calls
  truncate and fail to `None`. A selected exact span that truncates simply produces no proposition.
  This is the *same* format-starvation class that grammar just removed for selection — and here it is
  strictly destructive (the span's evidence vanishes), not merely degraded.
- **Representational (meaning mutation).** Even when a claim forms, a free paraphrase of a 1.5B model
  is free to move meaning: AIB candidate pair 22 invented a *reduction-of-anomalies* target where
  *bias reduction* was requested; pair 6 changed the EBQ measuring subject; a depression candidate
  reversed 40645's *unchanged* neuron-count finding into a *decreased* neuron count; 27737's null
  cognitive-change sentence was selected but the formed claim imported stronger neighboring material
  and changed scope. The `form_claim` prompt does instruct "preserve negation, null findings,
  direction, uncertainty, and qualifications" — but this is **prose the grammar does not enforce**,
  and a tiny model does not reliably honor prose constraints.

**Is "claim formation" the wrong compression boundary?** On this evidence, the *free-paraphrase*
form of it is. The design asks the model to **replace** the source span with a rewrite and then asks
the verifier to check the rewrite — so the source structure is discarded exactly where fidelity is
decided. The calibration line already pointed here: Run 0.6a found real *rewrite-level* additions the
automated audit missed ("don't say Run 0.6 proved zero invention"), and Run 0.6b decomposed the
overloaded selection into a source-local claim primitive. The natural, principle-aligned alternative
(PRINCIPLES.md: *the deterministic substrate is the source of truth and the model only narrates it*)
is **span-first**:
- the **exact quote + provenance/ancestry is the canonical evidence object**;
- the model emits, separately, a **typed candidate annotation** (subject / relation-predicate /
  object / population / direction / modality / **distinct** null-vs-mixed-vs-uncertain status /
  relation-stated-in-this-excerpt) — *candidate structure attached to the span, never a replacement
  source fact, never promoted to truth by successful JSON parsing*;
- each non-null field carries an exact supporting source substring/anchor, so deterministic code can
  validate the **anchor** (not the interpretation);
- fields permit explicit **NOT_STATED / NOT_APPLICABLE / UNCLEAR_FROM_EXCERPT**, so the model is
  never forced to invent structure to satisfy a schema;
- downstream synthesis operates over evidence spans + inspectable structure, not over a paraphrase.

This keeps both the source text and an interpreted structure, represents the semantic distinctions
downstream needs (subject, population, direction, modality, null status, relation endpoints) *without
replacing the source meaning*, and keeps the vocabulary limited to the loss classes the frozen
evidence actually motivates — not a universal scientific ontology. When interpretation is uncertain,
the honest answer is a "cannot tell" field state plus the still-canonical quote, not a confident
rewrite. This is the treatment the recommended experiment (§19–20) tests.

---

## 6. VERIFICATION VS RESPONSIVENESS (Boundary C)

**What the verifier actually does.** `VerificationConfig` (retrieval ≥ 0.70, exact quote = 1.0,
support ≥ 0.55, contradiction ≥ 0.55) answers a **claim↔source** question: does the source passage
lexically/semantically support (or contradict) the claim string? It attempts: source-quotation
validity, semantic entailment/support, and contradiction.

**What Callosum currently infers incorrectly from it.** Verified support is read, downstream and in
presentation, as though it also established **responsiveness** (does this answer the user's request?),
**relationship preservation**, **qualification preservation**, **significance**, and
**completeness**. It establishes none of these. The receipt makes the gap concrete: the EBQ
subject-error claim verifies at support 0.8914, and a generic network-caption verifies at 0.9375 —
both are "verified" and neither is responsive or sound. On the negative-control corpus (no relevant
literature at all), verification still produced **2 verified records**.

**The deeper design flaw.** With claim formation being paraphrase-first, the verifier is asked to
judge **one model-generated representation (the paraphrase) against the source — after the source
structure has already been discarded.** One model artifact judging another, downstream of the point
where meaning was lost. This is structurally weak regardless of thresholds.

**Is a separate responsiveness judgment required? Yes, and where should it sit?** Responsiveness is a
**claim/evidence ↔ request** relation, not a claim↔source relation, so the verifier is the wrong
place for it. The higher-fidelity referent for that judgment already exists and is preserved: the
**request contract / obligations** (§2). A responsiveness judgment should compare the *retained
obligation* against the *evidence object* — and, in a span-first world, it can do so **source-first**
(the canonical quote is available), avoiding the "model-judging-model-after-source-is-gone" trap. It
is plausibly an **orchestrator-level or deterministic-plus-judgment** step, and it is deliberately
**out of scope for the recommended isolation** (which tests source fidelity, not responsiveness). The
report is right not to design abstention here; responsiveness and abstention are separate, later
questions.

---

## 7. RELATIONSHIP-PRESERVATION ANALYSIS (Boundary D)

The receipt gives direct evidence that **nodes survive and edges do not**. Chunks 34974/35111
explicitly link the amygdala to prosociality/dispositions and attitudes/IAT/EBQ to the left amygdala;
those endpoints appear in retrieved and even selected source. Yet no verified brain→behavior or
brain→attitude *edge* reaches the ledger. The report's diagnosis is exact: *"an area list plus a
separate behavior/attitude does not reconstruct an edge."*

Three information classes are therefore distinct and must be independently preservable:
- **node identity** (which construct/area/behavior) — currently survives;
- **relation identity** (that A relates to B, and how) — currently lost;
- **qualification / epistemic status** (null / mixed / uncertain / direction) — currently lost (§8).

The root cause is representational: no evidence object *is a relation*. The pipeline extracts
per-span claims and never carries "these two constructs, and the relationship the excerpt states
between them." The aligned representation is a per-span typed structure that records relation
endpoints **and** whether the relation is *stated in this one excerpt* — respecting two standing
boundaries: **never infer an edge from disconnected endpoints** (an edge must be present in a single
span's evidence, not assembled across spans), and **deduplicate the object, not its relationships**.
This does **not** require a global ontology or a knowledge graph; it requires one first-class
"relation-stated-in-this-excerpt" field within the span-first annotation, which the recommended
experiment includes and tests.

---

## 8. QUALIFICATION / NULL / UNCERTAINTY PRESERVATION

This is a major scientific-fidelity failure and it is representational, not incidental. Retrieved
depression material contained gray-matter group nulls, null cognitive-change sentences, mixed
gray-matter findings, and uncertain mechanisms. **None survived to a verified qualified/null final
proposition.** The failure occurs at three points: the gate discards a null (28044); claim formation
imports stronger neighboring material over a selected null (27737, 27732) or outright **reverses** a
null into a directional finding (40645 unchanged → decreased); and verification does not police any of
this because the paraphrase it checks is already smoothed.

The structural cause is that null/mixed/uncertain preservation is currently requested **as prose**
inside the `form_claim` instructions, which a 1.5B ignores. The fix is to make these **distinct typed
fields** the annotation must fill from the excerpt, with an explicit "not stated in excerpt" option —
so a null is recorded *as a null*, not left to the model's discretion to remember. **null, mixed, and
uncertain are distinct information and must not be collapsed** into one vague "qualified" category:
a null result, a mixed/heterogeneous result, and an uncertain-mechanism statement mean different
things and support different downstream reasoning. Treating them as evidence *structure* (typed) is
the difference between preserving them and smoothing them into disposable prose.

---

## 9. RECOVERY POSTMORTEM (Boundary E)

**Epistemic job it is meant to perform.** Reopen the search space for obligations still unmet after
the first pass — find evidence the initial retrieval missed.

**What the current implementation actually does.** `recovery_query` writes a short retrieval phrase
from the subquestion + missing-obligation note; the pipeline then re-searches. On this receipt each
source unit produced 8 initial hits and **the same 8 again** during recovery (16 occurrences, 8
unique). Recovery made **0 new paper nominations and 0 new hits** and added **7 duplicate verified
records** — the 14 final verified records collapse to only 7 distinct claim strings *because
recovery duplicates every initial verified record.* It does not reopen the search space; it re-runs an
equivalent query against the same corpus, same kNN, same nominated papers. It is "re-query," not
"recovery," and its only current effect is to inflate the verified-record count in a misleading way.

**Disposition options.** (a) **Remove it** — it adds duplicate work and misleading counts; (b)
**rename + gap-condition it** with an *altered* retrieval strategy (different papers, broader kNN,
different query construction) so it genuinely explores new space; (c) at minimum, **deterministically
dedup the object** so recovery can never re-emit an already-verified record (the standing boundary:
deduplicate the object, not its relationships).

**Minimal experiment to determine whether in-corpus recovery adds value.** Run one recovery pass with
a deliberately *altered* strategy and measure whether it surfaces any paper/chunk **not** in the
initial nominated set. If it cannot, in-corpus recovery-by-re-query is worthless and should be removed
or deferred to the (separately backlogged, out-of-scope here) Ask-gap → Search/Discovery →
user-import → re-index flow — which is where genuine "the evidence isn't in the library yet" recovery
belongs, not in a same-corpus re-query.

---

## 10. TERMINAL-RENDERER STATUS

The constrained renderer (`ledger_renderer.py`, `verbatim-ledger-v1`) worked as designed and should
be left as-is. `validate_ledger` requires every row to be `verified`, to carry paper/chunk/span
ancestry and an exact quote, and — critically — the `(paper_id, chunk_id, span_id, quote)` tuple must
resolve in the sealed source-span catalog or it raises. `render_ledger` emits verbatim claims with
`"aggregation": "none"`, marks completeness `"not_certified"`, and always prints every unresolved
original unit. On this receipt: 14/14 IDs and spans resolved, zero renderer-added science or
aggregates, all 22 unresolved units visible.

Its correct behavior has one honest consequence worth stating: it faithfully renders the ~6
"problematic ledger copies" (the subject-corrupted AIB records, the population-broadened depression
records) **because they are in the verified ledger.** That is not a renderer defect — the renderer
must not second-guess the ledger — it is evidence that the *ledger itself* contains unsound verified
records, i.e. the claim-formation + verification failures (§5, §6). The renderer's value here is
precisely that it **exposes** those upstream defects in verbatim output rather than laundering them
into fluent prose. (The optional model-prose `synthesis.py` path is a comparison artifact, already
superseded by this constrained renderer for the product output.)

---

## 11. BUILT-ENVIRONMENT NEGATIVE-CONTROL INTERPRETATION

The user confirmed **after freeze** that the library contains **no** built-environment literature.
This is an externally supplied fact, kept separate from retrieval evidence, and it reframes the
built-env case entirely:

- Built-env's total failure is **correct behavior**, not a retrieval-recall failure. We must **not**
  infer "retrieval failed to find literature that must be there." The frozen positive-evidence
  usefulness gate is therefore inappropriate as a *capability* diagnostic for this case; it is
  reported unchanged, not retroactively relaxed (AIB and depression fail independently, so the final
  verdict does not depend on it).
- **The negative control is about responsiveness, not source fidelity.** A built-env-selected span
  can be completely irrelevant to the request and *still be faithfully represented*. So built-env
  must **never** be used to penalize a representation for faithfully encoding an irrelevant passage,
  and "zero evidence objects" is the wrong criterion. What built-env actually tests is: *does the
  system falsely treat an irrelevant-but-faithful passage as responsive?* — a responsiveness/mapping
  question. On this receipt the danger materialized: 2 built-env records were **verified** (generic
  caption, chunk 40566, 0.9375) — verification is not responsiveness (§6).
- **Source fidelity and request responsiveness must be kept separate; the negative control must not
  collapse them.** Because the recommended claim-representation isolation does **not** include a
  responsiveness judgment, built-env is carried in it as a **descriptive negative-control packet
  only** — never a primary claim-representation failure criterion.
- It remains the right future substrate for *"my review didn't surface enough responsive evidence for
  a reliable synthesis"* (abstention) rather than *"there is no evidence."* Abstention is **not
  designed here.**

---

## 12. RESEARCHER-WORKFLOW ANALOGUES

Used only to generate architecture hypotheses, not to assume the human workflow is optimal or to
anthropomorphize the model:

| Researcher instinct | Architectural hypothesis it motivates |
|---|---|
| "This passage may matter; I'm not ready to discard it." | Non-destructive gate: retain + rank, don't `discard` irreversibly (§4). |
| "What did the authors actually say?" | Span-first: the exact quote is canonical, not my paraphrase (§5). |
| "Did the result apply to this population?" | Typed, source-anchored **population** field, preserved (§5, §8). |
| "Was the effect null, mixed, or directional?" | **Distinct** typed null / mixed / uncertain / direction fields, not smoothed prose (§8). |
| "These constructs are mentioned separately — was their relation actually tested?" | Relation identity as a first-class "stated-in-this-excerpt" field; never infer an edge from disconnected endpoints (§7). |
| "My summary sounds cleaner than the source." | The paraphrase-first danger; the reason the rewrite must not be the canonical fact (§5). |
| "I don't have enough evidence yet." | Responsiveness / honest coverage, and eventual abstention — separate, out of scope here (§6, §11). |

---

## 13. WHICH TRANSFORMS SHOULD BE DETERMINISTIC

- **Already deterministic and working — keep:** ID assignment, provenance/ancestry, exact-quote
  matching, coverage bookkeeping, object dedup, and the constrained render (§10).
- **Should become (more) deterministic:**
  - **Gate noise/discard control** → delegate to the existing H1a `evidence_role` classifier
    (inc 577: `scientific | bibliographic | structural | unknown`), which targets exactly the
    abbrev-list/heading/metadata/keyword-list categories the gate's `discard` prompt enumerates —
    with `unknown` first-class and never auto-excluded. Removes most destructive model discard (§4).
  - **Anchor validation** of typed annotation fields — deterministic verification that each non-null
    field's claimed supporting substring actually occurs in the excerpt (validates the *anchor*, not
    the interpretation) (§5).
  - **Object dedup in recovery** — a verified record can never be re-emitted (§9).
  - **The no-inferred-edge constraint** — a relation may only be asserted from a single span that
    states it (§7).

---

## 14. WHICH TRANSFORMS REQUIRE LANGUAGE JUDGMENT

Irreducibly model-backed, but they should be **bounded and source-preserving**, not generative
compression:
- **Decomposition / obligation extraction** — natural-language, ID-free; works on the 1.5B on this
  receipt (request preservation passed).
- **Evidence screening / selection** — "is this span responsive to this obligation?"; works *with
  grammar* (256/256 on this receipt), though span *quality* remains a separate open question.
- **Typed span interpretation** — the subject/relation/qualifier/null structure of a span, as
  **candidate** annotation attached to the canonical quote, never promoted to fact (§5). This is the
  transform under test.
- **Responsiveness / coverage judgment** — request↔evidence; a genuinely new judgment the pipeline
  does not currently make; plausibly orchestrator-level; out of scope for the next isolation (§6).

---

## 15. WHICH TRANSFORMS MAY NOT BE NECESSARY

- **Free-paraphrase claim formation** — likely the wrong compression boundary in its current form; a
  candidate replacement is span-first + typed candidate annotation (§5). This is the specific
  hypothesis the recommended experiment tests.
- **Recovery-by-same-search** — adds only duplicate work and misleading counts on this receipt (§9).
- **The model `discard` branch of the gate** — replaceable by deterministic H1a noise control +
  non-destructive retain-and-rank (§4).
- **The optional model-prose terminal synthesis (`synthesis.py`)** — already superseded by the
  constrained renderer for product output; it is a comparison artifact.

None of these should be deleted on this postmortem alone; each is a *finding to test or redesign*,
and the recommended experiment tests the highest-value one (claim formation).

---

## 16. IMPLICATIONS FOR WORKER / ORCHESTRATOR ROLE BOUNDARIES

The demonstrated-fragile task is **generative compression (free paraphrase)** — not "small model" and
not "high-volume." So the worker/orchestrator boundary should be drawn at **generative-compression vs
source-preservation**, not tiny-vs-big-everywhere:

- **Tiny / high-volume workers remain viable** for bounded, source-preserving tasks: decomposition,
  obligation extraction, grammared evidence screening/selection, and typed source-anchored annotation.
- **The one place the naive "strong orchestrator + tiny workers everywhere" hypothesis is weakened**
  is generative compression. The aligned response is to **make that task source-preserving
  (representational fix)** *before* escalating it to a bigger model — because a source-preserving
  representation removes the very freedom that let the paraphrase mutate meaning, and it does so at any
  model size.
- **Selective escalation by task type** is the shape to test in 0.7.0 (§17), not uniform escalation.
  A responsiveness/coverage judgment (§6) and relationship assembly under the no-inferred-edge
  boundary (§7) are the tasks most likely to want an orchestrator; provenance/dedup/render/noise
  stay deterministic.
- **Anti-essentialist frame maintained:** behavior = model × prompt × representation × task
  decomposition × output constraints × deterministic machinery × corpus. This receipt varied one
  cell (added grammar to selection) and moved a large loss; it did not vary model size. **No
  Qwen-capacity verdict is licensed.**

---

## 17. IMPLICATIONS FOR THE EXISTING 0.7.0 PREREGISTRATION (analysis only — not edited)

- The 0.6.0 result **refines, does not invalidate,** the prereg's MODEL × REPRESENTATION PACKAGE
  shape. It localizes the representation axis that matters most: **claim/evidence representation
  (paraphrase-first vs span-first/typed)** — precisely what the reserved `R_0_6` should encode. It
  also confirms the prereg's insistence that structured decoding fixes *format*, not *semantics/scope*
  (grammar fixed selection's envelope; it will not, by itself, fix paraphrase meaning-mutation).
- It **weakens the simple "strong orchestrator + tiny workers everywhere" hypothesis in one specific
  place** (generative compression), and argues the prereg's benchmark should treat claim/evidence
  representation as a first-class factor and test **selective escalation by task type** rather than
  uniform escalation.
- **Worker tasks with demonstrated semantic fragility:** claim formation (generative compression);
  and, pending de-confounding, the context gate's growth/discard judgment. **Tasks that look
  tractable for small/high-volume workers:** decomposition/obligations, grammared selection.
- **This isolation does NOT produce `R_0_6`.** A winning Arm 2 yields a **candidate** claim/evidence
  representation only. The dependency chain is:
  `claim-representation isolation → candidate representation → integrate into revised 0.6 package →
  separately-authorized bounded end-to-end acceptance → if READY: freeze R_0_6.` A component-level
  win must not masquerade as package-level acceptance. `R_0_6` stays **unfrozen** (0.6.0 was a failed
  acceptance, and the prereg's READY gate is explicit).
- **Do not edit the preregistration** on the basis of this postmortem.

---

## 18. RANKED NEXT-EXPERIMENT OPTIONS

Ranked by information gain × reversibility ÷ scope. Each specifies hypothesis / boundary / treatment /
control / frozen / reusable artifacts / primary outcome / stopping rule / what-updates / what-would-not
/ inference needed / model sufficiency / scope.

**Rank 1 — Claim-representation isolation (RECOMMENDED).**
- *Hypothesis:* replacing generative rewrite with a source-preserving span-first/typed representation
  changes semantic fidelity, model held fixed.
- *Boundary:* selected span → claim.
- *Treatment/control:* three arms (see §19–20).
- *Frozen:* Qwen-1.5B settings, verifier, thresholds, retrieval, DB copy, unique claim-formation input
  packets, 0.6a rubric.
- *Reusable:* frozen 0.6.0 selected-span receipts; 0.6a human-label methodology; 0.6b source-local
  claim primitive; the `calibration/structured_output` `response_format` wrapper.
- *Primary outcome:* blinded human fidelity vs exact source + distinct null/mixed/uncertain retention
  + relation-endpoint preservation, per arm.
- *Stopping:* first observation, no tuning; freeze inventory and stop.
- *Updates architecture if:* Arm 2 > Arms 0/1 on fidelity → representation is the fix.
- *Would not justify:* capacity verdict; threshold changes; rebuild; freezing `R_0_6`.
- *Inference:* yes. *Qwen sufficient:* yes (fixed by design). *Scope:* small (one boundary, frozen
  inputs, ~3 arms × the frozen packet set).

**Rank 2 — Context-gate isolation.**
- *Hypothesis:* the gate's loss is dominated by mechanical truncation + destructive discard, not by
  irreducible reading-judgment failure.
- *Boundary:* context gate.
- *Treatment:* (a) grammar-enforce the gate to remove the 246/354 truncation confound; (b) delegate
  `discard` to deterministic H1a; (c) make growth non-destructive (retain + rank). Control: current
  ungrammared destructive gate.
- *Primary outcome:* fraction of useful passages retained through to selection; recovery of the
  specific losses (e.g. 28044).
- *Ranked second because:* its first-order fix is mechanical, its semantic judgment is unmeasurable
  until truncation is removed, and it does not decide the central quotation≠proposition thesis.
- *Inference:* yes. *Qwen sufficient:* yes. *Scope:* small–medium.

**Rank 3 — Combined gated semantic-loss sequence** (gate then claim). Higher coverage but **bigger**;
violates "prefer isolation / smallest." Deferred.

**Rank 4 — Selective stronger-model probe.** Only meaningful *after* Arm 2, and only if representation
proves insufficient. Uninterpretable now (paraphrase-first + ungrammared confounds unremoved). A
capacity claim before de-confounding would be an essentialist error.

**Rank 5 — Update 0.7.0 design first.** Unnecessary; the recommended experiment *feeds* a candidate
representation that the prereg's `R_0_6` slot is waiting for. No redesign is blocking.

**Rank 6 — No further 0.6.0 experiment.** Rejected: a cheap, high-information, reversible isolation
with an already-sketched treatment (0.6a/0.6b) exists and directly advances the roadmap.

---

## 19. RECOMMENDED SINGLE NEXT BOUNDED EXPERIMENT

**Claim-representation isolation** — hold Qwen-1.5B fixed and vary only the claim/evidence
representation contract on the frozen claim-formation input packets, to test whether source-preserving
representation preserves the meaning that free paraphrase mutated.

Rationale: claim formation is the clearest demonstrated destructive compression boundary (mechanical +
representational); it decides the central *quotation ≠ proposition fidelity* thesis; the same model is
held fixed (clean capacity-vs-representation attribution for this boundary); Arm 1 removes the format
confound; Arm 2 tests the representation itself; only after that is a capacity probe interpretable. It
reuses the most frozen artifacts (minimal new inference), is isolated and reversible, and yields the
**candidate representation** the eventual `R_0_6` will be built from — **not** `R_0_6` itself.

---

## 20. EXACT FREEZE / CONTROL / TREATMENT DESIGN

**Experimental unit (frozen before any inference).** A **unique claim-formation input packet**:
`exact source span + source-unit/obligation context + grown-context packet + exact claim-formation
input`. **Recovery pseudoreplication removed** — byte-equivalent / semantically-identical recovery
duplicate calls collapse to ONE unit; historical multiplicity is recorded as lineage only and never
inflates n. (The 0.6.0 receipt's 261 repeated occurrences and 7 duplicate verified records make this
non-optional.)

**Frozen (unchanged):** Qwen2.5-1.5B-Instruct Q4_K_M on the same JUNO/Ollama runtime, ctx 12288, temp
0, seed 42; the local NLI verifier and all thresholds (0.70/1.0/0.55/0.55); retrieval; the Run06
frozen DB copy (read-only, before/after hashes asserted); the frozen unique claim-formation input
packets; and the Run 0.6a human fidelity-label rubric.

**Arms** (vary the minimum needed; no semantic prompt improvement may sneak between 0 and 1):
- **Arm 0 — contemporaneous current-form control.** Current free-paraphrase `form_claim`, current
  ungrammared contract. It is a **fresh observation, not a presumed reproduction**; afterward it is
  compared to the historical frozen receipt and agreement/disagreement is reported.
- **Arm 1 — mechanical isolate.** The **same** semantic free-paraphrase job, varying **only** the
  structured-output enforcement mechanism (the established `response_format` wrapper). Isolates the
  152/328 truncation (mechanical-envelope) effect.
- **Arm 2 — treatment (span-first / typed candidate annotation).**
  - The **exact quote + provenance/ancestry remains the canonical evidence object.**
  - The model emits a **typed candidate annotation** attached to it — never promoted to a source fact
    by parsing (schema-valid ≠ semantically faithful).
  - **No operative self-critique is bundled in.** Any fidelity self-check output may be recorded
    separately as an **inert diagnostic** but must NOT alter the annotation, determine acceptance,
    trigger retry, repair the result, or count as validation.
  - Typed vocabulary is **limited to the loss classes the frozen evidence motivates**: subject /
    relation-predicate / object / population / direction / modality / **distinct** null vs mixed vs
    uncertain status / relation-stated-in-this-excerpt — **not** a universal scientific ontology.
  - Every field permits explicit **NOT_STATED / NOT_APPLICABLE / UNCLEAR_FROM_EXCERPT**; the model is
    never forced to invent structure to satisfy the schema.
  - Each **non-null** semantic field carries an exact supporting source substring / span-ID / offset
    **anchor**, enabling deterministic validation of the **anchor** (not of the interpretation).

**Primary outcome — fidelity of the representation to the exact source packet.** Human adjudication
with **arm identity hidden and order randomized**, scored against the exact source packet using the
frozen 0.6a rubric. **First verify FAITHFUL / LOSS / ADDITION / MALFORMED are mutually exclusive under
the existing 0.6a methodology** — a representation can both drop a qualification AND add unsupported
meaning; if the historical rubric defines precedence, preserve it; otherwise report an overall
fidelity judgment plus **independent** loss / addition / malformed flags. Do not alter a frozen
historical rubric for elegance; document the rule actually used. **Secondary:** explicit **distinct**
null/mixed/uncertain retention, and relationship-endpoint preservation, per arm. **Built-env packets
are carried descriptively only** (§11), never as a source-fidelity criterion.

**Stopping rule:** first observation, no tuning/retry; freeze the fidelity inventory and stop.
**Inference required:** yes (Arms 0–2). **Current Qwen sufficient:** yes — holding it fixed is the
point.

---

## 21. WHAT EACH POSSIBLE RESULT WOULD MEAN

- **Arm 2 clearly > Arms 0 and 1 on fidelity (and on distinct null/mixed/uncertain + relation
  retention).** The compression boundary is the culprit: free-paraphrase claim formation should be
  replaced by span-first/typed representation, and the eventual `R_0_6` candidate should be built from
  a span-first representation. → integrate into a revised 0.6 package and pursue a separately
  authorized bounded end-to-end acceptance (§17). *Does not* by itself license freezing `R_0_6`.
- **Arm 1 alone recovers most of the loss (Arm 2 ≈ Arm 1).** The dominant remaining claim loss is
  **mechanical** (truncation), and the cheap fix is simply to grammar-enforce claim formation; the
  representation change is not the decisive lever for fidelity. Re-weight priorities toward the gate
  and toward responsiveness.
- **Neither Arm 1 nor Arm 2 materially beats Arm 0.** Representation and format are insufficient at
  this boundary with this model → *now* a matched **model-capacity probe** (Rank 4) is justified and
  interpretable, because the representation and format confounds have been removed.
- **Arm 0 disagrees with the historical frozen receipt.** A runtime/nondeterminism caveat to record
  (temp 0/seed 42 notwithstanding); it bounds how much weight the cross-arm comparison can carry and
  must be reported honestly, not smoothed.

In all cases: built-env behavior informs only responsiveness (§11), never source fidelity; and no
end-to-end or capacity conclusion is drawn from a component-level isolation.

---

## 22. WHAT WE STILL CANNOT CONCLUDE

- Any **model-capacity verdict** for Qwen-1.5B (confounds unremoved; the receipt varied representation
  of one stage, not model size).
- Any **end-to-end causal (old-vs-new) claim** — no matched old-architecture condition was run.
- Whether the **context gate's semantic judgment** is good — 69% of its calls truncated; its judgment
  was mostly never exercised.
- Whether **in-corpus recovery** can ever add value — it has only ever been run as a same-corpus
  re-query.
- **Built-env recall** — the corpus is absent, so nothing about retrieval recall is testable there.
- **Package-level (`R_0_6`) acceptance** — a component-level fidelity win is not package readiness.
- **Responsiveness and completeness** as solved problems — no request-responsiveness judgment exists
  yet; abstention is undesigned.

---

## 23. DECISION

**RUN CLAIM-REPRESENTATION ISOLATION NEXT.**

Why this and not the alternatives: claim formation is the clearest demonstrated destructive
compression boundary on this receipt, carrying both a mechanical loss (152/328 truncations → deleted
evidence) and a representational loss (paraphrase meaning-mutation over exact quotes) — and it is the
boundary that decides the project's central *quotation ≠ proposition fidelity* thesis. The experiment
holds Qwen fixed (so any effect is representation, not capacity); Arm 1 removes the format confound
that currently makes the boundary uninterpretable; Arm 2 tests the source-preserving alternative the
0.6a/0.6b calibration line already pointed to; it reuses frozen artifacts with minimal new inference;
it is isolated, reversible, and small; and it yields the **candidate** representation the eventual
`R_0_6` will be built from. Context-gate isolation is the correct **second** experiment but is
ranked below claim formation because its first-order fix is mechanical, its semantic judgment cannot
be assessed until truncation is removed, and it does not decide the central thesis. A model-capacity
probe is deferred until representation and format confounds are removed, or it would be an
essentialist error. The 0.7.0 preregistration is **not edited**, and `R_0_6` is **not frozen** —
this experiment feeds a candidate representation into the prereg's reserved slot, it does not fill it.

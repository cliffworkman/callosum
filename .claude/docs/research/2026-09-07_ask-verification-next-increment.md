# Ask verification — next-increment research & scoping (0.6.0)

**Status:** research/scoping only. No production Ask code, verifier thresholds, Local-AI descriptor, or push
changed by this pass. STOP for Cliff/Lucien adjudication.
**Date:** 2026-09-07. **Basis:** inc 581 (`5ddb321`, live). **Diagnostic corpus:** the 18 frozen Gemini
acceptance claims **plus** a read-only sweep of all 81 persisted citation rows across 7 live Ask questions in
the demo DB (`C:\Users\cliff\callosum-data\library.sqlite`, read `mode=ro`). No provider reruns; no data
modified.

---

## ⛔ PHASE-GATE ADDENDUM (2026-09-07, later) — EVIDENCE GATE FAILED; Option 2-E NOT implemented

The provisionally-approved inc 582 (remove `retrieval_confidence` as a necessary condition for VERIFIED) was
put through the required pre-implementation evidence gate. **It failed. No production code was changed.**

**Semantic restatement (per Cliff's correction).** Because VERIFIED already requires `quote_confidence==1.0`,
the proposed "conditional retrieval gating" is in practice **removal of `retrieval_confidence` from the
VERIFIED decision**: VERIFIED would become `quote==1.0 ∧ support≥0.55 ∧ contradiction-rule-ok`, with retrieval
kept only as displayed diagnostic. Stated plainly, not obscured behind "conditional."

**Phase 1 — complete flip universe (frozen).** Query = citation rows with `quote_confidence≥1.0 ∧
support_confidence≥0.55 ∧ retrieval_confidence<0.70` (the rows that would newly become VERIFIED). Enumerated over
the demo DB (`library.sqlite`, `mode=ro`; 7 summaries / 81 rows) **and** a scratchpad copy of the frozen Codex
baseline (`baseline.sqlite`; 42 summaries / 354 rows). **Universe = 12 rows** (demo 3, baseline 9), frozen
SHA-256 `6b90ef80c737e87dc3cd84df2e67974ecf09aff24120915d110782f81645bde9`. Adjudication record SHA-256
`34ebdb0011a350535fc2c90ad3ae09a101ec28bb2a268f66cda2d1d4e787f4ff`. Not sampled (universe is small). *(My
earlier §4/§9 used a convenient 6-row subset; the complete universe is 12 and changes the conclusion.)*

**Phase 2 — support/fidelity adjudication (claim + exact quote + full chunk context; scores/status withheld
from the view, though not fully blind since the author had seen prior scores — hence the Phase-6 independent
audit).** Result: **SUPPORTED 10 · UNSUPPORTED 1 · UNRESOLVED 1.** Ship gate (0 UNSUPPORTED ∧ 0 UNRESOLVED):
**FAILED.**

Counterexamples (both currently `weak` only because retrieval<0.70; both would become VERIFIED under the
proposed semantics):
- **UNSUPPORTED — row/mapping 285** (chunk 32651). Claim: *"Mild cognitive impairment is associated with
  late-life depression and cognitive decline."* Source (introduction): *"depressive symptoms are a risk factor
  for cognitive decline in cognitively normal individuals, as well as in individuals with mild cognitive
  impairment … Major depressive disorder in late-life is a risk factor for … all-cause dementia."* The source
  never asserts MCI↔LLD or MCI→cognitive-decline; the claim **reassigns MCI as the subject** of two
  associations. **The NLI support gate false-positived at 0.9476.** retrieval=0.6396 is the sole blocking gate.
- **UNRESOLVED — row/mapping 269** (chunk 32651). Claim substitutes *"late-life depression"* for the source's
  *"depressive symptoms"* on the cognitive-decline atom; whether the late-life subset carries that association
  is not established by the quote. support=0.7631; retrieval=0.6808 is the sole blocking gate.

The other 10 flips are genuine, faithfully-supported substantive findings wrongly flagged by the chunk-length
retrieval bias (facial-anomaly ratings; arousal/happiness; LLD relapse; LLD→dementia risk; beta-amyloid in LLD
vs controls; GMV inconsistency; etc.). **So the chunk-length false-negative problem is real (10/12), but it
does not license wholesale removal of the gate.**

**Phase 3 — does whole-chunk retrieval uniquely prevent a false-positive class? YES (demonstrated, not
theoretical).** Rows 285 and 269 are exactly the class: a claim that **recombines/reassigns entities or scope**
from the source shares enough local vocabulary with a verbatim quote to fool the small cross-encoder NLI, yet is
semantically distant from the source *chunk as a whole*, so whole-chunk retrieval (0.64–0.68) is currently the
only gate that stops it. This **falsifies** the report's earlier "no observed unique safety property" claim
(which rested on the 6-row subset). Retrieval is a *noisy* signal — it produces chunk-length false negatives on
10/12 flips **and** a true-positive backstop on 2/12 — and the two cannot be separated by simply deleting it.

**Decision.** Per the pre-registered gate, **Option 2-E is not implemented.** `verification.py` is unchanged;
no threshold, quote-matching, NLI, contradiction, schema, prompt, or retrieval change was made. The **§9
recommendation below is SUPERSEDED** by this addendum.

**Revised forward path (research only, nothing implemented):**
- The retrieval-vs-quote asymmetry and its chunk-length false negatives are real, but the fix must **preserve
  retrieval's backstop against subject/scope NLI false-positives.** The candidate is **semantics D** (compute
  the retrieval check against the *quote/quote-region* rather than the whole chunk) — but it needs its own
  validation that it still rejects rows 285/269 (uncertain: those claims share vocabulary with their quotes), so
  it is **RESEARCH**, not a drop-in. A purpose-built labeled set (both false-negative and NLI-false-positive
  classes) is the prerequisite.
- **Option 1 (deterministic responsiveness band)** is unaffected and remains the leading **inc 583** candidate
  (deliberately deferred to observe answers after any false-negative rescue — which today does not ship).
- The stronger lever on rows 285/269 is **claim formation / a stronger support check** (NLI subject/scope
  fidelity), i.e. Option 3 territory — NEXT, gated on Qwen + a labeled eval.

*Frozen artifacts (working copies, scratchpad, ephemeral): `flip_universe_frozen.json`,
`flip_adjudication_frozen.json`. The frozen query + thresholds above make the universe reproducible by an
independent auditor against the same two DBs.*

---

## 0. What changed since the first draft (steering incorporated)

1. **Qwen is not "blocked on an unresolved compatibility problem."** Per Codex's corrected SCRATCH entry, the
   installed Desktop is **v0.5.7 (pre-inc-575)**; it *correctly* emits `max_output_tokens=2048` for its own
   old bundled Python and launches llama-server with `--n-predict 2048`. This is **stale installed-build
   state, not a post-575 regression**. Retained model assets/cache are not the cause. A current-main/post-575
   Desktop build regenerates the descriptor at 4096 with the same assets. **Cliff + Codex are cutting 0.5.8**
   to exercise the real upgrade path and unblock the Qwen OLD-vs-NEW replication. **Qwen data still does not
   exist**; the recommendation below is chosen to be robust to that.
2. **The retrieval-gate asymmetry is promoted from a footnote to the central finding**, and tested empirically
   against existing persisted data (below).
3. **Option D (responsiveness band) is de-crowned** — it is now the *safest* candidate, not automatically the
   next increment, pending the retrieval-gate diagnostic.

---

## 1. Current inc 581 verification architecture (traced)

Broad path (`summarization/faceted_pipeline.py::summarize_faceted`): pre-gate → planner → per-facet retrieval
over the live article-fulltext pool → H1a **deprioritization** hygiene → dedup + caps (per-paper 3 / per-facet
6 / global 36) → **bounded per-facet generation via the UNCHANGED generator** → **ONE batched
`_verify_candidates`** → `_assemble` (verified-first, ≤3 verified/≤2 flagged per facet) →
`_persist_verified_summary` (facets + 4-state coverage ride `scope_ref_json`, no migration) →
`19c_facet_coverage.jsx`.

Verifier (`verification.py::verify_many`, **shared by narrow + broad**, unchanged by 581), per (sentence,
citation):
- **retrieval_confidence** = embed the *claim sentence*, search the candidate pool, `1 − distance` to the
  **whole cited CHUNK**. Gate ≥ **0.70**.
- **quote_confidence** = `canonical_text_contains(quote, chunk.text)` → **1.0** iff the quote is a verbatim
  (whitespace-normalized) substring of the cited chunk, else 0.0. Gate **= 1.0**.
- **support_confidence** = NLI entailment, **premise = the QUOTE, hypothesis = the claim sentence** (local
  `cross-encoder/nli-MiniLM2-L6-H768`). Gate ≥ **0.55**. (`contradiction ≥ 0.55 AND > support` → `contradicted`.)
- `verified` iff all three gates pass. **A CLAIM verifies only if ALL its citations verify.**

Two structural facts drive everything: **retrieval is measured against the whole page-sized chunk while support
is measured against the precise quote**; and `_assemble` already has each cited chunk's `chunk_type`/
`evidence_role` in hand (unused).

## 2. Relevant inc 575 constraints

- Output ceiling **4096** across four lockstepped locations (`_require()` fails closed). Do **not** revert to
  2048; any new model stage needs a **bounded** output contract sized against 4096.
- `providers.py` (generator prompt/schema) is a **frozen input of the synthesis-overview-v1 qualification
  profile** — editing it is a documented maintainer decision, so generation-prompt changes are expensive.
- Prior Local-AI evidence: fixing retrieval contamination alone did **not** fix verification (0/4 both times);
  a 1.5B model **stretched one paper across four constructs** — claim formation matters at least as much as the
  verifier.

## 3. What is the retrieval gate actually contributing? (the central question)

**Q1 — intended property.** The `≥0.70` retrieval gate is the "local embedding similarity" leg of invariant
#1's three-signal design ("embedding similarity + NLI stance + verbatim quote"). Its intent: confirm the cited
chunk is *semantically about* the claim — i.e., guard against a citation whose quote is verbatim-present but
**incidental / off-topic**.

**Q2 — is that property already established by quote+support?** Largely yes, and more directly:
`quote_confidence==1.0` proves the exact evidence text **exists verbatim inside the cited chunk** (exact
provenance), and `support≥0.55` is the NLI saying that exact quote **entails the claim**. A claim entailed by a
passage that provably exists in the cited source *is* grounded, independent of the whole-chunk centroid.

**The codebase's own test confirms the off-topic case is caught by support, not uniquely by retrieval.**
`tests/test_summarization.py::test_claim_passes_quote_but_fails_support_and_retrieval` cites an *unrelated*
chunk (`quote="Banana orchard material is unrelated."`) for an alpha-beta claim and asserts
`retrieval==0.0` **AND `support==0.0`**. The exact false-positive class retrieval was meant to stop is
independently rejected by support.

**Q3/Q4 — does retrieval add information; what would it uniquely stop?** In principle it is an independent
embedding signal (a backstop against NLI error). But architecturally, **retrieval diverges from support only
when the claim is embedding-distant from the whole chunk — which happens when the claim is about a small part
of a large chunk (chunk-length dilution), NOT when the NLI is unreliable.** A paraphrase-driven NLI
false-positive would have a *high* claim↔chunk similarity too, so retrieval would not catch it. **No concrete
false-positive class stopped only by whole-chunk similarity is observed in the data or present in the test
suite.**

**Q5 — meaningful verification criterion, or a leaked retrieval-quality proxy?** Whole-chunk embedding
similarity is *literally the same metric used to select candidate chunks for generation* (`vector_store.search`
in `_faceted_retrieval` / `_source_chunks_for_scope`). It is a **retrieval-quality proxy that has leaked
downstream into epistemic adjudication**.

**Q6/Q7/Q8 — chunk-length bias.** Measured (demo DB, quote=1.0 rows): among high-support (sup≥0.70) rows, the
retrieval-**passed** median chunk length is **354–397 chars**; the retrieval-**failed** median is **876**; the
both-gates-fail bucket sits at **4012**. **Chunk length systematically depresses the retrieval score. Short
title/caption chunks are structurally advantaged; long prose chunks — the ones most likely to hold substantive
results — are penalized.** This is the same asymmetry seen in §4.

## 4. Retrieval-gate diagnostic (read-only, 7 live questions + the frozen one)

Buckets over **all 77 quote=1.0 citation rows** in the demo DB (status is the real persisted verifier output):

| Bucket | Definition | n | median support | median chunk len (where joinable) |
|---|---|--:|--:|--:|
| **B** verified control | sup≥.55, ret≥.70 | 33 | .986 | 354 |
| **C** support failure | ret≥.70, sup<.55 | 33 | .023 | 237 |
| **D** both fail | ret<.70, sup<.55 | 8 | .006 | 4012 |
| **A** retrieval-only failure | **sup≥.55, ret<.70** | **3** | **.984** | **876** |

**Adversarial inspection of every decision-flipping row (bucket A) — demo DB (3) + frozen acceptance (3) = 6:**

| source | claim | quote | ret | sup | judgment |
|---|---|---|--:|--:|---|
| demo s5 | anomalous faces rated less attractive/content/trustworthy, more anxious | "Anomalous faces were rated less attractive, less content, and more anxious than typical faces, and less trustworthy than beautiful faces…" | .686 | .981 | **genuine finding, fully supported** |
| demo s5 | looking at anomalous faces → more aroused, less happy | "Participants also felt more aroused and less happy looking at anomalous (relative to typical) faces." | .693 | .993 | **genuine finding, fully supported** |
| demo s6 | LLD → higher relapse rate vs younger depressed | "Depression in late life is associated with … greater rate of relapse compared to younger depressed patients (Dew et al., 1997)." | .678 | .984 | **genuine finding, fully supported** |
| frozen 11 | serotonin-system vulnerability in aging/neurodegeneration + cognition | verbatim intro sentence | .697 | .987 | **genuine finding, fully supported** |
| frozen 15 | LLD is risk factor for AND prodrome of dementia | verbatim intro sentence | .651 | .994 | **genuine finding, fully supported** |
| frozen 16 | depressive sx a risk factor for cognitive decline (normal + MCI) | verbatim intro sentence | .614 | .991 | **genuine finding, fully supported** |

**6/6 retrieval-only failures are genuine, substantive, correctly-supported findings.** No material qualifier
is lost; accepting any of them creates no epistemic error. Each was flagged **solely** because whole-chunk
retrieval fell in 0.61–0.70, and each sits on a longer-than-typical prose chunk.

**Bucket C (support failures, n=33) are correct rejections** and prove support is the load-bearing gate: e.g. a
whole multi-paragraph Discussion emitted as one "claim" citing a one-line quote (sup 0.32), and forward-looking
speculation ("future studies could…", sup 0.02). **Every genuine rejection in the corpus also fails support;
there is no observed case where retrieval rejects a bad claim that support does not also reject.**

**Freeze / honesty on scope:** candidate universe = all persisted `evidence_quotes⋈citation_mappings` rows
(81 demo; 30 frozen). Sampling rule = *all* quote=1.0 rows; the decision-flipping set (bucket A) is *complete*,
not sampled. Labels = {supported+substantive, supported+thin, unsupported/overreach}, applied before tallying.
37 demo rows (summaries 1–3) have chunk_ids that no longer resolve (re-chunked since) — their **scores** are
still valid for bucketing; only their chunk-length is unavailable, disclosed not imputed. **The decisive
limiting factor is that only 6 rows flip**, so this is a strong-signal / small-n result, not a calibration
study.

## 5. Alternative verification semantics (compared, none implemented)

| # | Semantics | False-positive risk | Independent signal lost | Chunk-length bias | Provenance | Latency | Local-AI indep. | Narrow-Ask impact | Feasible pre-9PM | Validation burden |
|---|---|---|---|---|---|---|---|---|---|---|
| A | **Current** (ret≥.70 ∧ quote=1 ∧ sup≥.55) | baseline | — | **present (biases FN)** | full | 0 | yes | n/a | n/a | n/a |
| B | Lower retrieval threshold | med (uncalibrated) | weakens, doesn't remove | reduced | full | 0 | yes | shared | no (needs calibration) | high |
| **C** | **Drop retrieval as a gate when quote=1** (ret kept as displayed diagnostic; verify iff quote=1 ∧ sup≥.55) | **low** (quote+support retained; off-topic caught by support per the test) | the (unobserved) whole-chunk backstop | **removed** | full (ret still shown) | 0 | yes | shared | yes (surgical `_status`) | med (labeled flips) |
| D | Retrieval computed vs the QUOTE region not the whole chunk | low-med | collapses toward support (redundant) | removed | full | ~0 | yes | shared | maybe | med |
| **E** | **Conditional gating**: quote=1 ∧ sup≥.55 verifies regardless of retrieval; retrieval still gates when quote<1 (region/no-exact provenance) | **low** | retained exactly where provenance is weaker | removed where quote is exact | full | 0 | yes | shared | yes (surgical `_status`) | med |
| F | "Strongest-citation" claim verify | **high** (weak citation rides a verified claim) | — | — | poor | 0 | yes | shared | — | — |

**Preferred if the diagnostic holds: E (conditional gating).** It changes **no threshold**, still requires an
**exact verbatim quote + NLI support**, keeps retrieval as displayed diagnostic (inspectability), and removes
retrieval-as-gate **only** where exact provenance already exists. It is the smallest change that removes the
chunk-length false-negative source while retaining the retrieval backstop precisely where provenance is weaker.
C is the blunter form of the same idea.

## 6. Failure taxonomy (mapped to the pooled data)

- **A. Retrieval-gate false negative:** 6 observed (frozen 11/15/16 + demo ×3). Well-supported, verbatim-quoted
  **substantive findings** flagged only by whole-chunk retrieval on longer chunks. **This is the "useful claims
  fail verification" problem, and it has a specific, correctable mechanism.**
- **B′. Thin-but-VERIFIED:** frozen 2/3/4/6 — title/table-caption restatements ("was investigated / analyzed /
  compared") that verify easily because short chunks retrieve tightly and the claim paraphrases the caption.
  (Same asymmetry, opposite sign.)
- **C. Support failure = generator overreach/bundling/speculation:** the *largest* failure class (33+8 rows) —
  correctly rejected. Includes whole-paragraph "claims" and forward-looking speculation.
- **Contradiction / bibliographic / multi-citation all-or-nothing:** small tails, working as designed.

**Dominant mechanisms, revised:** (1) by *count*, support correctly rejects generator overreach/bundling — the
verifier is largely doing its job; (2) by *epistemic importance*, the retrieval gate produces a
chunk-length-biased false-negative on exactly the substantive-claim class, and **the same bias is the root of
BOTH headline problems** (it rewards thin short-chunk claims and penalizes substantive long-chunk claims).

## 7. Qwen / Local-AI evidence

**Still none** (see §0). Once 0.5.8 lands and Codex runs Qwen OLD→NEW, the questions that matter: does Qwen
show the same thin-title/caption advantage and retrieval-only failures (both are **provider-independent**
verifier-side effects, so almost certainly yes)? more overreach / cross-facet smearing (inc-575 says likely)?
different facet plans? If Qwen produces *more* thin claims and *more* overreach, that **raises** the value of
both the verification-architecture fix (Option 2) and claim-formation work (Option 3), and **does not change**
the retrieval-gate finding (it is measured on the verifier, not the generator). **The recommendation below does
not depend on Qwen.**

## 8. Three next moves — ranked by evidence

1. **Option 2 — verification-architecture correction (retrieval gate).** *Addresses:* the retrieval false-
   negative on substantive claims (Problem A) — the task's headline — and the structural bias underneath the
   thin-verified problem too. *Evidence:* strongest of the three — 6/6 decision-flips are genuine findings,
   zero false positives introduced, chunk-length mechanism confirmed, the codebase's own off-topic test shows
   support already covers retrieval's guard-case. *Cost:* a **verifier change** (invariant #1), shared by narrow
   + broad → must clear a labeled-eval + independent-audit bar before shipping. *Shape:* semantics **E**.
2. **Option 1 — deterministic responsiveness band (finding vs descriptive).** *Addresses:* thin-but-verified
   (Problem B). *Evidence:* ~4/10 verified claims are thin. *Cost:* near-zero — display/order/label only, no
   verifier/generator/schema change, provider-agnostic, fail-open. *Note:* partly treats a **symptom** of
   Option 2's root cause; still independently useful for ordering; **the safe fallback**.
3. **Option 3 — claim formation / repair.** *Addresses:* generator overreach/bundling (the biggest *count*
   class, but correctly rejected today). *Cost:* highest epistemic risk (verifier gaming), Qwen-doubtful,
   prompt change trips the frozen profile. → **NEXT**, gated on Qwen + a labeled eval.

The objective is **scientifically useful verified synthesis, not more green badges** — which is exactly why
Option 2 (rescue real findings + remove the bias) outranks Option 1 (reorder what already verifies) on
evidence, while Option 1 outranks it on *shippability/safety*.

## 9. Recommended inc 582 (evidence-led, with a hard gate and a clean fallback)

**Primary recommendation — Option 2, semantics E, gated on today's decisive experiment + an independent audit:**

- **Now → midday (the decisive experiment, read-only, no provider):** expand the bucket-A (decision-flip) set
  by pooling every existing persisted quote=1.0 row (demo 77 + frozen 30 ≈ 107) and re-adjudicating each flip
  **blind** (ideally a second annotator / the independent-audit slot). Under semantics E the *only* rows whose
  outcome changes are bucket A (flagged→verified); the experiment therefore reduces to: **are the flips genuine
  findings (E correct) or overreach (E introduces false positives)?** Current tally: **6/6 genuine, 0 false
  positives.** Ship-gate: **zero** adjudicated false positives among the flips, confirmed by an independent
  reviewer.
- **If confirmed → implement E:** a surgical change in `verification.py::_status` — when `quote_confidence==1.0`
  and `support≥support_threshold`, return `verified` regardless of retrieval; when `quote<1.0`, retrieval keeps
  gating. `retrieval_confidence` stays computed, persisted, and **displayed** (never hidden — inspectability).
  No threshold lowered; no schema change; provenance untouched. **Pair with Option 1's responsiveness band** if
  time permits (complementary: E fixes false negatives, the band orders the verified set).
- **Fallback (if E cannot clear the audit bar by the 8 PM freeze):** ship **Option 1 alone** as inc 582 (safe,
  provider-agnostic, broad-only, zero verifier risk), and land E next increment on the now-assembled labeled
  set. inc 581 is already demo-ready and needs nothing from either.

**Why not ship E blindly on release day:** it touches invariant #1 and both Ask paths, on a **6-flip** sample.
The evidence is strong and one-directional, but the responsible bar is the blind re-adjudication + audit above —
which fits the dev window. This honors "don't defer to a vague future study" *and* "don't ship a risky
architecture just because there's time."

## 10. Smallest implementation scope (Option 2-E)

- `app/backend/summarization/verification.py::_status` — one conditional branch (≈5 lines): `verified` when
  `quote==1.0 ∧ support≥threshold` (retrieval no longer required for the exact-quote case); retrieval still
  required when `quote<1.0`. No dataclass/schema/persistence change; `retrieval_confidence` still stored/shown.
- Tests: extend `tests/test_summarization.py` / `test_reverify.py` — a fixture reproducing the bucket-A shape
  (quote=1.0, high support, retrieval<0.70) now `verified`; the banana off-topic fixture (quote=1.0, support=0)
  stays flagged (proves support still guards); a region-quote fixture (quote<1.0) still gated by retrieval.
- Gates: **rule #9 Principles** (this *strengthens* invariant #1's honesty — fewer false negatives, exact quote
  + support still required, retrieval still shown); QA route touch if the flagged/verified split surfaces
  differently; no new endpoint/egress/dep. Narrow-Ask regression check (shared verifier).

## 11. Exact validation needed

1. **Decisive (today, read-only):** blind re-adjudication of the ≤ ~10 bucket-A decision-flips pooled from
   demo + frozen DBs → **zero false positives** required to ship E.
2. **Regression (pre-freeze):** full summarization/verification/reverify suites green; a live narrow + a live
   broad Ask run confirming no previously-flagged-overreach claim now verifies (spot-check the flips only).
3. **Deferred (RESEARCH):** a purpose-built ~100+ labeled set to calibrate whether any residual retrieval role
   (semantics D vs E) is warranted, and to test Option 3 repair without gaming. Do **not** tune thresholds on
   the single frozen question.

## 12. Explicitly not recommended today

- **Lowering the 0.70 threshold (B):** uncalibrated bar-lowering. E is different — it removes a redundant gate
  where exact provenance exists, lowering nothing.
- **Strongest-citation (F) / different-slice-to-verifier (G):** change verification semantics toward *more*
  false positives.
- **Generation-prompt change / repair (A/3):** frozen-profile cost + gaming risk + Qwen-doubtful → NEXT.
- **Reverting 4096→2048:** reintroduces the inc-575 truncation defect.

---

*Diagnostic scripts were read-only ad-hoc queries against `library.sqlite` (`mode=ro`); no artifact was
written into any database. The 6-flip sample is the honest limiting factor and is stated as such throughout.*

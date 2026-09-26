# Overview integration: a researcher-facing overview in the experimental Ask E2E

Branch `experiment/ask-e2e-overview` (from tag `e2e-substrate-v3`, 2b340ff1), everything under `experiments/ask_cli_revised/`.
Nothing here ships in the app. This is the offline implementation only: no live E2E, model call, retrieval, database or library
access has been run for it. **It is not live-run authorization** (`EXPERIMENT_GATE.md` still applies).

## What it does

Shipped 0.5.x Ask opens with an "Overview" written by a second model pass over the verified claim texts. The E2E's final answer was
question-by-question claims and receipts. This adds an opening overview to the E2E, written by a new role **S**, without inheriting
the ledger's semantic mistakes:

* **The passage is the authority, not the claim.** In the real q_aib run, 24 claims rest on 10 distinct passages. One claim (p4)
  said "reduced prosociality *in* people with anomalous faces"; its passage says only "affecting prosociality". Claim
  verification passed it. So S is given each exact passage paired with the claims that restate it, and every overview statement
  must cite passages, never claims.
* **The sealed evidence ledger is not touched.** The overview is a SEPARATE artifact (`14a_overview.json`), hashed on its own and
  referencing the sealed ledger's hash. Model prose never enters the sealed ledger, so it stays distinguishable from
  source-verified records.
* **Screening, not proof.** Every statement is screened by deterministic lexical rules (`overview_guards.py`) and one batched local
  NLI call. Screening can only withhold; a statement that passes is one these tests could not fault. The exact cited passage is
  shown beside every statement.

## Files

| file | role |
|---|---|
| `overview_evidence.py` | pure: passages ("units") deduplicated from a sealed ledger, lexical flags, eligibility, claim-vs-passage novel terms |
| `overview_guards.py` | pure: the sentence screen (reason codes) and NLI reasons |
| `overview.py` | prompt, schema, the one model call, screening, request-part status, the hashed artifact, preflight |
| `overview_render.py` | the researcher-facing answer, and the detailed inspection (existing ledger rendering + construction record) |
| `overview_audit.py` | final audit: re-derives everything deterministic from the sealed ledger and compares byte-for-byte |
| `topology.py` | `Profile.S` (off by default), `OVERVIEW_S_OPTIONS`, `OVERVIEW_PROFILES = {"T5O": T5* + S}`; `WAVE1` is unchanged |
| `e2e.py` | binds S, runs stage `S1` after the last coverage stage over the SEALED ledger, writes the artifacts |
| `e2e_checks.py` | `overview_screening` check; ledger-level checks run over the ledger rendering inside the inspection |
| `execution_policy.py`, `stages.py` | additive: `StageResult.thinking` (private reasoning trace) |

**Not edited (pinned/frozen):** `hierarchy_contract.py`, `decompose/execution.py`, `decompose/tree.py`, `hierarchy_contract.*.json`,
`e2e_contracts*`, `supervisor_prompts.py`, the hierarchy inputs, every recorded run.

## Evidence units and eligibility

A unit is one exact passage plus the ledger claims that restate it, keyed by passage (identical text in another chunk of the same
paper merges). Repeated restatement is never corroboration. A passage is eligible for S unless it is: unattached (the coverage
authority judged it responsive to nothing), **truncated** (no terminal punctuation: a material qualification may be missing, and a
marker alone is not a safeguard), a **study description** (aims/methods, no result cue), an **absence statement** ("did not
examine"), longer than 600 chars, or over the caps (12 passages, 12,000 prompt chars; overflow is recorded, never silent).
Attachment to a request part is the coverage model's topical judgment: it is a necessary screen and **never a limit on what a
passage may be used for**, and S is not told which part a passage was attached to.

## The S stage

One call through the existing `stages.Supervisor` seam (allowance, NO ANSWER classification, prompt-too-large refusal, tracing;
no retry, no escalation, no fallback). Output: 1 to 6 statements `{text, unit_ids, bears_on}`, closed enums and a `maxLength` on
every growable field (the worst case is recomputed from the schema and pinned against the allowance). `bears_on` is the model's
reading of which request parts a statement addresses; it is a tag, never a claim that a part is answered.

Screen (any reason withholds): cited ids valid; numbers/ACRONYMS not invented; a direction word (less/reduced/more/...) or causal
cue must occur in a cited passage; a hedge must be kept; a null result must be kept and no negation introduced; **head-word
preposition agreement** (a word the passage attaches with "toward" may not be re-attached with "in/among/by": the actor/recipient
guard); a **lookalike substitution** guard ("shaped" for "shared"); a novel-vocabulary budget; no corroboration language ("several",
"consistently", "studies") from a single paper; no statement about absence; then local NLI (an embedding fallback has no
contradiction score and fails closed).

## States and the output

`ok` (any withheld statement makes it visibly **partial**), `no_eligible_evidence` (no call is made), `model_no_answer`
(capped/unparseable/schema-invalid/too large/timeout, outcome shown), `model_returned_empty`, `no_grounded_sentences`. A
single eligible passage may yield a narrow overview, marked as resting on one passage. Failures are mechanical states, never
scientific conclusions.

| file | contents |
|---|---|
| `14_final_answer.md` | **researcher-facing**: Overview, Supporting findings (cited passages, exact), Unresolved parts |
| `14b_detailed_inspection.md` | the existing ledger rendering, unchanged, then the construction record (claim dispositions, exclusions, withheld statements, receipts) |
| `14a_overview.json` | the separately hashed artifact (units, claims, proposals with reasons and NLI scores, parts, call receipt) |
| `14c_overview_reasoning.txt` | S's reasoning (private: it contains library text) |

Request parts are reported as `passage_stated`, `hedged_only`, `topical_only` or `no_responsive_evidence`; none is a completeness
verdict, and whole-part answers are never assessed. A passage may bear on a part it was not attached to.

## S execution envelope (explicit, fixed, unmeasured)

Qwen3.5 9B, **thinking on**, isolated Ollama. `num_ctx 20,480`, `num_predict 16,384` (thinking + answer share it), prompt cap
12,000 chars (~4,096 estimated tokens) so cap + allowance = context. Sampling is the Qwen3.5 model card's thinking-mode
recommendation (temperature 1.0, top_p 0.95, top_k 20, min_p 0, presence_penalty 1.5) with the harness seed 42.

Why: recorded Qwen3.5 thinking-on calls spent almost all tokens reasoning (final JSON ~85-190). 12 of 19 finished under 3.9K, 4
needed 5.5-7.1K, and 3 hit 8,192 with no output, including both whole-ledger audits. 16,384 is ~2x the largest budget at which
any call finished; the card recommends 32,768 for most thinking queries. The harness's temperature 0 is the setting under which
those 3 capped; the card recommends `presence_penalty` against endless repetition. This is a deliberate, recorded deviation for S
only; validation protects the answer either way, so it affects whether the call finishes, not what may be shown.

**Unmeasured, and the first live run is what measures them:** GPU residency at 20,480 context on the 8 GB card; whether 16K tokens
finish inside the 1,200 s watchdog (needs >= 13.65 tok/s; 32-34 measured at 12,288); whether this schema and prompt finish at
all with thinking on; and whether `presence_penalty` 1.5 interferes with faithful wording (a failure there withholds statements,
the safe direction). A capped call is a NO ANSWER, is not retried, and the settings are never changed after a failure. The first
run records `eval_count`, `done_reason`, `thinking_chars`, a repetition ratio (a loop vs. honest exhaustion) and post-stage
`size_vram/size`. Latency contract: one S call and one batched NLI call (LATENCY sections 4, 12, 13).

## Limits (stated, not hidden)

* Lexical guards plus a coarse NLI model are **screening**. A fluent, wrong-relation statement could still pass; the cited passage
  is always shown so a reader can judge.
* Whether a passage itself establishes a *requested relationship or effect* is a semantic assessment that does not exist in this
  pipeline (R and C judge topical responsiveness). It is named here as a dependency and is not hidden in a prompt: no part is ever
  reported answered, hedged statements stay hedged, and an intervention idea cannot become an effectiveness claim.
* Truncated passages are excluded, which can drop a genuinely useful passage (for example a cross-cultural statement) until
  retrieval supplies a complete one.
* The overview reports what retrieved passages say; it makes no statement about what the library or literature holds.

## Commands

    python -m experiments.ask_cli_revised.e2e --profile T5O --hierarchy --preflight-only   # shows the S prompt, budget, sampling; touches nothing
    python -m pytest experiments/ask_cli_revised -q                                        # offline tests (use the network-refusing launcher)

`E2E_SCORED_LEDGER=<a sealed 11_verified_ledger.json>` enables the read-only replay of the deterministic layer over a recorded run.

## Lineage

The design constraints (passage authority, no in-prose anchors, truncation excluded, single-passage overviews, separately hashed
artifact, two-tier output) are Cliff's steering; the scientific request and hierarchy are his. Nearest precedents: the shipped
inc-124 Overview (a model narrates only what was verified) and analytic-flexibility (the model proposes, local code verifies). It
implements no scholarly method.

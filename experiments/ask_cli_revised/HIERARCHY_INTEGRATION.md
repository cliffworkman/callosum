# Hierarchy integration: the approved q_aib v8 decomposition in the experimental Ask E2E

Branch `experiment/ask-e2e`, everything under `experiments/ask_cli_revised/`. Nothing here ships in the app. This is the
offline integration only: no live E2E, model call, retrieval, database or library access has been run for it.

## What it does

The E2E turns a request contract into subquestions (one obligation each). `hierarchy_contract.py` loads the approved v8
hierarchy (11 executable children: c1-c6, c8-c12; c7 is folded into c8; S1 is background and never asked), verifies it, and
emits a `hierarchical-request-v1` contract whose subquestions have exactly the shape the E2E already consumes. Retrieval,
evidence selection, R/C/P, sealing and rendering keep their code; the additions are additive and conditional on the new
contract version. The flat request path is the default and is byte-identical (`test_flat_path_golden.py`, hashes captured from
the unmodified code before any edit).

The E2E is used as it is: this integration reveals the limits of its current scientific-answering stages; it does not fix them.

## Files

| file | role |
|---|---|
| `hierarchy_contract.py` | pure loader/verifier, model-facing text, seal, pins/review, roll-up, authorization gate, run checks, `freeze` / `verify` CLI |
| `hierarchy_contract.frozen.json` | the pin CANDIDATE (UNREVIEWED; see below) |
| `HIERARCHY_FREEZE_REVIEW.md` | generated review sheet for the person who reviews the pins |
| `request_contract.py` | `request_subquestions` dispatches on the contract version; `obligation_display` honors a child's `model_display` |
| `stages.py` | item rows carry the child's hierarchy record; `seal` adds the structural roll-up |
| `e2e.py` | `--hierarchy`, `--preflight-only`, `--experiment-authorization`; readiness and gate run FIRST |
| `ledger_renderer.py` | additive contract blocks, nested headings, one reconciliation section |
| `e2e_checks.py` | hierarchical branch of `mechanical_report` |
| `test_hierarchy_*.py`, `test_flat_path_golden.py`, `hierarchy_test_support.py` | offline tests |

## What a model sees, and what it never sees

Model-facing (retrieval text, item lines shown to W/R/C/P): the child's exact wording; for a child with a recorded
`retained-scope` qualification (c11) the parent's exact wording as scope context; and exact approved constraint texts under
"Constraints for interpreting this question". Constraints are not part of the retrieval embedding text; the scope context is.

Never model-facing, but kept in the contract, the sealed ledger and the report: approval refs and hashes, RC/CD/D/M
identifiers, provenance labels (`deterministic_scaffold`, `researcher_approved`, ...), requirement records, human-review
meanings, and the D10 record for brain networks. A guard scans every model-facing string for those tokens and for any
mention of networks, at load time, at `execute()` time, and over the prompts a finished run actually sent.

A qualification is shown only if its exact approved text carries no provenance token. Two do not: c9's `no-reask-traits`
(names "c8" and an RC id) and c11's `retained-scope` (names c10/c11/RC-6). They stay machine-side and are listed in the report
as "Recorded, not shown to the models". c11 still receives c10's exact wording as operational scope in retrieval and assessment;
c9 receives nothing from c8's question.

## Decision D-1 = A and D10

The non-network D4 human-review meanings (behavior measures for c5; implicit/explicit attitude measures for c6; the documented
nature or direction of an association, qualified by "where supported", for both) are recorded exactly in the contract and the
report as human-review meanings that this run does not operationalize or assess. Their absence from the prompts is not a repeal
of D4, not a finding about any answer, and not evidence about their importance. The active no-presupposition constraint
(RC-8 for c6, RC-9 for c5) is model-facing. Brain networks stay optional (D10): recorded as superseded, never shown, and the
loader refuses a hierarchy in which they become required again. No qualification is synthesized for c6.

## Four labels, one vocabulary

representation `accounted` (24 of 24; a lexical check) | child-level responsiveness `judged_responsive / no_responsive_claim /
not_assessed` | individual obligation fulfilment `not_assessed` (constant) | parent answer completeness `not_certified`
(constant). The roll-up copies each obligation's owner child and that child's state unchanged; it states no fulfilment for an
obligation and no completeness for a parent. Checks and tests enforce it. The E2E still assesses ONE item per child, so a child
that owns several obligations (c5: whether, how, kinds) shows one state. Finer claims need separate evidence or adjudication.

## Refusal, before any side effect

The hierarchy is verified and gated before git, library, database, models, runtime, trace directory, or the sampler's output
directory are touched (`main()` and `run_topology()`; `execute()` re-asserts). It refuses a child that is not executable, a
changed approved string or hash, a duplicate approval, a lost c10 to c11 scope link, a lost c9 trait-scale pairing, networks
required again, an unclassifiable requirement, any pin drift, and unreviewed pins. A hierarchical run may not slice its
children, slice recovery gaps, or seed claims; smoke may only lower retrieval caps. There is no fallback to literal source text.

## The pin file is an UNREVIEWED candidate

`python -m experiments.ask_cli_revised.hierarchy_contract freeze` writes `hierarchy_contract.frozen.json` and the review sheet. The
same code generates and verifies the pins, so its checks prove only that the inputs are unchanged since generation. Inputs pinned:
`ASSEMBLED_HIERARCHY.json`, `CLOSURE_APPROVALS.json`, `q_aib.v6.researcher_decisions.json`, `q_aib.v8.closure_decisions.json`, the
original question, `decompose/execution.py`, `decompose/tree.py` and `hierarchy_contract.py` itself, plus per-child wording hashes,
the requirement classification table, the D-1 record and the model-facing hash. A person reviews the sheet, recomputes the input
hashes independently, and writes `hierarchy_contract.review.json` naming the pin file's sha256. The code never writes that file.
Any regeneration invalidates a review. A live run refuses until a matching review exists. `runnable_by_construction` children
(c1, c2, c3, c8, c10) cannot be re-derived here; their recorded state is protected by the hashes only.

## Commands

    python -m experiments.ask_cli_revised.hierarchy_contract verify                       # integrity; reports PINS UNREVIEWED
    python -m experiments.ask_cli_revised.e2e --hierarchy --preflight-only                # readiness + exact model-facing text; touches nothing
    python -m pytest experiments/ask_cli_revised -q                                       # offline tests

The live run is separately gated (`EXPERIMENT_GATE.md`) and is not part of this integration:

    python -m experiments.ask_cli_revised.e2e --profile T5 --question aib --hierarchy \
        --db <frozen library copy> --out <private run dir> --experiment-authorization <authorization.json>

Prerequisites: reviewed pins; an authorization JSON (`experiment_id`, `question_sha256s` containing the q_aib sha256,
`authorized_by`, `authorized_at`, `brief_confirmed: true`); a clean git tree (a scored run refuses any dirty or untracked file);
the frozen library copy whose fingerprint matches; the isolated Ollama endpoint reachable with the T5 models present.

## Known limits

* Child wording and the visible constraint/scope text change together, so a smoke comparison cannot separate them.
* One state per child, not per obligation.
* A larger item list plus a larger ledger can trigger the harness's existing prompt-too-large NO ANSWER for C; it is recorded
  as not assessed, never as a verdict.
* Offline tests prove carriage and structure. Whether R/C honor a constraint or the scope is only observable in a live run and by
  the researcher's adjudication.

## Lineage

The scientific request, the scope decisions (D1-D10), the clarification approvals (RC-1 to RC-10) and the closure dispositions
(CD-1 to CD-5) are Cliff's; existing attributions in the closure records stand (including the dispositions Lucien proposed and the
engine author recorded in them). This adapter's architecture and implementation are Claude's, authorized by Cliff's stated
requirements; no prior authorship is rewritten. It implements no scholarly method.

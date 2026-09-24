# Ask 0.7 E2E harness — how it runs and what it guarantees

Branch `experiment/ask-e2e` (worktree `.claude/worktrees/ask-e2e`). Plan and rationale: `E2E_TOPOLOGY_PLAN.md`.
Nothing here ships in the app; everything is under `experiments/ask_cli_revised/`.

## One arm on one question

    python -m experiments.ask_cli_revised.e2e --profile T0..T5 --question aib|lld|builtenv \
        --db <library copy> --out <private run dir> [--smoke [--smoke-seed <ledger.json>]] [--juno-sampler]

Sequence: `W -> verify -> R -> C -> P -> W -> verify -> R -> C -> render`.
W = bounded extraction (retrieve, context gate, evidence selection, claim formation); *verify* = the unchanged local
source verification; R = per-claim responsiveness; C = coverage audit over the ledger; P = one bounded recovery plan.
Stages a topology does not bind (R in a model-coverage arm) are absent; no-op stages (no new evidence, no planned search)
are recorded as `skipped` with a reason in `stage_log.json`.

Roles and bindings: `topology.py` (`WAVE1` = T0..T5). Frozen R/C/P prompts and schemas are the bakeoff's own
(`supervisor_prompts.py`, proven byte-equal on the frozen battery). Every model call goes through the execution-policy seam
(`execution_policy.run_stage_call`): one call, one allowance (Qwen3.5 recovery planning 8,192; everything else 4,096; worker
tasks their own 48–512), no retry, no escalation.

## What a scored run refuses to start without

* frozen model-facing contracts intact (`e2e_contracts.py`, hashes in `e2e_contracts.frozen.json`);
* a **clean git tree** (the exact SHA is recorded in the manifest; smoke runs may be dirty and are marked `scored: false`);
* the **library copy unchanged** from its frozen fingerprint (`library_copy.py`: counts, max ids, size, whole-file sha256,
  WAL bytes), verified before *and* after — drift after the run is a technical-validity issue in the manifest.

## Failure semantics (no mechanical failure becomes a verdict)

NO ANSWER (`answer is None`) is a mechanical state at every stage: a capped call is NO ANSWER even if partial JSON parses;
a valid empty selection is an *answer*. P NO ANSWER => no planned recovery and **no** fallback to legacy recovery. C NO ANSWER
=> every item `not_assessed`, no plan, no recovery. Gate NO ANSWER => the packet is neither accepted nor grown and is excluded
from extraction (`gate_no_answer`). `e2e_checks.py` separates *model mechanical* failures (count against the arm, never retried)
from *infrastructure* failures (technical-validity issue), and reports the actual gate NO ANSWER rate — no threshold.

## Artifacts (per run dir)

`00_question` … `10_verification` (retrieval trace), `11_verified_ledger.json` (sealed, hashed), `12_coverage_audit[.initial]`,
`13_recovery_plan`, `13_gap_recovery`, `14_final_answer.md` + `14_render_manifest` + `14_final_audit` (deterministic
responsiveness-aware renderer; conformance re-checked), `15_run_manifest.json` (profile, SHA, library fingerprint, model
digests, Ollama versions, caps, stage log with per-stage wall/swap seconds, residency snapshots, sampler), `16_mechanical_checks.json`,
`qwen_calls.jsonl` (every model call: model, stage, allowance, done_reason, outcome, tokens, wall, thinking chars).
Run dirs are private (`.local/`, never committed): they contain library text.

## Utilities

* `worker_preflight` — Qwen3.5 `think:false` worker: pass/fail on accepts-think-false, schemas hold, completes under caps.
* `e2e_checks.build_adjudication_sheet` — blinded sheet (opaque ids, no arm/model) of the attachments a run *asserted* as
  responsive; frozen AIB labels decide their own claims, everything else goes to the sheet; the key is a separate file.
* `e2e_checks.frozen_label_reuse` — AIB claims matching the frozen battery inherit Cliff's expected judgments.

## Smoke

`--smoke` lowers retrieval breadth and limits the initial units/recovery gaps (`SMOKE_LIMITS`, recorded in the manifest); it is
unscored and refused for scored runs. `--smoke-seed` replaces round-one W with an earlier run's source-verified claims so R/C/P
see real content when the worker yields none; the ledger must be for the same request and its sha256 is recorded.

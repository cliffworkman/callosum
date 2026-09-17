# Ask 0.7 pre-execution infrastructure

Experimental MODEL × REPRESENTATION PACKAGE infrastructure, outside production. This delivery has no live inference command, HTTP transport, weight downloader, model loader, or runtime launcher. `freeze_manifest_v0` is a pre-execution freeze, not an execution authorization.

## Offline commands

From the repository root, with the existing Python environment:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m experiments.ask_070.selfcheck
python -m experiments.ask_070 verify-freeze
python -m experiments.ask_070 score-synthetic --input experiments/ask_070/tests/fixtures/synthetic_cases.json --output <private-temp>/synthetic-score.json
python -m experiments.ask_070 audit-corpus --db <private-frozen-copy.sqlite> --procedure experiments/ask_070/specifications/heldout_selection_v0.json --output <private-temp>/presence.json --private-matches <private-temp>/matches.json
python -m experiments.ask_070.regression_check --out <private-temp>
```

`build-freeze --payload <frozen-payload.json>` rebuilds the pre-execution manifest and detached hash. `freeze.build()` and `freeze.verify()` are also Python entrypoints. Rebuilding after code/input changes is a new preparation action; it does not authorize changing a frozen execution or overwriting observations. Keep future run directories outside the repository.

## Boundaries

- R_CONTROL loads the unchanged production planner source directly to bypass inference imports in the parent package initializer. It preserves scope selection, prompt, tolerant extraction, parser, caps, deduplication, and fallback. Strict whole-response/schema diagnostics never choose its effective representation. Shared A1 FORMAT enforcement is recorded separately. Any demonstrated incompatibility between parity and FORMAT must stop final freeze.
- R_0_6 always raises `REPRESENTATION_PACKAGE_NOT_AVAILABLE`. No replacement package exists.
- `run_synthetic_cell` accepts only `FakeRuntimeAdapter` and `SYNTHETIC` tasks. This is an explicit transport seam for infrastructure verification, not a live runner. The package interface supports preparation and interpretation of arbitrary future task kinds; current R_CONTROL supports only the existing request planner. Unsupported combinations fail visibly.
- A cell hashes exact model/runtime configuration, package, hardware configuration, total context, output-budget policy, and frozen task. All original question whitespace is preserved in input identity. Production prompt trimming remains a separately pinned transform.
- Claims are exclusive directories. Submission is journaled durably before calling an adapter. An interrupted or already claimed observation cannot be resubmitted. Cold, warm, and padded Stage-1 trials are separate predeclared identities, never failure-triggered retries. Failure cannot add a trial; unavailable prerequisites leave later trials explicitly not run.
- REALISTIC is 12,288 **total** tokens. Semantic output-cap policy remains `REQUIRED_FINAL_FREEZE_VALUE`; the neutral-only 4096 cap does not resolve it. Future common or package-specific caps are representable without changing the interface. Package-specific envelopes belong to the package contrast.
- B_worker=3.0 s and B_orch=15.0 s are warm product/interaction budgets. Exceeding them on neutral fixtures is descriptive only. L_screen=600 s is the Stage-1 catastrophic ceiling. Mechanical admission is not semantic viability.

## Corpus and referents

The four candidate question texts and deterministic selection procedure were fixed before lexical inspection. Positive qualification means plausible lexical presence, never answerability. Negative qualification would mean absence under this exact lexical procedure, never scientific absence. No replacements are automatic.

The three positive domains qualified. The Parkinson's/microbiome negative slot is `NEGATIVE_CONTROL_REPLACEMENT_REQUIRED`: conservative same-paper matching found paper 208, including a Parkinson reference-region match. This does not adjudicate that paper's substantive relevance.

Deterministic question spans and offsets are frozen. Phrase categorization is explicitly a Codex draft requiring genuine human review; it is not accepted EVAL ground truth. Scientific answer targets were not authored. These inventories are external to every representation package and never enter prompts. Historical q_aib/q_builtenv/q_depr remain DEV with original hashes and denominator-provenance caveats.

## Scoring and receipts

The offline scorer computes arithmetic on external human labels (synthetic labels only in this delivery). It retains all five overall fidelity categories and independent LOSS/ADDITION/MALFORMED flags, separate mechanical/responsiveness/completeness/contamination axes, and per-question results. Missing labels and denominators are explicit. Contamination is a hard separate outcome. Numeric final thresholds are unresolved, not inferred from proposals or observations.

Matched contrasts include model conditional on package, package within model across models, and their difference-in-differences. Hardware, context, task inputs, and unit sets must match. No prompt effect or pure-capacity claim is produced. Wilson reporting uses the lower endpoint of a two-sided 95% interval. There is no cross-question average or weighted context-loss composite.

Correctness artifacts privately retain wire requests, raw provider bytes/text, metadata, effective representation, and transformation decisions. Performance-only artifacts are allowlisted numeric/enumerated fields plus opaque hashes; they contain no scholarly text or filesystem paths. Missing/failed/indeterminate/corrupt observations cannot pass by silence. The small schema validator rejects unsupported schema keywords rather than silently accepting unvalidated features.

## Remaining final-freeze dependencies

Non-semantic infrastructure preparation does not mean R_0_6 is the only remaining decision. Dependencies include human blinded adjudication and separately authorized revised-0.6 acceptance; accepted R_0_6; negative-control domain replacement; human referent review; final fidelity/materiality numerics; semantic output-cap and thinking policies; acquired weight/runtime/template hashes; mechanical preflight evidence; hardware availability; frozen downstream task packets; and Gemini call budget/egress authorization. All remain explicit in `freeze_manifest_v0`.

The included offline guard denies network connections/DNS, subprocess creation inside guarded workloads, model-library imports, and production model/provider entrypoints. Existing regressions may import lazy app definitions under the guard, but cannot load models or invoke providers. This evidence covers task-owned processes, not unrelated activity on the host.

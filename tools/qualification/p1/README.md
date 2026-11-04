# P1 packaged-model qualification on a hosted Windows runner (inc 633)

P1 asks one question: does the **signed Windows packaged runtime** (`win-x86_64-py3.11-s1-2094b5a287a1dd54`) load
the pinned Arctic S and DeBERTa checkpoints through Callosum's own provisioning, resolvers and contract checks,
offline, with outputs matching the frozen reference? A PASS answers only that. It does not close P1b (DeBERTa
latency/memory acceptance), P2 (packaged backend), P3 (worker lifecycle), P4 (installed Tauri app), macOS/Linux,
issue #110, the independent security review or the 0.6.0 release gate.

The local laptop track for P1 is closed as **RESOURCE-BLOCKED**: the maintainer laptop's ordinary free-memory
baseline sits below the local harness's start gate. Its evidence is preserved privately and unchanged; none of its
unexecuted tests is counted as passed. This directory replaces it with a run on a fresh GitHub-hosted VM.

## Trigger

`.github/workflows/p1-qualification.yml` runs on a **push to `qualify/p1-0.6.0` only**. There is no
`workflow_dispatch` (that requires the file on the default branch), no schedule, no tag or pull-request trigger, and
the job also checks the repository and ref. Every push to that branch is an execution; re-running a job re-runs the
same commit. Permissions are `contents: read`; checkout does not persist credentials; no secret is referenced.

## Isolation contract

A fresh hosted VM replaces the laptop's protected-path ACL checks: fresh workspace, no private data, no research
library, no model cache, no account credentials, public checkpoints and synthetic fixtures only, no release or
deployment access. The driver also strips `HF_*`, `TRANSFORMERS_*`, `CALLOSUM_*`, `PYTHON*` and Actions token
variables from every interpreter it starts.

## Procedure (`p1_qualify.ps1`)

Each stage runs once; a failed stage stops the run (except that Arctic and DeBERTa both run once `verify` passes).

| Stage | What it proves |
|---|---|
| resources | runner memory/disk recorded; start gate 6 GiB available physical, 8 GiB free commit, 6 GiB disk |
| commit | HEAD is the triggering commit; `d6649dfb` (and the regression PASS `c7c645fe`) are ancestors; only this directory, the workflow and the two files of the inc-634 Arctic pooling fix (`app/backend/embeddings/models.py`, `tests/test_embedding_profiles.py`) differ from `d6649dfb`; checkout clean |
| download | the archive, manifest and signature from the project's immutable `python-runtime-…` release (HTTPS, no token) |
| archive | 382,931,495 bytes, SHA-256 `ce0d2052…4c` (pinned here; the primary trust anchor) |
| manifest | runtime ID, archive hash/size, tree hash, entry count, unpacked bytes, interpreter path and version equal the pinned values |
| extract | `p1_extract_runtime.ps1`: .NET tar reader mirroring `python_runtime.rs` `extract_verified` (rejects traversal, links, wrong root, collisions, oversize); stream digest must equal `a51f65b3…fc` before anything runs |
| tree | `p1_tree_digest.ps1` re-reads the extracted files: 41,338 entries, 1,315,019,532 bytes, `a51f65b3…fc` |
| signature | `p1_minisign.py` verifies the manifest's Minisign signature against the `PUBLIC_KEY` in `python_runtime.rs` |
| runtime_id | `package_python_runtime.py id` (run by the packaged interpreter) reproduces the runtime ID from the committed inputs |
| identity | `python.exe -I -B`: executable, prefix, isolated mode, no bytecode writes, Python 3.11.15, every distribution equal to the signed manifest |
| provision | the app's inc-615 `Provisioner` fetches only the two P1 manifests into a disposable `HF_HOME`, verifies every file's size and SHA-256 and the static contracts |
| boundary | profiles enabled; one outbound **block** rule for the exact `python.exe` path; positive control (pwsh connects to the same IP); negative controls (the packaged interpreter's connections to the IP, `huggingface.co` and `github.com` must fail with WSAEACCES 10013); Hub offline mode on; an unprovisioned model is unavailable. Without a demonstrated block the run stops INCONCLUSIVE |
| verify | offline: manifests re-hashed, static contracts, provisioning receipts, `local_files_only_for` true, cache holds only the two repositories, no partial files |
| arctic | offline: `resolve_profile_embedding_model` (Arctic S profile, pooling/max-seq contract enforced) encodes the 3 frozen texts; cosine ≥ 0.99999 against the reference for each; query path shape |
| deberta | offline: `resolve_support_scorer` (runs `verify_nli_checkpoint`); a wrong label order must be refused; max \|Δp\| ≤ 0.001 for all three probabilities and for the app's (entailment, contradiction) extraction; 4 app-derived statuses unchanged; thresholds 0.7/1.0/0.55/0.55 unchanged |
| after | runtime tree digest unchanged, checkpoints re-verified, no bytecode in the checkout, checkout unchanged, no surviving runtime process |
| cleanup | experiment firewall rules removed and profiles restored (the workflow repeats the removal) |

Model processes run serially, one model per process. Each is sampled every second for working set, private bytes,
child processes and system memory; it is stopped (INCONCLUSIVE) below 1.5 GiB available physical memory or on
timeout. The probe also records its own peak working set and peak commit (`GetProcessMemoryInfo`).

**Verdict:** any failed integrity, contract, scientific or isolation check is **FAIL**; otherwise any failed
infrastructure check or incomplete stage is **INCONCLUSIVE**; **PASS** needs every stage complete and every check
passed. The job fails unless the verdict is PASS.

## Fixture (`fixtures/p1-probe-v1.json`), frozen before the first execution

Inputs are the synthetic sentences of the 2026-10-31 packaged smoke probe (3 Arctic texts, 2 DeBERTa premise/
hypothesis pairs); no library content. References are that probe's development-environment outputs; the historical
packaged outputs are included for information only. The four expected statuses were derived from the frozen
reference probabilities with the app's own `LocalCitationVerifier._status` at fixed retrieval/quote confidences
(1.0/1.0 and 0.0/0.0) before any run. Source hashes are in the fixture's `provenance`.

**Reduced coverage, stated:** the private G1 fixtures (Set A 99 pairs, Set B 209 pairs) are not published, so their
categorical parity remains P1b work. MiniLM retrieval similarity is not exercised in P1.

## Evidence

The artifact `p1-qualification-<run_id>-<attempt>` (90 days) holds `p1-receipt.json` (verdict, every check with its
kind and detail, resources, runtime and model identities, process measurements, harness hashes, limitations, what is
not covered), `p1-summary.md`, each phase's JSON and stdout/stderr, the extraction log and entry list.

## Limitations

- The block covers the exact `python.exe` image; a child process of another image would not be covered. None is
  expected, any is recorded, and any other than `conhost.exe` fails isolation.
- Name resolution is done by the Windows DNS Client service, so DNS queries can leave the VM (public host names only).
- Absence of observed traffic is never used as evidence; the block is shown by refused connections plus a positive
  control.
- Hosted-VM memory figures are P1 evidence only, not the predeclared P1b acceptance.

## Local self-test

`python -B tools/qualification/p1/p1_selftest.py [--manifest … --signature …]` checks the fixture, the extraction
and digest scripts against the packaging code on synthetic archives (plus malformed ones), the signature verifier,
PowerShell syntax and the workflow's trigger and permissions. It downloads nothing and loads no model.

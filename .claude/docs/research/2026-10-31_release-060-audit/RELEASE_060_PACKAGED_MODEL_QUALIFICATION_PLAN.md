# Callosum 0.6.0: packaged Arctic S and DeBERTa qualification plan (inc 631)

**Status:** plan only. Nothing here has run. No model was downloaded or loaded, no installer was built, no account
or ACL was changed. Every execution step below needs Cliff's per-experiment authorization (the experiment gate).

**Baseline:** full regression PASS on `c7c645fe` (inc 630, attempt-2). That run **did not load either model**: both
real-snapshot tests skipped and every model-backed test uses fakes. It is evidence for code paths, not for models.

Facts below were read from the code at `c7c645fe`, not inferred from earlier plans.

## 1. What the code implements

| Item | Arctic S (retrieval) | DeBERTa (claim verification NLI) |
|---|---|---|
| Hub id @ pinned revision | `Snowflake/snowflake-arctic-embed-s` @ `e596f507467533e48a2e17c007f0e1dacc837b33` | `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` @ `6f5cf0a2b59cabb106aca4c287eed12e357e90eb` |
| Where pinned | `model_runtime.PINNED_MODEL_REVISIONS` | same |
| Byte manifest | `model_provisioning/manifests.py`, track `arctic-s`: every loaded file with size and SHA-256; `model.safetensors` 132,870,584 B | track `deberta-v3-base`; `model.safetensors` 368,877,646 B, `spm.model`, `tokenizer.json`, configs |
| Static contract | `bert`, CLS pooling, max_seq 512, dim 384 | `deberta-v2`, `DebertaV2ForSequenceClassification`, labels 0/1/2 = entailment/neutral/contradiction, tokenizer `DebertaV2*` |
| Stored identity | `model_version` = `…@e596f50…;pooling=cls;max_seq=512;query_prefix=v1;doc_prefix=none` | provenance `verification_nli.{profile, model_name, revision, preference, fallback_reason, thresholds…}` |
| Role | Ask evidence ranking only. Verification similarity stays on MiniLM (0.70 gate) | Support/contradiction scoring in synthesis verification. Stance features stay on MiniLM2 |
| Default | MiniLM is the default and fallback; Arctic is preferred automatically once its index is complete (inc 618) | MiniLM2 is effective. DeBERTa is automatic only when `DEBERTA_RELEASE_GATES` are all true; `packaged_runtime_acceptance` is **False**, so automatic use and automatic download are unarmed |
| Thresholds | n/a (no retrieval threshold change) | support ≥ 0.55, contradiction ≥ 0.55, retrieval ≥ 0.70, quote = 1.0, all MiniLM2-calibrated and recorded as such (`thresholds_calibrated_on`). G1 CONDITIONAL accepted by product decision, not a PASS |
| Provisioning | automatic in the packaged app (`CALLOSUM_APP_DATA_DIR` set), per-track daemon thread, restart-safe, bounded backoff, verified against the manifest; after verification consumers load `local_files_only=True` | same machinery, but not started while the gate is unarmed |
| Absence / failure | Ask uses MiniLM with a recorded fallback reason; a user-forced incomplete Arctic raises `IncompleteEmbeddingIndexError` (fail closed); selection of an incomplete index returns 409 | MiniLM2 with reason `not_provisioned` / `not_verified` / `not_qualified` / `insufficient_memory` / `memory_unmeasured`; a DeBERTa failure inside an operation fails it with no row written and no MiniLM2 substitution (inc 609); a manual selection of an unverified checkpoint returns 409 and never downloads |
| Device | no explicit device anywhere; sentence-transformers auto-detects. **The packaged runtime is CPU-only torch** (`cpu-torch-2.13.0` recipe; Intel macOS `cpu-torch-2.2.2` with transformers 4.57.6) | same |

**GPU is not a packaged-release concern:** every shipped runtime is CPU-only. GPU behaviour matters only for source
checkouts. JUNO is therefore not needed for packaged qualification and should not be used (§5).

## 2. Arctic S qualification matrix

| Requirement | Existing evidence | Missing evidence | Required real-model or packaged test | Safety prerequisites | Acceptance |
|---|---|---|---|---|---|
| Per-library choice; MiniLM default and rollback | `test_embedding_profiles.py`, `test_arctic_activation.py` (fakes); regression PASS | none for logic | covered within P2 below (select automatic, explicit MiniLM, back to automatic) | disposable library | explicit MiniLM persists after Arctic completes; clearing restores automatic |
| Exact model identity in vector search | AST test that every `vector_store.search` passes identity-scoped `candidate_embedding_ids`; inc 610 identity receipt | real vectors from the packaged runtime | P1 parity probe; P2 checks stored `model_version` rows | — | packaged vs dev cosine ≥ 0.99999 on 3 texts; no row with another identity read for an Arctic search |
| Cannot select until complete | `select_profile` 409; tests | none for logic | P2: select before completion | — | 409 with the coverage message |
| Incomplete selected index fails closed | `IncompleteEmbeddingIndexError` tests (T11) | packaged path | P2: forced incomplete user choice | — | Ask refuses with the error; no MiniLM substitution under a user choice |
| Interrupted indexing resumes | `test_index_recovery.py`, `test_modernization.py` (fake worker, real subprocess in inc 618's two-process activation) | real encoder, packaged worker launch, real kill | P3: kill the worker, then the backend, mid-index | worker ownership checked (§4) | coverage never decreases; resumes without a click; no orphan worker; lock free |
| No corruption or mixing of MiniLM vectors | T15/T26 fingerprints (fake encoder) | real encoder | P2: fingerprint MiniLM `embeddings` before and after | DB copy only | MiniLM rows byte-identical; `vector_integrity` clean |
| Retrieval choice does not alter verification | verification similarity hard-wired to MiniLM (`profiles.py`); tests | real run | P2: one synthesis under MiniLM and under Arctic on the same fixture | — | verification provenance identical except retrieval identity; thresholds unchanged |
| Clean packaged install provisions and loads | manifest + offline verification tests; real-snapshot test exists but **skipped** in inc 630 | everything real | P1 (runtime) then P4 (installer) | download authorization; disposable HF cache | provisioner reaches `verified`; offline reload succeeds with `HF_HUB_OFFLINE=1` |
| Real inference, not mocks | inc 610 research receipt (dev env); G2 measured the Arctic worker at 623 MB working set (dev env, torch 2.6) | packaged runtime (torch 2.13) throughput and memory | P1 probe + P3 bounded indexing on a ~10-paper copy | memory floor (§4) | completes; peak RSS recorded; batch-size recovery observed if memory pressure occurs |

## 3. DeBERTa qualification matrix

| Requirement | Existing evidence | Missing evidence | Required real-model or packaged test | Safety prerequisites | Acceptance |
|---|---|---|---|---|---|
| Exact model and revision | pinned and byte-manifested (§1); contract test ties manifest to `NLI_PROFILES` | packaged download | P1: provision into a disposable cache | download authorization | manifest digest verifies; contract passes |
| Loads without `sentencepiece`/`protobuf` | verified locally on Windows in the 0.6.0 audit (dev env) | packaged runtime; Intel macOS transformers 4.57.6 lane | P1 on Windows; CI on macOS arm64/x64 and Linux | no dependency change (runtime-ID inputs) | `verify_nli_checkpoint` passes in the packaged interpreter |
| Label order, architecture, tokenizer | `verify_nli_checkpoint`, `test_nli_profiles.py` | real checkpoint in packaged runtime | P1 | — | label map exact; mismatch fails closed |
| CPU latency and memory | G2 CONDITIONAL GO: +≈3 s per 21-pair verification, +≈1.06 GB peak working set, peak commit 2.3 GB (dev env, Python 3.12, torch 2.6) | **packaged runtime not measured** (this is the open `packaged_runtime_acceptance` gate) | P1b: cold and warm 21-pair recheck on the packaged runtime, concurrent with an Arctic worker once | memory floor; nothing else running | within the G2 envelope agreed with Cliff, or a new decision |
| Scientific behaviour unchanged | G1 CONDITIONAL (exact app thresholds, Set A 99 / Set B 209 pairs) | packaged numerical parity | P1 parity: 2 pairs, |Δp| ≤ 1e-3 vs dev | — | parity holds; **no threshold change** under any result |
| Absence and load failure | `test_verifier_resolution.py`, `test_nli_failure_and_provenance.py` (fakes) | packaged path | P2: no snapshot; corrupt snapshot (Try again path) | disposable cache | MiniLM2 with recorded reason; corrupt → `invalid`, Ask unaffected |
| Retrieval vs verification separation | code (§1); tests | real run | P2 synthesis provenance | — | provenance names the verifier that ran; MiniLM2 never labelled DeBERTa |
| Pipeline compatibility | `verify_many` batching tests (inc 490), latency contract | real 21-pair batch | P1b | — | one batched call per synthesis; statuses unchanged apart from the documented `status_note` |
| Arming decision | gate constant pinned by a test | the P1b receipt itself | none: a product decision after P1b | — | Cliff arms the gate, or 0.6.0 ships with DeBERTa automatic preference disarmed |

## 4. Local execution plan (Windows first)

**Evidence supports running the next step locally on Windows.** The committed
`python-runtime-inputs.json` names Windows runtime `win-x86_64-py3.11-s1-2094b5a287a1dd54`, the same ID as the
runtime already installed by 0.5.16. So the packaged interpreter can be qualified **without building an installer
and without a runtime download**, as `smoke_test_backend.py` already does (portable interpreter + staged source).

| Item | Plan |
|---|---|
| Workspace | a new disposable root (for example `C:\callosum-631`), outside Dropbox and outside every protected path; a staged `callosum-src` from a bundle of `c7c645fe` (or the documentation HEAD, which has no code change) |
| Runtime | a **copy** of the installed runtime directory into the disposable root, verified against its canonical tree digest before use. The installed copy is never executed in place and never written |
| Account | the existing `callosum-val` (standard, already denied the 30 protected targets). No new account, no ACL change |
| Model storage | `HF_HOME` inside the disposable root. About 0.5 GB of weights (133 MB + 369 MB) plus the provisioner state dir |
| Network | open only for the provisioning step, restricted by intent to `huggingface.co`; every load and test after that runs with `HF_HUB_OFFLINE=1` and the proxy suppression used in inc 630 |
| Resources | C: has 59 GB free. Machine: 16 GB RAM, about 24.8 GB commit limit. Idle free commit was 6.5 to 7.1 GB with applications open and 12.9 GB with them closed. Floor for P1b: 8 GB free commit, as in inc 630, with other applications closed (DeBERTa + app + worker ≈ 3 GB peak commit in G2) |
| Protected data | no protected path in any environment variable; DB is a disposable copy or synthetic; the inc 630 BEFORE/AFTER manifest and access-denial checks are reused |
| Observation | the packaged interpreter runs the real backend: `/health`, `/embedding-profiles`, `/modernization`, synthesis provenance read from the API and the disposable DB, worker processes from `Get-Process`, peak RSS sampled from outside |
| Evidence | a private `validation-631` folder beside `validation-630`, with config, hashes, raw JSON and one verdict file written only by an administrator-side AFTER stage, as in inc 630 |

Stages, smallest first:
- **P1 (runtime model load):** provision both models in the packaged interpreter, verify manifests, reload offline,
  run `verify_nli_checkpoint`, run the parity probes. No app server.
- **P1b (DeBERTa packaged acceptance):** cold and warm 21-pair recheck, alone and once beside an Arctic worker;
  record latency and peak memory. This is the evidence the unarmed gate names.
- **P2 (app behaviour on a disposable library):** the packaged interpreter serves the backend on a 10-paper copy or
  synthetic fixture; Arctic index build, selection refusals, fail-closed, verifier provenance, MiniLM fingerprints.
- **P3 (worker lifecycle):** kills at worker, backend and classification points; resume and no orphan.
- **P4 (installer):** only after P1 to P3. A full install needs a real installer build: either CI artifacts (needs the
  branch on GitHub, which is outward-facing and needs authorization) or a local Tauri build (cargo and node are
  present; nothing installed or built in inc 631). Install only into `callosum-val`, never the maintainer's account.

**macOS and Linux** can only be qualified in CI (`desktop-shell-{macos,linux}.yml`, extending `smoke_test_backend.py`
per Test plan §4). The Intel macOS lane runs a different stack (torch 2.2.2, transformers 4.57.6) and needs its own
DeBERTa contract check.

## 5. JUNO
Not needed: the shipped runtimes are CPU-only, so representative packaged behaviour is CPU behaviour on desktop
hardware. If GPU behaviour in source checkouts ever needs a receipt, it would be a separate, explicitly authorized
plan: a separate process that shares nothing with production services, capped threads and memory, a time-boxed
window agreed with the host's administrator, thermal monitoring with a stop rule, and production services untouched.
Not proposed for 0.6.0.

# Callosum 0.6.0: packaged Arctic S and DeBERTa qualification plan (inc 631, revised incs 632A and 632C)

**Status:** plan only. Nothing in this plan has run. No model was downloaded or loaded, no installer was built, no
account or ACL was changed. Every execution stage needs Cliff's separate per-experiment authorization.

Facts below were read from the code at `c7c645fe` (no code changed since), not inferred from earlier plans.

## Revision log
**Revision 1, 2026-11-03 (inc 632A)**, after an independent review of the inc 631 version. Corrections, each verified:
1. *Inc 631 said neither model had ever loaded in a packaged runtime.* **Wrong.** Both pinned checkpoints loaded in the
   installed 0.5.16 packaged interpreter on 2026-10-31 in a compatibility smoke probe (Scope §3), confirmed from the
   probe's raw outputs (§0). What has not happened is an app-path load, a manifest-verified load, the P1 protocol, or
   an installer run. §0 separates the four claims.
2. *Inc 631 budgeted about 0.5 GB of weights.* **Incomplete.** P1b to P4 also need MiniLM and MiniLM2. Full snapshots
   total about 0.9 GB (§6).
3. *Inc 631 said the inc 630 BEFORE/AFTER checks would be reused.* **Clarified:** the mechanisms are reused; a fresh
   baseline, token namespace and AFTER close each new window. Old receipts prove nothing about a new run (§7).
4. *Inc 631 said provisioning would be restricted to `huggingface.co`.* **Not enforceable as written:** the locked
   `hf-xet` client transfers weights from separate storage hosts, and Windows Firewall cannot filter by hostname (§7.3).
5. *Inc 631's P2 criterion expected identical verification provenance under MiniLM and Arctic retrieval.* **Too
   strong:** different retrieval legitimately changes the evidence verified. Split into Tests A and B (§8.1).
6. *Inc 631's DeBERTa parity criterion was numerical only.* **Strengthened** with app-status stability on the frozen
   G1 sets and predeclared P1b resource rules (§8.2, §8.3).

The rows in §1 to §5 that these corrections change are marked **[R1]**.

**Revision 2, 2026-11-03 (incs 632B, 632B-R, 632C).** The installed-runtime source assumed in §4 and §7.1 was
disproved. The original text is kept below, marked **[R2: superseded]**. Each point was verified from receipts:
1. *History.* The 2026-10-31 compatibility smoke probe (§0, claim 1) ran the installed 0.5.16 interpreter **in place**
   as `python.exe -I probe.py`. `-I` implies `-E`, so Python ignored `PYTHONDONTWRITEBYTECODE` as well. Extraction
   gives source files new modification times, so the shipped `.pyc` headers no longer matched. On import, Python
   recompiled and **replaced 3,195 shipped `__pycache__/*.pyc` files** (2026-10-31 13:30 to 13:34, net +121,450 B,
   same paths, same entry count).
2. *Failed digest.* In inc 632B the installed tree gave 41,338 entries, 1,315,140,982 B and SHA-256
   `63d7609ec5a5434bdd776e0ca3227343ab35f2b35a331f4454d28b967bc8c990`, not the signed
   `a51f65b35c9d5abbdf3317569f5ee798bcb20fd6437459913b3fcf030167f2fc`. The installed runtime is therefore not a
   verifiable source. It **has not been repaired**: the desktop app keeps running it (it checks only its receipt), and
   repairing it would modify the maintainer's install, which is a separate decision.
3. *Recovery.* In inc 632B-R the signed release archive `win-x86_64-py3.11-s1-2094b5a287a1dd54.tar.gz` was downloaded
   once. Its 382,931,495 B and SHA-256 `ce0d2052a0a9dc1cc542aa9ebcbe32b938984f6ed948e5b8659de2c011334d4c` match the
   manifest and the original install receipt. It was extracted under the installer's rules, with no execution, to
   `C:\callosum-632\recovery-632br\runtime`. Two independent computations reproduced `a51f65b3…` exactly (41,338
   entries, 1,315,019,532 B). Against these pristine bytes, the installed tree differs in exactly the 3,195 `.pyc` files
   and nowhere else.
4. *Signature limitation.* The manifest's minisign signature was **not** re-verified: the project's verifier crate was
   not available offline, and fetching it would have been a second download. The binding is the hash chain to the
   2026-10-01 install receipt, written after the installer did verify the signature. It is not a signer
   authentication made in 2026.
5. *Smoke check versus P1.* The 2026-10-31 probe remains a historical packaged-interpreter **compatibility smoke check**
   (direct library calls, the maintainer's cache, no manifest, no contract, no isolation, run in place). It is not P1.
   P1 (§9) remains unstarted.
6. *Revised P1 source.* P1 runs a **fresh per-experiment copy of the recovered pristine runtime**, never the reference
   copy and never the installed runtime. The copy is digest-verified (file digest **and** directory inventory) before
   and after. `callosum-val` is denied write access to it. The interpreter runs as `python.exe -I -B`, because `-B`
   (not the environment variable) is what stops bytecode writes under `-I`.

## 0. Evidence boundaries: four distinct claims

| Claim | Status | Evidence |
|---|---|---|
| 1. Both models have loaded in a packaged Callosum interpreter | **Yes, historically (smoke only)** | 2026-10-31 probe: installed 0.5.16 runtime `win-x86_64-py3.11-s1-2094b5a287a1dd54`, executed in place, offline, direct `SentenceTransformer`/`CrossEncoder` calls at the pinned revisions from the maintainer's cache. Recomputed from the saved outputs: Arctic cosine ≥ 0.999999866, max \|Δ\| 7.45e-8; DeBERTa max \|Δp\| 2.65e-5. Raw outputs and command preserved privately |
| 2. They have loaded through the packaged Callosum application (resolvers, contracts, provenance) | **No** | never run |
| 3. The current pinned runtime has passed the P1 protocol (manifest-verified, contract-checked, offline, isolated) | **No** | never run |
| 4. An installer has passed end-to-end qualification | **No** | never run |

| Evidence class | What exists | What it supports | What it does not |
|---|---|---|---|
| Development-model evidence | inc 610 Arctic identity receipt; G1 (Set A 99, Set B 209 pairs through the app path) and G2 receipts, all on Python 3.12 / torch 2.6 | scientific behaviour at the shipped thresholds (G1 **CONDITIONAL**, accepted by product decision); dev CPU cost (G2 CONDITIONAL GO) | packaged-runtime behaviour |
| Historical packaged-interpreter smoke | the probe above | the packaged dependency stack can load both checkpoints and agrees numerically on 3 texts and 2 pairs | app-path loading, manifest identity (manifests came later, inc 615), contracts, latency, memory, isolation |
| Inc 630 regression | full suite PASS at `c7c645fe` (Python 3.11.14 from `uv`, locked deps, source clone) | code-path correctness with fakes | any real model; the packaged interpreter (3.11.15 build `20260718`); installed layout |
| Required inc 632+ evidence | P1, P1b, P2, P3, P4 below | — | — |

**Changed since the probe:** the byte manifests and offline-after-verify loading (inc 615), app-side contract
enforcement and verifier resolution (incs 618, 619), the five test corrections. The runtime ID and the pinned
revisions are unchanged.

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
| Device | no explicit device anywhere; sentence-transformers auto-detects. **The packaged runtime is CPU-only torch** (`cpu-torch-2.13.0` recipe; Intel macOS `cpu-torch-2.2.2` with transformers 4.57.6 and huggingface-hub 0.36.2) | same |

**GPU is not a packaged-release concern:** every shipped runtime is CPU-only. GPU behaviour matters only for source
checkouts. JUNO is therefore not needed for packaged qualification and should not be used (§5).

## 2. Arctic S qualification matrix

| Requirement | Existing evidence | Missing evidence | Required real-model or packaged test | Safety prerequisites | Acceptance |
|---|---|---|---|---|---|
| Per-library choice; MiniLM default and rollback | `test_embedding_profiles.py`, `test_arctic_activation.py` (fakes); regression PASS | none for logic | covered within P2 below (select automatic, explicit MiniLM, back to automatic) | disposable library | explicit MiniLM persists after Arctic completes; clearing restores automatic |
| Exact model identity in vector search | AST test that every `vector_store.search` passes identity-scoped `candidate_embedding_ids`; inc 610 identity receipt | real vectors from the packaged runtime through the app's loader | P1 parity probe; P2 checks stored `model_version` rows | — | packaged vs dev cosine ≥ 0.99999 on the fixed texts; no row with another identity read for an Arctic search |
| Cannot select until complete | `select_profile` 409; tests | none for logic | P2: select before completion | — | 409 with the coverage message |
| Incomplete selected index fails closed | `IncompleteEmbeddingIndexError` tests (T11) | packaged path | P2: forced incomplete user choice | — | Ask refuses with the error; no MiniLM substitution under a user choice |
| Interrupted indexing resumes | `test_index_recovery.py`, `test_modernization.py` (fake worker, real subprocess in inc 618's two-process activation) | real encoder, packaged worker launch, real kill | P3: kill the worker, then the backend, mid-index | worker ownership checked (§4) | coverage never decreases; resumes without a click; no orphan worker; lock free |
| No corruption or mixing of MiniLM vectors | T15/T26 fingerprints (fake encoder) | real encoder | P2: fingerprint MiniLM `embeddings` before and after | DB copy only | MiniLM rows byte-identical; `vector_integrity` clean |
| Retrieval choice does not alter verification **[R1]** | verification similarity hard-wired to MiniLM (`profiles.py`); tests | real run | **§8.1 Tests A and B** (replaces "one synthesis under each, provenance identical") | — | §8.1 |
| Clean packaged install provisions and loads | manifest + offline verification tests; real-snapshot test exists but **skipped** in inc 630; **[R1]** historical smoke load in the packaged interpreter (§0) | manifest-verified provisioning in the packaged interpreter; any installer | P1 (runtime) then P4 (installer) | download authorization; disposable HF cache (§6, §7) | provisioner reaches `verified`; offline reload succeeds |
| Real inference, not mocks | inc 610 research receipt (dev env); G2 measured the Arctic worker at 623 MB working set (dev env, torch 2.6); **[R1]** historical packaged smoke on 3 texts | packaged runtime throughput and memory through the app | P1 probe + P3 bounded indexing on a ~10-paper copy | memory floor (§7) | completes; peak RSS recorded; batch-size recovery observed if memory pressure occurs |

## 3. DeBERTa qualification matrix

| Requirement | Existing evidence | Missing evidence | Required real-model or packaged test | Safety prerequisites | Acceptance |
|---|---|---|---|---|---|
| Exact model and revision | pinned and byte-manifested (§1); contract test ties manifest to `NLI_PROFILES` | packaged download | P1: provision into a disposable cache | download authorization | manifest digest verifies; contract passes |
| Loads without `sentencepiece`/`protobuf` | verified on Windows in the 0.6.0 audit; **[R1]** the historical probe loaded it in the packaged interpreter | the packaged interpreter through `verify_nli_checkpoint`; Intel macOS transformers 4.57.6 lane | P1 on Windows; CI on macOS arm64/x64 and Linux | no dependency change (runtime-ID inputs) | `verify_nli_checkpoint` passes in the packaged interpreter |
| Label order, architecture, tokenizer | `verify_nli_checkpoint`, `test_nli_profiles.py` | real checkpoint in packaged runtime | P1 | — | label map exact; mismatch fails closed |
| CPU latency and memory | G2 CONDITIONAL GO: +≈3 s per 21-pair verification, +≈1.06 GB peak working set, peak commit 2.3 GB (dev env, Python 3.12, torch 2.6) | **packaged runtime not measured** (the open `packaged_runtime_acceptance` gate) | P1b, **predeclared in §8.3** | memory floor; nothing else running | §8.3 |
| Scientific behaviour unchanged **[R1]** | G1 CONDITIONAL (exact app thresholds, Set A 99 / Set B 209 pairs); historical smoke \|Δp\| 2.65e-5 on 2 pairs | packaged numerical **and categorical** parity on frozen fixtures | **§8.2** | — | §8.2; **no threshold change** under any result |
| Absence and load failure | `test_verifier_resolution.py`, `test_nli_failure_and_provenance.py` (fakes) | packaged path | P2: no snapshot; corrupt snapshot (Try again path) | disposable cache | MiniLM2 with recorded reason; corrupt → `invalid`, Ask unaffected |
| Retrieval vs verification separation | code (§1); tests | real run | P2 synthesis provenance | — | provenance names the verifier that ran; MiniLM2 never labelled DeBERTa |
| Pipeline compatibility | `verify_many` batching tests (inc 490), latency contract | real 21-pair batch | P1b | — | one batched call per synthesis; statuses unchanged apart from the documented `status_note` |
| Arming decision | gate constant pinned by a test | the P1b receipt itself | none: a product decision after P1b | — | Cliff arms the gate, or 0.6.0 ships with DeBERTa automatic preference disarmed |

## 4. Local execution plan (Windows first)

**Evidence supports preparing the next step locally on Windows.** The committed
`app/desktop-shell/packaging/python-runtime-inputs.json` names Windows runtime
`win-x86_64-py3.11-s1-2094b5a287a1dd54` (CPython 3.11.15, build `20260718`, `cpu-torch-2.13.0` recipe). The installed
0.5.16 runtime has the same ID, and its `runtime-install.json` records the activation-time tree SHA-256
`a51f65b35c9d5abbdf3317569f5ee798bcb20fd6437459913b3fcf030167f2fc`. So the packaged interpreter can be qualified
**without building an installer and without a runtime download**, as `smoke_test_backend.py` already does (portable
interpreter + staged source). Re-hashing the installed tree before copying is the first preflight step (§7).
**[R2: superseded]** The installed tree failed that re-hash (Revision 2). P1 instead uses the signed archive,
downloaded once in inc 632B-R. Its extracted tree reproduced `a51f65b3…`. No installer is built.

| Item | Plan |
|---|---|
| Workspace | a new disposable root (§7.1), outside Dropbox and every protected path; a staged `callosum-src` from a bundle of `c7c645fe` (or a later documentation-only HEAD) |
| Runtime | a **copy** of the installed runtime directory, verified against the activation tree digest. The installed copy is never executed in place again and never written. **[R2: superseded]** Now a fresh per-experiment copy of the recovered pristine runtime `C:\callosum-632\recovery-632br\runtime` (Revision 2, point 6). The installed runtime is not used |
| Account | the existing `callosum-val` (standard). No new account, no ACL change outside the disposable root |
| Model storage **[R1]** | a dedicated `HF_HOME` inside the disposable root; full per-stage snapshot set and headroom in §6 (about 0.9 GB for all four models, 2 GB budget) |
| Network **[R1]** | a bounded, observed download phase, then an offline phase enforced per §7.3; never described as isolation |
| Resources | C: had 59 GB free on 2026-11-03. Machine: 16 GB RAM, about 24.8 GB commit limit. Idle free commit was 6.5 to 7.1 GB with applications open and 12.9 GB with them closed. Floors in §7 and §8.3 |
| Protected data **[R1]** | the inc 630 safety mechanisms, re-run fresh for each window (§7); no protected path in any environment variable; DB is a disposable copy or synthetic |
| Observation | the packaged interpreter runs the real backend: `/health`, `/embedding-profiles`, `/modernization`, synthesis provenance read from the API and the disposable DB, worker processes from `Get-Process`, peak RSS sampled from outside |
| Evidence | a private `validation-632` folder beside `validation-630`, with config, hashes, raw JSON and one verdict file written only by an administrator-side AFTER stage |

Stage boundaries are in §9. **macOS and Linux** can only be qualified in CI (`desktop-shell-{macos,linux}.yml`,
extending `smoke_test_backend.py` per Test plan §4). The Intel macOS lane runs a different stack and needs its own
DeBERTa contract and parity check. Windows results qualify neither.

## 5. JUNO
Not needed: the shipped runtimes are CPU-only, so representative packaged behaviour is CPU behaviour on desktop
hardware. If GPU behaviour in source checkouts ever needs a receipt, it would be a separate, explicitly authorized
plan: a separate process that shares nothing with production services, capped threads and memory, a time-boxed
window agreed with the host's administrator, thermal monitoring with a stop rule, and production services untouched.
Not proposed for 0.6.0.

## 6. Model dependencies per stage (R1)

Sizes are the pinned snapshot file sets as they sit in an existing cache (metadata read only, nothing opened or
copied). Only Arctic S and DeBERTa have a committed byte manifest.

| Model | Pinned revision | Files a load needs | Snapshot size | Committed manifest | Who loads it, and how |
|---|---|---|---|---|---|
| `sentence-transformers/all-MiniLM-L6-v2` | `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` | 11 (safetensors 90.9 MB, tokenizer, vocab, pooling and ST configs) | 87 MB | **No** | baseline retrieval, paper/axis embeddings, verification similarity (0.70 gate). Loaded with `local_files_only=False`: **downloads implicitly on first use** unless offline |
| `cross-encoder/nli-MiniLM2-L6-H768` | `b95119ce93d3e065de6214e38cd4a97b0f2f2c6d` | 8 (safetensors 328.5 MB, BPE vocab/merges, tokenizer) | 316 MB | **No** | compatibility verifier and stance features. Implicit download on first use; its verifier has an embedding **fallback** if NLI fails (DeBERTa has none) |
| `Snowflake/snowflake-arctic-embed-s` | `e596f507…` | 12 (manifest) | 128 MB | Yes | provisioner, then `local_files_only=True` |
| `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` | `6f5cf0a2…` | 7 (manifest) | 362 MB | Yes | provisioner (only when armed or forced), then `local_files_only=True` |
| `sentence-transformers/allenai-specter` | `2c68eeca…` | 11 | 420 MB | No | Publishers and citation-equity features only. **Not needed by P1 to P4**; must stay absent |

| Stage | Models required | Load path | Implicit-download risk if a model is absent |
|---|---|---|---|
| P1 | Arctic S, DeBERTa | direct loads plus the app's contract checks (`verify_nli_checkpoint`, manifest verification) | none if offline is enforced |
| P1b | DeBERTa, MiniLM2, **MiniLM** (the verification process loads it, as G2 recorded), Arctic S (concurrency load) | app path: `resolve_support_scorer` → `LocalCitationVerifier.verify_many` | MiniLM and MiniLM2 would download implicitly |
| P2 | all four | full app resolvers | MiniLM and MiniLM2 would download implicitly; a missing MiniLM2 would also trigger the embedding fallback |
| P3 | Arctic S (worker), MiniLM (Ask during indexing) | worker subprocess and resolvers | as above |
| P4 | all four, provisioned by the installed app itself | installer path | the point of P4 is to observe this; it is the only stage where app-driven download is the test |

**Provisioning policy.**
1. Each stage downloads only what it needs, at its own authorization; nothing is fetched early.
2. Never read or grant access to the maintainer's Hugging Face cache from `callosum-val`. Files are obtained from the
   Hub into the disposable `HF_HOME`; the maintainer's cache is not a source.
3. Arctic S and DeBERTa are verified against the committed manifests. MiniLM and MiniLM2 have no committed manifest:
   the download phase records every file's size and SHA-256 in a private receipt, and the Hub's own LFS hash check is
   noted as the only upstream check. This is weaker than a manifest and is reported as such.
4. After verification the snapshot directory is made read-only for the account; every load is offline.
5. **Budget:** about 0.9 GB for all four snapshots. A standard account usually cannot create symlinks, so the Hub cache
   stores real copies; temporary `.incomplete` files can double the largest file during transfer. Plan for 2 GB of
   model storage and require at least 10 GB free on the volume before any download.

## 7. Fresh isolation for each experiment window (R1)

The inc 630 mechanisms are reused; none of their receipts are. Every window has its own SETUP, BEFORE and AFTER.

### 7.1 Layout and identity
| Item | Requirement |
|---|---|
| Root | `C:\callosum-632\` (not under any user profile, Dropbox, or `callosum-worktrees\integrate-607-608`). Subfolders: `runtime\`, `src\`, `hf\`, `db\`, `tmp\`, `evidence\` |
| Evidence | `%USERPROFILE%\callosum-worktrees\validation-632\<window>\`, written only by the administrator stages; `<window>` is `p1`, `p1b`, … |
| Token namespace | `632-<window>-<uuid>`; RUN refuses tokens from `validation-630` and any reused token |
| Ownership and ACL | root owned by Administrators; `callosum-val` gets Modify on `tmp\`, `db\`, `hf\` (download phase only), `evidence\`; Read and Execute on `runtime\` and `src\`. After the download phase `hf\` drops to Read and Execute |
| Runtime copy | SETUP re-hashes the installed runtime tree with the same canonical algorithm as `python_runtime.rs` (validated by reproducing `a51f65b3…` on the installed tree before copying), copies it, re-hashes the copy, refuses on any mismatch. AFTER re-hashes the copy. **[R2: superseded]** SETUP re-hashes the recovered pristine reference instead (`a51f65b3…`; it is never executed). It copies the reference into the attempt root and verifies the copy's file digest and directory inventory. It then sets the copy's ACL: owner Administrators, `callosum-val` read and execute plus an explicit write/append/attribute/delete deny. AFTER repeats both checks; any added, removed or rewritten file, `.pyc` included, or any new directory, even an empty one, is a FAIL |
| Bytecode **[R2]** | every interpreter launch is `python.exe -I -B`. `-I` ignores `PYTHONDONTWRITEBYTECODE`, so the variable alone is not a control |
| Module resolution | the copied interpreter runs with `-I` (isolated: no user site, no `PYTHON*` variables, no script-directory insertion) from `src\` with an explicit `sys.path` entry for the staged source only; the child proof prints `sys.path` and `app.__file__`, which must lie under `C:\callosum-632\src` |
| Identity guard | as inc 630: token account name, not in Administrators or CodexSandboxUsers, registered and effective profile `C:\Users\callosum-val`, checked before any Python starts |
| Environment guard | as inc 630, plus: `HF_HOME`, `HF_HUB_CACHE`, `TMP`, `TEMP` point inside the root; `CALLOSUM_DB_URL`, `SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE`, `CURL_CA_BUNDLE`, `HF_TOKEN`, `HUGGING_FACE_HUB_TOKEN`, `PYTHONPATH`, `CALLOSUM_APP_DATA_DIR` (except where P2 sets it inside the root) must be absent. The receipt is written **after** the token check (fixes the inc 630 receipt-overwrite defect) |
| Protected targets | the same 30 access-denial targets, re-probed in this window; they already include the maintainer's Hugging Face hub cache and the installed runtime directory |
| Fixture inputs | the frozen G1 inputs (private G1 raw receipt and disposable G1 database, itself a protected target) are copied into `db\` by the administrator SETUP, hashed before and after; the account never reads the originals |

### 7.2 BEFORE and AFTER
- **BEFORE** (administrator, immediately before the window): refuses on an open desktop app or model port, free
  commit below the stage floor, or under 10 GB free disk, before writing anything. Then records the protected
  manifest, the main checkout's HEAD and status, seals of `validation-630` (both attempts), the runtime-copy digest,
  and the process list of `callosum-val`.
- **AFTER** (administrator, always, including after a failure, Ctrl+C, crash or reboot): waits up to 120 s for
  `callosum-val` processes, lists survivors, recomputes the manifest and seals, scans for files written outside the
  root since BEFORE in the account's profile and `%TEMP%`, and writes the only verdict. Precedence as inc 630:
  SAFETY-STOP, INCONCLUSIVE, FAIL, PASS. A missing receipt is INCONCLUSIVE, never PASS.
- **Unexpected process or write:** any `callosum-val` process not descended from the stage's own launcher, or any
  write outside the root, is a named problem.

### 7.3 Network: intended, observed, enforced
| | Download phase | Offline phase |
|---|---|---|
| Intended destinations | `huggingface.co` for resolution, plus Hugging Face storage hosts for the weights: the locked `hf-xet` 1.5.2 client transfers from Xet storage endpoints, and plain LFS redirects to a CDN host | none |
| Observed | `Get-NetTCPConnection` sampled for the interpreter's process tree, remote addresses and reverse-resolved names recorded; hub client logging at INFO | the same sampling must show no remote connection |
| Enforced | **nothing hostname-specific.** Windows Firewall filters by program, address and port, not hostname. The phase is bounded in time and observed, not restricted | an outbound **block** rule scoped to the copied `python.exe` path (covers worker subprocesses, which use the same interpreter), plus `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` and proxy suppression. Adding and removing that rule is a firewall change and needs explicit authorization |

Without the firewall rule the offline phase may only be described as proxy-suppressed and Hub-offline, as in inc 630.

### 7.4 Resource floors
P1 needs 8 GB free commit (as inc 630). P1b and P2 need 8 GB free commit and 6 GB free physical memory at BEFORE
(G2 peak commit 2.3 GB plus the 1.2 GB worker estimate plus the app). The inc 610 `ResourcePolicy` precheck still
runs inside the app. Disk: 10 GB free.

## 8. Scientific acceptance criteria (R1)

### 8.1 Arctic S: retrieval versus verification
- **Test A, verifier independence.** Fixed claim text, passage text, quote, source identifiers, verifier and thresholds;
  run verification twice, once with the run's retrieval profile recorded as MiniLM and once as Arctic S. **Accept** when
  support, contradiction and retrieval similarity are bitwise equal and the status is equal. The verifier must not read
  retrieval identity.
- **Test B, retrieval integration.** Each profile selects its own passages for the same question on the same
  disposable library. **Accept** when: provenance names the retrieval model that actually served; every retrieved
  vector carries that model's full identity; no partial Arctic index is served; every citation resolves to a real chunk
  of the cited paper; each claim is verified against the passage actually selected for it. Passages and statuses
  **may differ** between profiles and are reported, not compared for equality.

### 8.2 DeBERTa: numerical and categorical parity
- **Fixtures:** the frozen G1 inputs and outputs only: Set A (Phase 34, 99 pairs) and Set B (SciFact dev, 209 pairs),
  input hashes in the G1 predeclaration, reference outputs in the private G1 raw receipt (dev environment, the same app
  path). No new pairs are chosen.
- **Run:** the same app path (`resolve_support_scorer` → `verify_many`, `VerificationConfig()` defaults), in the packaged
  interpreter, offline, for **both** MiniLM2 and DeBERTa, so a MiniLM retrieval-similarity shift is not mistaken for an
  NLI difference.
- **Numerical:** max |Δ| per probability ≤ 1e-3 against the frozen reference. Provenance of the number: an engineering
  tolerance set by the 0.6.0 audit (Test plan §4), not a scientific calibration; the historical packaged probe observed
  2.65e-5.
- **Categorical:** the app status per pair must equal the frozen status. **Any status flip is reported by pair and is a
  stop for review, even when the numerical tolerance passes.** Counts are reported separately for each set, never pooled.
- **Boundary coverage, stated as a limitation:** in the frozen DeBERTa results only 3 of 308 pairs lie within 0.05 of a
  0.55 threshold (2 support, 1 contradiction, all Set B) and 1 within 0.02. The MiniLM retrieval similarity lies within
  0.005 of the 0.70 gate for 11 pairs (6 in A, 5 in B). Categorical stability near the NLI thresholds is therefore only
  weakly tested by existing fixtures; no fixture is added to fix that.
- Thresholds 0.55 / 0.55 / 0.70 / 1.0 and `thresholds_calibrated_on` are unchanged. Parity says nothing about
  calibration; G1 stays **CONDITIONAL**.

### 8.3 P1b resource acceptance (predeclared)
- **Fixture:** G2's exact 21-pair subset cannot be reconstructed: its harness was not retained and the raw receipt
  records only counts. P1b therefore uses a **new fixed subset declared before measurement**: the first 21 Set A items
  in the order stored in the private G1 raw receipt (SHA-256 `2A7BA846E525DC17514E15217629A40986FD86908F9D1B7E4C895838FC4EC464`),
  listed by item id in the P1b predeclaration. The G2 comparison is envelope-level, not same-pair.
- **Processes:** each measurement in a fresh process. *Cold* = process start to the first verified pair, with model
  files already in the OS file cache (one discarded warm-up process first); *warm* = the 21-pair `verify_many` call
  after the cold call, repeated 8 times (G2's count).
- **Repetitions:** 3 fresh processes per model, each producing one cold and 8 warm values. Reported: per-process median,
  and the range of medians.
- **Memory:** `GetProcessMemoryInfo` typed call (G2's corrected method): working set and peak working set, private
  commit and peak commit, sampled after imports, after the MiniLM load, after the NLI load and at exit.
- **Threads:** torch default (record `torch.get_num_threads()`); no override.
- **Concurrency:** one run per model with an Arctic encoding worker shaped like G2's (same loader, 4 threads, batch 8,
  below-normal priority).
- **Prerequisites:** §7.4 floors; desktop app closed; record free physical and commit before each process.
- **Acceptance (DeBERTa, packaged):** warm 21-pair median ≤ 7.2 s solo and ≤ 8.8 s concurrent (G2's dev maxima); peak
  working set ≤ 2,016 MB × 1.25 = 2,520 MB; peak commit ≤ 2,298 MB × 1.25 = 2,870 MB. The 25 % allowance for the
  different runtime is declared here, before any packaged measurement.
- **Noise:** a run whose free memory fell below the policy reserve, or that overlapped another heavy process, is
  discarded and repeated once; both are recorded. Two discarded runs in a row is INCONCLUSIVE.
- **Review, not automatic acceptance:** any value outside the range, any MiniLM2 regression of more than 25 % against
  G2, or any status flip in §8.2 goes to Cliff. Tolerances are not revised after measurement.

## 9. Stage boundaries (R1)

| Stage | A PASS shows | A PASS does not show |
|---|---|---|
| P1 packaged-interpreter model compatibility | the copied, digest-verified 0.5.16/0.6.0 runtime loads manifest-verified Arctic S and DeBERTa offline; contracts hold; numerical parity on the probe set | app resolvers, provenance, latency, memory, any installer, other platforms |
| P1b packaged DeBERTa runtime acceptance | §8.2 and §8.3 hold on Windows in the packaged interpreter; evidence for `packaged_runtime_acceptance` | that the gate should be armed (a product decision); macOS, Linux, 8 GB machines |
| P2 packaged-backend app behaviour | real resolvers, Arctic index build and selection rules, fail-closed paths, verifier resolution and provenance, MiniLM preservation, §8.1 | worker recovery, Tauri, installer, upgrade |
| P3 worker and recovery | real worker spawn from the staged layout, interrupted indexing, backend kill, restart reconciliation, integrity, no orphan (Windows Job Object path not included: no Tauri) | Tauri-owned process lifetime, installer |
| P4 installer and installed app | correct runtime install and selection, staged source and resources, Tauri launching the backend, worker ownership and shutdown, clean install and upgrade from 0.5.16, model and cache paths, Status and recovery UI | macOS or Linux |

No earlier stage closes a later one. macOS arm64, macOS x64 (Intel stack) and Linux each need their own CI evidence.

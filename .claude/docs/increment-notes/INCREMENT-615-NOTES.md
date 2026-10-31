# Increment 615 — Automatic model provisioning and recovery

Branch `integrate/inc607-608-ask` (worktree `C:\Users\cliff\callosum-worktrees\integrate-607-608`), on `6f5635e5`.
Local commit only: not pushed, not merged.

Authorized by the 2026-10-31 "Increment 615: Automatic Model Provisioning and Recovery" instruction. It resolves the
infrastructure half of release blocker B2. It also records the accepted G1/G2 decision: DeBERTa is the intended
preferred verifier, accepted on a **CONDITIONAL** G1 result that is not retroactively a PASS.

## Implemented
- **`app/backend/model_provisioning/`** (new package)
  - `manifests.py`: pinned byte manifests for Arctic S (`e596f507…`, 12 files, 133.9 MB) and DeBERTa-v3 base NLI
    (`6f5cf0a2…`, 7 files, 380.0 MB). Each file has its size and SHA-256, recorded from the qualified research
    snapshots the G1/G2 runs loaded offline. Also static contract checks, read from JSON without loading weights:
    - Arctic: model type, CLS-only pooling, 384 dimensions, max sequence 512;
    - DeBERTa: architecture, label order, tokenizer class.
  - `provisioner.py`: one restart-safe track with:
    - `status()`: local, no network, no hashing;
    - `provision_once(force=False)`: one bounded attempt;
    - failure classification;
    - an atomic JSON state file and the inc-610 OS lock per track.
  - `runner.py`:
    - per-track daemon runners;
    - the DeBERTa release gates;
    - the enable switch;
    - `local_files_only_for(model_name)`;
    - the lifespan start/stop hooks.
- **`app/backend/api/app.py`:** starts provisioning in the lifespan and stops it on shutdown. Neither call blocks.
  Three frontend-fallback helpers moved verbatim to the new `api/frontend_fallback.py` to keep `app.py` under the
  600-line cap (565).
- **`app/backend/api/dependencies.py`:** Arctic query encoding and DeBERTa verification load with
  `local_files_only=True` once their checkpoint is verified. The MiniLM and MiniLM2 paths are byte-for-byte
  unchanged.
- **`app/backend/embeddings/index_supervisor.py`:** the Arctic index worker gets `--local-files-only` once provisioned.
- **`tests/conftest.py`:** the suite never starts a download and never reads the real provisioning state.
- **`tests/test_model_provisioning.py`** (new, 28 tests).

**Unchanged:**
- every model identity, pooling, prefix, threshold and the 0.70 retrieval-verification gate;
- source-role rules, Qwen2.5 synthesis, historical provenance;
- no migration, endpoint, UI, new dependency or threshold.
- **No model is activated.**

## Model acquisition and verification contract
1. **States:** `absent`, `downloading`, `waiting_for_network`, `interrupted`, `present_unverified`, `verified`,
   `invalid`, `insufficient_resources`.
   - **Retryable:** `waiting_for_network`, `interrupted`, `insufficient_resources`.
   - **Terminal:** `verified`, and `invalid` until an explicit retry.
2. **Verified** means every manifest file matches its pinned size and SHA-256, and the static contract holds.
   - The receipt is trusted only while the manifest digest and each file's size and mtime still match. Any touch
     returns the track to `present_unverified` and a re-hash, which needs no download.
   - Verified ≠ qualified: provisioning never makes a scientific claim.
3. **Acquisition** fetches only missing or short files, one at a time, through `huggingface_hub` into the shared Hub
   cache. The cache resumes its own `.incomplete` files, and Callosum never deletes cache entries. Prerequisites:
   - free disk of at least the bytes needed plus 64 MB;
   - memory at or above the inc-610 pause floor;
   - `HF_HUB_OFFLINE` honoured (no request).
4. **Failure classification**, by class name across the MRO so it works for hub 0.x (requests) and 1.x (httpx):
   - connection, timeout, `LocalEntryNotFoundError`, 408/429/5xx → `waiting_for_network`;
   - repository/revision/entry missing, gated, 401/403/404/410 → `invalid` (`pinned_revision_unavailable`);
   - `ENOSPC` → `insufficient_resources`;
   - anything else → `interrupted`.
5. **Backoff:** 30 s, 2 min, 10 min, 30 min, then 30 min repeated. Bounded, never terminal. An integrity or contract
   failure is never retried automatically. `provision_once(force=True)` is the explicit retry: it re-fetches only the
   files whose bytes failed, with `force_download`.
6. **Ownership:** one OS lock per track. A second instance makes no request and reports `downloading` (owned
   elsewhere). A dead owner's lock is freed by the OS, so a stale `downloading` reads as `interrupted` and resumes.
7. **Independence:** separate state files, locks and threads. DeBERTa's unavailability can never block Arctic,
   indexing or classification.
8. **Automatic start:**
   - On in the packaged app (`CALLOSUM_APP_DATA_DIR`) or with `CALLOSUM_MODEL_PROVISIONING=1`.
   - Off for source checkouts and tests. `CALLOSUM_DISABLE_MODEL_PROVISIONING=1` always wins.
   - Tracks started: Arctic always; DeBERTa only when `DEBERTA_RELEASE_GATES` are all true.
9. **DeBERTa release gates** (recorded booleans, not derived from provisioning, so not circular):
   - `runtime_qualification_recorded = True`;
   - `operation_memory_guard = False`;
   - `verifier_provenance_and_failure = False`;
   - `packaged_runtime_acceptance = False`.

   **Unarmed.**
10. **Once an operation starts:** the scorer is resolved once per job, so provisioning finishing mid-operation cannot
    switch the verifier. The inc-609 fail-closed behaviour is untouched.

## Offline, interruption and restart-recovery receipt (automated)
All cases are in `tests/test_model_provisioning.py`:
- already cached: zero requests;
- first time: one request per file;
- network down at start, then restored, with backoff;
- offline mode: zero requests;
- killed mid-transfer: restart reports `interrupted` and fetches only the unfinished file;
- a real subprocess holding the lock, then killed;
- two instances in one process;
- revision unavailable: terminal across restart, explicit retry recovers;
- corrupt download and corrupt pre-existing cache;
- contract mismatch (labels, pooling);
- disk, memory and ENOSPC exhaustion;
- receipt survives restart and detects a touched file;
- track independence;
- only manifest constants in requests;
- runner retries to settlement and stops on terminal;
- gate unarmed;
- switch logic;
- manifests agree with the profiles;
- import loads no model framework;
- consumers go offline only when verified, with MiniLM2 unchanged;
- **real pinned Arctic S and DeBERTa snapshots verify from the local cache with a fetcher that fails on any call.**

## Manual verification script
1. In the worktree: `$env:CALLOSUM_MODEL_PROVISIONING = "1"`, `$env:CALLOSUM_MODEL_PROVISIONING_DIR = "<temp dir>"`,
   then start uvicorn against a disposable DB.
2. Within seconds, `<temp dir>\arctic-s.json` reads `"state": "verified"` on a machine that already holds the pinned
   snapshot, with no network request. The app serves throughout.
3. With `$env:HF_HUB_OFFLINE = "1"` and a cache without the snapshot, the state reads `waiting_for_network` with a
   `next_attempt_at`.
4. There is no `deberta-v3-base.json` (gate unarmed).

## Not done / owed
- **Status-popover/UI and an endpoint for provisioning state.** This belongs to the modernization coordinator
  increment. Without it, a first-run Arctic download in the packaged app is invisible to the user (invariant #5 owed
  before release).
- Automatic Arctic activation, DeBERTa operation-level selection, memory precheck, verifier-keyed ETA, cautious
  `contradicted` wording, packaged-runtime recheck.
- Real network download and real Hub resume were not exercised. They are mocked by design (no unbounded download
  during development).

## Pytest
- `tests/test_model_provisioning.py`: 28 passed.
- Regression: embedding profiles, model runtime, NLI profiles, startup migration, summaries, index recovery,
  admission indexing, citation stance, re-verify, summarization, structure currentness: 196 passed.
- `test_frontend_assembly.py`: 3 failures, identical on clean HEAD (this worktree has no esbuild install); unrelated.
- Gates: line budget OK, tach OK, QA surface map OK, ruff format/check clean.

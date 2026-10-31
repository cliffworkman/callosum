# Security audit: automatic model provisioning (inc 615)

**Date:** 2026-10-31.
**Scope:** `app/backend/model_provisioning/` (manifests, provisioner, runner), its lifespan hook in `api/app.py`, and
the three consumers that switch to `local_files_only` once a checkpoint is verified (`api/dependencies.py`,
`embeddings/index_supervisor.py`).
**Triggers:** a new external fetch path (Hugging Face Hub) and a new file-write path (provisioning state files).

## Threat review
| Area | Finding |
|---|---|
| **Data egress** | A request carries only constants from the pinned manifest: repository id, git revision and filename. No library text, path, identifier or user data can enter a request; the module imports nothing from persistence. Test `test_requests_name_only_the_pinned_manifest`. Model downloads already occurred implicitly before this increment (sentence-transformers fetches on first load); provisioning makes that explicit, pinned and bounded |
| **Supply chain / integrity** | Every file is checked against a pinned size and SHA-256 recorded from the qualified research snapshots. A file the Hub serves with different bytes at the same revision fails as `invalid` and is never loaded through the offline path. Static contract checks (architecture, label order, tokenizer, pooling) read only JSON. Load-time `verify_nli_checkpoint` still runs (fail-closed, inc 609) |
| **SSRF / external calls** | The host is the Hub client's fixed endpoint; no URL comes from input. Timeouts are the Hub client's own (`HF_HUB_DOWNLOAD_TIMEOUT`, `HF_HUB_ETAG_TIMEOUT`). `HF_HUB_OFFLINE` is honoured: no request is attempted |
| **File-path safety** | State files are `<state_dir>/<track>.json` and `.lock`, with `track` drawn from a fixed manifest dictionary. Writes are atomic (`tmp` + `os.replace`). Cache writes are performed by `huggingface_hub` into its own cache; Callosum never deletes cache entries. Filenames come from the manifest only |
| **Resource exhaustion** | Disk space is checked before a transfer (need + 64 MB margin); a full disk (`ENOSPC`) is classified as `insufficient_resources`, not a crash. Provisioning loads no model: hashing streams 1 MB chunks. A transfer does not start below the inc-610 memory pause floor. Retries follow a bounded backoff (30 s, 2 min, 10 min, 30 min, then 30 min) |
| **Concurrency** | One OS-level lock per track (the inc-610 `WorkerLock`), released by the OS on process death, so two instances never download the same checkpoint and a killed download is detected as `interrupted` |
| **Activation / consent posture** | Provisioning activates nothing. Arctic downloads automatically only in the packaged app (`CALLOSUM_APP_DATA_DIR`) or when `CALLOSUM_MODEL_PROVISIONING=1`; `CALLOSUM_DISABLE_MODEL_PROVISIONING=1` turns it off. DeBERTa's automatic download is behind four recorded release gates, three of which are false |
| **Secrets** | None used. Gated or private repositories are classified as `pinned_revision_unavailable`; no token is read or sent by Callosum |
| **Dependencies** | No new dependency. `huggingface_hub` is already installed as a dependency of `transformers` (0.36.2 / 1.24.0 in `uv.lock`; 0.28.1 in dev). Exceptions are classified by class name across the MRO, so behaviour does not depend on its requests (0.x) or httpx (1.x) transport. Declaring it directly would change the frozen Python-runtime lock and was deliberately not done |
| **Output / logging** | Diagnostics are whitespace-collapsed and truncated to 400 characters; they contain exception text from the Hub client and manifest filenames only |

## Negative-path checks (all automated, `tests/test_model_provisioning.py`, 28 passed)
- Network refused at start, then restored: `waiting_for_network` with backoff 30 → 120 → capped; then `verified`.
- Offline mode: no request made.
- Process killed while owning a track (real subprocess holding the lock): other instance makes no request; after the
  kill, `interrupted`.
- Pinned revision unavailable (404 / gated / repository missing): terminal `invalid`, never retried automatically,
  survives restart; explicit retry recovers.
- Same-size corrupt artifact (download or pre-existing cache): terminal `invalid` naming the file; explicit retry
  re-fetches only that file with `force_download`.
- Contract mismatch (swapped NLI labels, non-CLS pooling): `invalid`.
- Insufficient disk, insufficient memory, `ENOSPC`: retryable `insufficient_resources`.
- Importing the package loads no torch, transformers or sentence-transformers.
- Real pinned Arctic S and DeBERTa snapshots verify from the local cache with a fetcher that fails on any call.

**Security Audit: PASS**

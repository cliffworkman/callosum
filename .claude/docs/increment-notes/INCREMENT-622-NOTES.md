# Increment 622 — Model recovery and final-code regression

Branch `integrate/inc607-608-ask` (worktree `C:\Users\cliff\callosum-worktrees\integrate-607-608`), on `5d5d922a`.
Local only: not pushed, not merged, no version bump, no gate armed. Feature freeze: one authorized repair (F8).

Evidence (gitignored, local): `C:\Users\cliff\callosum-worktrees\integrate-607-608\.local\validation-622\`.

## Implemented
- **`POST /modernization/models/{track}/retry`** (`routers/modernization.py`): the explicit "Try again". `track` must be a
  pinned manifest key and the body is ignored. It starts a `ProvisioningRunner(force=True)` around the existing
  `provision_once(force=True)`. No new acquisition code.
- **`model_recovery` on `GET /modernization`:** the models a retry applies to, with `can_retry` and `retrying`, from
  provisioning state only.
- **Eligibility:** `invalid`, or a retryable state on a track with no automatic runner. The second case exists because a
  DeBERTa retry interrupted by a restart would otherwise wait for a runner that never comes. Normal downloads and waits
  on a track with its runner are never listed.
- **Runner:** `force`, `on_settled`, `active`, `is_retry`. A forced runner keeps its force through network and resource
  waits (a plain attempt would re-declare the corrupt file invalid) and stops at the first terminal state, or if another
  process owns the track.
- **Provisioner:** `manual_retries` counts `invalid` to retry transitions and a verified result clears it, so the panel can
  say "The last Try again did not fix this."
- **Coordinator:** a public `wake()`, so scheduling re-checks as soon as a retry settles. Every existing condition still
  applies.
- **Presentation:** `recovery_message()`; "no in-app repair" is gone. During a retry the summary is `working`; the failure
  returns if the retry fails. DeBERTa adds a `verifier_model` note. Still one Status entry.
- **Frontend:** a "Try again" button per listed model in the existing panel, disabled during the request, named per model
  for assistive technology. `model_recovery` joined the idle-tick signature.
- **Help:** a "Model download failures" paragraph.

## Key technical detail
- **Pause does not block an explicit retry and a retry does not lift Pause.** Pause has always governed classification
  and indexing, not model acquisition. After a repair, indexing stays stopped until Resume. A running retry also keeps
  going if the user pauses; the Status row keeps reporting it.
- **Repair is not activation.** Verified DeBERTa changes nothing: all of its release gates remain as they were, including
  `packaged_runtime_acceptance = False`, and MiniLM2 stays the automatic verifier.
- `force` re-fetches `missing + corrupt` only, so verified files keep their bytes and mtimes. A contract-only failure
  re-verifies, fetches nothing, and returns to `invalid`.

## Scientific behaviour
Unchanged. No retrieval, identity, threshold, source-role, generation or provenance code was edited. A test compares every
`chunks`, `chunk_structure` and `embeddings` row before and after a repair.

## Results
See the receipts table at the end of this file. **No real model was downloaded or loaded.** The network is mocked in every
test and in the browser check.

## Manual verification script
1. `python .local\validation-622\browser_recovery.py` with `CALLOSUM_DB_URL` overridden; read `browser\result.json`.
2. By hand, on a disposable library: corrupt one Arctic file in a provisioned cache, reopen Callosum, open
   **Settings → Library behavior → Library modernization**, click **Try again**, and confirm that the panel reports the
   retry, then verification or the same failure.

## Not run
A real Hugging Face transfer and `force_download` over a corrupt blob on each OS; a packaged build; two real app processes
with a browser attached; the control at mobile width. The tracked items from inc 621 stay open: see the blocker matrix.

## Security
Audit `.claude/security-audits/2026-11-01_model-retry.md`: PASS, **self-review**. No independent review exists for
incs 616-622.

## Receipts

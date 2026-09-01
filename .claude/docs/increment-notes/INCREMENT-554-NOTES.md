# Increment 554 Notes — Local AI Setup Visibility and Runtime Repair

## Outcome

The first public Local AI Preview exposed four connected release defects during the v0.5.0 live check:

1. onboarding looked inert during the roughly 1.04 GiB setup and allowed an accidental **Next**;
2. closing onboarding removed the only visible setup feedback even though Tauri correctly continued ownership;
3. an in-place desktop update retained old Python `*.dist-info`, so the installed runtime reported
   `tokenizers==0.22.2` beside newer Transformers code requiring `>=0.23.1`; and
4. the production Preview still used the frozen 4,096-token qualification context, so Funding Discovery's bounded
   6,348-token prompt failed locally before generation. Critical Read's generic error then misleadingly suggested a
   cloud API key even though managed Local AI was selected.

This increment repairs all four without changing the selected provider or privacy scope.

## Setup and Status contract

- Rust publishes checking, runtime download/preparation, model download, verification, and authenticated-startup
  phases. Streaming downloads expose bytes received, expected bytes, and an ETA derived only after 0.5 seconds of
  phase-local transfer evidence; hashing/startup never invent a percentage.
- The shared Local AI card renders those phases through the existing `ProgressBar`, scrolls new feedback into the
  wizard viewport, names the phase on the disabled setup action, and says explicitly to keep Callosum open.
- **Next** is disabled during active setup. **Continue in background** is the deliberate escape: it completes the
  onboarding acknowledgement but does not cancel or duplicate Tauri's app-scoped operation.
- One frontend status observer—not a modal-scoped duplicate poll—updates **Setting up Local AI** every 1.5 seconds.
  The row carries only on-device phase/byte state and bounded navigation. Clicking it reopens the AI-only wizard at
  the current phase. Completion and failure leave a finished receipt.
- Setup errors now clear the in-progress stage and persist a bounded diagnostic; retry remains local.

## Packaged Python root cause and repair

The live v0.5.0 installation contained multiple metadata generations at once (including
`tokenizers-0.22.2.dist-info` and `tokenizers-0.23.1.dist-info`, plus multiple Transformers and
sentence-transformers generations). Python imported newer package source while `importlib.metadata` selected the
older tokenizers distribution. A clean staged runtime did not reproduce the failure.

The fix is not an ad-hoc user `pip install`:

- `sentence-transformers==5.6.1`, `transformers==5.14.1`, and `tokenizers==0.22.2` are exact lock/runtime identities;
- the packaging smoke verifies Transformers' own tokenizers constraint and imports `CrossEncoder` before launch;
- the NSIS preinstall hook removes only `$INSTDIR\\python-runtime` and `$INSTDIR\\callosum-src`, after Tauri's
  running-app check and immediately before the installer copies fresh immutable resources; and
- the model/runtime downloaded under app data is outside those directories and remains intact across repair.

The first blocking Linux CI run proved this smoke was useful beyond Windows: the older Linux packager deleted all of
`torch/bin` to avoid linuxdeploy traversing Torch's internal test executables, which also deleted the required
`torch_shm_manager`. The packager now deletes only `test_*`/`*Test` files and asserts that helper remains executable
before the same CrossEncoder smoke. This packaging correction was made before the v0.5.1 tag.

This prevents stale overlay metadata without deleting settings, the library, or the verified 1.04 GiB model.

## Managed context identity

The historical developer/qualification path remains byte-for-byte meaningful at 4,096 context and 256 output.
Production Local AI Preview now launches with, publishes, and requires 12,288 context and 2,048 output. The increase
fits the observed Funding prompt (6,348 input tokens) plus the existing output allowance and the bounded Critical
Read contract. A descriptor that claims the old product context is rejected. This is a product transport-capacity
fix, not scientific qualification, prompt tuning, hardware routing, or a fallback policy.

## Invariants

- Tauri alone owns installation and the llama-server process; frontend unmount never owns cancellation.
- Local setup/request failure never calls or suggests that Callosum must call a cloud provider.
- Frozen research configuration and Phase 5A history are unchanged.
- Installer cleanup is an allowlisted replacement of Callosum-owned bundled resources, not broad user-data cleanup.
- No token, descriptor, filesystem path, prompt, scholarly text, or model output enters setup status.

## Verification

Completed during implementation:

- `cargo check --lib`: pass.
- `cargo fmt --all -- --check` and focused managed-local Rust tests: **29 passed, 4 ignored**.
- focused/broader Python slices covering managed-local, Funding, Critical Read, frontend assembly, and desktop
  packaging: **160 logical passes** after rebuilding the generated frontend (the single pre-rebuild failure was the
  expected generated-artifact sync assertion).
- direct clean staged-runtime dependency/CrossEncoder import: pass.
- direct current v0.5.0 installed-runtime check: reproduced the reported tokenizers ImportError, confirming the
  updater-overlay diagnosis.

The final validation receipt is recorded in the commit hand-off after the full affected rerun and static gates.

## Manual patch-release checks

1. Install the patch over v0.5.0 and verify it requires no manual Python command and does not redownload the model.
2. Start Local AI setup in onboarding. Confirm named phases, MiB/ETA, disabled **Next**, and visible feedback.
3. Choose **Continue in background**, open Status, click **Setting up Local AI**, and confirm the same operation and
   progress return without a second download/process.
4. Run Synthesize Ask, Critical Read critique suggestion, and Funding Discovery LLM triage with Local AI selected.
5. Confirm no Gemini/OpenAI/Anthropic traffic and no cloud-key repair prompt on an injected local failure.
6. Restart Callosum; confirm Local AI reuses the verified model, reaches Ready, and leaves no orphan on exit.

## Experience review

- **Migrator:** the in-place updater repairs stale immutable Python resources automatically; the user's app-data
  model and library are untouched.
- **Multi-tasker:** a long setup may leave the modal explicitly, remains visible globally, and has a direct route
  back. Accidental forward navigation is blocked without trapping the user.

The environment did not permit delegating separate persona agents; this pass applied the repository's named persona
questions directly and records that limitation rather than claiming independent review.

## Revert

Revert this increment's commit. Existing v0.5.0 installs with overlaid Python metadata would again require a clean
reinstall, and production Local AI would again reject prompts beyond the old 4,096-token context. No migration or
database rollback is involved.

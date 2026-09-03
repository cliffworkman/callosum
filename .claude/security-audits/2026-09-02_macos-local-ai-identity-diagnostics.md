# Security Audit: macOS Local AI and identity diagnostics

Date: 2026-09-02
Status: CONDITIONAL PASS — live Apple Silicon acceptance is release-blocking

## Scope

Extend the existing one-model managed Local AI Preview from Windows x64 to the already-shipped Apple Silicon
macOS application, make ORCID a first-class local identity independent of OpenAlex enrichment, and provide
privacy-safe copy/paste diagnostics for both affected onboarding flows.

## Invariants preserved

- The macOS installer accepts one immutable official llama.cpp b10516 arm64 archive and the existing immutable
  publisher-owned Qwen artifact. Host allowlisting, exact byte counts, SHA-256 verification, partial paths, and
  atomic promotion remain mandatory.
- Tar extraction accepts one pinned archive root and only `llama-server` plus adjacent `.dylib` runtime files.
  Nested/traversal paths, non-file/non-symlink entries, unallowlisted link targets, and links resolving outside the
  private runtime root fail closed.
- The runtime binds only to literal `127.0.0.1`, uses the existing random per-launch bearer token outside argv,
  publishes no descriptor before authenticated readiness and execution observation match, and retains Unix
  process-group cleanup.
- Selecting Local AI still cannot trigger cloud fallback.
- An ORCID is validated locally with ISO 7064 MOD 11-2, canonicalized, and saved before any OpenAlex request.
  Provider absence, timeout, or no-result cannot invalidate that identity.
- Copyable diagnostics are allowlisted structured fields. They contain no credentials, raw provider exception,
  full ORCID, scholarly text, or filesystem path.

## New egress and privacy surface

There is no new host or data class. Apple Silicon setup uses the same narrow runtime/model download hosts as the
Windows setup, with an additional immutable official GitHub release artifact. OpenAlex continues to receive only
the public name/ORCID identifiers the user explicitly supplies for publication enrichment. Diagnostic copying is
local and user-initiated; Callosum does not transmit the report.

## Validation boundary

Windows compilation, complete Rust tests (38 passed, 5 opt-in live tests ignored), the complete Python suite
(2763 passed, 3 skipped), focused identity/API/frontend tests, Ruff, and the line budget pass
locally. The macOS workflow now blocks on a live test that downloads and verifies both artifacts, starts the
managed runtime, exercises Overview/primary-synthesis/Help provider contracts without cloud credentials, shuts
down, and proves the descriptor/token were removed. This audit must be promoted to PASS only after that Apple
Silicon job succeeds; no release tag may be created before then.

## Apple Silicon acceptance (recorded 2026-09-03) — precondition satisfied

The gating job has since run and passed, so the condition set above is met.

- Workflow run `33711884431` ("Desktop shell (macOS)") at commit `e5dd236`.
- `live_pinned_preview_installs_and_runs_three_generation_contracts` — **ok in 867.15s** on the Apple Silicon
  runner. The duration is part of the evidence: a real pinned-artifact download, digest verification, managed
  runtime start, and three real provider contracts, not a stubbed path.
- The step's own post-conditions (`test ! -e .../managed-local-ai/target.json`,
  `test ! -e .../managed-local-ai/auth-token`) ran under `set -euo pipefail` and the step succeeded, so the
  descriptor and the per-launch bearer token are proven removed on cleanup — the specific residual-credential
  risk this audit was gating on.
- Every subsequent step passed: `.app` build, the resource-aware re-sign, updater-artifact regeneration
  (`Callosum.app.tar.gz` + `.sig`), `.dmg` wrap, and the real mount / Gatekeeper-simulation / screenshot check.

One platform-only defect had to be fixed first (`e5dd236`): the macOS compiler rejected a borrow the Windows
build could not compile-check — a tar entry's filename borrowed from the entry while that same entry was being
streamed. The fix owns the validated filename before streaming and changes no behaviour.

**Security Audit: PASS.**

Verified independently against the code (not from the implementing agent's report): the tar extraction rejects
`..` and absolute paths structurally by matching only `Component::Normal`, and additionally enforces a
canonicalised containment check before writing (`install_macos.rs:97-120,149`); diagnostics carry
`orcid_checksum_valid`/`candidate_orcid_match`/`rejection_reason` but never the ORCID value, no filesystem
paths, no tokens, and `diagnostic_report()` whitelists detail values to primitives only.

## Intel extension (2026-09-03)

The same boundary now includes native Intel macOS. The installer selects the official pinned llama.cpp b10516
`macos-x64` archive only when compiled for `x86_64`, verifies archive size/SHA-256 plus a separately derived
launcher and deterministic bundle-manifest digest, and uses the same allowlisted tar extraction and lifecycle.
The application, portable CPython dependency bundle, Local AI acceptance test, `.dmg`, signed updater archive,
and Gatekeeper exercise are all built on GitHub's native `macos-15-intel` runner. Apple Silicon and Intel remain
separate artifacts and updater targets; neither architecture is mislabeled as universal.

The native acceptance completed successfully in GitHub Actions run `33760636237` on 2026-09-03. Both the
`macos-15-intel` and Apple Silicon lanes passed portable-backend import/health, the live managed Local AI test,
application packaging, signed updater generation, mounted-DMG execution, and Gatekeeper assessment. The Intel
live test installed the pinned x64 runtime, proved requested and observed CPU execution at zero GPU layers,
exercised Overview, primary-synthesis, and Help provider contracts without cloud credentials or egress, and
removed the managed descriptor and launch token during cleanup. This is the release acceptance for 0.5.4.

### Intel packaged-ML compatibility boundary

PyTorch 2.2.2 is upstream's final official native Intel-macOS wheel; newer upstream versions no longer publish
x86_64 macOS wheels. That legacy wheel has known advisories, including GHSA-53q9-r3pm-6pq6 in PyTorch's pickle
loader. The compatible Transformers 4.57.6 lane also predates later fixes for remote-configuration,
`save_pretrained`, Trainer, and LightGlue paths. Callosum mitigates its owned model-loading path by pinning every
Hugging Face model revision and requiring `use_safetensors=True` on every SentenceTransformer/CrossEncoder
construction; a repository that lacks safetensors fails rather than falling back to a pickle checkpoint. The two
production configurations consumed on this lane were inspected at their pinned revisions: they are ordinary
BERT/Roberta configurations, provide `model.safetensors`, and contain no `auto_map`, custom-code, or internal
attention-implementation field implicated in the remote-configuration issue. Callosum neither saves these models
nor invokes Trainer, LightGlue, JIT, LSTM, packed-sequence, or quantized APIs with attacker-controlled tensors.

This is a constrained compatibility risk, not a claim that the legacy dependency has no vulnerabilities. Moving
Intel Macs to a current non-Torch inference runtime or retiring Intel support when the hosted runner disappears is
the appropriate follow-up. Native packaging, backend import/health, and managed Local AI acceptance remain
release-blocking on every future Intel build; the 0.5.4 candidate passed those gates in run `33760636237`.

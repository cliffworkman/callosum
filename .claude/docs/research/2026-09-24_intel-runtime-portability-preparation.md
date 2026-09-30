# Intel runtime portability preparation — #106 / PR #103

Status: local source preparation; publication requires Cliff's explicit authorization. PR #103
remains draft, open, unmerged, and at b0d98e6376ccf17011e5c4a3dc385a94a8268c74. This document
does not claim that the existing published artifact or the current PR has been repaired.

## Evidence and cause

On Intel iMac17,1, Sequoia 15.8 (24H23), a pristine runtime downloaded by the normal signed
installer for b0d98e63 failed on the cryptography Rust binding. `import cryptography` alone and
`pip check` passed; neither loads the binding. The full backend import failed.

Runtime `macos-x86_64-py3.11-s1-73624c15ff4d9219` contains cryptography 50.0.0 with
`libssl.3.dylib` and `libcrypto.3.dylib` dependencies under `/usr/local/opt/openssl@3/lib/`.
The September 16 runtime workflow, run 35118838638, Intel job 104871123342, downloaded the
50.0.0 source distribution and built a `cp311-abi3-macosx_10_12_x86_64` wheel on its runner.
Thus the version alone is not the explanation: the unguarded source build inherited runner
OpenSSL dependencies. PyPI's 49.0.0 and 50.0.0 macOS wheels target arm64; 48.0.1 provides the
Intel-compatible universal2 wheel verified on this target.

## Source changes

- Scope `cryptography>=48.0.1,<49` to Intel macOS; preserve the existing range elsewhere.
  The frozen lock resolves 48.0.1 on Intel macOS and 50.0.0 elsewhere. Other locked package
  versions are unchanged.
- Require a cryptography wheel during the macOS install; there is no source-build fallback.
  Preserve pip's wheel URLs/hashes in `package-install-report.json` inside the runtime tree.
- Import the Rust binding, run `pip check`, and scan every Mach-O load command before the
  existing full backend smoke. Record native linkage and binary hashes in
  `native-dependencies.json`, covered by the existing archive/tree hash and manifest signature.
- Fail on absolute non-system library loads, including weak/re-export/lazy/upward loads.
  Library IDs and search hints are recorded, not mistaken for required dependencies. Upstream
  torch/scikit-learn/scipy wheels contain unused builder search hints; these are not evidence
  that the corresponding libraries are required. This is not a complete dyld resolver or OS-floor
  certification.
- Include the guard in runtime identity inputs. No signing or installer verification is weakened.

## Validation

- Targeted packaging/linkage suite: 57 passed, 1 Windows symlink test skipped. Ruff passed.
- The guard rejects the actual original extension for both missing Homebrew OpenSSL libraries.
- A fresh, separate runtime built from this exact recipe on the iMac passes: binary-wheel install,
  cryptography Rust import, `pip check`, all 262 Mach-O files (zero absolute non-system dependency
  violations), ML imports, backend `/health` 200, and `instance_role=ui`.
- The selected wheel is `cryptography-48.0.1-cp311-abi3-macosx_10_9_universal2.whl`, SHA256
  `3e4a1a3232eef2e6c732827d5722db29a0cc8b27af2a4d865b094cf954be9ca1`.
- No manual post-install package repair was applied to the fresh recipe output. This is local
  clean-target build evidence, not a new CI, signed-install, or old-macOS compatibility result.
- There is no new b0d98e63 full Chrome acceptance result yet. The earlier d9c243 capture completed
  only with manual refreshes. Both no-refresh transitions still need real-user observation.

## New immutable IDs and publication ordering

Shared dependency definitions participate in every ID even though only Intel's package selection
changes. All four artifacts must exist before the app branch references this spec:

| Platform | Prepared runtime ID |
| --- | --- |
| Windows x64 | `win-x86_64-py3.11-s1-2094b5a287a1dd54` |
| macOS arm64 | `macos-aarch64-py3.11-s1-1e588472d8125324` |
| macOS Intel | `macos-x86_64-py3.11-s1-bb4609aaf91bc315` |
| Linux x64 | `linux-x86_64-py3.11-s1-3f1825380a8001da` |

After explicit authorization:

1. Push the reviewed preparation commit to its separate staging branch. Keep PR #103 on its
   existing published IDs until all replacement assets exist.
2. Dispatch `desktop-python-runtime.yml` at that exact staging commit. This workflow signs and
   publishes four immutable runtime releases; dispatch itself is a publication action.
3. Require every build/smoke/signing job to succeed. Verify each release has the matching archive,
   manifest and signature, and that the manifest IDs/input hashes match the reviewed spec.
   Verify signatures and archive/tree hashes; do not replace any existing release asset.
4. Advance browser-capture-research through ordinary commits/fast-forward only, incorporating
   this preparation commit after any separately verified UI fix. Push normally.
5. Obtain CI/CodeQL and platform-build results for the actual resulting PR head. Install its
   new x64 app using an empty disposable runtime cache, retain normal signature/hash checks,
   and repeat the actual Chrome acceptance including both UI transitions.

Do not mark ready, merge, publish an app release, or submit store artifacts as part of this sequence.
Those require separate explicit authorization. Until publication and fresh install acceptance,
the reproducible runtime gate is prepared but not closed.

## Contribution lineage

- Cliff Workman: direction, real-hardware testing and visible Chrome acceptance actions; requested
  the original minimal disposable diagnosis and the later reproducible-runtime gate.
- Earlier Claude/ChatGPT work: existing browser-capture implementation and acceptance chronology,
  retained in PR #103 and its experiment receipts; this preparation does not reattribute it.
- Lucien: critique/handoff emphasizing that app launch is not full capture acceptance and a fresh
  app can still reuse a repaired runtime. No model/version attribution is inferred.
- Codex (GPT-6): final pristine-runtime reproduction, build-provenance evidence, platform-scoped
  recipe/lock change, native dependency guard and focused regression tests described here.

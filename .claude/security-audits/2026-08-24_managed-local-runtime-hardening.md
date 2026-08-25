# Security audit — managed local runtime hardening

**Date:** 2026-08-24
**Scope:** developer-only managed llama-server hashing, bundle identity, execution observation, readiness, descriptor
schema, Python validation, and operational smoke testing

## Trust-boundary findings

| Area | Finding |
|---|---|
| Requested vs observed state | Requested CPU/CUDA and layer count are immutable intent only. The target is unpublished until bounded startup observation proves an exact backend/layer match; absent or mismatched evidence fails closed and triggers cleanup. Python repeats equality/shape validation. |
| Offload control | Every launch carries an explicit `--n-gpu-layers` integer, including zero. This closes llama.cpp automatic-offload behavior that previously made a CPU descriptor empirically false. |
| Runtime identity | Identity includes the launcher digest and a versioned canonical digest over direct-child, allowlisted execution libraries. Relative names, sizes, and hashes are sorted; no absolute paths, models, mutable caches/logs, or arbitrary recursive content enters the manifest. |
| Path confinement | Runtime/model paths remain canonical files. Each manifest entry is canonicalized, must be a direct child and stay under the canonical runtime root, and cannot traverse or follow an external symlink/reparse target. Direct file reads avoid shell expansion. |
| Hashing availability | SHA-256 remains streaming and deterministic but now uses a 64 KiB heap buffer, eliminating the reproducible default-stack denial of service without increasing thread stack size or loading large artifacts into memory. I/O errors fail closed. |
| Runtime output privacy | llama.cpp b10516 requires trace verbosity for actual layer evidence. The owner retains only numeric offload/backend evidence and discards all other stream content as it is read. Nothing is forwarded to app logs, files, terminal, frontend, or descriptor. |
| Descriptor privacy | Schema 2 contains digests, aliases, declared/requested/observed execution, generation settings, and a private credential reference. It contains no raw bearer, runtime/model path, prompt, generated output, scholarly content, or hardware inventory. |
| Existing sidecar controls | Literal IPv4 `127.0.0.1`, ephemeral port, private per-launch bearer file, authenticated inference/readiness, opaque model alias, direct argv, disabled web UI/offline mode, no proxy inheritance in Python, crash invalidation, and process-tree cleanup remain intact. |
| Egress/fallback | Resolution remains Overview-only and `DEVELOPER_TEST_ONLY`. A local startup, execution, transport, parser, or lifecycle failure cannot select or call a cloud provider. |

## Residual risks and boundaries

- A same-user malicious process can access same-user resources; loopback and ACLs are not an OS sandbox. This is the
  unchanged Phase 2 boundary.
- Execution observation is version-qualified startup output because tested llama.cpp `/props` does not publish actual
  offloaded layers. Unsupported or changed output fails closed; it must not be guessed from argv.
- The allowlist intentionally identifies shipped llama.cpp execution libraries without hashing arbitrary adjacent
  executables or nested directories. Future packaging layouts/backends require explicit allowlist qualification.
- Bundle hashing adds bounded startup I/O proportional to execution-library size. This is developer-only today and
  must be measured before any product lifecycle decision; weakening identity is not an acceptable optimization.
- The test model remains scientifically unqualified. Operational parser success is not scientific evidence.

## Verification evidence

- Unit coverage includes zero/tiny/multi-megabyte digest semantics, a 512 KiB-stack regression, deterministic/root-
  independent manifests, same launcher plus changed DLL, traversal/nested/symlink escape, explicit 0/8/25 argv,
  exact/mismatched requested-observed state, descriptor privacy, auth/loopback, crash invalidation, and cleanup.
- A normal-default-stack Windows standalone owner hashed the real CPU/CUDA bundles without reproducing the old crash.
- Real Windows CPU/CUDA package evidence proves identical launcher hashes and distinct bundle manifest hashes.
- Machines A and B (Windows) and Juno (Debian) explicit CPU/8/25 smoke tests passed with exact observed matches,
  production Overview prompt/parser success, bounded Windows Job Object / Unix process-group shutdown, and zero
  orphans. The same model digest and llama.cpp upstream commit were used on all three machines.

## Result

**Security Audit: PASS.** The managed target now fails closed on unverified or mismatched execution and runtime
identity covers the backend-bearing bundle. The full repository/static gates and live three-machine smoke matrix are
green. No user-facing or production-qualified Automatic AI capability is introduced.

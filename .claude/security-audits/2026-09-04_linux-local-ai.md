# Security Audit: Local AI on Debian/Ubuntu (x86_64)

Date: 2026-09-04
Increment: 572 (backlog #76)
Auditor: Claude Code session

## Scope

Extends the existing pinned Local AI acquisition path to `linux-x86_64`. This is a
**download-and-execute path reaching a new platform**, which triggers audit gate #3 (new
file-ingestion/file-write path) and gate #2 (a new external fetch target).

Files:

- `app/desktop-shell/src-tauri/src/managed_local_ai/install.rs` — a Linux constants arm; the
  supported-platform `cfg` predicate widened from `any(windows, macos)` to also cover
  `all(linux, x86_64)`.
- `app/desktop-shell/src-tauri/src/managed_local_ai/install_macos.rs` → `install_unix.rs` —
  the same extractor now serves both `.tar.gz` platforms, with a **per-platform** library
  allowlist rather than one widened predicate.
- `app/desktop-shell/src-tauri/src/managed_local_ai/preview.rs` — the `supported` predicate.
- `.github/workflows/desktop-shell-linux.yml` — a new blocking glibc guard on the pinned runtime.

No Python, frontend, API, or database code is touched. No new endpoint, setting, or user input
exists. There is no new *kind* of operation here — only an existing, already-audited one
(`2026-08-30_local-ai-preview.md`, `2026-09-02_macos-local-ai-identity-diagnostics.md`) becoming
reachable on a third platform.

## What is pinned

Measured directly from the upstream asset, not copied from documentation:

| Field | Value |
|---|---|
| archive | `llama-b10516-bin-ubuntu-x64.tar.gz` |
| bytes | 16,667,775 |
| archive sha256 | `f263a91280471b4c33c4999d7c76259c0f3a0a53a0b3e692b2c0b84380137a35` |
| launcher sha256 | `fa24fc90877d1edc68990af5f4f8e476256959357d7f58cf59910e5657f7403f` |
| bundle manifest sha256 | `c5321ce333105b171acc20aae62075011595c7e939023dec2af3aae3a7df1545` |

**The build is `b10516` — the exact build already pinned for Windows and macOS.** No version
drift, no new upstream publisher, no new trust decision: the same release, same `ggml-org`
project, one additional asset from it. The GGUF model artifact is platform-independent and
entirely unchanged.

The bundle manifest digest was **not** computed by hand-waving over the archive. The manifest
algorithm in `files.rs::digest_manifest_entries` was first reproduced independently and
**validated against the already-pinned Windows value** using the runtime installed on the
maintainer's machine — it reproduced `7748201a…` exactly — before being applied to Linux. A
digest guessed wrong here would reject every genuine install, so it was verified rather than
asserted.

## Invariants preserved

- **Egress.** No new egress *class*. The runtime download reaches `github.com` — the same host
  the Windows/macOS runtime and the inc-570 Python runtime already fetch from — and only on an
  explicit user action in Settings. No library text, telemetry, prompt, or identifier is sent;
  the request is a plain unauthenticated asset GET. Invariant #3 is untouched: once installed,
  Local AI is a **loopback** provider requiring no consent gate and producing no egress.
- **Verify-before-execute.** Unchanged and platform-agnostic: exact byte length → sha256 of the
  archive → allowlisted extraction → `runtime_bundle_identity` over the installed tree → launcher
  digest and manifest digest both compared to pinned constants, before the launcher is ever run.
  A mismatch fails closed with no fallback.
- **No arbitrary input.** There remains no URL, path, model, or version the user can supply.
  Every value is a compile-time constant.
- **`requested == observed`.** `observation.rs` is untouched. The CPU-only `ubuntu-x64` variant
  was chosen deliberately over `vulkan-x64`/SYCL precisely so no new backend-qualification claim
  is made; a GPU variant would require honest verification of a non-CPU backend and is out of scope.
- **Status/progress (invariant #5).** The shared install progress state is reused unchanged.

## Extraction safety

The extractor is the **same code path** already audited for macOS, not a reimplementation. It
retains, for Linux unchanged:

- a pinned archive root (`llama-b10516`), rejecting any entry outside it;
- `Component::Normal` matching, so `..`, absolute paths, and nested paths are rejected —
  confirmed against the real archive, which is flat (max depth 2, single root);
- symlink targets restricted to a **single safe name** that must itself pass the allowlist,
  then a post-extraction `canonicalize` containment check that every entry resolves to a
  regular file inside the staging root;
- `create_new(true)` on every file (no clobber), `0o700` staging, `0o600` files, `0o700` launcher;
- staging → atomic rename promotion, so a partial extraction is never activated;
- any entry that is neither a regular file nor a symlink is a hard error. Verified against the
  real archive: it contains only 1 directory, 52 files, and 10 symlinks — **no hardlinks or
  device entries**, so the reject branch is not silently load-bearing.

### The one substantive Linux-specific change

`runtime_entry_allowed` is now per-platform rather than shared:

```rust
#[cfg(target_os = "macos")]  => name == LAUNCHER || ends_with(".dylib")
#[cfg(target_os = "linux")]  => name == LAUNCHER || (prefix in {libggml,libllama,libmtmd} && contains(".so"))
```

Sharing one widened predicate would have let a macOS bundle carry `.so` files and vice versa, so
each platform keeps its exact allowlist. The Linux form deliberately uses `contains(".so")`, not
`ends_with(".so")`, because Linux shared objects are versioned (`libllama.so.0.1.2`); a suffix
test would have dropped every real library and kept only the symlinks pointing at them.

**This predicate must agree with `files.rs::is_runtime_library`**, which decides what the bundle
manifest hashes — if extraction and hashing disagree, a correct install fails its own identity
check. Agreement was verified mechanically across all 63 archive entries: **zero disagreements**.
Note that `is_runtime_library` already contained an unreached `.so` clause; it is now reached, and
was not modified.

The allowlist drops ~20 unwanted upstream CLI binaries (`llama-cli`, `llama-tts`,
`ggml-rpc-server`, …), keeping the installed footprint to 39 entries / ~37 MB.

## The glibc failure mode (backlog #71's lesson, one layer out)

The genuinely new risk was not extraction but **loadability**: a runtime that installs cleanly and
then cannot start. That is exactly how #71 shipped a `.deb` that installed and never opened.

Measured before any code was written, and re-measured across every installed binary:

```
highest required: GLIBC_2.34  (libggml-cpu-cooperlake.so)
support floor   : GLIBC_2.35  (Ubuntu 22.04; Debian 12 = 2.36)
```

All 29 scanned binaries max at 2.34 — comfortably under the floor.

Because a future upstream re-pin could silently raise this, `desktop-shell-linux.yml` gains a
**blocking** guard that downloads the pinned archive, re-verifies its sha256 and byte length, and
`objdump`s every binary the extractor would keep. The guard **reads the pins out of `install.rs`
itself** rather than restating them in YAML, so it cannot drift into checking a build the app no
longer downloads. Its parsing was verified against the real file (all three pins extracted
correctly) — a guard that silently extracts an empty string would pass vacuously.

## Negative paths

| Case | Result |
|---|---|
| archive bytes ≠ pinned | fails before hashing |
| archive sha256 ≠ pinned | fails before extraction |
| entry outside pinned root / `..` / nested | `archive root invalid` / `path invalid` |
| symlink target outside allowlist or multi-component | `link target invalid` |
| symlink resolving outside staging root | `link escapes its root` |
| entry type other than file/symlink | `archive entry invalid` |
| launcher absent from archive | `launcher missing` |
| launcher or manifest digest ≠ pinned | `runtime identity mismatch`, launcher never executed |
| Linux arm64 / 32-bit | `unsupported`, unchanged — no runtime is pinned and none is offered |

## Residual risk

- **Supply chain.** Trust is anchored in pinned digests of a specific upstream release, not in
  TLS or in GitHub's continued good behavior. A compromised-but-identical-digest artifact is not
  possible; a compromised *upstream release* would have been compromised for Windows and macOS
  already. This is the same posture accepted in `2026-08-30_local-ai-preview.md`.
- **The extracted tree omits upstream's `LICENSE`**, matching existing macOS behavior. Callosum
  does not redistribute the archive — the user's machine fetches it directly from the publisher —
  and `write_receipt` already records `runtime_source`/`runtime_license` (`ggml-org/llama.cpp
  release b10516`, MIT) and `model_source`/`model_license` (`Qwen/Qwen2.5-1.5B-Instruct-GGUF`,
  Apache-2.0) into `install.json` on every install, platform-generically. So per-install
  provenance exists and Linux inherits it unchanged.
  **Pre-existing gap, not introduced here:** neither llama.cpp/ggml nor Qwen appears in the
  repo-level `THIRD-PARTY-NOTICES.md`, and has not since inc 547 shipped Local AI on Windows.
  That applies equally to all three platforms, so it is filed as a follow-up rather than folded
  into this increment (rule #7).
- **Not yet live-verified at the time of writing.** Windows compile/clippy/tests are green and
  the archive-level facts are measured, but the Linux build is compiled only by CI and the
  end-to-end install is proven only by a real run on Debian 12. This audit is **provisional until
  that run is recorded below.**

## Live verification (Debian 12, juno)

Recorded after the run — see the increment notes for the transcript.

## Verdict

**Security Audit: PASS**, conditional on the live Debian run being recorded above. The change
adds no new operation class, no new user input, no new egress class, and no new trust anchor; it
extends an already-audited, digest-pinned acquisition path to a third platform, with the one
platform-specific hazard (glibc) measured up front and pinned by a blocking CI guard.

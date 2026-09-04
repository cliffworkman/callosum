# Increment 572 Notes — Local AI on Debian/Ubuntu (#76)

## What changed

Local AI was Windows + macOS only. `install.rs::installed_paths` returned `Ok(None)` under
`#[cfg(not(any(windows, target_os = "macos")))]`, so a Linux user's Settings card fell through to
`LOCAL_AI_UNSUPPORTED_ARCHITECTURE` — meaning **no AI feature at all without a cloud key**, against
the entire point of Local AI (inc 547): no account, no key.

Linux x86_64 now installs and runs the same pinned runtime as the other two platforms.

## The work was mostly deletion of a `cfg`, because the pieces already existed

Almost nothing here is new machinery. What made this tractable:

- Upstream publishes `llama-b10516-bin-ubuntu-x64.tar.gz` at **the exact build already pinned** for
  Windows and macOS. No re-pinning, no version drift, no new publisher to trust.
- `install_macos.rs` was already a general `.tar.gz` extractor — same pinned root, same allowlist,
  same containment checks. It is now `install_unix.rs` and serves both platforms.
- `process.rs`'s Unix lifecycle (`process_group(0)`, `SIGTERM` to the negative pgid) was written for
  macOS under `#[cfg(unix)]`, so Linux inherits teardown, crash monitoring and descriptor cleanup.
- `files.rs::is_runtime_library` **already had a `.so` clause** with no consumer. It is now reached,
  and was not modified.
- The GGUF model is platform-independent and already pinned.
- **No frontend change at all.** `preview.rs`'s `supported` predicate is the single switch; flipping
  it moves Linux from `unsupported` to `not_installed`, and every existing Settings state applies.

The widening is one predicate, `any(windows, macos)` → `any(windows, macos, all(linux, x86_64))`,
applied to all 12 sites. Because the same inner text appears in both the positive and the
`not(...)` forms, one replace covers both — the "unsupported" arm narrows exactly as the supported
arm widens, so the two can't drift apart.

## The two things that would have silently broken it

**1. `ends_with(".so")` would have installed nothing usable.** Linux shared objects are versioned —
`libllama.so.0.1.2` — reached through two-level symlink chains
(`libggml-base.so` → `.so.0` → `.so.0.20.2`). A suffix test keeps the 10 symlinks and drops all 29
real libraries they point at. The Linux allowlist therefore mirrors `is_runtime_library` exactly:
prefix in `{libggml, libllama, libmtmd}` **and** `contains(".so")`.

That agreement is load-bearing, not stylistic: the extractor decides what lands on disk and
`is_runtime_library` decides what the bundle manifest hashes. If they disagree, a *correct* install
fails its own identity check. Verified mechanically across all 63 archive entries — zero
disagreements.

**2. The bundle digest had to be computed, not guessed.** `RUNTIME_BUNDLE_SHA256` pins a manifest
over the installed tree; a wrong value rejects every genuine install with no fallback. Two traps:
`runtime_bundle_identity` **canonicalizes**, so the 10 symlinks each appear in the manifest under
their own name with their *target's* size and digest — a first pass that skipped symlinks produced
a plausible, wrong digest. And the manifest format had to be byte-exact.

So the algorithm was reproduced independently and **validated against the already-pinned Windows
value** using the runtime installed on this machine — reproducing `7748201a…` exactly — before
being trusted for Linux. Verify, don't assume: the check cost one command and would have caught a
silent format error that CI could not.

Resulting pins, all measured from the real asset:

| | |
|---|---|
| archive bytes | 16,667,775 |
| archive sha256 | `f263a912…0137a35` |
| launcher sha256 | `fa24fc90…5f7403f` |
| bundle manifest | `c5321ce3…7df1545` |
| installed | 39 entries (29 files + 10 symlinks), ~37 MB |

The allowlist drops ~20 unwanted upstream binaries (`llama-cli`, `llama-tts`, `ggml-rpc-server`, …).

## The glibc guard — #71's lesson, one layer out

The real risk was never extraction; it was **a runtime that installs cleanly and then won't start**.
That is precisely how #71 shipped a `.deb` that installed and never opened. So it was checked first,
before any design:

```
highest required : GLIBC_2.34   (libggml-cpu-cooperlake.so, worst of 29 binaries)
support floor    : GLIBC_2.35   (Ubuntu 22.04; Debian 12 = 2.36)
```

It runs — the same floor our own shell binary lands on.

Because a future re-pin could silently raise that, `desktop-shell-linux.yml` gains a **blocking**
guard that downloads the pinned archive, re-verifies sha256 and byte length, and `objdump`s every
binary the extractor keeps. It **reads the pins out of `install.rs`** rather than restating them in
YAML — a second copy would drift the moment the runtime is re-pinned, and a guard checking a build
the app no longer downloads is worth nothing. The parsing was verified against the real file (all
three pins extracted correctly); a guard that silently extracts an empty string passes vacuously.

## Verification

- **Windows: clippy `-D warnings` clean, `cargo test` 48 passed / 0 failed / 6 ignored** — identical
  to the inc-571 baseline, so Windows is provably unchanged. This mattered: widening a `#[cfg]` can
  silently change what compiles elsewhere, which is exactly the inc-570 mistake (a cross-platform
  edit compiled only on Windows).
- Archive structure verified against the real asset: 1 dir / 52 files / 10 symlinks, single
  `llama-b10516` root, max depth 2 — **no hardlinks or device entries**, so the extractor's reject
  branch isn't silently load-bearing.
- Full `pytest` run recorded below. Zero Python or JSX changed — a Rust `#[cfg]` cannot affect it —
  but it was run rather than reasoned about.
- Security audit: `.claude/security-audits/2026-09-04_linux-local-ai.md`.

### Honest limits

- **macOS and Linux compile only in CI.** They cannot be built on this machine, so the Linux arm's
  *compilation* is proven by `desktop-shell-linux.yml`, not locally. Everything provable locally —
  the digests, the archive structure, the predicate agreement, the glibc headroom, Windows
  non-regression — was proven locally.
- **The end-to-end install is proven only by a live run on Debian 12 (juno).** Until that is
  recorded, the audit is explicitly provisional. Unit tests cannot prove a download-verify-execute
  path.

## Follow-up found, not fixed

Neither llama.cpp/ggml nor Qwen appears in the repo-level `THIRD-PARTY-NOTICES.md`, and hasn't since
inc 547. Per-install provenance *is* recorded — `write_receipt` writes `runtime_source`/
`runtime_license` (MIT) and `model_source`/`model_license` (Apache-2.0) into `install.json`,
platform-generically, so Linux inherits it — but the repo notices file has the gap. It applies
equally to all three platforms and predates this work, so it is filed rather than folded in (rule
#7). See `INCREMENT-BACKLOG.md`.

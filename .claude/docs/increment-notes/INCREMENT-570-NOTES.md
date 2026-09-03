# Increment 570 Notes — the Python runtime leaves the app package (and #71 closes)

## Why

Every desktop update re-shipped and reinstalled the entire bundled Python environment — torch, numpy,
sentence-transformers, ~1.2 GB unpacked — even when none of it had changed. Cliff's framing: that makes
updating "something you have to budget time around," which is a real adoption cost for a reference
manager people are supposed to keep current.

Cliff briefed Codex on the architecture; Codex ran out of credits mid-refactor, with the core module
sitting **untracked** in the working tree. This increment takes the handoff, proves it, fixes what was
broken, and closes backlog #71 along the way.

## What the architecture is

`python-runtime` is removed from Tauri's `bundle.resources`; only `callosum-src` still ships with the
app. A deterministic `runtime_id` (OS, arch, CPython build, dependency-lock hash, packaging schema —
plus a glibc floor on Linux) keys an immutable artifact built once by `desktop-python-runtime.yml`,
published as a `python-runtime-<id>` release and **reused across Callosum releases**. At first run the
shell resolves that id, downloads the artifact, verifies it, stages it, smoke-tests it, and atomically
activates it under the per-user local app-data directory. Ordinary app updates never touch it.

Credit where due: the design is Codex's and it is sound — signature checked before the manifest is even
parsed, `archive_url` pinned to a locally computed value, a canonical digest over the *extracted tree*,
and staging that leaves any previous known-good runtime intact.

## Three defects, none found by reading the code

**1. First-run provisioning could never have worked.** `verify_manifest_signature` handed the raw `.sig`
bytes to `minisign_verify::Signature::decode`, but `tauri signer sign` writes that document
**base64-encoded**. Every genuine manifest was rejected with `PYTHON_RUNTIME_SIGNATURE_INVALID`.

This mattered far more than an ordinary bug: with the interpreter no longer in the package, a fresh
install would have had *no Python at all*. The module had eight unit tests, but every one built its own
fixtures — so nothing exercised the one property that cannot be assumed, **that the verifier accepts what
the signer emits**. Caught only by fetching the real published manifest and running it through the real
verification path.

**2. macOS and Linux upgraders were forced into the full download.** `try_migrate_legacy` was
`#[cfg(windows)]`-only, although its logic is entirely platform-agnostic and the old bundled runtime sits
on disk for those users exactly as it does on Windows. Gating it to Windows denied everyone else the
saving this whole increment exists to deliver. Now cross-platform; it requires an exact tree-digest match
and otherwise falls through to a verified download, so being wrong costs bandwidth, never correctness.

**3. The CI failure that looked like the fix's fault.** After moving the Linux shell build to the glibc
floor, it failed with `can't find crate for tauri` — which reads as "Ubuntu 22.04 can't build Tauri."
It is not: jammy installed `libwebkit2gtk-4.1-dev 2.50.4-0ubuntu0.22.04.1` cleanly. The cause was
`rust-cache` restoring artifacts compiled on 24.04, because its default key is only `Linux-x64`.

The first fix — `key: ${{ env.ImageOS }}` — **silently did nothing**, for two compounding reasons worth
recording: `env.*` in a `with:` expression resolves only workflow-declared `env:` maps, never
runner-provided variables; and a differing *suffix* cannot prevent a match anyway, because restore-keys
match by **prefix**. Fixed with `prefix-key: v1-rust-jammy`, which leads both the key and the
restore-keys.

## Backlog #71 — the Debian `.deb` installs but never opens

Diagnosed on the real Debian 12 box, not by inspection:

```
/usr/bin/callosum-shell: /lib/x86_64-linux-gnu/libc.so.6:
    version `GLIBC_2.39' not found (required by /usr/bin/callosum-shell)
```

Debian 12 ships glibc **2.36**; the binary demanded **2.39** — so the loader refused it outright, which
is why the box had no app-data directory at all. Exactly two weak symbols force it, `pidfd_spawnp` and
`pidfd_getpid`, from Rust std's process spawning. Environmental, not code: `runs-on: ubuntu-latest` is
now Ubuntu 24.04.

All three suspects the backlog had listed are **disproven** on the real box, recorded so nobody re-runs
them: the bundled interpreter works (`Python 3.11.15`, exec bit intact), the whole Python/ML stack
imports cleanly, resources resolve to `/usr/lib/Callosum` correctly, and `ldd` reports exactly one
missing entry — libc.

Fixes: the shell now builds on `ubuntu-22.04` (glibc 2.35), matching the floor Codex had already set for
the runtime artifact, so both halves of the Linux lane target Ubuntu 22.04+/Debian 12+. A blocking
`objdump` guard fails the build if the binary ever requires a newer glibc than the floor — one cheap
command that catches the entire class without needing a Debian box, which is precisely what was missing
when this shipped broken.

**A second, independent startup bug** surfaced while diagnosing: `resolved_paths` aborted when
`document_dir()` could not be resolved, which on Linux happens with no `XDG_DOCUMENTS_DIR` and no
`~/.config/user-dirs.dirs` — a bare Xvfb runner or a minimal Debian. It returned before spawning
anything, hanging the splash on "Starting…" forever, indistinguishable from the glibc break and almost
certainly what CI had been hitting on 24.04. `library_dir` is only the *default* location offered for a
user's library, so it now falls back rather than failing closed.

## Verification

- **Full first-run provisioning, against the real published artifact: 547 s on Windows.** Download
  365 MB → signature → archive sha256 → extract 41,338 entries → tree digest → smoke test → atomic
  activate. A second call correctly **reused** the runtime instead of re-downloading, which is the
  property the whole architecture exists to deliver. Kept as an opt-in test
  (`provisions_the_published_runtime_end_to_end`).
- Making that testable required decoupling progress from Tauri (`ProgressSink`, `provision_into`);
  `provision_runtime`'s behaviour is unchanged.
- `cargo test` 48 passed / 0 failed / 6 ignored; `clippy -D warnings` clean; `fmt` clean.
- `tests/test_desktop_packaging.py` 13 passed / 1 skipped.
- Security audit `2026-09-03_persistent-python-runtime.md` — **PASS**, and not a rubber stamp: it closed
  two real coverage gaps (`validate_link_target` had *no* test despite being the only control in front of
  symlink writes outside the extraction root; manifest validation never checked a substituted
  `archive_url`, including an attacker-chosen path on an allowlisted host).

## Honest limits

- **Provisioning is verified on Windows only.** macOS and Linux are covered by unit tests and CI's
  installed-app runs, but the full download-and-activate has not been run by hand there.
- The `ubuntu-22.04` runner label is being retired by GitHub. Both Linux lanes depend on it and it works
  today; a pinned container is the durable form. Filed rather than scrambled at.
- `python_runtime.rs` is 1187 lines. Rule #1's 600-line cap is written for everything under `app/`, but
  `check_line_budget.py` only enforces `.py`/`.jsx` and `backend.rs` has sat at 602 for some time — so
  Rust has never in practice been held to it. Raised as a policy question for Cliff rather than
  unilaterally splitting a module I did not write.

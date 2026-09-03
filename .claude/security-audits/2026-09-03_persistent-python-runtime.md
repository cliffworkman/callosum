# Security Audit: independently distributed Python runtime

Date: 2026-09-03
Scope: `app/desktop-shell/src-tauri/src/python_runtime.rs`, `.github/workflows/desktop-python-runtime.yml`,
`app/desktop-shell/packaging/package_python_runtime.py`, `python-runtime-inputs.json`

## What changed and why it needs an audit

The portable CPython environment (~1.2 GB unpacked: torch, numpy, sentence-transformers) has been
**removed from `bundle.resources`** and is now fetched at first run from GitHub Releases, verified, and
executed. Previously every desktop update re-shipped that unchanged environment, making updates
something users had to budget time around.

Triggers gate **#3** (new file-ingestion/write path) and gate **#6** (new direct dependency: `base64`,
already present transitively; promoted to direct). This is the highest-consequence surface in the
desktop shell: the artifact it downloads *is* the interpreter that then runs Callosum's backend.

## Trust chain

Layered, and each layer is checked before the next is used:

1. **Signature first.** `runtime-manifest.json` is signed in CI by `npx tauri signer sign` using the
   **existing** `TAURI_SIGNING_PRIVATE_KEY` — the same key that signs updater artifacts, so no new key
   material or trust root is introduced. `verify_manifest_signature` checks it with `minisign_verify`
   against `PUBLIC_KEY` compiled into the binary, **before** the manifest is parsed and long before the
   archive is fetched.
   *Verified*: `PUBLIC_KEY` base64-decodes byte-identical to `tauri.conf.json`'s `plugins.updater.pubkey`.
2. **Manifest bound to this build.** `validate_manifest` requires `runtime_id`, `platform`, `arch`,
   `python_version`, `python_build`, `python_relative_path`, `glibc_min` and `distribution_boundary` to
   equal the values compiled in from `python-runtime-inputs.json`, so a validly signed manifest for a
   *different* platform or runtime cannot be substituted.
3. **Download location is pinned, not trusted.** `archive_url` must equal
   `{RELEASE_BASE}/{tag}/{runtime_id}.tar.gz`, computed locally. A signed manifest therefore cannot
   redirect provisioning anywhere — including to another path on an allowlisted host.
4. **Archive identity.** Exact `Content-Length` match against `archive_bytes`, streamed SHA-256 compared
   to `archive_sha256`, with the running total checked against the cap on every chunk.
5. **Extracted-tree identity.** `tree_digest` over canonical, sorted, domain-separated lines
   (`kind\trelative\tsize\tidentity\texecutable`) compared to `tree_sha256`. This is what makes the
   *result* of extraction verifiable, not merely the bytes that arrived.
6. **Smoke test before activation** — the interpreter must actually run, then the receipt is written and
   staging is atomically renamed into place.

## Archive extraction

The historically dangerous part. `extract_verified` is sound, and structurally so rather than by
pattern-matching bad input:

- `archive_relative_path` requires the first component to be exactly `Component::Normal("python-runtime")`
  and **every** remaining component to be `Component::Normal`. `..`, absolute paths, drive prefixes and
  root components are rejected by construction — the same shape as the already-audited
  `install_macos.rs` (`2026-09-02_macos-local-ai-identity-diagnostics.md`).
- `validate_link_target` rejects empty, backslash-bearing and absolute targets, then walks components
  tracking depth and rejects any `..` that would escape the runtime root.
- Symlinks are **rejected outright on Windows**, and on Unix are created only *after* every regular file
  is written — so a symlink cannot be pre-placed and then used as a write target mid-extraction.
- `create_new(true)` on every file: extraction refuses to overwrite anything that already exists.
- Duplicate archive paths are rejected (`paths.insert`).
- Only directory, symlink and regular-file entry types are accepted; anything else fails closed.
- Caps enforced against **both** the signed manifest and independent absolute maxima
  (`MAX_ENTRIES` 150k, `MAX_UNPACKED_BYTES` 8 GiB, `MAX_ARCHIVE_BYTES` 3 GiB), with `checked_add` on the
  running byte total. A hostile manifest cannot raise a limit; a hostile archive cannot exceed one.

## Network

- Host allowlist: `github.com`, `release-assets.githubusercontent.com`, `objects.githubusercontent.com`,
  checked against the **final** URL after redirects, which are capped at 8. `.no_proxy()` is set.
- Manifest and signature reads are size-bounded (2 MiB / 64 KiB) by both `Content-Length` and a
  `take(maximum + 1)` guard, so a lying or absent header cannot cause an unbounded read.
- No credentials are attached to any request, so a redirect through an unexpected host leaks nothing.

## Where it writes

Only under the per-user local app-data directory (`app_local_data_dir()/python-runtimes/<runtime_id>`).
Nothing writes to the root-owned install tree — which is what makes this work under a `.deb` install,
where `/usr/lib/Callosum` is not user-writable. A failed download, hash mismatch, failed smoke test or
failed activation leaves any previously installed runtime untouched: staging is a separate directory and
is removed on any error before activation is attempted.

## Findings and fixes

**One critical defect, found and fixed during this work.** `verify_manifest_signature` passed the raw
`.sig` bytes to `Signature::decode`, but `tauri signer sign` writes the minisign document
**base64-encoded**. Every genuine manifest was therefore rejected with
`PYTHON_RUNTIME_SIGNATURE_INVALID`. Because the interpreter no longer ships in the package, this was not
a degraded mode — a fresh install would have had no Python at all. Fixed in `34f1900`; `decode_signature`
now accepts both encodings and still fails closed on anything else.

This was not caught by inspection. The module had eight unit tests, but every one constructed its own
fixtures, so nothing exercised the one property that cannot be assumed: **that the verifier accepts what
the signer emits.** The new
`published_manifest_signature_verifies_against_the_builtin_key` fetches the real published manifest and
signature and runs the real verification path; it fails on the pre-fix code with exactly that error code.

**Two coverage gaps closed in this audit:**

- `validate_link_target` — the only control standing in front of symlink-based writes outside the
  extraction root — had **no test at all**. Added `symlink_targets_may_not_escape_the_runtime_root`,
  covering `../../../../etc/passwd`, absolute targets, a bare `..` at depth 0, and backslash targets,
  while confirming legitimate in-tree links (`bin/python3 -> python3.11`, as python-build-standalone
  actually ships) still pass.
- `manifest_validation_is_exact_and_bounded` checked a wrong `runtime_id` but not a substituted
  `archive_url`. Extended to reject both an off-host URL and — the more interesting case — an
  attacker-chosen path on an *allowlisted* host, which a host check alone would let through.

## Negative paths exercised

| Check | Result |
|---|---|
| Real published signature vs. real verification path | Rejected pre-fix (`PYTHON_RUNTIME_SIGNATURE_INVALID`); accepted post-fix |
| Tampered signature | Rejected (`updater_public_key_is_valid_but_bad_signature_is_rejected`) |
| Traversal / wrong archive root | Rejected (`archive_paths_reject_traversal_and_wrong_root`) |
| Symlink escaping the root (4 shapes) | Rejected; legitimate in-tree links still accepted |
| `archive_url` substituted, off-host and same-host | Both rejected |
| Wrong `runtime_id`, out-of-bounds sizes/counts | Rejected |
| Incomplete/foreign receipt | Rejected (`receipt_requires_matching_identity_and_interpreter`) |
| Activation over an invalid target | Replaces only invalid targets, atomically |
| **Full first-run provisioning against the real artifact** | **Passed** — 547 s on Windows; second run reused the runtime rather than re-downloading |

`cargo test`: 48 passed, 0 failed, 6 ignored. `clippy -D warnings` clean.

## Residual risks (accepted, disclosed)

1. **Compromise of the signing key would allow a malicious runtime.** This is inherent to the design and
   is the same trust root the existing updater already relies on, so it widens the *consequence* of that
   key's compromise (arbitrary code, not just an app update) without adding a new trust root. Keeping the
   key in GitHub Actions secrets and never in the repository remains the control.
2. **Only the final redirect host is allowlisted.** An intermediate hop could be an arbitrary host. No
   credentials are sent and the archive is hash-pinned, so the exposure is metadata only.
3. **Provisioning is verified on Windows only.** The macOS and Linux paths are exercised by unit tests
   and by CI's installed-app runs, but the full download-and-activate has not been run by hand on those
   platforms. Stated rather than implied.
4. **`try_migrate_legacy` now runs on all platforms.** It requires an exact tree-digest match against the
   signed manifest before reusing an on-disk runtime, and falls through to a normal verified download
   otherwise, so a mismatch costs bandwidth rather than correctness.

**Security Audit: PASS.**

Verified against the code and by live execution. The critical signature defect and both coverage gaps
were found by running the real artifacts through the real code, not by reading it.

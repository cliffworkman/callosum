# Increment 546 — EndNote Linux ABI/package matrix

**Date:** 2026-08-30
**Scope:** developer-only EndNote runtime compatibility research. No production runtime, importer, installer,
dependency, route, setting, UI, or user-visible behavior changed.

## Result

The exact stripped MariaDB 10.11.19 candidate from increment 545 passed a clean seven-release amd64/glibc matrix:

- Ubuntu 20.04, 22.04, 24.04, and 26.04;
- Debian 11, 12, and 13; and
- both root and uid/gid 1000 execution.

Every run resolved its dynamic libraries, returned the public X7 fixture's 59 rows/54 columns, preserved the source
digest, and left no process. The unprivileged runs took 157–187 ms. The normal Juno/Python 3.11 developer probe
also reproduced the canonical 28-file manifest and returned 59/54 in 259 ms.

## Policy

The initial support promise is deliberately narrower than technical compatibility: Ubuntu 22.04/24.04/26.04 LTS
and Debian 12/13, amd64 only, bounded by the overall Callosum `.deb` envelope. Ubuntu 20.04 and Debian 11 are
boundary evidence, not supported targets.

The optional component must declare `libc6`, `libcrypt1`, `libgcc-s1`, `libstdc++6`, and `libsystemd0` and must
not vendor those system libraries. Actual release packaging must derive version bounds on its pinned build baseline
and install-test the final `.deb`; the EndNote component cannot broaden Callosum's overall Linux support claim.

## Security/lifecycle receipt

- runtime and fixture mounted read-only;
- fresh private temp root per run;
- 1 GiB, 2 CPU, and 128 PID caps;
- container network absent plus explicit `--skip-networking`;
- unprivileged user pass on all releases;
- source hash unchanged;
- no orphan on any pass; and
- all temporary archives, binaries, fixture copies, scripts, receipts, and research images removed from Juno.

The isolated container's MAC-address warning contained no scholarly content and was non-fatal. A private explicit
temp directory was required by the read-only container root; the existing developer harness already owns a writable
temporary root and therefore needed no code change.

## Boundary

This closes only the runtime-specific Linux ABI/package-policy research gate. Legal approval, release-source/
signature machinery, macOS, real attached-PDF and modern-SQLite fixtures, and production import/UI work remain.

Full evidence: `.claude/docs/research/2026-08-30_endnote_linux_abi_matrix.md`.

## Revert

Documentation-only. Revert this increment commit.

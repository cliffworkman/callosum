# Increment 544 — standalone Linux EndNote runtime proof

**Date:** 2026-08-30
**Scope:** backlog #57 Phase 6B developer evidence and runtime-manifest hardening only. No production import,
runtime bundle, dependency, route, setting, UI, migration, paper write, PDF ingest, or user-visible behavior changed.

## Goal

Close Increment 542's known Linux evidence gap without turning Docker into a product dependency: derive a narrow
runtime bundle from the already-pinned official MariaDB image, execute that bundle directly on Juno's Debian host,
and make the developer receipt identify every bundled file used by the bootstrap path rather than the launcher alone.

## Runtime boundary

The temporary research bundle was extracted from official image
`mariadb@sha256:ce66c7be32a03aabe7241d0a10993a2db827ef652a35d25727d92a832ac8ef73`.
It contains only:

- `sbin/mariadbd`;
- `share/english/errmsg.sys`; and
- the 26 files in `share/charsets`.

The resulting 28-file bundle is 25,758,167 bytes. Its launcher SHA-256 is
`b5f84a207c71e6243871a171f169b43597ed20470a6bed50787121ead367bdc2`; the canonical relative-path/size/SHA-256
manifest digest is `4e2c4577f201298bec7dff5e63cdd641e24fd4f38925224d9c0a44e33068d7dc`.
An independent extraction at a different absolute root produced the same digest.

The launcher is the Ubuntu 22.04.5 / glibc 2.35 build reporting
`Ver 10.11.19-MariaDB-ubu2204 for debian-linux-gnu on x86_64`. On Debian 12 / glibc 2.36, all 18 named dynamic
library dependencies resolved from the OS. Those system libraries are a declared host ABI dependency, not hidden
inside the bundle or falsely included in its identity. This is direct-host compatibility evidence for one Debian
host, not a claim of compatibility with every Linux distribution.

## Implementation

`tools/endnote/legacy_bootstrap.py` now uses `linux-bootstrap-files-v1` instead of the incomplete
`launcher-only-development-v1` scope. Both Windows and Linux manifests require and hash the bounded
`share/english` and `share/charsets` trees; Windows continues to require and hash adjacent `server.dll` as well.
The existing link/junction, root-escape, file-count, byte-count, canonical-ordering, and streaming-hash controls
apply unchanged.

Two focused regressions prove that Linux identity is relocation-stable, changes when message data changes, contains
no absolute root, and fails closed when required share data is missing.

## Live Juno acceptance

Only EndNote's public `Sample_Library_X7.enlx` was transferred. Its SHA-256 remained
`ad53d894baf15045a7504107e576c9591ff01fca76176a9d32e4c50a3043ab98`; no personal fixture was used.

- Execution was direct on the Debian host, outside Docker.
- The developer probe returned 59 `refs` rows / 54 columns in 259 ms.
- The receipt reported `linux-bootstrap-files-v1`, 28 manifest entries, and the digest above.
- Networking remained explicitly disabled, the source hash was unchanged, and the receipt contained no source or
  runtime path and no bibliographic content.
- Process inspection after completion found zero matching `mariadbd` children.

Juno's system Python cannot collect the repository test suite because its global environment lacks the project's
Alembic dependency. That is not an executor failure: the dependency-free live CLI acceptance succeeded, while the
32-test focused suite ran in Callosum's local project environment.

## Verification

- Focused executor suite: **32 passed**.
- Fresh collection: **2,657 tests**.
- Fresh full parallel suite: **2,657 passed, 3 skipped** in 17:14.
- Ruff format/check for the touched Python files: clean.
- Bandit, Tach, line-budget, targeted pre-commit, secret/private-path scan, and `git diff --check`: clean.
- Live direct-host Juno acceptance: receipt above; independent relocation digest matched; no orphan.
- CI receipt follows after push.

## Remaining gates

- production Linux packaging still needs an explicit supported-distro/ABI policy and dependency declaration;
- reproducible macOS arm64/x86_64 build, signing, notarization, and lifecycle proof;
- GPL-2.0 server aggregate/corresponding-source/notices review beside Callosum AGPL-3.0;
- real attached-PDF and modern SQLite-era `.enlx` fixtures; and
- full legacy/modern schema mapping, atomic deduplication/PDF/group import, route/job/UI, and audit closure.

No runtime binary or model/library content is committed. Existing RIS/XML fallbacks remain unchanged.

## Revert

Revert this increment. The backend does not import the developer tool, and no migration or active behavior depends
on it.

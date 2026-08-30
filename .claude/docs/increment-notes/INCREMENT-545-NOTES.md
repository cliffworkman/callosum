# Increment 545 — EndNote MariaDB distribution review

**Date:** 2026-08-30
**Scope:** backlog #57 Phase 6B license/provenance research only. No runtime, downloader, importer, route, setting,
UI, dependency, or user-visible behavior changed.

## Goal

Resolve the engineering part of the MariaDB GPL-2.0 / Callosum AGPL-3.0 distribution gate and state precisely
what still requires human legal approval before an optional EndNote runtime can ship.

## Result

MariaDB Server 10.11.19 is GPL-2.0-only; Callosum is AGPL-3.0-or-later. They cannot be merged or linked into one
program under those licenses. The existing process seam—separate executable/address space, direct argv, fixed stdin,
bounded files, no client library or copied code—has the technical characteristics normally associated with separate
programs in an aggregate. Because MariaDB is required for one optional feature, that legal classification still
needs qualified human approval. This increment does not grant it.

The approved engineering direction is therefore conditional:

- keep MariaDB optional, separately installed, separately identified, and separately licensed;
- publish its exact source, notices, signatures, transformation recipe, and derived-asset signature beside the
  binary;
- impose no Callosum license/EULA terms on MariaDB; and
- block installer/updater/catalog integration until legal sign-off.

The complete analysis and forbidden-shortcut checklist are in
`.claude/docs/research/2026-08-30_endnote_mariadb_distribution_review.md`.

## Signed artifact verification

Official MariaDB 10.11.19 binary and source archives were downloaded into a restricted Juno temp root. Both API
SHA-256 values matched, and both GPG signatures verified against published fingerprint
`177F 4010 FE56 CA33 3630 0305 F165 6F24 C74C D1D8`.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| Linux systemd x86-64 binary tarball | 357,390,930 | `7efb257927f31f4422f496246b32590d0b7617f3d9dd900e575de761b302d919` |
| source tarball | 114,812,324 | `b8e543ee69d380fb1cfd563226f49e0fe96e4d67e7b7a9045ee514a168ed2066` |

The binary/source top-level `COPYING` and `THIRDPARTY` files were byte-identical. A pruned 31-file
runtime-plus-notices candidate ran directly on Debian and returned the public fixture's 59 rows/54 columns in
259 ms with no orphan.

## Size/provenance experiment

The official bintar launcher is unstripped (310,372,864 bytes). GNU binutils 2.40
`strip --strip-unneeded` produced byte-identical 31,468,440-byte outputs from two copies. The stripped candidate
again returned 59 rows/54 columns in 259 ms and left no process. Its 31-file distribution manifest is
`241049c9a9e0e9391de772c486244f4ca34c38c601cd22050834fdab22818b6a` (31,838,098 bytes total).

This is feasibility evidence only. Because stripping changes the upstream-signed binary, a future derived asset
requires a Callosum signature and a published input/toolchain/command/output receipt.

## Verification

- Official binary/source SHA-256: matched MariaDB release API.
- Official binary/source GPG signatures: good; fingerprint matched published MariaDB key.
- Original signed bintar candidate: 59 rows/54 columns, 259 ms, source unchanged, zero orphan.
- Two deterministic stripped copies: byte-identical; stripped candidate 59 rows/54 columns, 259 ms, zero orphan.
- Documentation/static/git checks follow at closure.

## Remaining gates

- qualified legal approval of the separate-program/aggregate conclusion;
- implementation and review of source mirroring, transformation receipts, notices, derived signing, update
  retention, and installer disclosure;
- tested Linux distro/ABI policy and reproducible macOS builds/signing/notarization;
- real attached-PDF and modern SQLite-era fixtures; and
- full schema mapping/import/UI/security-audit closure.

All downloaded archives, binaries, fixtures, receipts, and temporary keyrings are removed after this increment.

## Revert

Documentation-only. Revert this increment commit.

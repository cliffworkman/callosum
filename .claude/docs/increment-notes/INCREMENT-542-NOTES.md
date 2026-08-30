# Increment 542 — developer-only EndNote bootstrap executor

**Date:** 2026-08-30
**Scope:** backlog #57 Phase 6B proof tooling only. No production import, dependency, runtime bundle, route,
setting, UI, migration, paper write, PDF ingest, or user-visible behavior changed.

## Goal

Turn increment 541's one-shot MariaDB decision into an executable, adversarially tested developer contract
before any production importer or distribution work begins.

## Implementation

`tools/endnote/legacy_bootstrap.py` supports one exact profile, `endnote-x1-x7-myisam-v1`, and only a
developer-supplied runtime. It:

- rejects archive size/count/entry/expanded-size/compression-ratio violations, absolute/traversing/backslash
  names, duplicate/case-colliding names, encryption, unsupported compression, symlinks, and special files;
- streams SHA-256 and creates a digest-matching private archive copy before the engine sees any byte;
- manually copies only `db.opt` plus `refs`, `refs_ext`, `misc`, and `pdf_index` MyISAM triplets—never
  `extractall` and never PDFs or arbitrary archive members;
- manifests a bounded allowlist of launcher/server/message/charset files with relative names, size, and SHA-256;
- constructs static SQL for `ALTER TABLE rdb.refs FORCE`, row count, and hex-encoded column identity only;
- launches direct argv with `--no-defaults`, `--bootstrap`, `--skip-networking`, disabled binlog/InnoDB/external
  locking/symbolic links/local infile, an empty plugin directory, private datadir, and `--secure-file-priv`;
- feeds fixed bounded stdin from a temporary file, bounds stdout/stderr/engine log together, applies a wall-time
  limit, and kills the process tree on timeout or overrun; and
- accepts only bounded numeric/hex receipts and emits a frozen `DEVELOPER_TEST_ONLY` JSON receipt with hashes,
  counts, runtime version, elapsed time, and network-disabled state—not paths, credentials, or scholarly rows.

The child receives only an allowlist of basic OS/runtime environment variables. Provider and Mendeley secrets
are not forwarded.

## Live Windows acceptance

Only EndNote's public `Sample_Library_X7.enlx` was used; no personal fixture row was opened or printed.

- Official MariaDB `mariadb-10.11.19-winx64.zip`: 93,557,290 bytes.
- Verified SHA-256: `398ea30e5036010bbebe01d2b1804280424dcc2626e36d8e95155c04d25a0490`.
- Runtime: `Ver 10.11.19-MariaDB for Win64 on AMD64 (MariaDB Server)`.
- Launcher SHA-256: `a96d7b256e215ae8e0970249189d72abef44940b12fe2d0aa68cc2b6d3babcf0`.
- 29-entry allowlisted bundle manifest SHA-256:
  `5249e968191f8921c89496c5e700f28efc24ca5195ebf787a97594d9d5bf3b6e`.
- Public archive SHA-256: `ad53d894baf15045a7504107e576c9591ff01fca76176a9d32e4c50a3043ab98`;
  47 entries / 318,922 expanded bytes.
- Result: 59 rows / 54 columns, exit zero, 1,187 ms executor time, source unchanged, receipt path-free, no new
  `mariadbd` process after completion.

The first live attempt exited 2 and published no receipt. Its operational log showed that this official Windows
build does not compile/expose wsrep, making `--skip-wsrep` an unknown option. The flag was removed as redundant;
the build cannot activate a feature it does not contain, while the no-network/bootstrap and other hardening
flags remain explicit. The clean rerun above is the acceptance receipt. Download, expanded runtime, diagnostic
work, private archives, logs, and receipts were removed afterward.

## Linux status

Juno is Debian 12 with Docker but no standalone `mariadbd`. Increment 541 already proved the identical
one-shot fixed-stdin operation using the official `mariadb:10.11.19` image. Docker remains explicitly
research-only and is not an end-user dependency. This increment did not fabricate a standalone-Linux receipt;
portable Linux runtime/dependency identity remains a production packaging gate.

## Verification

- Focused executor suite: **30 passed**.
- Affected EndNote/Mendeley/Zotero/citation-import/collection-axis suite: **86 passed**.
- Fresh collection: **2,655 tests**.
- Clean full parallel suite after concurrent Increment 543 settled: **2,655 passed, 3 skipped** in 26:56.
- The first full run overlapped Increment 543's demo snapshot regeneration and reported three demo-only failures;
  after that parallel commit landed, its focused suite passed 26/26 and the clean full rerun above passed.
- Ruff format/check for the new Python files: clean.
- Fresh public-X7 Windows acceptance: receipt above; no orphan; exact acceptance temp root removed.
- Full affected/static/collection/remote receipts follow before increment closure.

## Remaining gates

- deterministic distributable Windows and standalone Linux runtime manifests;
- reproducible macOS arm64/x86_64 build, signing, notarization, and lifecycle proof;
- GPL-2.0 server aggregate/corresponding-source/notices review beside Callosum AGPL-3.0;
- real attached-PDF and modern SQLite-era `.enlx` fixtures;
- full legacy/modern schema mapping, atomic deduplication/PDF/group import, route/job/UI, and audit closure.

Existing RIS/XML fallbacks remain unchanged.

## Revert

Revert this increment. The backend does not import the developer tool, and no migration or active behavior
depends on it.

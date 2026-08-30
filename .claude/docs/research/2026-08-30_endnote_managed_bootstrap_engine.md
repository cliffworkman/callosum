# EndNote legacy MyISAM managed-engine design (increment 541)

**Date:** 2026-08-30
**Scope:** architecture, packaging, and security evidence only. No production importer, runtime bundle, route,
setting, migration, or user-facing behavior was added.

## Decision

Proceed to a **developer-only, bounded one-shot bootstrap executor**. Do not build or supervise a persistent
MariaDB service.

MariaDB's `mariadbd --bootstrap` mode can consume a fixed SQL program on standard input, operate on a private
copy of EndNote's MyISAM tables, emit a bounded export under `--secure-file-priv`, and exit. Combined with
`--skip-networking`, this removes the TCP, Unix-socket/named-pipe, database-account, readiness, and long-lived
daemon surfaces that made the original managed-service design disproportionate.

This is a conditional engineering **GO**, not approval to ship the engine. Production distribution remains
gated on:

1. a reviewed, reproducible per-platform runtime manifest and update policy;
2. macOS arm64/x86_64 build, signing, notarization, and live execution evidence (the current official 10.11.19
   download inventory supplies Windows, Linux, and source artifacts, but no macOS binary);
3. GPL-2.0 server aggregation/source-notice review alongside Callosum's AGPL-3.0 distribution;
4. a real `.enlx` fixture containing an attached PDF; and
5. a separate modern SQLite-era `.enlx` fixture.

Docker remains a research instrument, never an end-user dependency.

## Live evidence

Only EndNote's public X7 vendor sample was exercised. No personal library row was queried or transferred. The
source archive stayed read-only and retained SHA-256
`ad53d894baf15045a7504107e576c9591ff01fca76176a9d32e4c50a3043ab98`.

### Windows 11 x86-64

- Runtime: MariaDB Community Server `10.11.19-MariaDB`, source revision
  `93e051860a9c7e87ee8cee6ed38b640d491f7170`.
- Official portable archive: `mariadb-10.11.19-winx64.zip`, 93,557,290 bytes, SHA-256
  `398ea30e5036010bbebe01d2b1804280424dcc2626e36d8e95155c04d25a0490`; the digest exactly matched MariaDB
  Foundation's download receipt.
- Full expanded package: 611 files / 300,457,120 bytes.
- Experimental bootstrap-only manifest: 29 files / 20,240,927 bytes (`mariadbd.exe`, `server.dll`, English
  messages, and character-set data). This proves pruning is plausible; it is not yet a shipping manifest.
- A fresh private copy accepted `ALTER TABLE rdb.refs FORCE`, then exported only aggregate receipts: 59 rows
  and 54 columns. Exit code was zero, the original archive hash remained unchanged, and no `mariadbd` process
  remained.

### Debian 12 x86-64

- Runtime: the official `mariadb:10.11.19` image, digest
  `sha256:ce66c7be32a03aabe7241d0a10993a2db827ef652a35d25727d92a832ac8ef73`.
- The container's `mariadbd` was 25,495,992 bytes and dynamically depended on the expected libc/C++ plus
  compression, crypto, async-I/O, and system libraries; a portable Linux manifest must pin or declare those
  dependencies rather than assume the host happens to provide them.
- A non-root one-shot container with `--network none` and the same bootstrap contract upgraded the copied table,
  exported the 59-row count, and exited zero. The first attempt without Docker's `-i` supplied no SQL and is
  excluded; the fresh accepted run used stdin correctly.
- Uploaded fixture/work/output material and containers were removed. The image cache contains no scholarly
  content.

### macOS

Not tested. No performance, compatibility, signing, or lifecycle claim is made. MariaDB Foundation's current
10.11.19 download inventory exposed Windows x86-64, Linux x86-64, and source packages, but no macOS binary.
Homebrew is not a zero-configuration Callosum packaging strategy. A Callosum-owned macOS build would require a
reproducible upstream-source build for both Apple Silicon and Intel plus signing/notarization validation.

## Minimum execution contract

The future executor should accept only an app-generated immutable job description:

- source archive digest and detected exact schema profile;
- private copied datadir and private output directory;
- pinned runtime bundle identity;
- fixed wall-time, input, row, field, and output-byte caps; and
- a static SQL template selected by the recognized schema profile.

It must launch `mariadbd` directly—never through a shell—with an argument set equivalent to:

```text
--no-defaults
--bootstrap
--skip-grant-tables
--skip-networking
--skip-log-bin
--skip-innodb
--skip-wsrep
--default-storage-engine=MyISAM
--basedir=<owned runtime root>
--datadir=<private copied datadir>
--secure-file-priv=<private output directory>
--log-error=<private operational log>
```

`--no-defaults` prevents a host MariaDB configuration from changing semantics. `--bootstrap` plus
`--skip-networking` means there is no queryable server endpoint; `--skip-grant-tables` therefore avoids an
otherwise unnecessary system-schema initialization without widening an IPC boundary. `--secure-file-priv`
confines SQL file output. InnoDB, replication/wsrep, binary logging, and unused dynamic plugins should remain
disabled.

The SQL itself must be version-controlled and static. Archive content must never become an identifier, path, or
SQL fragment. Text columns should be exported in an unambiguous bounded representation (for example fixed
columns with `HEX(...)` plus numeric fields), not naïve tab-separated raw text that can contain tabs/newlines.

## Ownership and lifecycle

The narrowest repository seam is:

```text
Tauri package/runtime identity
  -> Python import job
  -> direct one-shot mariadbd child inside the existing Tauri-owned backend process tree
  -> private bounded export
  -> existing canonical paper/collection import domain
```

Tauri should resolve and attest the packaged engine root, pass only that owned path and bundle identity to the
backend, and retain whole-process-tree cleanup (Windows Job Object; Unix process group). Python should own the
per-import child, timeout, stdin template, output validation, transaction, and temporary-directory lifecycle.
There is no second supervisor and no runtime to keep warm.

On backend crash, the engine child remains inside Tauri's existing process tree. On ordinary failure, Python
terminates the child, rejects partial output, and cleans the private working copy. A startup janitor may remove
only signed/owned stale import directories after validating their exact root and marker; it must never scan or
delete arbitrary temp paths.

## Archive and data boundary

Before engine launch, a pure boundary layer must:

1. copy/hash the user-selected archive without modifying it;
2. preflight central-directory entry count, names, compressed/uncompressed sizes, ratio, duplicates,
   case-collisions, nesting, symlinks/reparse points, absolute paths, traversal, and special files;
3. detect legacy MyISAM versus modern SQLite explicitly;
4. extract only the exact allowlisted legacy table triplets needed by the recognized profile;
5. reject missing/unexpected tables or schema before any Callosum database write; and
6. keep attached PDFs outside the engine datadir for separate signature/MIME/size/hash validation.

Engine output is staging evidence, not a partial import. Only after all records, memberships, identifiers, and
attachment references validate should the existing transaction-safe import domain write to Callosum.

## Packaging and license findings

- MariaDB Community Server is GPL-2.0. Callosum is AGPL-3.0. A separately executed server bundle is designed as
  an aggregate rather than linked code, but the project must obtain a real distribution review and preserve the
  MariaDB license, notices, exact corresponding source/build recipe, checksums/signatures, and update ownership.
- The official downloads API provides signed/checksummed release artifacts. A future build must pin exact files
  and construct a deterministic allowlisted bundle manifest, like the managed-local runtime identity work—not
  download "latest" at runtime.
- Windows proved a small bootstrap-only subset, but each retained file and dependency must be justified and
  regression-tested. Linux needs a portable dependency manifest or explicit `.deb` dependencies. macOS needs a
  reproducible Callosum-owned build; Homebrew cannot be silently required.
- The engine is substantial enough that it should remain optional capability material, not inflate every
  installer before a real user-facing EndNote path and all three platform receipts exist.

## Threat summary

| Threat | Design response | Residual gate |
|---|---|---|
| Archive traversal/bomb/special files | bounded manual extraction into a private owned root | adversarial extractor tests |
| Source-table mutation | hash + copy first; engine sees only copy | regression proof on real fixtures |
| Local database exposure | bootstrap mode + `--skip-networking`; no socket/pipe/TCP client | live per-platform listener check |
| SQL injection | fixed schema-profile templates; no archive-derived SQL | template/hash tests |
| Arbitrary file read/write | private datadir + `--secure-file-priv`; direct argv | sandbox/path-escape tests |
| Content in logs | operational log only; sanitize engine errors; never enable general query log | log-content tests |
| Orphan process/data | existing process-tree containment, timeout, exact-root cleanup | crash/forced-cleanup tests |
| Runtime tampering | deterministic bundle manifest + signature/checksum provenance | production manifest design |
| License/source omission | GPL aggregate review, notices, corresponding source/build recipe | maintainer/legal sign-off |

## Developer executor result (increment 542)

`tools/endnote/legacy_bootstrap.py` implements the approved developer-only boundary without entering an app
import path. It performs bounded ZIP preflight, streaming SHA-256, a digest-verified private archive copy,
allowlisted table extraction, deterministic runtime manifesting, fixed SQL, direct-argv bootstrap execution,
bounded stdout/stderr/engine log, timeout/process-tree cleanup, encoded aggregate receipt validation, and a final
source-hash check. Its receipt contains no input/runtime path or bibliographic row.

A fresh Windows acceptance run used the official 10.11.19 archive already pinned above. It returned the public
X7 sample's 59 rows/54 columns in 1,187 ms, left the source SHA-256 unchanged, emitted a 29-entry runtime manifest,
and left no `mariadbd` process. The first attempt safely exposed one build-specific assumption: this Windows
package does not compile/expose wsrep, so `--skip-wsrep` is rejected as unknown. The harness removed that redundant
flag; bootstrap mode, `--skip-networking`, `--skip-log-bin`, disabled InnoDB, external locking/symlinks/local
infile restrictions, private datadir, and `--secure-file-priv` remain explicit.

## Standalone Linux proof (increment 544)

A 28-file temporary research bundle was extracted from the already-pinned official MariaDB image and run directly
on Juno's Debian 12 host, outside Docker. It contains `sbin/mariadbd`, English messages, and character-set data;
the canonical manifest is 25,758,167 bytes with SHA-256
`4e2c4577f201298bec7dff5e63cdd641e24fd4f38925224d9c0a44e33068d7dc`. A second extraction at a different root
produced the same digest. The Ubuntu 22.04.5/glibc 2.35 launcher resolved all 18 named OS-owned dependencies on
Debian 12/glibc 2.36 and reproduced the public fixture's 59 rows/54 columns in 259 ms with no orphan.

The developer manifest now hashes all 28 bundle files as `linux-bootstrap-files-v1`; it no longer presents a
launcher-only digest as complete runtime identity. This proves one real direct-host compatibility point. It does
not establish compatibility for every Linux distribution, and it deliberately does not vendor glibc/system
libraries. A shipping design still needs an explicit distro/ABI support matrix or package-dependency policy.

No route, UI, bundled engine, paper write, PDF ingestion, or production activation was added. The next work is
not broader parser coding: close the remaining platform/package/license and missing-fixture gates listed above.

## Authoritative sources checked

- MariaDB server variables (`skip_networking`, `socket`, `secure_file_priv`):
  <https://mariadb.com/docs/server/server-management/variables-and-modes/server-system-variables>
- `mariadbd` options and bootstrap/install behavior:
  <https://mariadb.com/docs/server/server-management/starting-and-stopping-mariadb/mariadbd-options>
  and <https://mariadb.com/docs/server/clients-and-utilities/deployment-tools/mariadb-install-db>
- MariaDB client protocol behavior:
  <https://mariadb.com/docs/server/clients-and-utilities/mariadb-client/mariadb-command-line-client>
- MariaDB licensing FAQ: <https://mariadb.com/docs/general-resources/community/community/faq/licensing-questions/licensing-faq>
- MariaDB Foundation downloads REST API: <https://mariadb.org/downloads-rest-api/>
- Binary package guidance: <https://mariadb.com/docs/server/server-management/install-and-upgrade-mariadb/installing-mariadb/binary-packages/installing-mariadb-binary-tarballs>

# Security audit — EndNote Compressed Library import (backlog #57 Phase 6B)

**Date opened:** 2026-08-30
**Status:** **OPEN — developer executor proven on Windows plus a seven-release Linux matrix; production importer not started**
**Planned surface:** untrusted `.enlx`/`.enl` archive ingestion; legacy MyISAM or modern SQLite format detection;
bibliographic/group/attachment extraction into existing import pipelines.

This stub is opened before implementation, as required by the Phase 6 handoff. It is not a PASS. Increment 535's
research proved that a disposable MariaDB engine can read a copied EndNote X7 vendor fixture after an explicit
table upgrade; it did not establish a safe packaged runtime or a complete importer.

Increment 541 narrows the engine from a private service to a one-shot `mariadbd --bootstrap` child. Live tests
on Windows and Debian used only a copied public X7 fixture, `--skip-networking`, fixed SQL over stdin, and
`--secure-file-priv` output; both upgraded/read 59 rows and exited without an orphan. Windows also proved a
20,240,927-byte/29-file experimental runtime subset. This materially reduces the attack surface but does not
close this audit. See `.claude/docs/research/2026-08-30_endnote_managed_bootstrap_engine.md`.

Increment 542 implements the developer executor outside application imports. Thirty focused tests cover bounded
archive/profile handling, private-copy integrity, traversal/case/symlink rejection, streaming hashes,
allowlisted runtime identity, fixed command/SQL, timeout and total-log bounds, receipt validation, path-free
errors, and credential-free child environments. A fresh Windows live run over the public fixture reproduced
59 rows/54 columns, preserved the archive hash, published no path/content, and left no process. The official
Windows build has no wsrep option compiled in; the unsupported `--skip-wsrep` flag was removed rather than
loosening error handling. The process still explicitly disables network, binlog, InnoDB, external locking,
symbolic links, and local infile. This materially advances—but does not close—the audit.

Increment 544 extracted a 28-file launcher/message/charset bundle from the pinned official MariaDB 10.11.19
image and ran it directly on Juno's Debian 12 host, outside Docker. All 18 OS-owned dynamic dependencies resolved;
the public X7 result remained 59 rows/54 columns, source-immutable, network-disabled, and orphan-free. Linux
identity now hashes all 28 relative-path/size/content entries rather than only the launcher, and an independent
relocation reproduced the manifest digest. This is one Debian/glibc compatibility point, not a cross-distro or
shipping-package claim, so the audit remains open.

Increment 545 completes the engineering license/provenance review but does not supply legal approval. MariaDB
Server is GPL-2.0-only and Callosum is AGPL-3.0-or-later; they must not be linked, merged, or presented as one
relicensed program. The separate process/argv/stdin/file boundary has the technical characteristics of independent
programs in an aggregate, but the feature-specific dependency still requires qualified review. Official 10.11.19
Linux binary and source hashes/signatures were verified; both an original signed-bintar candidate and a
deterministically stripped 31.8 MB candidate reproduced the public fixture receipt and left no process. A future
release must mirror exact source/notices, record every transform, sign the derived asset, and remain blocked from
installer/updater/catalog integration until legal sign-off. See
`.claude/docs/research/2026-08-30_endnote_mariadb_distribution_review.md`.

Increment 546 closes the runtime-specific Linux ABI/package-policy research gate. The exact stripped candidate
passed Ubuntu 20.04/22.04/24.04/26.04 and Debian 11/12/13, both as root and uid 1000, under a read-only runtime/
fixture mount, private writable temp root, 1 GiB/2 CPU/128 PID caps, absent container network plus
`--skip-networking`, source-hash verification, and orphan checks. The initial supported component envelope is
Ubuntu 22.04/24.04/26.04 and Debian 12/13 on amd64, never broader than the actual Callosum `.deb`. The future
package declares five direct OS libraries instead of vendoring system copies. This does not close the audit or
authorize distribution. See `.claude/docs/research/2026-08-30_endnote_linux_abi_matrix.md`.

## Approved POC boundary

- Developer-supplied pinned runtime only; no bundled binary, downloader, route, UI, or user data write.
- One-shot bootstrap mode only. No TCP, Unix socket, Windows named pipe/shared memory, installed service,
  persistent database account, or warm engine.
- Direct argv; `--no-defaults`, `--bootstrap`, `--skip-networking`, `--skip-log-bin`, disabled InnoDB (and an
  attested Windows build with no wsrep support), private copied datadir, and private `--secure-file-priv` output.
- Static versioned SQL selected only after exact format/schema recognition; no archive-derived SQL or path.
- Tauri attests the runtime root/identity and owns the containing process tree; Python owns the bounded import
  child and temporary job. No dual supervision.
- Public X7 fixture only until the archive/executor boundary passes adversarial tests.

## Production blockers after increment 546

- After legal approval permits integration, convert the proven manifest into a signed/pinned optional asset and
  install/run the actual Callosum `.deb` plus component on every claimed Linux release. The runtime-only matrix
  and package policy are complete; the integrated package does not exist yet.
- Reproducible macOS arm64/x86_64 build plus signing/notarization/live lifecycle proof; upstream 10.11.19 offers
  no official macOS binary in its current download inventory.
- Qualified legal approval of the GPL-2.0-only server / AGPL-3.0-or-later separate-program aggregate boundary;
  engineering source/notice/signature/transformation requirements are now specified but not implemented.
- Real attached-PDF `.enlx` fixture and modern SQLite-era `.enlx` fixture.
- Full production row/schema/attachment mapping and corrupt-engine-table negative suites beyond the aggregate
  developer receipt; attachment MIME/signature/deduplication cannot close without a real attached-PDF fixture.

## Required review before closure

- Copy-first processing and immutable source handling; ZIP entry-count, per-entry, total-expanded-size,
  compression-ratio, nesting, row, field, attachment, and wall-time bounds.
- Exact format/schema allowlists and fail-closed version detection; no dynamic SQL identifiers from archive data.
- MyISAM work only in a private temporary copy/datadir. Engine process must be app-owned, unprivileged,
  network-disabled, bounded, crash-cleaned, and unable to discover other databases or host paths.
- Runtime provenance, license/redistribution, binary integrity/update ownership, per-platform packaging, and
  compatibility policy for any database engine shipped or required.
- Archive path traversal, symlink/reparse-point escape, special-file, absolute-path, case-collision, and duplicate
  entry rejection; attachment MIME/signature validation and safe generated destinations.
- Identity matching before paper creation; attachment deduplication; group provenance; no silent partial import.
- No bibliographic content in ordinary logs or errors; personal fixtures remain gitignored, read-only, and local.
- Negative fixtures for schema mismatch, corrupt tables, required table upgrade failure, oversized archives,
  malicious paths, missing attachments, duplicate records, process crash, timeout, and cleanup.

# Security audit — EndNote Compressed Library import (backlog #57 Phase 6B)

**Date opened:** 2026-08-30
**Status:** **OPEN — managed-engine design conditionally approved for a developer POC; production importer not started**
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

## Approved POC boundary

- Developer-supplied pinned runtime only; no bundled binary, downloader, route, UI, or user data write.
- One-shot bootstrap mode only. No TCP, Unix socket, Windows named pipe/shared memory, installed service,
  persistent database account, or warm engine.
- Direct argv; `--no-defaults`, `--bootstrap`, `--skip-networking`, `--skip-log-bin`, disabled InnoDB/wsrep,
  private copied datadir, and private `--secure-file-priv` output.
- Static versioned SQL selected only after exact format/schema recognition; no archive-derived SQL or path.
- Tauri attests the runtime root/identity and owns the containing process tree; Python owns the bounded import
  child and temporary job. No dual supervision.
- Public X7 fixture only until the archive/executor boundary passes adversarial tests.

## Production blockers after increment 541

- Reproducible Windows/Linux runtime manifests and live standalone Linux dependency proof.
- Reproducible macOS arm64/x86_64 build plus signing/notarization/live lifecycle proof; upstream 10.11.19 offers
  no official macOS binary in its current download inventory.
- GPL-2.0 server aggregation/corresponding-source/notices review alongside Callosum's AGPL-3.0 distribution.
- Real attached-PDF `.enlx` fixture and modern SQLite-era `.enlx` fixture.
- Full archive, schema, encoded-export, timeout, crash, path, log-content, and cleanup negative suites.

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

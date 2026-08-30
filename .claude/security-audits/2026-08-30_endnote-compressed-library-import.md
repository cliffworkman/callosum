# Security audit — EndNote Compressed Library import (backlog #57 Phase 6B)

**Date opened:** 2026-08-30
**Status:** **OPEN — feasibility spike complete; production importer not started**
**Planned surface:** untrusted `.enlx`/`.enl` archive ingestion; legacy MyISAM or modern SQLite format detection;
bibliographic/group/attachment extraction into existing import pipelines.

This stub is opened before implementation, as required by the Phase 6 handoff. It is not a PASS. Increment 535's
research proved that a disposable MariaDB engine can read a copied EndNote X7 vendor fixture after an explicit
table upgrade; it did not establish a safe packaged runtime or a complete importer.

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

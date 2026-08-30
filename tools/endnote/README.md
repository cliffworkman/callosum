# Developer EndNote bootstrap probe

This directory contains reusable **developer-only** evidence tooling for the legacy MyISAM branch of EndNote
Compressed Libraries. It is not imported by Callosum's backend and does not expose a route, setting, or UI.

The probe accepts a developer-supplied MariaDB executable and an `.enlx` archive matching the exact
`endnote-x1-x7-myisam-v1` table profile. It then:

1. bounds and hashes the archive before extraction;
2. creates a digest-verified private copy;
3. extracts only the allowlisted engine tables without `extractall`;
4. manifests the allowlisted runtime files;
5. runs fixed SQL through one-shot `mariadbd --bootstrap` with networking, binary logging, InnoDB, external
   locking, symbolic links, and local infile disabled;
6. accepts only bounded numeric/hex-encoded receipts; and
7. removes the private datadir and process on success, failure, or timeout.

Example:

```powershell
.venv\Scripts\python.exe -m tools.endnote.legacy_bootstrap `
  --archive C:\path\to\Sample_Library_X7.enlx `
  --runtime C:\path\to\mariadbd.exe
```

The JSON receipt contains archive/runtime digests and aggregate schema facts, but no source path, runtime path,
credential, title, author, or bibliographic row. Windows and Linux bundle identity covers the launcher plus the
allowlisted message and charset data used by this bootstrap path; Windows additionally covers `server.dll`. The
Linux proof uses OS-owned dynamic-library dependencies and therefore does not establish compatibility with every
Linux distribution. Do not point this probe at personal material while the EndNote security audit remains open.
The runtime is never downloaded or bundled by this tool.

Production import remains gated on per-platform runtime packaging/provenance, macOS lifecycle proof, license
review, attached-PDF coverage, a modern SQLite-era fixture, complete schema mapping, and the still-open security
audit. See `.claude/docs/research/2026-08-30_endnote_managed_bootstrap_engine.md`.

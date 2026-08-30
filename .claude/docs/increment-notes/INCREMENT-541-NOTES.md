# Increment 541 — EndNote one-shot managed-engine decision

**Date:** 2026-08-30
**Scope:** backlog #57 Phase 6B architecture, packaging, and security audit only. No production code, dependency,
runtime bundle, route, setting, UI, migration, or user library write changed.

## Question

Can the real-engine strategy proven in increment 535 be made narrow enough for a zero-configuration EndNote
import without shipping or supervising a persistent private database service?

## Result

Yes, conditionally. MariaDB's one-shot `mariadbd --bootstrap` mode accepts fixed SQL on stdin and exits. With
`--no-defaults`, `--skip-networking`, disabled InnoDB/wsrep/binlog, a private copied datadir, and
`--secure-file-priv` output, it needs no TCP/socket/pipe endpoint, database account, readiness protocol, or warm
daemon.

Only EndNote's public X7 vendor sample was used. No personal row content was queried, printed, or transferred.

### Windows receipt

- MariaDB `10.11.19-MariaDB`, source revision `93e051860a9c7e87ee8cee6ed38b640d491f7170`.
- Official `mariadb-10.11.19-winx64.zip`: 93,557,290 bytes; SHA-256
  `398ea30e5036010bbebe01d2b1804280424dcc2626e36d8e95155c04d25a0490`, matching the Foundation receipt.
- Expanded distribution: 611 files / 300,457,120 bytes.
- Experimental bootstrap-only subset: 29 files / 20,240,927 bytes.
- Copy-only `ALTER TABLE rdb.refs FORCE` plus aggregate export returned 59 rows / 54 columns; exit zero; no
  remaining process; source archive hash unchanged.

### Debian receipt

- Official `mariadb:10.11.19` image digest
  `sha256:ce66c7be32a03aabe7241d0a10993a2db827ef652a35d25727d92a832ac8ef73`.
- Non-root, `--network none`, stdin-enabled one-shot bootstrap returned 59 rows and exited zero.
- The first container attempt omitted `-i`, therefore supplied no SQL; it is excluded. The fresh accepted run
  used stdin correctly.
- Fixture, SQL, datadirs, output, and container were removed; no remote work artifact remained.

### Unproven

- macOS execution/build/signing/notarization (the current official 10.11.19 inventory has no macOS binary);
- a standalone portable Linux dependency manifest outside the research container;
- final Windows pruning/dependency manifest;
- GPL-2.0 server aggregation/corresponding-source obligations beside Callosum AGPL-3.0;
- real attached-PDF and modern SQLite-era fixtures.

## Architecture decision

Tauri will eventually resolve/attest the runtime bundle and retain whole-backend process-tree cleanup. Python's
explicit import job will own one direct-argv bootstrap child, fixed SQL, timeout, output validation, atomic
Callosum transaction, and exact-root cleanup. This is layered ownership, not dual supervision: no separate
Tauri daemon state exists.

The SQL template is static per exact schema profile. Archive data never becomes SQL or a path. Exported text
must use an unambiguous bounded encoding such as fixed numeric/`HEX(...)` columns rather than raw TSV. No engine
output becomes a partial import; the complete snapshot validates before the existing paper/collection domain
writes.

Detailed design/threat model:
`.claude/docs/research/2026-08-30_endnote_managed_bootstrap_engine.md`.

## Decision and next increment

**CONDITIONAL GO** to a developer-only bootstrap executor harness using a developer-supplied pinned runtime and
the public X7 fixture. It must prove archive preflight, command/SQL immutability, runtime identity, no listener,
timeout/forced cleanup, bounded encoded output, and source immutability on Windows and Linux.

Do not add a bundled runtime, downloader, route, UI, paper write, PDF ingest, or production activation yet.

## Verification

- Current official MariaDB download/options/licensing documentation was consulted; exact sources are recorded in
  the research document.
- Gitignored fixture coverage rechecked.
- Live Windows and Debian receipts above completed.
- Remote and local material/process cleanup verified; no engine, container, fixture copy, SQL scratch file, or
  downloaded runtime remained.
- `.venv` line-budget gate: **576 application-source files within the 600-line cap**.
- `.venv` Bandit wrapper: exit 0.
- The shell-default Anaconda interpreter initially lacked Bandit; with maintainer approval it now has the exact
  `.venv` version (`1.9.4`), and the previously failing default `python tools/run_bandit.py` command exits 0.
- `.venv` Tach: **All modules validated**.
- Targeted pre-commit initially removed Markdown trailing spaces from the two new documents; the clean rerun,
  secret/private-path scan, `git diff --check`, exact commit, and remote CI receipts follow before closure.
- No runtime test suite is claimed because tracked production code did not change.

## Revert

Revert this increment commit. It changes only developer documentation and ledgers.

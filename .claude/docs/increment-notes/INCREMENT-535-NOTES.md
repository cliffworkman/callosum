# Increment 535 — EndNote legacy-MyISAM feasibility spike

**Date:** 2026-08-30
**Scope:** backlog #57 Phase 6B research only. No production importer, dependency, schema, UI, provider, citation,
or protected-store behavior changed.

## Question

Can Callosum safely read the `.frm`/`.MYD`/`.MYI` tables empirically present in its EndNote X1 and X7.7 fixtures
without inventing a binary parser or requiring a persistent database service?

## Evidence and result

Current MySQL's supported raw-table import expects `.sdi`, not these legacy `.frm` definitions. The old Oracle
`frm_reader.py` reconstructs schema only; `myisamchk` repairs/checks tables but is not a query interface. No
credible maintained pure-language reader was found.

A bounded live experiment used only EndNote's public X7 vendor sample, copied to Juno and opened inside the
official `mariadb:10.11` container with no published port and a disposable datadir. MariaDB recognized seven
tables and directly queried three. The core `refs` table correctly failed with `Table rebuild required`; an
explicit `ALTER TABLE ... FORCE` on the disposable copy upgraded it, after which all 59 reference rows and the
expected 54-column bibliographic schema were accessible. No row content was printed. The container, uploaded
archive, extracted tables, and datadir were removed; the personal X1 fixture never left the workstation.

## Decision

An ephemeral real engine is the only currently defensible legacy-MyISAM strategy. It is feasible but too large
an unreviewed security/packaging surface to smuggle into the importer increment. Docker is a research tool, not a
zero-configuration product dependency. Phase B is now gated on a managed-engine design/packaging audit, a fixture
with an attached PDF, and a separate modern SQLite-era fixture. Existing RIS/XML fallbacks remain unchanged.

The required Phase A and Phase B security audit stubs were opened. Neither is a PASS.

## Verification

- `git check-ignore -v .claude/backups/endnote-fixtures` — fixtures remain covered by `.claude/backups/` ignore.
- Public X7 SHA-256 before transfer: `AD53D894BAF15045A7504107E576C9591FF01FCA76176A9D32E4C50A3043AB98`.
- MariaDB live receipt: `10.11.19`, official image digest
  `sha256:ce66c7be32a03aabe7241d0a10993a2db827ef652a35d25727d92a832ac8ef73`; row counts above.
- Remote cleanup returned `cleaned`; no fixture/table/datadir remained under `/tmp/callosum-endnote-*`.
- Documentation-only increment: runtime tests are not claimed.

## Revert

Revert this increment commit. It removes only research/audit/ledger documentation; no application behavior or
persisted user data is involved.

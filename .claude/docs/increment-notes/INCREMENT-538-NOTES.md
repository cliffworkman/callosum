# Increment 538 — dormant Mendeley snapshot import core

**Date:** 2026-08-30
**Scope:** backlog #57 Phase 6A safe work behind the gated OAuth boundary. Adds a bounded, transaction-safe
metadata/folder import domain over synthetic version-1 Mendeley payloads. No route, live request, token use, PDF
download, or user-facing native Mendeley behavior activates.

## Evidence-driven contract

The current official Mendeley API reference was re-read before implementation. Its version-1 documents contract
requires `id`, `title`, and `type`; represents people with `first_name`/required `last_name`; and exposes
bibliographic metadata including `year`, `source`, identifiers, and the `bib`/`all` fields. The separate folders
contract exposes `id`, `name`, and optional `parent_id`; exact membership comes from the paginated
`/folders/{id}/documents` resource. Sources reviewed 2026-08-30:

- <https://dev.mendeley.com/methods/>
- <https://dev.mendeley.com/reference/topics/versioning.html>
- <https://github.com/Mendeley/mendeley-python-sdk>

The mapper accepts the already-pinned version-1 response shape and converts it to the existing
`csl_record_to_paper_fields` contract. Unknown bounded future document types retain their provider type in the
CSL provenance extension and safely map to generic `document`; Callosum does not hard-fail merely because
Mendeley's controlled vocabulary expands.

## Import and identity behavior

`app/backend/importers/mendeley.py` is transport-free and dormant. It:

- validates the complete documents/folders/membership snapshot before touching the database;
- caps snapshots at 50,000 documents, 2,000 folders, 100,000 exact memberships, 1,000 authors per record, and
  bounded official/local string sizes;
- rejects duplicate IDs, malformed fields, missing parents, hierarchy cycles, and unknown membership targets;
- maps common metadata through Callosum's existing CSL/paper field seam without overwriting a matched paper;
- checks DOI then title/year/first-author through `find_existing_paper_by_identity` before creation;
- records every stable source UUID in the already-existing generic `paper_external_identifiers` table under
  `mendeley-document`, making even year/author-poor records idempotent without a new Mendeley-specific column;
- fails closed when source provenance and canonical metadata resolve to different papers;
- upserts source-owned `collections` hierarchy and replaces membership for each supplied Mendeley folder inside
  one savepoint; missing folders are not deleted or guessed;
- leaves user-owned axes untouched. Increment 536's explicit collection-to-axis action can consume these rows
  later without another axis model.

Two source records with the same DOI link to one canonical paper, keep both source UUIDs, and collapse duplicate
folder membership to one `(collection, paper)` pair.

## Credential state and activation boundary

The maintainer added a Mendeley secret to the gitignored `.env`; presence was checked without reading or printing
the value. A registered client ID and exact redirect identity are not present under Mendeley-named variables, and
the official confidential-client/no-documented-PKCE desktop constraint from increment 537 is unchanged. This
increment does not load `.env`, instantiate the HTTP client, or attempt OAuth. Live activation remains a separate
security increment.

## Verification

- New importer suite: **9 passed** in 10.12s.
- Combined importer/client/citation/collection-axis/persistence/merge affected suite: **73 passed** in 114.64s.
- Full collection: **2625 tests** in 25.14s.
- Full bounded-parallel suite: **2625 passed, 3 skipped** in 1583.08s (26m23s) with four workers.
- The prescribed `-n auto` attempt was stopped without a result after its host-wide fan-out starved even a
  read-only process query; its exact newly started worker PIDs were terminated. The same complete suite was then
  rerun successfully at `-n 4`. No unrelated/older Python process was touched.
- Ruff format/check, Bandit, Tach, 576-file line budget, `git diff --check`, and added-line
  secret/private-path scans: passed.
- Final staged pre-commit passed every applicable hook. Concurrent Claude Code website/demo work stayed unstaged;
  tracked `www/` paths were temporarily hidden from change detection only for the hook window, then normal index
  tracking was restored. No concurrent file content was staged, reverted, or rewritten.
- Remote receipts follow after push.
- All fixtures are synthetic. No Mendeley account, token, endpoint, PDF, scholarly library, or provider egress
  was used.

## Remaining work

1. Resolve the registered public/confidential desktop client and fixed redirect ownership problem, then perform
   a separately audited live OAuth handshake.
2. Add the route/job/UI only after live payloads validate the frozen mapper and transaction behavior.
3. Design and test bounded streaming PDF download/ingest with a real authenticated file response and fixture.

Until then, the existing Zotero bridge and metadata exports remain the supported Mendeley paths.

## Revert

Revert this increment. It has no migration, route, or production behavior effect; existing database rows are not
created unless a developer/test explicitly calls the dormant import function.

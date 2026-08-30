# Native Mendeley + EndNote whole-library import (metadata + PDFs + folders)

**Date:** 2026-08-29
**Scope:** backlog #57 Phase 6; research pass supporting a real, higher-fidelity import path for two real users
(the maintainer uses Mendeley; a colleague adopting callosum uses EndNote)

## Why this research exists

Backlog #57's already-shipped Phase 2 (EndNote, inc 486) and Phase 3 (Mendeley-via-Zotero, inc 487) were built
and documented honestly as *partial* solutions. Reviewing them against a real user's actual need surfaced two
concrete gaps:

- **EndNote's only supported path (RIS export) is metadata-only.** Confirmed by reading
  `app/backend/metadata/citation_import.py` directly: `parse_ris`/`parse_bibtex`/`parse_csl_json` produce paper
  metadata fields only. No PDF, attachment, or folder/group handling exists anywhere in that module. A user who
  imports via RIS then has to separately point callosum at a folder of PDFs, with **no automatic linking**
  back to the freshly-imported records — the exact "import metadata, then follow a folder, wind up with a
  jillion duplicates to merge" failure mode a real user flagged live.
- **Mendeley's only full-fidelity path requires installing an entirely separate application (Zotero) as a
  bridge.** Re-confirmed via `.claude/docs/research/2026-08-21_mendeley_via_zotero_bridge.md`: Mendeley → Zotero's
  own online importer (requires Mendeley data already synced to Elsevier's cloud) → a local Zotero library →
  callosum's existing Zotero importer. Real, valid friction for anyone who doesn't want a second reference
  manager installed just to leave the first one.

This research asks: is there a better, more direct, single-vendor-tool path for each, and does it preserve
folder/group structure well enough to map onto callosum's axis system?

## Mendeley: the official REST API, no Zotero required

`dev.mendeley.com`'s current, live documentation confirms a complete, legitimate, first-party path exists and
needs no bridge application:

- **OAuth 2.0 Authorization Code flow.** The user authenticates at Mendeley's own consent screen and grants
  *this app* delegated access to *their own* library. This is the same posture as callosum's existing ORCID
  OIDC sign-in (`app/backend/api/auth/`) — the vendor's own sanctioned door, not a protected-store workaround.
  It is the structural opposite of the `.enl`-decryption boundary APPROACH-AVOIDANCE already forbids.
- **`GET /documents`** — paginated library metadata, filterable by `group_id`/`modified_since`; personal-folder
  membership is exposed through the separate `/folders/{id}/documents` endpoint, not a `folder_id` filter.
- **`GET /folders`** — a genuinely hierarchical resource via `parent_id` (distinct from Groups, which are
  shared/collaborative and out of scope here — personal library only, matching the existing Mendeley-bridge
  research's own "personal library only" boundary).
- **`GET /folders/{id}/documents`** — exact folder membership.
- **`GET /files`** (filterable by `document_id`) and **`GET /files/{id}`**, which 303-redirects to a short-lived
  signed download URL for the actual PDF bytes.
- **Reference implementation**: [`Mendeley/mendeley-python-sdk`](https://github.com/Mendeley/mendeley-python-sdk)
  (Apache-2.0, published under the Mendeley GitHub org itself — an *official*, if now-dormant [last commit
  2023-05-29], vendor artifact). Its `File.download(directory)` method does exactly `GET /files/{id}` and
  streams the PDF to disk. This is a materially stronger evidence base than the Zotero-bridge path had — a
  vendor-published, vendor-authored proof that the documents+folders+files call pattern works end to end.

Sources: https://dev.mendeley.com/methods/, https://dev.mendeley.com/overview/core_resources.html,
https://dev.mendeley.com/reference/topics/authorization_overview.html,
https://github.com/Mendeley/mendeley-python-sdk

**Prerequisite that cannot be done in code**: callosum needs its own registered OAuth application on
dev.mendeley.com (a `client_id`/`client_secret` pair) before this can be built and live-tested. This is a
one-time manual registration step for the maintainer, the same category of task as the existing Google Docs
OAuth client setup — not something an implementing session can do on its own.

Native Mendeley Reference Manager exports (BibTeX/RIS/EndNote XML/Word XML, via `File > Export`) remain
metadata-only per Elsevier's own current support documentation — confirmed no different from what was already
known; the REST API is the only Mendeley path that carries files and real folder structure together.

### Desktop OAuth constraint + safe scaffold (2026-08-30, increment 537)

A fresh official-doc review found an architectural constraint hidden by the earlier high-level feasibility
result. Mendeley's authorization-code flow authenticates `/oauth/token` with HTTP Basic using the registered
client ID and **client secret**; its own authorization overview classifies this as a confidential-client flow.
The official docs expose no PKCE parameter or public-client authorization-code variant. The alternative implicit
flow avoids a secret but issues one-hour access tokens with no refresh protocol. Registration also pins an exact
redirect URI. Those facts matter for Callosum's packaged desktop shape:

- embedding one shared application secret in a distributed binary would not keep it confidential;
- using the ordinary backend callback is not reliable while its port may move on collision;
- silently switching to implicit flow would lose refresh and would not implement the approved design.

Therefore increment 537 does **not** publish a callback or persist tokens. It retains a reusable, hermetically
tested client under `integrations/mendeley/client.py`: exact official authorize/token endpoints and versioned
Accept headers; read-only `/documents?view=all`, `/folders`, `/folders/{id}/documents`, and `/files`; bearer-only
authorization; 500-item pages with hard page/item/body/URL limits; same-resource pagination with cycle rejection;
and a non-following `/files/{id}` 303 check allowlisted to the documented `downloads.mendeley.com` host. Provider
errors are sanitized so tokens/secrets and response bodies do not enter exceptions.

The remaining prerequisite is now more precise than “register an app”: inspect the actual My Applications form
and/or obtain Mendeley support confirmation for a desktop-safe public-client/PKCE or brokered-confidential-client
shape, register the exact redirect design, then exercise authorization, refresh, pagination, and signed-download
behavior live before any user-facing activation. Official sources reviewed 2026-08-30:

- https://dev.mendeley.com/reference/topics/authorization_auth_code.html
- https://dev.mendeley.com/reference/topics/authorization_implicit.html
- https://dev.mendeley.com/reference/topics/authorization_overview.html
- https://dev.mendeley.com/reference/topics/application_registration.html
- https://dev.mendeley.com/reference/topics/versioning.html
- https://dev.mendeley.com/reference/topics/pagination.html
- https://dev.mendeley.com/methods/

## EndNote: the Compressed Library (`.enlx`), no separate app required

Clarivate's current EndNote 2025 documentation confirms `File > Compress Library (.enlx)` is a live, supported
feature that bundles the complete library — the `.enl` database, the companion `.Data` folder (including a
`PDF/` subfolder holding every attachment binary), and group/group-set structure — into a single ZIP archive,
with explicit UI options to include/exclude file attachments and to scope the export to one group or group set.
Hard vendor-documented limits: libraries over 4GB or with more than 65,535 files cannot be compressed this way.

Source: https://docs.endnote.com/docs/endnote/2025/v1/macos/en/content/02library/saving_a_cmprssdcpy_ofa_lib.htm

**The `.enl` database is SQLite in current EndNote (20/21-era) — but this is a recent change, not the
universal format.** The open-source reverse-engineering below documents the modern SQLite-based layout: an
internal runtime mirror at `MyLibrary.Data/sdb/sdb.eni`, with `refs`/`file_res`/`groups`/`misc` tables. Two
independent projects agree on this modern schema, a materially stronger evidence base than a single blog post
or guess:

- [`IEBH/RefLib`](https://github.com/IEBH/RefLib) (MIT, Node.js, `npm @iebh/reflib`) — part of Bond University's
  "Systematic Review Accelerator" academic tooling, in real production use. Opens `.enlx` (unzips, delegates to
  its `.enl` reader) and reads bibliographic fields from the `refs` table. Does not currently surface
  attachments or groups even though the data exists in the same file.
- [`TCMzhoutong/endnote-cli`](https://github.com/TCMzhoutong/endnote-cli) (Apache-2.0, Python) — newer, less
  proven (single maintainer, ~12 stars, created April 2026) but materially more complete: documents a `refs`
  table (classic EndNote fields, `\r`-separated multi-value fields like authors/keywords), a `file_res` table
  mapping references to attachment files under `.Data/PDF/`, and a `groups` table plus `misc` (code 17) XML
  blobs encoding group → group-set hierarchy via `<member>` UUID references. Its own README flags a `misc` code
  4 legacy table as "stale, don't rely on it."

**Correction from direct inspection of real fixture files (see below): older EndNote versions use a completely
different, non-SQLite format.** Both of the maintainer's real EndNote X1 (~2007-2008) library and a vendor
sample EndNote **X7.7** (~2015) `.enlx` file were inspected directly (`zipfile`/`file` on the real bytes, not
assumed from documentation) and **both use an embedded MySQL MyISAM storage engine**, not SQLite: the `.enl`
itself is a ZIP containing `rdb/` (and, for X7.7, also `tdb/`) folders full of `refs.frm`/`refs.MYD`/`refs.MYI`,
`misc.frm`/`.MYD`/`.MYI`, `terms.*`, `jterms.*`, `csort.*`, `pdf_index.*` — classic MyISAM table-definition
(`.frm`), data (`.MYD`), and index (`.MYI`) files. **This means the SQLite-based format the two open-source
projects document is a materially more recent EndNote change than initially assumed** — likely introduced
somewhere between the X7.7/X9 era and EndNote 20, not something present "since EndNote 20/21" as a stable long-
running format. **Any real implementation must detect which storage engine a given `.enl`/`.enlx` actually uses
before choosing a parsing strategy** (a real, now-verified case for the fail-closed schema-detection
requirement below, not merely a hypothetical one) — a MySQL-MyISAM importer and a SQLite importer are two
different, non-overlapping pieces of work, and neither of the maintainer's two real fixtures represents the
SQLite-era format at all.

**Real safety caveat, load-bearing for implementation**: this schema is reverse-engineered and undocumented by
Clarivate, so it may differ across EndNote versions. Any parser must be:
- **Read-only.** `endnote-cli`'s own README documents that live writes trigger an EndNote-only SQLite trigger
  function (`EN_MAKE_SORT_KEY`) unavailable outside the application — irrelevant to callosum since this is a
  one-way import, never a write-back, but worth stating explicitly so no future change accidentally attempts one.
- **Fail-closed on schema mismatch.** Verify the expected tables/columns exist before trusting them; refuse
  cleanly with a clear message on an unrecognized shape rather than silently importing wrong or partial data.
- **Bounded.** Cap ZIP entry count/size, SQLite row counts, and attachment counts before processing — this is
  untrusted file content by the project's own rule #4 (external/untrusted input validated at the boundary).

**EndNote's separate "EndNote XML" export** (distinct from RIS, `File > Export > EndNote XML`) is confirmed to
exist and preserve richer bibliographic detail than RIS (rich-text styling, more field fidelity) but — confirmed
by inspecting a real sample export — carries **no group/group-set information at all** and **no file
attachments**. It is not a substitute for `.enlx`; useful only as a possible secondary/fallback metadata format,
not for the folder→axis or PDF-import halves of this feature.

Sources: https://docs.endnote.com/docs/endnote/2025/v1/windows/en/content/15independentbibs_export/exporting_to_endnote_xml.htm,
https://github.com/IEBH/RefLib, https://github.com/TCMzhoutong/endnote-cli

## Real fixture material available (directly inspected, not assumed)

The maintainer has real EndNote installations/libraries copied to `C:\Users\cliff\Dropbox\Dropbox\01_Work\`:

- `EndNotex1/My EndNote Library.enl` (+ companion `EndNotex1/My EndNote Library.Data/`) — a **real personal
  EndNote X1 library**, not just program install cruft (the `Connections/` folder alongside it is indeed just
  EndNote's own bundled `.enz` Z39.50 connection-configuration files, not library data — confirmed separately).
  Directly inspected: the `.enl` is a ZIP containing `rdb/` MyISAM table files (`refs.frm/.MYD/.MYI`,
  `misc.*`, `terms.*`, `jterms.*`, `csort.*`, `pdf_index.*`). A `PDF/` subfolder exists under `.Data/` but
  appears to hold no actual attachment files in this copy.
- `EndNotex7.7/Examples/Sample_Library_X7.enlx` — a **real, vendor-shipped sample Compressed Library** (EndNote's
  own bundled example, not the maintainer's personal library). Directly inspected via Python's `zipfile`: same
  MyISAM `rdb/`+`tdb/` table-file structure as the X1 fixture above (`refs.frm`/`.MYD`/`.MYI` etc., ~107KB of
  reference data), and its `PDF/` entry is present but empty (0 attachment files) — useful for validating
  ZIP-extraction and MyISAM-table-reading mechanics, but **not** for testing the PDF-attachment-import half of
  this feature; a real fixture with actual attached PDFs is still needed for that (ask the maintainer or his
  EndNote-using colleague for one, or accept a temporary attachment-path coverage gap and disclose it).
  `EndNotex7.7/My EndNote Library.xml` at the top level may be a real personal EndNote-XML export — useful for
  confirming the "no groups, no attachments" finding above against real data.

**Both real fixtures use the older MyISAM format, not SQLite** (see the correction above) — despite X7.7 being
roughly a decade newer than X1, neither predates nor reaches the SQLite-based era the open-source
reverse-engineering documents. **Practical scoping implication**: build and verify the MyISAM-based importer
first, since it's the only format with real fixture coverage right now; treat the modern SQLite-based format
(`sdb/sdb.eni`) as a second, currently-fixture-less variant to detect and either support opportunistically (the
open-source schema docs above are a real reference to build from) or fail closed on with a clear "unsupported
EndNote library version" message — do not assume MyISAM support implies SQLite support or vice versa, they are
different parsers.

## MyISAM reader feasibility spike (2026-08-30, increment 535)

The open reader question above now has an empirical answer, but not yet a production implementation.

### Maintained-reader review

- No credible maintained pure-Python, Rust, or standalone library was found that accepts the complete legacy
  `.frm` + `.MYD` + `.MYI` table identity and exposes rows with MySQL-compatible field semantics. Oracle's old
  `mysql-utilities` `frm_reader.py` reconstructs table definitions from `.frm`; it does not read `.MYD` rows.
- `myisamchk` is a table check/repair utility, not a row-query API. Repairing the user's original files would
  violate the copy-first boundary in any case.
- Current MySQL 8.4 `IMPORT TABLE` requires `.sdi` metadata from a compatible data-dictionary version. These
  EndNote fixtures have legacy `.frm`, not `.sdi`, so that current import mechanism is not applicable.
- MySQL 5.7 documents the old raw `.frm`/`.MYD`/`.MYI` data-directory workflow and a Windows `noinstall` ZIP,
  but it is an entire manually initialized server distribution—not an embeddable table reader.

Primary sources consulted: MySQL 8.4 `IMPORT TABLE` and MyISAM storage-engine manuals; MySQL 5.7 Windows
`noinstall` archive instructions; MariaDB's `mariadb-upgrade` documentation; Oracle's archived
`mysql/mysql-utilities` source.

### Disposable-engine live experiment

The only file transferred off the workstation was EndNote's public vendor-shipped X7 sample. The personal X1
fixture remained local and unread beyond the earlier structure/hash inspection. On the Debian Juno host, a
disposable, no-published-port `mariadb:10.11` official container (MariaDB `10.11.19`, image digest
`sha256:ce66c7be32a03aabe7241d0a10993a2db827ef652a35d25727d92a832ac8ef73`) received an extracted **copy** of
the sample tables in an isolated temporary datadir:

- the engine recognized `csort`, `jterms`, `misc`, `pdf_index`, `refs`, `refs_ext`, and `terms`;
- `misc` (81 rows), `pdf_index` (59), and `refs_ext` (59) were queryable directly;
- opening `refs` failed with MariaDB error 1707, `Table rebuild required`;
- `ALTER TABLE endnote.refs FORCE` on the disposable copy completed, after which `refs` returned 59 rows and
  exposed the expected 54 bibliographic columns (`id`, `reference_type`, author/year/title/.../access date);
- the container, extracted tables, temporary datadir, and uploaded archive were removed afterward.

No bibliographic row content was printed or retained. The container image cache contains no fixture content.

### Decision

**Technically feasible through an ephemeral real engine; not safe to implement as an ordinary parser yet.** A
hand-written MyISAM decoder is rejected. The smallest defensible legacy path is a separately owned, private,
temporary database-engine helper that operates only on bounded copies, has no network listener, performs an
explicit schema/version/upgrade preflight, exports parameterized bounded rows, then destroys its datadir.

That helper is a material packaging and security surface: Callosum would have to pin and distribute compatible
server binaries for Windows/macOS/Linux (or disclose an external prerequisite), supervise cleanup/crashes,
maintain license/source obligations, and prove both X1 and X7 schemas. Docker was appropriate for this research
experiment but fails the zero-configuration product goal and must not become the user-facing dependency.

Therefore Phase B moves from **unknown reader strategy** to **strategy proven, production implementation gated**.
Before code, approve and design the managed-engine packaging increment; obtain an `.enlx` fixture with a real
attached PDF; and separately obtain a modern SQLite-era fixture. Until then, existing RIS/EndNote XML imports
remain the safe metadata-only fallbacks, and unknown `.enlx` variants must remain unsupported rather than guessed.

## Folder/collection preservation, and a related already-inert gap

| Source | Folders/groups preserved? |
|---|---|
| EndNote Compressed Library (`.enlx`) | Yes, structurally — the `groups`/`misc` tables travel inside the zipped `.enl`/`sdb.eni`. |
| EndNote XML export | No — confirmed empirically; flat per-record export only. |
| Mendeley native export (BibTeX/RIS/EndNote XML/Word XML) | No — metadata-only per Elsevier's own docs. |
| Mendeley REST API | Yes — `/folders` is a first-class hierarchical resource distinct from the flat exports. |

Separately, and worth fixing in the same effort: callosum's **existing, already-shipped** native Zotero importer
(`app/backend/importers/zotero.py`, `_upsert_collections`) already writes Zotero collection structure into local
`collections`/`collection_papers` tables on every import — but no backend route or frontend file reads this data
today (confirmed via grep across `app/backend/api/routers/*.py` and `app/frontend/js/*.jsx`). It is written once
and permanently inert. The backlog's "folders/collections superseded by axes" decision was about *manual*
folder-creation inside callosum's own UI; it was never a decision about *imported* structure from another tool,
which is a different question and currently just wasted, unsurfaced data.

## Proposed shared design (not yet built): imported folders/groups → axes

Give all three sources (Zotero's already-populated-but-unread `collections`, EndNote's `.enlx` group-set
hierarchy, Mendeley's `/folders`) one consistent "import as axis" step: default to creating a manual **Curated
Axis** per top-level folder/group (the existing user-defined-container concept, not a scored one), with an
explicit opt-in to instead create a normal auto-scored axis from the same paper set. Additive only — no change
to the existing axis system's own semantics.

## Duplicate handling

All three import paths should run every incoming work through the same identity-matching discipline already
used elsewhere in the codebase (`find_existing_paper_by_identity` — the function the native Zotero importer and
the Zotero-citation `/citations/zotero/resolve` endpoint already share) before creating a new paper row, and
should resolve PDF attachment to an existing-vs-new paper the same way the native Zotero importer already does.
This directly addresses the "jillion duplicates to merge" complaint — it is reuse of an already-correct existing
pattern, not new design.

## Principles / APPROACH-AVOIDANCE boundary

Neither path produces a claim/signal/judgment about the literature — this is format migration, the same posture
already established for the Zotero-field-conversion feature ("a faithful format migration, not a claim about the
literature"). Neither touches the no-protected-store-reaching boundary: EndNote's path reads a file the user
explicitly exported and handed to callosum (the same copy-then-read posture the Zotero importer already uses,
not live decryption of a running application's database — the EndNote 1.19+-encryption workaround already
declined for the Mendeley bridge stays declined here too, unnecessary since `.enlx` is an explicit, unencrypted
export); Mendeley's path uses the vendor's own sanctioned OAuth consent flow, which is the *opposite* of reaching
into a protected store without permission.

## Security posture (both trigger the audit gate)

- **Mendeley**: new OAuth integration + new external API calls + a new file-ingestion path. Needs its own
  security-audit entry covering token storage (mirror the existing BYOK/ORCID write-only-over-the-wire pattern),
  the exact OAuth scope requested, and resource caps on paginated documents/folders/files calls.
- **EndNote**: a new file-ingestion path parsing an untrusted, reverse-engineered binary/ZIP format — squarely
  rule #4 territory. Needs ZIP entry-count/size bounds, parameterized (never dynamic) SQLite queries, a hard cap
  on documents/attachments per import, and the fail-closed schema-version check described above.

## What this research does NOT reopen

The separate, narrower, harder question of converting **live citation fields already embedded inside an
existing Word manuscript** authored with Mendeley Cite or EndNote Cite-While-You-Write remains correctly
declined — see `.claude/docs/research/2026-08-21_word_citation_migration_formats.md` (still current; a fresh
2026-08-29 research pass reconfirmed no vendor schema, no open-source reference implementation, and no
reverse-engineering write-up exists for Mendeley Cite's Word content-control payload, independently corroborated
by a competitor's own Feb-2025 admission of the same gap). This document is about whole-library import only.

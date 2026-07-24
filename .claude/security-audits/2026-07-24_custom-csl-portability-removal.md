# Security audit — personal CSL portability and removal (2026-07-24)

## Scope

Increment 367 adds local export and explicit removal to the personal CSL lifecycle. It adds
`GET /citations/styles/{style_id}/export`, `DELETE /citations/styles/{style_id}`, two Settings controls, and a
portable XML comment used only to preserve a Callosum-local style id across devices. It adds no external host,
dependency, database schema, background task, credential, PDF/library-text flow, or broader filesystem authority.

## Threat review

- **Path and identifier authority:** both routes accept a style id, never a path. Runtime lookup still requires
  the strict 120-character lowercase `[a-z0-9-]` grammar, a fixed bundled id or `custom-*`, a regular non-symlink
  file under the fixed local citation-style directory, and the existing 1,000,000-byte bound. Export filenames
  are formed only after that lookup from the same grammar-constrained id.
- **Export disclosure:** bundled export is refused. Personal export reads only the exact resolved CSL file and
  returns public formatting XML; no settings, credentials, manuscript text, library record, local directory, or
  arbitrary file content enters the response.
- **Portable marker:** export inserts one exact `<!-- callosum-style-id: custom-* -->` prolog comment. Import
  recognizes it only before the root, validates the captured id against the same strict grammar, strips it before
  all XML/CSL/citeproc validation and storage, and rejects malformed or misplaced reserved markers. The marker is
  honored only when its target id is unused; a collision with another canonical style falls back to a
  server-derived id, so it cannot overwrite by naming a target.
- **Deterministic ids:** new unmarked imports use a canonical-URL slug plus SHA-256 prefix, independent of install
  order in ordinary operation. Existing pre-increment unsuffixed ids remain valid; their export marker preserves
  them during migration to another local settings store.
- **Bounds:** the request envelope allows only 180 extra bytes for the export marker. After marker removal, the
  existing UTF-8 1,000,000-byte, 20,000-element, 100-level, DTD/entity, metadata, layout, dependency, and real
  citeproc checks still apply. Stored XML never contains the marker.
- **Removal:** bundled and unknown ids are refused. The active application default is refused until the user
  chooses another. An independent style with any installed dependent is refused until those dependents are
  removed, preventing local catalog orphaning. Successful deletion targets only the resolved non-symlink
  `custom-*` file and removes its id from Favorites and Recent styles.
- **Document safety:** Callosum cannot enumerate external Writer/Word/Docs files. Settings therefore requires a
  destructive confirmation stating that existing documents will not render until the same style is reinstalled,
  tells the user to export first, and disables removal while the style is the application default. The portable
  marker makes that backup restore the exact document-facing id.
- **Egress / SSRF:** export and removal are local file operations. Canonical HTTP(S) CSL identifiers are never
  fetched. URL import and repository installation remain separate, unimplemented networked slices.

## Negative-path proof

- Bundled export/removal returns 409; unknown personal ids return 404.
- Default removal returns 409 and leaves the file intact.
- Parent removal returns 409 naming installed dependent ids; dependent-first removal then succeeds.
- Successful removal deletes the file, catalog row, Favorite and Recent references; rendering the removed id
  returns 422.
- An exported legacy id reimports unchanged into a second isolated settings directory, stores marker-free XML,
  and reports `already_installed` on exact repeat.
- A marker placed inside CSL content is rejected without persistence.

## Result

**Security Audit: PASS**

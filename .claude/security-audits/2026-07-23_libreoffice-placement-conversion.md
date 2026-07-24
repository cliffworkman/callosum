# Security audit — LibreOffice citation placement conversion (2026-07-23)

## Scope

Increment 364 adds an explicit Writer command that converts eligible live citations between inline, footnote, and
endnote placement, optionally saving a separate ODF copy. It adds no endpoint, external host, dependency, secret,
database schema, background task, citation source, or privilege boundary.

## Threat review

- **Bounded input:** target style comes from the existing local style manifest; note placement is a fixed
  `footnote|endnote` choice. The copy filename is explicit local user input under the same trust boundary as
  Writer Save As.
- **Fail-closed inventory:** conversion rejects mixed/unsupported contexts, tracked changes, malformed/newer
  fields, duplicate IDs, damaged bibliography bounds, duplicate/malformed conversion state, multiple clusters per
  note, other ReferenceMarks sharing a note, and notes containing user prose.
- **Render-before-write:** the complete ordered target sequence and bibliography render through the existing
  loopback-only contract before an Undo context opens. A missing target render aborts without mutation.
- **Mutation authority:** only an explicit menu/macro action relocates fields. Writer service names are selected
  from fixed mappings; encoded citation identities are preserved, not regenerated from visible text.
- **Transaction / rollback:** one Writer Undo context contains state-mark creation, reverse-order relocation, and
  bounded bibliography rebuilding. Postconditions verify identity/order/count, placement, native note indexes,
  visible values, preferences, and bibliography. Exceptions trigger Undo and exact snapshot comparison.
- **Undo/Redo synchronization:** a zero-width Callosum state ReferenceMark is natively undoable. A scoped
  `XUndoManagerListener` reacts only to the exact conversion action title and only repairs Callosum-reserved
  bibliography bookmark variants around already-restored exact text while the Undo manager is locked.
- **Copy isolation:** converted-copy mode stores ODF locally, undoes the open document, clears Redo, and verifies
  the original snapshot. Save failure follows the same restoration check.
- **Egress / SSRF:** no new request or host exists. Citation rendering retains the adapter's fixed loopback path.
- **Persistence / supply chain:** state is non-sensitive document metadata. No package, database, or credential
  change is introduced.

## Negative-path proof

- Empty, same-target, mixed, malformed, duplicate, tracked-change, prose-bearing, and multi-cluster states abort
  before relocation.
- An injected failure on the second relocation restores the exact main text, fields, notes, bibliography,
  preferences, and state mark.
- Writer Undo/Redo restores the same complete snapshots for a successful conversion.
- Separate-copy mode reopens with target native notes while the source document remains byte-for-byte equivalent
  under the conversion snapshot.

## Result

**Security Audit: PASS**

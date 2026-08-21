# Zotero Integration Scope

## Purpose

Zotero is the first import target because it has a local SQLite database and filesystem attachment store.

## Planned Responsibilities

- Locate or accept a Zotero data directory.
- Copy `zotero.sqlite` before reading it.
- Read items, itemData, creators, collections, tags, notes, annotations, and attachments.
- Resolve storage attachment paths using `itemAttachments.linkMode`.
- Preserve Zotero item keys and collection membership.
- Avoid writing to Zotero's database or storage.
- Record missing linked files instead of dropping them.

## Zotero-Specific Notes

- `itemAttachments.linkMode` distinguishes imported stored files, linked files, and linked URLs. Import logic must branch on this field because linked files may not exist on the current machine.
- Zotero annotations live under their PDF attachment item, not directly under the bibliographic item. The adapter flattens that ownership while retaining the attachment identity.
- Highlight/underline rectangles use standard PDF bottom-left coordinates. The importer validates and translates them through the owning PDF's PyMuPDF page transform before storing Callosum's `pdf-points-top-left` boxes. Unsupported types, malformed/out-of-page rectangles, missing PDFs, and rotated pages keep raw Zotero position JSON but never receive a guessed exact overlay.
- Zotero attachments should feed Callosum's V1 default of copying available PDFs into the managed store. Link-in-place should remain explicit.

## Risks

- Zotero schema changes between versions.
- Attachments may be linked files rather than stored files.
- Better BibTeX citation keys may be present or absent.
- Zotero 8 native citation-key behavior may affect future imports.

## First Validation

Read a copied Zotero database and produce canonical local records with attachment paths.

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
- Zotero annotations live in the database, but annotation position data is Zotero-specific JSON keyed to Zotero Reader coordinates. Imported annotation locations need a translation layer before they can be mixed with Callosum's own PDF-space bounding boxes.
- Zotero attachments should feed Callosum's V1 default of copying available PDFs into the managed store. Link-in-place should remain explicit.

## Risks

- Zotero schema changes between versions.
- Attachments may be linked files rather than stored files.
- Better BibTeX citation keys may be present or absent.
- Zotero 8 native citation-key behavior may affect future imports.

## First Validation

Read a copied Zotero database and produce canonical local records with attachment paths.

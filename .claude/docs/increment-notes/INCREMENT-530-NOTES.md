# Increment 530 — Word Zotero field conversion

**Date:** 2026-08-29
**Scope:** close the last selected Word parity lift with an exact, fail-closed Zotero inline-field migration.

## Implemented

The Word task pane now exposes **Convert Zotero citations…**. A read-only WordApi 1.5 scan collects main-story,
footnote, and endnote fields plus main-story bookmark names. Pure logic accepts only Zotero's current first-party
inline citation and bibliography field contracts, parses bounded self-contained CSL JSON, retains grouped order and
per-item locator/label/prefix/suffix/author overrides, and reports unsupported modes without guessing.

After a count-specific confirmation, a second scan must match the first scan's deterministic snapshot. Distinct
embedded records then pass once through unchanged `POST /citations/zotero/resolve`, which matches existing local
papers first and creates metadata-only Zotero-origin rows only when needed. The adapter stamps the resulting
`callosum-<paper_id>` identity, writes existing Custom XML citation controls, deletes only the verified Zotero
fields, and invokes the unchanged Refresh/parser/citeproc lifecycle. One valid Zotero bibliography is replaced only
when no note-style, Bookmark-mode, malformed, or ambiguous Zotero material remains.

## Research basis

The implementation was not inferred from a sample document. Zotero's current official core plus Windows
integration revision `c0aa6e4bef039d94e17e81cb28b1fe9170c45b96` and Mac integration revision
`51faa4b21e1a433a6c0f69a4bdfc5a7882341f23` confirm the literal `ADDIN ZOTERO_` wrapper,
`ITEM CSL_CITATION`, `BIBL … CSL_BIBLIOGRAPHY`, and `ZOTERO_BREF_` contracts. Microsoft's current Word
JavaScript API documentation confirms field code/result and WordApi 1.5 deletion. No Zotero code was copied.

## Safety boundary

Opened document fields are untrusted: code is capped at 1 MiB, citations at 100 items, a run at 500 fields and 300
distinct works, and malformed/foreign/oversized content remains untouched. The relay adds only the exact bounded
resolver path and retains bearer auth. There is no provider/model call or fallback. Office.js cannot create a backup
or guarantee one-step rollback; the confirmation tells the author to use Save As and explains that local library
rows created before a later Word batch failure are outside Word Undo.

## Verification

Pure parsing, classification, snapshot, canonical deduplication, grouped override restoration, result validation,
bounds, static Office glue, exact tunnel ingress, and the pre-existing resolver contract are automated: Word
pure/static **90/90**, focused pytest **55 passed**, and the full repository suite **2568 passed, 3 skipped** in
993.85s. Ruff, Bandit, Tach, JavaScript syntax, line budget, QA coverage, changed-file pre-commit, privacy/path,
website review, and diff checks passed. Real Word field mutation cannot be driven here and remains explicitly
deferred to the consolidated manual checklist in QA route 34.

## Deliberate non-scope

Note-style and Bookmark-mode Zotero citations remain Zotero-owned; a partial conversion never removes their
bibliography. Mendeley Cite and EndNote fields remain declined because their available vendor documentation does not
establish an equivalent complete/versioned self-contained payload contract. No prompt, parser, citeproc rule,
provider behavior, style semantics, or production database schema changed.

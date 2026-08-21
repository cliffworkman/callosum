# Word citation migration formats — Mendeley Cite and EndNote

**Date:** 2026-08-21  
**Scope:** backlog #57 Phase 5; research gate only

## Decision

Do **not** implement a Mendeley Cite or EndNote Word-document converter from the evidence currently available.
First-party documentation establishes the outer Word mechanisms, but does not publish a sufficiently complete,
versioned payload contract for lossless conversion:

- current Mendeley Cite citations are Word **content controls**;
- current EndNote Cite While You Write citations are Word **fields**, including the `ADDIN EN.CITE` family and an
  embedded Traveling Library;
- neither vendor's documentation located in this review specifies the complete machine-readable citation payload,
  its versioning, all item/locator/affix options, or safe relationships between every relevant OOXML part.

That is enough to identify foreign live citations, but not enough to decode, rewrite, or delete them safely. A
converter built from conflicting third-party observations or one sample document could silently lose grouped-cite
membership, locators, prefixes/suffixes, suppressed-author state, record metadata, or future-version data. For a
scholarly manuscript, leaving a field untouched is preferable to manufacturing a plausible conversion.

## Mendeley Cite evidence

Elsevier's current support documentation says that Mendeley Cite inserts citations into a Word **content control**.
Its documented flattening workflow removes the Mendeley code by removing content controls. The normal insert/edit
guides explain user-visible citation behavior.

What those first-party pages do **not** publish is the exact content-control tag, whether and how a payload is split
between the tag and an OOXML custom part/web-extension part, a JSON/XML schema, encoding rules, schema versions, or
the full grouped-citation option model. Third-party implementations found during the spike make conflicting claims
about where the authoritative metadata lives. They are useful leads for a future fixture-backed investigation, not
a compatibility contract.

Primary sources reviewed:

- [Why is my citation inserted into a content control?](https://service.elsevier.com/app/answers/detail/a_id/34155/c/16076/supporthub/mendeley/)
- [How do I remove the Mendeley code from a document in Mendeley Cite?](https://www.elsevier.support/mendeley/answer/how-do-i-remove-the-mendeley-code-from-a-document-in-mendeley-cite)
- [How do I insert citations into my document with Mendeley Cite?](https://service.elsevier.com/app/answers/detail/a_id/28672/supporthub/mendeley/p/10524/)
- [How do I edit or delete a citation with Mendeley Cite?](https://service.elsevier.com/app/answers/detail/a_id/28668/supporthub/mendeley/p/10524/)
- [Importing from Mendeley into Zotero](https://www.zotero.org/support/kb/mendeley_import), which explicitly says
  Zotero cannot read citations created with Mendeley Cite.

## EndNote evidence

Clarivate's current EndNote documentation says formatted Cite While You Write citations use Word field codes and
carry a Traveling Library containing most reference data. Its troubleshooting documentation explicitly identifies
garbled `{ ADDIN EN.CITE ... }` code. The documented safe workflows are EndNote-owned operations: unformat citations,
remove field codes on a copy, or export references from the Traveling Library.

What the first-party pages do **not** publish is a normative `EN.CITE` payload grammar or XML schema, the full
citation-item/options vocabulary, schema/version negotiation, or the relationship between long field payloads and
any nested `EN.CITE.DATA` representation. The manual specifically warns users not to modify field codes directly.

Primary sources reviewed:

- [Field Codes](https://docs.endnote.com/docs/endnote/2025/v1/windows/en/content/09word/field_codes.htm)
- [Garbled ADDIN EN.CITE Code](https://docs.endnote.com/docs/endnote/2025/v1/windows/en/content/appendices/garbled_addin_en.cite_code.htm)
- [The Traveling Library](https://docs.endnote.com/docs/endnote/2025/v1/windows/en/content/09word/the_traveling_library.htm)
- [Removing Field Codes](https://docs.endnote.com/docs/endnote/2025/v1/windows/en/content/09word/removing_field_codes.htm)
- [Unformatting Citations](https://docs.endnote.com/docs/endnote/2025/v1/windows/en/content/09word/unformatting_citations.htm)

## Evidence required before implementation

Reopen the converter only when at least one of these exists for each source format:

1. a vendor-published, versioned payload/schema contract covering grouped citations and per-item options; or
2. a vendor-supported export/conversion API whose output has a documented contract; or
3. explicit maintainer approval for a narrower experimental importer backed by a legally shareable fixture corpus
   generated across current application versions, with fail-closed version detection and byte-preserving fallback.

Any future implementation must operate on a copy, never mutate unsupported fields, preserve the original OOXML
parts for rollback, cap ZIP/XML/payload resource use, and prove round-trip behavior for grouped citations,
locators, affixes, author suppression, Unicode, missing library records, and malformed input. It also needs a real
Word manual-verification matrix because Office.js behavior is not fully headless-testable in this repository.

## Supported user path today

Callosum can migrate the **library** first (EndNote via documented RIS; Mendeley via Zotero's documented bridge),
then insert new Callosum citations with its Word add-in. Existing Mendeley Cite and EndNote live fields remain
owned by their originating tools. Users who need static submission text should use the originating tool's own
document-copy/flatten workflow; that is not live-citation migration and must not be presented as such.

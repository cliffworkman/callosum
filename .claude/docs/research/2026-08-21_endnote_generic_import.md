# EndNote → generic citation import research — 2026-08-21

## Question

Can backlog #57 Phase 2 honestly use Callosum's existing BibTeX/RIS/CSL-JSON importer for a current EndNote
library, and does EndNote document an export convention the existing parser mishandles?

## Primary-source findings

1. EndNote 2025's own transfer documentation lists **BibTeX**, **BibTeX Using EN Label Field**, and
   **RefMan (RIS) Export** among the included output styles intended for transfer to other programs. EndNote's
   export instructions specifically call RefMan (RIS) “a good choice” when the destination format is uncertain.
   Sources: [EndNote 2025 — Exporting References for Database Import](https://docs.endnote.com/docs/endnote/2025/v1/windows/en/content/15independentbibs_export/exporting_references_for_database_import.htm),
   [EndNote 2025 — Exporting for Other Bibliographic Applications](https://docs.endnote.com/docs/endnote/2025/v1/macos/en/content/15independentbibs_export/export_biblio_apps.htm).
2. EndNote's export is text-only: its supported-formats documentation says images are not included. That matches
   Callosum's existing modal promise that generic citation-file import produces metadata-only papers, not PDFs.
   Source: [EndNote 2025 — Supported Formats for Export](https://docs.endnote.com/docs/endnote/2025/v1/macos/en/content/15independentbibs_export/supported_formats.htm).
3. EndNote Web exposes selected-reference export in RIS, and Clarivate documents that EndNote Online may emit RIS
   with a `.txt` extension. Callosum's picker already accepts `.txt` and `detect_format()` recognizes RIS by its
   tags, so no filename/format control change is needed. Sources:
   [EndNote 2025 — EndNote Web/Online](https://docs.endnote.com/docs/endnote/2025/v1/windows/en/content/22enweb/endnote_online.htm),
   [Web of Science — adding/removing profile publications](https://webofscience.help.clarivate.com/en-us/Content/wos-researcher-profile-adding-removing-publications.html).
4. Clarivate's current RIS acceptance contract recognizes author tags `AU/A1/A2/A3/A4`, title tags
   `TI/T1/BT/CT/T3/TT/ST`, journal tags `T2/J1/J2/JF/JO`, year tags `DA/Y1/Y2/PY`, and `CPAPER` conference
   records. Callosum lacked `A4`, several title aliases, `J1`, `Y2`, and the `CPAPER` type mapping. The parser now
   accepts that documented alias set; its synthetic regression fixture cites the contract directly.
5. The current EndNote manual does not publish the literal BibTeX output templates. Examples on EndNote's own
   community site show brace-delimited entries, but that is not enough to prove every current/default/custom
   style's byte shape. No primary source found in this review establishes the handoff's suspected
   `@ARTICLE(...)` EndNote convention. Consequently this slice does **not** add speculative parenthesis parsing
   or claim compatibility with arbitrary user-customized EndNote output styles. RIS is the documented path.

## Repository evidence and boundary

- No genuine EndNote-generated `.ris`, `.txt`, `.bib`, `.xml`, `.enl`, or `.enlx` sample exists under
  `tests/fixtures/`, `integrations/`, or the repository's tracked files as of this review.
- `tests/test_citation_import.py` already exercised ordinary RIS (`TY/AU/TI/PY/T2/...`) through both parser and
  `/library/import`. Increment 486 adds the missing Clarivate alias contract, explicitly labeled a synthetic
  stand-in.
- EndNote XML is proprietary and not accepted by the generic importer. The recommended handoff is deliberately:
  **EndNote → File/Export → RefMan (RIS) Export → Callosum + Add/Import file**.

## Outcome

**Feasible and narrowly hardened, but Phase 2 remains partial.** The documented RIS route needs no new endpoint,
job, or UI. The parser now covers the current Clarivate alias set and Help gives the shortest supported export
path. The backlog's literal completion condition—verification against a real EndNote-created export—cannot be
satisfied by this synthetic fixture and remains open for Cliff/Claude to close with an actual file.

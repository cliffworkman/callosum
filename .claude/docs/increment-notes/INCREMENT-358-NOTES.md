# Increment 358 — LibreOffice refresh current section

## Context

P1 roadmap item #13 calls for current-section refresh in large manuscripts. “Section” needed a stable Writer
definition before implementation: paragraph style names are localizable and arbitrary, while Writer's documented
`OutlineLevel` is semantic document structure.

## Section contract

- `OutlineLevel` 0 is body text; levels 1–10 are headings.
- The current section starts at the nearest preceding heading and includes nested lower-ranked headings.
- It ends at the next heading of the same or higher rank.
- Text before the first heading is a preamble section; a heading-free document is one section.

This follows the
[LibreOffice ParagraphProperties contract](https://api.libreoffice.org/docs/idl/ref/servicecom_1_1sun_1_1star_1_1style_1_1ParagraphProperties.html)
and [Writer heading model](https://help.libreoffice.org/latest/en-GB/text/swriter/01/06060000.html).

## Implemented

- Added **Refresh current section** to the Writer Callosum menu and macro exports.
- Enumerated main-text paragraphs, read outline levels through `XPropertySet` with a compatible direct-attribute
  fallback, and bounded the containing heading subtree with Writer range comparisons.
- Selected only recognized Callosum marks whose anchors begin inside that range.
- Reused full-document citeproc rendering for numbering/disambiguation correctness and the existing targeted
  UndoManager write plan for exact-surface mutation.
- Other sections and the managed bibliography remain untouched. The document-wide citation-pending flag remains
  set because a section refresh cannot prove the rest of the document is current.
- A cursor outside comparable main text or a citation-free section reports the condition without rendering.
- Extension version bumped 0.7.0 → 0.8.0 and the `.oxt` rebuilt.
- Hardened the real-UNO harness with a unique per-run profile, deleted only after its own processes stop.

## Verification

- `pytest -n auto -q` — **1465 passed, 1 skipped**.
- Targeted LibreOffice adapter/install/OXT tests — **80 passed**.
- Ruff check/format and OXT build — clean.
- `python adapters/libreoffice/run_roundtrip.py` — real headless LibreOffice, isolated installed `.oxt`, and real
  seeded Callosum server. The new case uses actual Writer paragraph breaks plus Heading 1/Heading 2 styles and
  proves parent+nested inclusion, preamble/next-peer/bibliography isolation, and retained global pending state.

## Gates

- **Principles / governance:** non-triggering. This is deterministic document formatting and makes no scholarly
  claim, ranking, quality judgment, or worker assessment.
- **Security:** audit `2026-07-23_libreoffice-section-refresh.md` is **PASS**.
- **QA:** no web-app surface changed. Pure boundary tests plus the required real-UNO harness cover the authority.

## Manual verification debt

Cliff should install 0.8.0 and click **Refresh current section** from a body paragraph under nested headings, a
preamble, and a citation-free section. Automated Writer proves behavior but not rendered menu appearance. Existing
citations-panel and bibliography-editing click-through debt remains open.

## Next

The remaining #13 items are document-event observation/immediate reopen state, progress/cancellation, and
incremental rendering. The event-listener lifecycle is the next bounded slice; progress/cancellation requires a
larger rendering protocol rather than another menu wrapper.

# Increment 519 — Word citation payloads behind short Custom XML references

**Date:** 2026-08-28
**Scope:** Microsoft Word add-in document storage only; no backend/provider/citeproc/UI behavior change.

## Why this increment came first

The Word parity handoff surfaced an approved 2026-08-18 decision that inc 509's grouped-citation composer had
not carried through: the original inc-165 format embedded the full `{items:[CSL-JSON...]}` payload, base64, in
each Content Control `.tag`. A grouped citation therefore made the tag grow with full author lists, titles,
abstracts, and occurrence overrides. Native note placement would add more operations on top of that format, so
the storage seam was corrected before beginning the larger note-style increment.

Microsoft's current Office.js surface provides document Custom XML Parts in WordApi 1.4, including add, opaque
part ID, get/get-or-null, `getXml`, `setXml`, and delete. The project therefore uses that existing document-native
store rather than inventing a backend document registry.

Sources consulted:

- [Word.CustomXmlPart](https://learn.microsoft.com/en-us/javascript/api/word/word.customxmlpart?view=word-js-preview)
- [OfficeDev Custom XML Part sample](https://github.com/OfficeDev/office-js-snippets/blob/prod/samples/word/50-document/manage-custom-xml-part.yaml)
- [Word API requirement sets](https://learn.microsoft.com/en-us/javascript/api/requirement-sets/word/word-api-requirement-sets?view=word-js-preview)

## Storage contract

New citation Content Control tag:

```text
CALLOSUM_CITATION xml:<encoded Word CustomXmlPart.id>
```

Referenced XML part:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<callosumCitation xmlns="https://callosum.app/schemas/word-citation/1" version="1">
  <payload encoding="base64">...exact UTF-8 JSON {"items":[...]}...</payload>
</callosumCitation>
```

The tag is bounded by the opaque part ID rather than scholarly payload size. The XML decoder accepts only the
exact namespace/version/payload shape and fails closed on missing, foreign, malformed, or empty data.

## Compatibility and lifecycle

- **New insert:** add a Custom XML Part, then tag the citation Content Control with its opaque ID.
- **Edit current citation:** update the same part via `setXml`; the stable tag reference does not change.
- **Edit legacy citation:** create a part and retag after the updated payload exists.
- **Refresh:** resolve all parts before rendering; valid legacy base64 tags migrate at this already-mutating
  boundary. If copy/paste produced two controls referencing the same part, every duplicate after the first gets
  its own cloned part so later edits stay citation-local.
- **Diagnostics/panel:** resolve parts read-only. A missing or invalid part is malformed; it is never guessed.
- **Delete:** delete the part only when no other body citation references it.
- **Flatten:** keep rendered text, delete every Callosum Content Control, and delete each referenced citation part.
- **Unsupported host:** operations requiring the new store fail with an explicit WordApi 1.4 requirement rather
  than falling through to an undefined Office.js property.

Legacy `CALLOSUM_CITATION <base64>` tags remain readable. No document migration runs on load, diagnostics, or
panel open. Migration occurs only through Refresh or editing, where the document is already expected to change.

## Scientific and privacy boundaries

The resolved `items` arrays reach the existing `/citations/render-document` request unchanged. Prompts,
providers, citeproc behavior, CSL semantics, paper-ID stamping, reference filtering, and bibliography rendering
do not change. The XML is document-local and contains the same metadata the document already carried; no new
egress, credential, persistence service, endpoint, dependency, or telemetry exists.

## Verification

- `node --check adapters/word/taskpane.js` — PASS.
- `node --check adapters/word/taskpane_core.js` — PASS.
- `node --test adapters/word/taskpane_core.test.js` — **38/38 PASS**.
- Focused `pytest -n auto -q tests/test_word_addin.py tests/test_access_control.py tests/test_citations.py` —
  **82 passed** in 2m32s.
- Full `.venv\Scripts\python.exe -m pytest -n auto -q` — **2563 passed, 3 skipped** in 20m32s.
- Ruff check + format — PASS (**819 files already formatted**).
- Bandit project wrapper — PASS.
- Tach — PASS.
- 569-file line-budget gate — PASS.
- Targeted pre-commit — PASS after its first pass removed trailing whitespace/fixed EOF in this notes file.
- QA surface map — **430/430 gated API surfaces**; six report-only frontend items remain in the pre-existing
  synthesis-Overview surface, unrelated to Word; no new uncovered surface.
- `git diff --check` — PASS.

Pure tests cover legacy round-trip, short opaque references, Unicode XML round-trip, exact schema/version
rejection, missing-part diagnostic representation, and current-record panel grouping.

## Honest verification boundary

No available agent can drive real Word. The Office.js glue—Custom XML add/get/set/delete, legacy migration,
copy/paste de-aliasing, and cleanup—is **not yet live-verified** on desktop Word or Word on the web. It is based on
Microsoft's current WordApi 1.4 contract and official sample, but must not be described as live-proven.

Cross-document copy/paste behavior is especially important to check live: if Word copies a Content Control tag
without its document Custom XML Part, the destination correctly fails closed and Document diagnostics reports a
malformed citation, but portability would need a follow-up design rather than guessed recovery.

## Manual Word verification owed

1. Insert a grouped citation with Unicode metadata; inspect that its tag is short and the citation refreshes.
2. Edit it; verify the tag reference remains stable and content changes.
3. Open an old base64-tag document and Refresh; verify migration without citation-text change.
4. Copy/paste within one document, Refresh, edit one copy; verify the other does not change.
5. Delete one citation and Flatten a copy; verify no live controls/associated parts remain.
6. Run Document diagnostics after intentionally removing a referenced part; verify fail-closed malformed status.
7. Repeat the basic path in Word on the web.
8. Copy a live citation to another document and record whether Word carries the XML part; do not assume it does.

## Follow-up

After live storage verification, resume the handoff's P1 priority: native note-style footnote/endnote placement,
including note-body scanning and one-based native note indexes. Do not claim note support in this increment.

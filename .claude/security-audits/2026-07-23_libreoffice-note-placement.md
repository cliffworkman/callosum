# Security audit — LibreOffice footnote/endnote placement (2026-07-23)

## Scope

Increment 363 adds a bounded document-local note-placement property, a packaged Writer menu action, and native
Endnote creation for note-family citations. It adds no endpoint, dependency, external host, secret, database
schema, filesystem path, background task, or new citation source.

## Threat review

- **Input validation:** placement accepts only `footnote` or `endnote`. Interactive users choose from a fixed
  dropdown; malformed stored legacy values default to footnotes.
- **Mutation authority:** a native note is created only during an explicit citation insertion with a note-family
  style active. The chosen service is selected from a fixed two-value mapping, never dynamically imported or
  interpolated from untrusted input.
- **Existing documents:** changing placement inventories live citation contexts first. Any incompatible,
  unsupported, or mixed non-inline placement aborts before the document property changes.
- **Document scope:** the existing Callosum ReferenceMark payload and text-container operations are reused.
  Endnote access uses Writer's own ordered `XIndexAccess` collection.
- **Correctness:** citeproc receives the complete ordered citation set and the native one-based endnote index.
  The adapter does not synthesize note-state behavior itself.
- **Egress / SSRF:** no new request or host is introduced. Rendering retains the existing loopback-only path.
- **Secrets / persistence / supply chain:** the saved placement is non-sensitive document metadata. No package
  dependency or database persistence changes; the OXT version changes only.

## Negative-path proof

- Unknown placement values are rejected; malformed persisted values fall back to footnotes.
- Existing endnotes prevent switching the document preference to footnotes, and vice versa.
- The rejected operation leaves the saved placement unchanged.
- Existing inline citations cannot become notes through this selector.
- Real Writer proves cursor lookup and flatten remain bounded to the endnote's own text container.

## Result

**Security Audit: PASS**

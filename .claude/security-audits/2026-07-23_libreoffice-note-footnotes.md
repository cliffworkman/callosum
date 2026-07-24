# Security audit — LibreOffice note citations in Writer footnotes (2026-07-23)

## Scope

Increment 362 adds a bounded optional `noteIndex` to the existing local citation-render request and allows the
LibreOffice adapter to create and manage native Writer Footnote text containers for note-family CSL styles. It
adds no endpoint, dependency, external network host, secret, persistence schema, filesystem path, background
task, or new citation source.

## Threat review

- **Boundary validation:** `noteIndex` is a strict integer from 0 through 5000. Negative, oversized, fractional,
  and boolean values are rejected at the API boundary and again in the render layer.
- **Egress / SSRF:** rendering still uses the existing configured loopback Callosum endpoint and bundled local
  citeproc sidecar. Note placement performs no request and introduces no external host.
- **Document trust boundary:** only recognized Callosum ReferenceMarks are scanned. Their containing Writer text
  is classified through Writer's own text-range API; unsupported, mixed, or endnote contexts fail closed.
- **Mutation authority:** a footnote is created only by an explicit citation insertion while a note style is
  selected. An incompatible style change validates all existing fields before mutating either document content
  or the document-local preference.
- **Deletion scope:** deletion removes the containing footnote only when the live citation was removed and the
  note has no remaining text. User-authored note prose is retained.
- **Flattening / rollback:** flatten removes only recognized live ReferenceMarks and retains their visible note
  text. Existing transactional refresh/rollback behavior remains in force for rendered updates.
- **Correctness:** citeproc still receives the complete ordered citation set. Supplying native one-based note
  positions preserves first/subsequent-note state instead of manufacturing note strings client-side.
- **Secrets / filesystem / supply chain:** no secret or filesystem access is added. No dependency or package
  manifest changes; the extension version changes only.

## Negative-path proof

- Invalid `noteIndex` types and bounds return 422.
- An inline document cannot be switched to a note style, or a note document to an in-text style, without an
  explicit future conversion path.
- Endnotes and mixed citation placements are rejected rather than partially rendered.
- A cursor outside the main document text cannot create an accidental nested footnote.
- Deleting a citation from a note containing other text does not delete that note.
- Real Writer proves a refused style switch leaves the saved style unchanged.

## Result

**Security Audit: PASS**

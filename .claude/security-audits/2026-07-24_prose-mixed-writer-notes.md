# Security audit - prose-mixed Writer notes (2026-07-24)

## Scope

Increment 372 changes only where an explicit LibreOffice **Add citation...** action places an existing live
citation payload. It adds no endpoint, dependency, external host, file path, secret, persistence schema, or
background task.

## Threat review

- **Cursor authority:** Writer's own text-range relationships classify the caret as main document text, the
  configured native note placement, the other note placement, or unsupported text. No string or UI label is
  trusted to identify the destination.
- **Fail-before-mutation:** a caret inside the wrong note placement or unsupported Writer text raises before a
  note, ReferenceMark, document preference, or render request is created.
- **Mutation boundary:** successful insertion writes one recognized Callosum ReferenceMark at the explicit caret.
  It does not rewrite neighboring prose or other fields. Refresh and deletion continue to target recognized
  ReferenceMarks only.
- **Loss prevention:** placement conversion still rejects notes containing multiple live clusters or user prose.
  The refusal snapshot is identical before and after the call; no partial conversion is attempted.
- **Egress:** the adapter still calls only the user-configured loopback Callosum server. This change adds no fetch
  or data-egress path.
- **Injection / output encoding:** citation payloads retain the existing bounded JSON field schema and rendered
  text sanitization. User prose is never parsed as payload, UNO command, Python, or shell input.
- **Resource caps / secrets / supply chain:** existing document-render limits are unchanged. No secret or
  filesystem access and no dependency change were introduced.

## Negative-path proof

- A pure classifier test accepts main text and matching notes, but rejects a mismatched endnote/footnote and an
  unsupported text container.
- Installed OXT `0.17.0` inserts two distinct citation identities into one footnote and one endnote through the
  real Writer view caret. Both share native `noteIndex=1`.
- Idempotent refresh preserves the complete prose-bearing note string.
- Placement conversion refuses each prose-bearing multi-cluster note and leaves the document snapshot unchanged.
- Deleting the first cluster leaves the second field, note, and prose; deleting the last field still leaves the
  prose-bearing native note.

## Result

**Security Audit: PASS**

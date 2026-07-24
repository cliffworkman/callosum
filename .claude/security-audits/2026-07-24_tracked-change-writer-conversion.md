# Security audit - tracked-change-aware Writer conversion (2026-07-24)

## Scope

Increment 373 narrows the existing blanket tracked-change refusal for explicit LibreOffice placement conversion.
It adds no endpoint, dependency, external host, file path, secret, persistence schema, or background task.

## Threat review

- **Authoritative ranges:** redlines are enumerated through Writer's `XEnumerationAccess`; overlap uses the
  `RedlineStart`/`RedlineEnd` text ranges Writer exposes. The redline object itself is never assumed to implement
  a readable `XTextRange`.
- **Complete mutation inventory:** preflight includes every source citation field, full source citation note and
  main anchor, conversion-state marker/insertion point, and managed bibliography range/insertion point.
- **Conservative boundaries:** non-empty spans use half-open overlap. A collapsed tracked or managed point is
  treated as conflicting when it touches the other span, avoiding anchor-gravity guesses.
- **Fail-before-mutation:** missing, incomparable, cross-container, or otherwise unreadable redline endpoints
  refuse before target rendering, preference changes, or Writer mutation.
- **No implicit review decision:** conversion never accepts or rejects a tracked change. When recording is on,
  it is paused only around Callosum's atomic relocation and restored before the transaction commits.
- **Verified preservation:** stable redline identifier, type, author, comment, description, selected range text,
  and container class are included in exact post-conversion and rollback signatures.
- **Rollback:** any structural or redline-signature mismatch enters the existing Writer Undo rollback. Track
  Changes recording is restored after successful conversion and after rollback.
- **Egress / injection / resources:** citation rendering still uses the configured loopback Callosum service and
  bounded JSON field schema. No new network, markup-evaluation, filesystem, secret, or dependency surface exists.

## Negative-path proof

- Pure tests cover overlapping, adjacent, and collapsed spans; unrelated and managed redlines; unreadable-range
  fail-closed behavior; and recording-state suspension/restoration.
- Installed OXT `0.18.0` preserved three real Writer redlines: a main-text insertion, main-text deletion, and an
  insertion inside an ordinary footnote. Identity/type/description/text/context remained exact through
  inline-to-footnote conversion and Writer Undo/Redo, with recording still enabled.
- A real tracked insertion inside a live ReferenceMark was detected by exact range overlap and refused before
  mutation; the conversion snapshot and Track Changes setting remained unchanged.

## Result

**Security Audit: PASS**

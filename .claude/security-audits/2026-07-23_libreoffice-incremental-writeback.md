# Security audit — LibreOffice incremental write-back (2026-07-23)

## Scope

Increment 361 compares complete citeproc output with live managed Writer ranges and skips writes whose rendered
result is already current. It adds no endpoint, dependency, network host, secret, persistence schema, filesystem
path, background task, or new mutation authority.

## Threat review

- **Egress / SSRF:** the existing configured loopback render request remains unchanged and still receives the
  complete ordered citation set. Delta planning makes no request and introduces no external host.
- **Input / parsing:** comparisons operate on bounded recognized ReferenceMark text and the text between the two
  managed bibliography bookmarks. They neither execute nor interpolate document content.
- **Mutation authority:** the planner can only remove writes from the existing requested refresh transaction.
  It cannot add a target outside the already selected citation surface.
- **Damaged bounds / manual edits:** a missing bibliography endpoint, invalid range, or exact-text mismatch is
  treated as not current and follows the existing transactional rebuild path.
- **Explicit user intent:** providing a bibliography cursor location bypasses the no-op optimization so an
  explicit move is never silently skipped.
- **Correctness:** citeproc rendering is not incremental or cropped. Full-document context preserves numbering,
  disambiguation, and membership semantics before local write comparison.
- **Undo / rollback:** an empty delta returns before opening UndoManager. Any nonempty delta retains the existing
  single-group write, exception rollback, and post-rollback verification.
- **Secrets / filesystem / supply chain:** no secret or filesystem access is added. No dependency or package
  entry changes; the extension version changes only.

## Negative-path proof

- Exact current citation and bibliography output produces no Writer mutation and no UndoManager context.
- A single stale citation schedules exactly one citation write.
- Stale bibliography text schedules exactly one bibliography rebuild.
- A damaged bookmark pair is never accepted as current.
- An explicit bibliography move still rebuilds even when the text already matches.

## Result

**Security Audit: PASS**

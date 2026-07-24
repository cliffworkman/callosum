# Security audit - CSL source editor (2026-07-24)

## Scope

Increment 370 adds localhost read, validate, and save routes for the source of an independent personal CSL style,
plus a Settings modal that calls them. It adds one guarded local file replacement and one local provenance update.
There is no database migration, dependency, credential, external host, background task, or LLM path.

## Threat review

- **Authorization and scope:** the existing app middleware covers all three API routes. Style ids still resolve
  only through the server-owned bundled or personal-style stores. Source access rejects bundled styles,
  dependent personal styles, unknown ids, paths, and URLs; users must create an independent personal duplicate.
- **XML and execution:** request bodies retain the 1,000,000-character API cap. The existing candidate validator
  rejects DTD/entities and excessive depth/element counts, parses with external entities and network access
  disabled, applies the official CSL 1.0.2 RELAX NG and Schematron macro checks, and executes the candidate through
  the local citeproc sidecar before save. An edit cannot turn an independent style into a dependent one.
- **Identity and integrity:** save requires the candidate canonical CSL id to equal the installed id. It also
  requires the exact SHA-256 revision returned when the editor opened, so a concurrent or out-of-band change
  returns 409 instead of being overwritten. The revision is checked both before validation and again immediately
  before replacement, so a change that lands during citeproc validation also wins. The custom-style writer uses
  an atomic same-directory replacement. If provenance recording fails, the previous XML is restored.
- **Preview and output:** unsaved preview receives only the candidate CSL, selected locale, and fixed fictional
  records. It does not read papers, PDFs, manuscripts, credentials, or arbitrary files. React renders validation
  messages and preview output as text/normal React content.
- **Egress and resources:** validation, preview, and save make no network request. Input, XML tree, and citeproc
  process bounds are inherited from the audited import lifecycle. The editor and file mutation share a reentrant
  in-process lock; provenance stays in its bounded fixed sidecar.

## Negative-path proof

- Tests prove bundled and dependent source access returns 409.
- Tests prove a changed canonical id and dependent conversion fail without mutating the installed source.
- Tests prove validation changes the draft preview without writing the file.
- Tests prove save retains the local and canonical ids, records the edit timestamp, changes real render output,
  rejects reuse of a stale revision, and preserves a newer source written during validation.

## Result

**Security Audit: PASS**

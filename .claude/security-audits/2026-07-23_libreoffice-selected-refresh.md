# Security audit — LibreOffice selected-citation refresh (2026-07-23)

## Scope

Increment 357 adds a fixed **Refresh citation at cursor** Writer command. It resolves an existing Callosum
ReferenceMark at the caret, sends the same full-document render request used by existing refresh commands, and
transactionally writes back only that mark. No backend endpoint, external integration, dependency, file path, or
document schema is added.

## Threat review

- **Input validation / output encoding:** the target must be a ReferenceMark already accepted by
  `scan_citations_in_order`; malformed, foreign, and unsupported-version marks are excluded. Rendered output
  follows the existing plain-text `_replace_mark_text` path.
- **Injection:** the menu dispatches the fixed
  `service:com.callosum.cite.Dispatcher?refreshSelectedCitation` action. Packaging tests require every declared
  action to exist in the local registry. No dynamic code, SQL, shell, HTML, or user-controlled dispatch is added.
- **SSRF / external calls / egress:** the command uses the already-configured Callosum base URL and existing
  citation-render endpoint. It adds no host or public-service path and sends no data beyond the document citation
  payload already used by full and partial refresh.
- **Secrets:** none read, stored, displayed, or transmitted.
- **Resource caps:** one bounded document scan and one existing full-context citeproc render. Write-back contains
  exactly one mark and no bibliography entries.
- **File-path safety / supply chain:** no filesystem operation, dependency, or new package entry. Extension
  version 0.7.0 uses the existing `.oxt` builder.
- **State integrity:** the existing UndoManager transaction and rollback verification cover the one-mark plan.
  The command does not clear the document-wide citation-dirty flag, avoiding a false-clean state for unrefreshed
  marks.

## Negative-path checks

- Unit coverage proves the mark under the caret is the only requested target and that a caret outside a
  recognized mark causes no render or mutation.
- The real Writer round trip deliberately corrupts two citation texts, refreshes the first at the caret, and
  proves the second citation and bibliography remain unchanged while the global pending flag remains set.
- Existing transactional fault-injection coverage continues to prove failed write-back rolls the document back.

## Result

**Security Audit: PASS**

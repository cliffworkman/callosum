# Security audit — LibreOffice dirty-state indicator (2026-07-23)

## Scope

Increment 350 stores two document-local refresh-pending flags, surfaces them in a Writer Infobar, and adds a
fixed **Refresh pending** extension action that renders exactly the flagged surfaces. It also reports the flags in
existing document diagnostics. No backend endpoint, external integration, dependency, or file path is added.

## Threat review

- **Input validation / output encoding:** both flags are fixed `"0"`/`"1"` user properties written only by the
  adapter. The Infobar copy is fixed application text; no citation metadata is interpolated into the UI.
- **Injection:** the Infobar button URL is the fixed
  `service:com.callosum.cite.Dispatcher?refreshPending` action. A packaging test resolves that suffix against the
  local action registry. No SQL, shell, markup, or dynamic dispatch string is introduced.
- **SSRF / external calls / egress:** the action only invokes the existing citeproc render call against the
  already-configured callosum base URL. It adds no host, public service, browser navigation, or LLM path. The
  request still contains only the citation document already sent by existing refresh commands.
- **Secrets:** none read, stored, displayed, or transmitted.
- **Resource caps:** one fixed-size Infobar and two scalar properties per document. Refresh pending makes one
  existing full-context citeproc request and mutates only flagged surfaces; there is no polling, listener,
  background task, or unbounded collection.
- **File-path safety:** no filesystem operation. Dirty state persists through Writer's existing document-property
  storage.
- **Supply chain:** no dependency or package-entry change. Extension version 0.6.0 uses the existing `.oxt`
  builder.

## Negative-path checks

- Unit tests cover clean/default state, citation-only/bibliography-only/both dirty combinations, exact-surface
  refresh routing, no-op clean refresh, non-dismissible Infobar construction, removal on clean state, and the
  fixed action-registry target.
- `_auto_refresh` failure coverage proves an exception after a citation mutation conservatively marks both
  surfaces pending rather than presenting a false-clean document.
- The real Writer round trip proved the Infobar appears for citation-only and both-surface pending states,
  disappears only after the matching refresh, and **Refresh pending** resolves both surfaces while both automatic
  modes remain paused.

## Result

**Security Audit: PASS**

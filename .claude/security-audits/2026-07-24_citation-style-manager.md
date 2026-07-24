# Security audit — shared citation-style manager (2026-07-24)

## Scope

Increment 365 adds a searchable metadata catalog over the bundled CSL files, local style preferences, a
fixed-example preview endpoint, a Settings manager, and the matching LibreOffice Writer workflow. It adds two API
operations (`POST /citations/styles/preview`, `PUT /citations/styles/preferences`) and enriches the existing
`GET /citations/styles` response. It adds no external host, dependency, secret, database schema, background task,
library lookup, or privilege boundary.

## Threat review

- **Bounded identifiers and search:** styles and locales must belong to the existing fixed manifests. Search input
  is capped at 120 characters and tokenized locally; recent history is deduplicated and capped at eight.
- **XML/path safety:** `ElementTree` reads only `{PROJECT_ROOT}/app/backend/citations/csl/styles/{manifest-id}.csl`,
  where every id comes from the source-controlled style manifest. User input never reaches a path, XML document,
  or parser configuration.
- **Preview isolation:** preview records are fixed fictional CSL-JSON literals. The endpoint never accepts record
  data, paper ids, library text, or file paths and never queries the repository. Rendering uses the existing local
  citeproc sidecar.
- **Persistence:** default style/locale, favorites, and recents are non-secret local preferences in the existing
  `app-settings.json` store. Invalid or corrupt saved values fail soft to the bundled defaults. Updates preserve
  unrelated settings.
- **Document authority:** a blank Writer document reads the application default but does not embed it until the
  first citation operation. Existing document properties remain authoritative. Applying a document style still
  validates placement compatibility and refreshes transactionally before the secondary Recent update.
- **Failure honesty:** unknown styles/locales return 422, an unavailable citeproc engine returns 503, and a render
  failure returns 502. A failed Recent update cannot turn a successful document restyle into a false failure.
- **Frontend rendering:** metadata and preview output are rendered as React text, not injected HTML. The new UI
  introduces no `dangerouslySetInnerHTML`, script URL, file upload, or credential surface.
- **Egress / SSRF:** catalog parsing, settings writes, and previews are local. No user-controlled URL is accepted
  and no network client or external request was added.
- **Supply chain:** no package or remote style source was introduced. Custom style installation/import remains
  explicitly deferred.

## Negative-path proof

- Oversized searches, unknown styles, and unknown locales fail cleanly.
- Corrupt saved ids/locales are filtered to known manifest values.
- Preview assertions identify the fictional Rivera/Chen and Okafor records and never touch the paper repository.
- Real Writer proves application-default inheritance without premature document mutation, document-local
  persistence, and Recent recording after a successful style change.

## Result

**Security Audit: PASS**

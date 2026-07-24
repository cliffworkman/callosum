# Security audit - note-position context (2026-07-24)

## Scope

Increment 371 hardens the existing `POST /citations/render-document` `noteIndex` semantics and expands the
installed LibreOffice fixture across imported note styles, ibid variants, near-note distance, and ordinary
Writer footnotes. It adds no endpoint, dependency, external host, file path, secret, persistence schema, or
background task.

## Threat review

- **Input validation:** every `noteIndex` remains a strict integer from 0 through 5000. A render is now either
  wholly inline (`0`) or wholly note-based (positive), and positive indexes cannot descend. Equal positive
  indexes remain valid because CSL permits multiple citation clusters in one note.
- **Output encoding:** citation HTML still passes through the existing sanitizer and plain-text converter.
  Position testing uses literal diagnostic labels only in hermetic test styles.
- **Injection:** CSL imports still pass the official local CSL 1.0.2 schema/macro checks and real citeproc
  instantiation before installation. No string is evaluated as Python, UNO commands, or shell input.
- **Egress / SSRF:** citeproc remains a fixed local Node subprocess. Writer calls the configured loopback
  Callosum server. No new fetch or data-egress path exists.
- **Document mutation:** ordinary footnotes contribute only their native collection index. The adapter scans
  them to locate live Callosum marks but writes only recognized ReferenceMark anchors; real Writer proves that
  intervening ordinary note text remains byte-for-byte unchanged.
- **Resource caps:** the existing 5000-cluster, total-item, per-cluster-item, and CSL-size limits are unchanged.
- **Secrets / paths / supply chain:** no secret or filesystem access was added and no dependency changed.

## Negative-path proof

- Mixed `[0, 1]` and `[1, 0]` sequences return HTTP 422.
- Descending `[2, 1]` returns HTTP 422.
- Equal positive `[1, 1, 2]` remains accepted.
- An imported diagnostic note style rendered exact first, ibid, ibid-with-locator, near-note, and far-subsequent
  branches through the public API.
- The installed OXT rendered those branches from Writer indexes `1,2,3,4,5,8`; ordinary notes at 6 and 7 were
  unchanged after the full refresh.

## Result

**Security Audit: PASS**

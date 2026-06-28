# Security audit — Google Docs add-on (Apps Script) (inc 170, SP2)

**Date:** 2026-06-28
**Feature:** The Google Docs cite-while-you-write add-on (`adapters/googledocs/`: `Code.gs`, `gdocs_core.js`,
`sidebar.html`, `appsscript.json`). Client code that runs in **Google's Apps Script cloud** and reaches the user's
LOCAL callosum through the inc-169 cloudflared bridge (`https://callosum.clffwrkmn.net`) with the inc-168 bearer
token. **No callosum code/endpoint/dependency/migration change** — it consumes existing, already-audited cite
endpoints.
**Audit triggers:** net-new client feature (3+ files); a new place a secret (the access token) is stored; new
external-facing consumer of the exposed app. (No new callosum endpoint, external fetch FROM callosum, ingestion, or
auth logic — those gates are not tripped.)

## What it does / what it can reach
The add-on calls only the cite endpoints the bridge allows (§6 of the README): `GET /papers?q=`,
`POST /papers/export` (csl-json), `POST /citations/render-document`, `GET /citations/styles`. The bridge's
**cite-only ingress (inc 169) is the hard boundary** — even a bug or a widened scope in the add-on cannot reach
`/settings`, the folder-scan routes, or `/papers/{id}` edit/delete (they 404 at the tunnel). The inc-168 **bearer
token** is required on every call (constant-time check at callosum).

## Threat review
- **Secret handling (the new bit).** The access token is stored in Apps Script **UserProperties** (per-user,
  per-script, in Google's cloud) and sent only as `Authorization: Bearer` to the user's own bridge URL. The sidebar
  **never receives the token back** — `getSettings()` returns `hasToken` (a bool), never the value; `saveSettings`
  only overwrites the stored token when a new one is supplied. The token is not logged. Storing it in Google's
  UserProperties is **inherent to choosing a cloud add-on** and is the user's explicit opt-in (they paste it); it is
  revocable any time (Settings → Remote access → Regenerate, then re-paste). No secret is committed to the repo.
- **OAuth scopes (least privilege).** `documents.currentonly` (edit only the active document — not Drive-wide),
  `script.external_request` (UrlFetchApp → the bridge), `script.container.ui` (show the sidebar). No Drive, Gmail,
  or broad document scopes.
- **Egress (invariant #3 posture).** With Remote access on + the tunnel up, the add-on transmits the user's search
  text + the cited works' metadata to the user's bridge (→ Cloudflare edge → localhost). This is the **same egress
  the inc-169 audit already covers** (the user's opt-in; transits Cloudflare + Google). No library *full text* is
  sent — the cite endpoints return citation metadata + citeproc-rendered strings. No NEW egress vector vs. the
  bridge audit; the add-on is just the first real consumer.
- **Injection / output.** `searchPapers` URL-encodes the query (`encodeURIComponent`). Server-rendered citation
  strings are inserted as plain text into the document (no HTML interpretation in Docs). citeproc output is already
  server-side-sanitized (`_safe_html`); the add-on uses the plain-text `text` / `bibliography_text` fields.
- **Supply chain.** No dependencies — Apps Script built-ins only (`UrlFetchApp`, `DocumentApp`, `PropertiesService`,
  `Utilities`, `HtmlService`); `node --test` is a Node built-in. `gdocs_core.js` is loaded by both Node (tests) and
  Apps Script; no third-party code.
- **Resource exhaustion.** Search is capped (`limit=20`); render-document is bounded server-side (MAX_CLUSTERS /
  MAX_ITEMS_PER_CLUSTER) + behind the inc-168 rate limiter; the sidebar disables the Insert button while in flight.

## Negative-path checks
- Token not set → the add-on errors before any fetch ("Set your Callosum URL + token …"). ✔
- `_fetch` maps 401 → "Unauthorized — check your access token"; 404 (cite-only block / tunnel down) → a clear
  "not reachable through the bridge" message; other 4xx/5xx → a bounded error string (no stack trace to the user). ✔
- Malformed DocumentProperties (`cite:<id>` / order list) → `parseItems`/`parseOrder` return `[]` (never guess);
  Refresh prunes dead ids. ✔ (node-tested)
- The token is never returned by `getSettings()` (only `hasToken`). ✔

## Residual risk / posture
- Trusting Google (Apps Script) + Cloudflare with the transit + the token-at-rest is **inherent to choosing a cloud
  add-on**; documented, and it is the user's opt-in. A fully-local alternative (the Word desktop add-in, inc 164)
  exists for users who don't want cloud transit.
- The cite-only guarantee depends on the bridge ingress allowlist staying intact (recorded in the inc-169 audit).

## Result
**Security Audit: PASS** — least-privilege scopes, token write-only to the sidebar + not logged + revocable, no new
egress vector beyond the audited bridge, the cite-only ingress remains the hard boundary, no callosum code change,
no dependency. The cloud transit + token-at-rest in Google UserProperties are the user's explicit opt-in, inherent
to the chosen architecture, and documented.

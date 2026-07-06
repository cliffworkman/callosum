# Security audit — OpenURL institutional link-resolver hand-off (inc 263)

**Date:** 2026-07-06
**Feature:** A "Get via my library" hand-off. callosum builds an OpenURL (Z39.88-2004) from a paper's
bibliographic metadata and returns it for the **user's own browser** to open against their institution's
**official** link resolver. New pieces: `acquisition/openurl.py` (pure builder), `GET /papers/{id}/library-link`
(returns the URL), a non-secret `openurl_resolver_base` setting.

**Audit triggers:** #1 new API endpoint + request-schema change (settings); a new user-facing "link-out" surface.

## Threat review

- **Data egress / SSRF — the central question.** callosum **never fetches the resolver URL.** The endpoint
  *builds a string and returns it*; the user's browser performs the navigation. No `httpx`/`requests` call is
  made to the resolver or the publisher, server-side. → **No SSRF surface** (there is no server-side request to
  a user-influenced host at all). The only data that "leaves" is a **DOI/title/ISSN etc. — public bibliographic
  metadata** — placed into a URL the **user's own browser** opens to their **own institution's** resolver. This
  is **not** library *text* and does **not** touch the `CALLOSUM_ALLOW_DATA_EGRESS` gate (that channel — Gemini
  generation — is unchanged and still off by default).
- **No credentials, ever.** No login is driven, no cookies/session are read or stored, no Playwright. The user
  authenticates in their *own* browser via their *own* SSO, entirely outside callosum. (This is what keeps the
  deferred connector lane's veto lines — "no server-side credential handling," "no session harvesting" —
  uncrossed.)
- **Input validation (boundary).** `openurl_resolver_base` is validated on `PUT /settings` via
  `resolver_base_valid()` — must be **http/https with a host, ≤500 chars** — else **422**. The value is the
  user's own published library URL (self-supplied, single-user threat model).
- **Output encoding / injection.** The OpenURL query is assembled with `urllib.parse.urlencode`, so DOI/title/
  author values are percent-encoded — a title containing `&`, `=`, `"`, `<`, or a newline cannot break out of the
  query or inject parameters. The frontend opens the returned URL with `window.open(url, "_blank", "noopener")`
  (no `opener` handle back to callosum).
- **Honest failure.** No DOI and no title → `build_openurl` returns `None` → the endpoint reports
  `{configured:true, url:null, detail:"…lacks a DOI or title…"}` (never a guessed link). No resolver configured
  → `{configured:false}`. Default-off: with no base set, the feature is dormant.
- **Secret handling.** `openurl_resolver_base` is **not a secret** (a public URL) — stored in the plaintext
  settings file and returnable by `GET /settings`, exactly like `contact_email`. No new secret is introduced.
- **Resource/DoS.** The endpoint does pure string work on one paper record; no external call, no unbounded loop.
- **File-path safety.** No file write/read path is added (the downloaded PDF is captured by the *existing*,
  already-audited attach/watched-folder ingest — unchanged here).
- **Supply chain.** No new dependency (stdlib `urllib.parse` only).

## Negative-path checks (results)

- `PUT /settings {openurl_resolver_base:"ftp://x"}` and `"not-a-url"` → **422** (asserted in `tests/test_openurl.py`).
- Title with `& = " < \n` → percent-encoded in the built URL; no parameter injection (asserted).
- Paper with neither DOI nor title → `url:null` + honest detail, **no link** (asserted).
- No resolver configured → `{configured:false}`, and **no outbound request** is made (the code path builds a
  string only; asserted structurally — the router imports no HTTP client for this endpoint).
- Egress gate untouched: no Gemini/genai call is on this path.

## Verdict

**Security Audit: PASS.** The hand-off is a local, deterministic link-builder: no server-side fetch (no SSRF),
no credential handling/storage, no scraping, output properly encoded, input validated at the boundary,
default-off, and the `CALLOSUM_ALLOW_DATA_EGRESS` channel is untouched. The deferred credentialed-connector
bright lines remain uncrossed.

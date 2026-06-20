# Security audit — Serve-time frontend assembly (increment 37, Phase 5)

Date: 2026-06-17
Scope: the frontend is no longer a single `callosum-app.html`; it is modular source under
`app/frontend/` (`index.html` + `styles.css` + ordered `js/*.jsx`) assembled into one document
at `/` by `app/backend/api/frontend.py::build_frontend_document`. Triggered the audit gate:
a new file-read/serve path + a net-new feature spanning 3+ files.

## Threat review

- **Authn/authz.** Unchanged — local, single-user, loopback-bound, CORS GET-only to localhost.
  No new route: `/` already existed; it now returns an assembled document instead of a static
  file. No new browser-facing file-serving surface (no `StaticFiles` mount, no per-asset routes)
  — the project's "no extra file-serving surface" stance is preserved.
- **Input validation / path safety.** The assembler reads a FIXED set of project-owned files
  (`app/frontend/index.html`, `styles.css`, `sorted(app/frontend/js/*.jsx)`). **No client input
  reaches any path** — there is no user-supplied filename, no traversal vector. The override path
  (`CALLOSUM_FRONTEND_PATH` / `frontend_path`) still serves a single operator-chosen file (env/arg,
  never client data), exactly as before.
- **Output encoding / injection.** The assembled document is byte-for-byte equivalent to the
  former hand-maintained `callosum-app.html` (the splitter asserted faithful reassembly; the
  served doc is 2023 lines, identical structure). The JSX chunks are concatenated into ONE
  `<script type="text/babel">` (no module boundaries) so the in-browser behavior/scope is
  unchanged — proven by the headless E2E running green with **0 console errors**. Placeholders
  (`{{STYLES}}`/`{{SCRIPT}}`) are substituted only with project-owned source. No client value is
  interpolated into the document.
- **Supply chain / asset integrity.** Brand assets (logo/favicon) remain inlined as base64 in the
  source (favicon in `index.html`, logo in a JSX chunk); `tools/inline_brand_assets.py` re-inlines
  from `app/media/*.png`. No new third-party dependency; the CDN `<script>` tags (React, ReactDOM,
  Babel) are unchanged from before.
- **Egress / SSRF.** None. Assembly is pure local file reads; no network.
- **Resource caps.** The assembled document is built once and cached in-process (`_cache`) — bounded,
  no per-request filesystem churn. A missing `app/frontend/` degrades to an honest 200 HTML notice
  (the API keeps serving), mirroring the prior missing-file behavior.
- **Trust boundary.** Injecting script would require local write access to `app/frontend/` — which
  is already total compromise of a local single-user app; there is no remote vector.

## Negative-path checks
- Default (no env): `/` assembles and returns the full document (verified: placeholders gone, CSS +
  all components present, `ReactDOM.createRoot` present). E2E exercises the live app end-to-end.
- Override to a real file: serves that file (`test_frontend_root_serves_configured_html_file`).
- Override to a missing file: graceful 200 notice, API still answers (`test_missing_frontend_file_*`).
- JSON endpoints not shadowed by `/` (`test_frontend_static_route_does_not_shadow_json_endpoints`).

## Verdict
**Security Audit: PASS** for the current local, single-user context. No new client-reachable input,
no new file-serving surface, output equivalent to the prior single file, egress unchanged. Auth +
rate-limiting before any public deployment remain tracked in CLAUDE.md.

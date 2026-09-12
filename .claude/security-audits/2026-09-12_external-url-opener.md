# Security audit — external-URL opener (app-shell boundary) — inc 589

**Date:** 2026-09-12
**Scope:** A new desktop-shell mechanism to open external http(s) URLs in the user's system browser:
`tauri-plugin-opener` (new dependency), the `open_external_url` Tauri command (`app/desktop-shell/src-tauri/
src/external.rs`), its ACL permission/capability, the `open_release_page` consolidation onto the same opener,
and the frontend `openExternalUrl` helper + global external-anchor interceptor (`app/frontend/js/00_lib.jsx`).

**Trigger:** new external mechanism + new Tauri command + new third-party dependency + new capability/permission.

## Why this exists
Inside the packaged Tauri webview, `window.open(url, "_blank")` and an ordinary `<a target="_blank" href>` do NOT
reach the system browser — every "Open article ↗" / library hand-off silently failed (a real user clicked ~10
times and got only an empty new tab). This is a release-integrity fix: the UI advertised a manual recovery action
that did nothing in the packaged app. The Wanted triage logic itself was correct; the failure was purely the
desktop-shell external-URL boundary.

## Threat review

- **Input validation / scheme safety (the security boundary).** The Rust command `open_external_url` is the
  authority: it accepts **only** `http://` / `https://` (case-insensitive, after trim) and returns an error for
  every other input — `file://`, `javascript:`, `mailto:`, custom schemes, and bare/schemeless strings — verified
  by a unit test (`external::tests::accepts_http_and_https_and_rejects_other_schemes`). The JS interceptor's
  classification is UX/routing only and is **not** trusted as the boundary.
- **Command / shell injection, RCE.** The opener hands the URL to the OS URL handler via `tauri-plugin-opener`
  (`OpenerExt::open_url`) — not through a shell, and the URL is an argument, not a command. Combined with the
  http(s)-only guard, there is no path to launch an arbitrary executable, a custom-scheme protocol handler, or a
  `file://` target. No `tauri-plugin-shell` / arbitrary-command capability is added.
- **SSRF / egress.** The app never fetches the URL — it hands it to the user's own browser (the free-and-legal
  hand-off). No server-side request, no library text leaves the machine. The opened URLs are public
  DOI/OpenAlex/publisher/notice pages already shown in the UI.
- **Capability scope (least privilege).** `allow-open-external-url` grants exactly one command to the existing
  splash+main capability; the generated ACL manifest resolves `open_external_url` and the capability already
  carries `remote.urls: ["http://127.0.0.1:*/*"]` (inc 423) so the loopback-loaded main window can invoke it. No
  broad permission was added; the opener plugin's own frontend commands are **not** granted to the webview (the
  frontend can only reach the opener through our validated command).
- **Supply chain.** `tauri-plugin-opener = "2"` is a first-party Tauri-org plugin, same trust tier and pinning
  style as the already-used `tauri-plugin-updater` / `tauri-plugin-single-instance`. `cargo check`/`cargo test`
  pass against Tauri 2.11.5.
- **Residual risk (accepted).** A user-initiated click can open any public web URL derived from library metadata
  (e.g. a DOI that redirects to a publisher). This is inherent to any "open link" feature and identical to the
  risk of clicking a link in a browser; the http(s) guard removes the dangerous scheme classes. No elevation.

## Negative-path checks (performed)
- `open_external_url` with `file:///…`, `javascript:…`, `ftp://…`, `mailto:…`, `""`, and a schemeless string all
  return `Err("only http(s) URLs may be opened")` (Rust unit test, passing).
- Frontend interceptor (Playwright DOM run, stubbed `__TAURI__`): external https → routed; same-origin, `#hash`,
  `mailto:`, `download` anchor, already-`preventDefault`ed click → all left to native handling; a click on a child
  element inside an external anchor → correctly resolved via `closest`.
- ACL manifest (`gen/schemas/acl-manifests.json`) resolves `open_external_url` / `allow-open-external-url`;
  capability retains `remote` + `127.0.0.1` (inc 421/423 checks).

## Decisive QA still owed (documented, not a blocker for the code being correct)
The actual packaged Tauri → system-browser open cannot be automated (native window, no scripted click). It is
verified by the 0.5.12 release build + the maintainer's live click-test: one Wanted article link, one Details
link, one legacy `<a target="_blank">` source link, the updater release-page action, and bounded Open-all all
opening in the OS default browser with no Tauri child webview created and the Callosum window staying healthy.

**Security Audit: PASS**

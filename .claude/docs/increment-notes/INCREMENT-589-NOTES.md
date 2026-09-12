# Increment 589 — App-shell external-URL boundary (the "Open article" links never opened), shipped in 0.5.12

A real user on the **packaged 0.5.11** reported that the new "Open article ↗" links did nothing — clicking ~10
times only ever produced an empty browser tab; "Open all blocked" and the Details-pane link had the same problem.

**This is a release-integrity fix, not a logic fix.** The 0.5.11 Wanted triage — the structured
`acquisition_state`, sort/filter/summary, the bounded Open-all, DOI import, and OA-acquisition logic — was all
**correct** and is untouched. The failure was purely the **desktop-shell external-URL opening boundary**: inside
the Tauri WebView2, neither `window.open(url, "_blank")` nor an ordinary `<a target="_blank" href>` hands the URL
to the system browser.

## Root cause (investigated first, per the steering)
The only pre-existing external opener was `updater::open_release_page` — **Linux-only** (`xdg-open`), a **no-op on
Windows/macOS**, and hardcoded to one URL. No opener/shell plugin was registered. Every other external link used
`window.open`, which is exactly what fails in the packaged webview. So there was no adequate mechanism to reuse.

## One canonical, scheme-validated opener boundary
- **`tauri-plugin-opener`** (first-party Tauri plugin, pinned `"2"`) registered in `lib.rs`.
- **`external::open_external_url(app, url)`** (`src-tauri/src/external.rs`) — the single seam. Accepts **only**
  `http(s)` (rejecting `file://`/`javascript:`/`mailto:`/custom schemes) and opens via `OpenerExt::open_url`.
  The validation is a pure `validated_external_url` helper with a **passing unit test**. ACL-gated by a new
  `allow-open-external-url` permission on the existing splash+main capability (which already carries the inc-423
  `remote.urls` loopback grant); the generated ACL manifest resolves it (inc-421 check).
- **`open_release_page` consolidated** onto the same opener (cross-platform now; the Linux-only no-op is gone —
  `RELEASES_PAGE`'s `#[cfg(linux)]` removed). No second updater-only path remains.
- **Frontend `openExternalUrl(url)`** (`app/frontend/js/00b_external_links.jsx`, extracted from `00_lib` for the
  600-cap): invokes the command in Tauri, falls back to `window.open` in a plain browser (dev / remote-access
  tunnel). Every explicit external `window.open` call site now routes through it — Wanted per-row + Open-all,
  Details article link + library-resolver hand-off, Add-with-DOI, and the two Transparency "Open externally"
  buttons.

## The whole class, not 28 anchors: a global external-anchor interceptor
Auditing found ~28 `<a target="_blank" href="https://…">` anchors (My Publications OpenAlex, Publishers
homepage/DOAJ/AJOL, funding sources, reference-integrity notices, citation-style links, provider "Get a key",
correction records, …) that share the **same** boundary bug. Rather than a broad per-component rewrite, one
**Tauri-only global click interceptor** (`00b_external_links.jsx`) routes external-host anchor clicks through
`openExternalUrl`. The invariant is now *external http(s) anchor → canonical openExternalUrl → OS browser*, not
"we fixed N anchors." It intercepts ONLY a primary (left/keyboard) click on an un-handled, non-download,
**external-host** http(s) anchor; it leaves alone already-`preventDefault`ed clicks, same-origin/hash internal
navigation, `mailto:`/`file:`/custom schemes, download anchors, and middle/aux clicks. `closest` resolves a click
on a child element. A modifier+left-click opens in the system browser (foreground) — the app has no tabs to
background into (documented, not emulated). JS classification is UX/routing; the Rust command re-validates the
scheme as the security authority.

## Verification
- **Rust:** `cargo test --lib external` passes (`accepts_http_and_https_and_rejects_other_schemes` — accepts
  http/https, rejects `file://`/`javascript:`/`ftp:`/`mailto:`/empty/schemeless). `cargo check` clean against
  Tauri 2.11.5. ACL manifest resolves `open_external_url`; capability retains `remote`/`127.0.0.1`.
- **Interceptor (Playwright DOM run, stubbed `__TAURI__`):** all seven scenarios exactly as specified — external
  https → `invoke("open_external_url", {url})`; same-origin, `#hash`, `mailto:`, download anchor, already-prevented
  → untouched; child-span-in-anchor → resolved.
- **Frontend:** rebuilt; `test_frontend_assembly.py` 87 green; line budget OK; no external `window.open` literal
  remains (only the helper's browser fallback).
- **Security audit:** `.claude/security-audits/2026-09-12_external-url-opener.md` — PASS.
- **Decisive packaged-app QA (cannot be automated — native window, no scripted click):** owed against the 0.5.12
  installer — one Wanted link, one Details link, one legacy `<a target="_blank">` source link, the updater
  release-page action, and bounded Open-all all opening in the OS default browser with no Tauri child webview and
  Callosum staying healthy. Everything automatable is green; this is the remaining manual confirmation.

## Scope discipline
No change to the Wanted triage/sort/filter, sticky bar, DOI import, OA-acquisition logic, or any unrelated
production code. The fix is confined to the external-URL opening boundary.

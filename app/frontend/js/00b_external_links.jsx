// The app-shell external-URL boundary (inc 589). Extracted from 00_lib.jsx to keep that chunk under the 600-line
// cap. Function declarations hoist across the shared esbuild IIFE, so every caller (Wanted, Details, Add-with-DOI,
// transparency, …) resolves openExternalUrl regardless of file order.

// Open an external (http/https) URL in the user's browser. Inside the packaged Tauri webview, window.open(url,
// "_blank") does NOT hand the URL to the system browser — every "Open article ↗" / library hand-off silently
// opened an empty tab. When running in Tauri, route through the ACL-gated, scheme-validated `open_external_url`
// command; a plain browser (the dev server or the remote-access tunnel, no __TAURI__) keeps using window.open.
// Use this for EVERY external URL, never window.open directly.
function openExternalUrl(url) {
  if (!url) return;
  if (typeof window !== "undefined" && window.__TAURI__) {
    window.__TAURI__.core
      .invoke("open_external_url", { url })
      .catch((e) => console.warn("[callosum] open external URL failed:", e));
    return;
  }
  window.open(url, "_blank", "noopener,noreferrer");
}

// Decide whether the global Tauri external-link interceptor should route an anchor click through openExternalUrl.
// This is UX/routing only — the Rust `open_external_url` command remains the security authority and independently
// re-validates the scheme. Returns the absolute URL to open, or null to leave the click to native handling.
// Intercept ONLY a primary (left / keyboard) click on an un-handled, non-download, EXTERNAL-host http(s) anchor.
// Deliberately NOT intercepted: already-handled clicks, non-left buttons (middle/aux click keeps native behavior),
// hash/same-origin internal navigation, and mailto:/file:/javascript:/custom schemes.
function externalAnchorTarget(anchor, event) {
  if (event && (event.defaultPrevented || event.button !== 0)) return null;
  if (!anchor || !anchor.getAttribute || anchor.hasAttribute("download")) return null;
  const raw = anchor.getAttribute("href");
  if (!raw) return null;
  let url;
  try { url = new URL(raw, window.location.href); } catch (_) { return null; }
  if (url.protocol !== "http:" && url.protocol !== "https:") return null;  // skip mailto/file/javascript/custom/hash
  if (url.host === window.location.host) return null;                       // skip same-origin (internal) navigation
  return url.href;
}

// In the packaged Tauri webview an ordinary <a target="_blank" href="https://…"> ALSO fails to reach the system
// browser (same boundary as window.open). Rather than convert every external anchor across the app, intercept
// external-host anchor clicks ONCE here. Only active in Tauri; a plain browser keeps native anchor behavior. A
// modifier+left-click opens in the system browser (foreground) rather than a background tab — the app has no tabs
// to background into; middle/aux-click is left to native handling. `closest` resolves a click on a child element.
if (typeof window !== "undefined" && window.__TAURI__) {
  document.addEventListener("click", (e) => {
    try {
      const anchor = e.target && e.target.closest ? e.target.closest("a[href]") : null;
      const target = externalAnchorTarget(anchor, e);
      if (!target) return;
      e.preventDefault();
      openExternalUrl(target);
    } catch (err) { console.warn("[callosum] external-link interceptor:", err); }
  });
}

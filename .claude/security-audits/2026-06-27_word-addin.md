# Security audit — Microsoft Word add-in, SP1 (inc 164)

**Date:** 2026-06-27
**Feature:** A Word add-in (Office.js task pane) that searches the local library and inserts a formatted citation.
Architecture A (user-chosen): callosum serves the task pane over **HTTPS, same-origin** with its API; the add-in
reaches the library with **no egress and no CORS change**. New file-serving routes (`routers/word.py`) +
`adapters/word/` client code + an HTTPS run-mode helper (`tools/run_https.py`) + a `WordSettings` Settings section.
**Audit triggers:** (1) new API endpoints, (3) a new file-serving path, (5) a net-new feature spanning 3+ files.

## Threat review
- **Input validation / path safety.** The `/integrations/word/*` file routes are **explicit per-filename routes**
  (one route per file: `taskpane.html|taskpane.js|taskpane_core.js|taskpane.css|icon.png` + `manifest.xml`), each
  calling `_serve(name)` with a **fixed media-type allowlist** (`_FILES`). **No request input reaches the path** —
  there is no `{filename}` path parameter, so directory traversal is structurally impossible; an undefined path is a
  plain 404. Files are read from a constant `WORD_DIR = PROJECT_ROOT / "adapters" / "word"`.
- **Process launch.** `POST /integrations/word/install` opens the add-in *folder* with the OS handler
  (`os.startfile` / `open` / `xdg-open`) over the constant `WORD_DIR` — no request-derived argument; mirrors the
  audited inc-162 libreoffice `_open_with_os`. Monkeypatched in tests so no real process launches. Failure →
  graceful `{opened:false}` (never 500).
- **Data egress (invariant #3).** **NONE.** The task pane is served from `https://localhost:8443` and its fetches
  (`/papers?q=`, `/citations/render`) are **same-origin loopback** → nothing leaves the machine. office.js loads
  from `appsforoffice.microsoft.com` — that is the **Office platform SDK** loaded in Word's webview (required for
  any Office add-in), **not callosum sending library data anywhere**. The Gemini egress gate is untouched and not
  involved (no LLM in this path).
- **CORS.** Unchanged (`allow_methods=["GET"]`, localhost-origin regex). Same-origin requests do not go through
  CORS at all, so the add-in's POSTs to `/citations/render` work without broadening the policy.
- **TLS / cert.** HTTPS run-mode uses a **local self-signed dev cert** the user installs once via
  `npx office-addin-dev-certs install` (the standard Office flow; installs a CA into the OS trust store so Word's
  WebView2 trusts `https://localhost`). The cert/key live in the user's `~/.office-addin-dev-certs/` — **never in
  the repo, never in code, never logged**. `tools/run_https.py` reads their paths only.
- **Secrets.** None handled. The manifest + task pane contain no keys.
- **Resource caps / untrusted content.** The served files are static app-owned assets. The task pane consumes the
  local API's already-validated JSON; it renders search rows + the citation via `textContent`/escaping (no
  `innerHTML` of API data without escaping).
- **Supply chain.** **No new Python or committed JS dependency.** office.js is CDN-loaded by Word (MS's SDK);
  `office-addin-dev-certs` is run on-demand via `npx` (not committed). `node --test` (pure-logic tests) is built
  into Node.
- **SRI on office.js (the one external script).** **Not applicable / deliberately omitted.** Unlike the inc-53
  React/Babel cdnjs pins (immutable files), Microsoft serves a continuously-updated office.js at the fixed
  `…/lib/1/hosted/office.js` path and **requires** loading it from there; a pinned `integrity` hash would break the
  add-in on every Office update. The risk is bounded — office.js runs in Word's webview, and the cite data path is
  same-origin loopback (no library data flows to the CDN).

## Negative-path checks
- Unknown filename (`GET /integrations/word/secrets.txt`) → **404** (no matching route; not a traversal). ✔
- `/install` with the OS opener raising → **`{opened:false}`**, 200, never 500. ✔
- Manifest served with `application/xml` + the fixed GUID + the `https://localhost:8443` SourceLocation. ✔
- Egress with the toggle off is irrelevant (no egress path exists here); confirmed no `generativelanguage`/external
  host is contacted by the headed Settings drive. ✔

## Local-only posture / deployment gate
Like the libreoffice-install (inc 162), library-scan (inc 87), and watched-folders (inc 98) routes, these serve
files + open a local folder — **fine on 127.0.0.1 (the server is the user's machine), dangerous if the app is ever
hosted.** **Gate or remove `/integrations/word/*` + the HTTPS run-mode before any hosted deployment**, and re-audit
under the Security baseline's pre-deploy checklist.

## Principles (rule #9)
**Non-triggering.** Packaging + a thin field-placer that reuses the audited citeproc render (inc 106) — no new
claim/signal/judgment about the literature, no new provenance/fact-vs-candidate surface. The egress posture is
*strengthened* (all loopback). Credit-the-lineage: the live-field/CSL-JSON design follows the Zotero
`CSL_CITATION` pattern (already credited in `THIRD-PARTY-NOTICES.md`); office.js is Microsoft's SDK (noted in the
adapter README).

## Result
**Security Audit: PASS.** No egress, no new dependency, no traversal surface, fail-closed install, local-only with
the standard pre-hosted-deploy gate recorded.

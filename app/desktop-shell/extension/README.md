# Callosum Capture — browser extension (#61 Phase 2, Part 3)

MV3 extension for Chrome and Edge. Sends the active tab's scholarly metadata (or, when the tab
itself is a PDF, the PDF's bytes) to the locally-installed Callosum connector host, which
authenticates the request and hands it to `/capture/*`. This extension never talks to Callosum's
API directly with its own credential — the connector host mints the session; the extension only
ever uses the session and origin the host handed back for this one exchange, validated before use
(see `validateBackendOrigin` in `background.js`).

## Permissions — one concrete Phase 1 reason each

| Permission | Why |
|---|---|
| `nativeMessaging` | Talk to the connector host (`org.callosum.connector`). |
| `activeTab` | Read the clicked page / fetch its PDF bytes — granted only by the user's click gesture, never ambient. |
| `scripting` | `chrome.scripting.executeScript` needs it to run the metadata extractor in the page. |
| `host_permissions: ["http://127.0.0.1/*"]` | POST the authenticated capture request. Port-agnostic because Callosum's loopback port changes per launch; the connector host supplies the port, and `background.js` validates it strictly (scheme, host, port, no credentials, no path) before ever using it as a fetch target. |

No `<all_urls>`, no `cookies`, no `webRequest`. Nothing here reads or replays browser credentials
for any site — captured metadata comes only from `<meta>` tags and JSON-LD already visible in the
page's DOM, exactly as any content script could already see.

## Extraction (generic only — no publisher-specific code)

`background.js`'s `extractPageMetadata` looks for, in order of preference: a DOI (Highwire
`citation_doi`), Highwire `citation_*` tags (title/authors/journal/date/pdf url), then JSON-LD
`schema.org` `ScholarlyArticle`/`Article` blocks. Stable identifiers are preferred over heuristic
bibliographic matching — a DOI beats a scraped title, always.

## Direct PDF is an empirical capability, not a promise

On the explicit click, the handler fetches the active HTTP(S) tab's own URL under its existing
`activeTab` grant. A `.pdf` suffix is only a hint: publisher `/article/file` URLs are recognized
from `%PDF-` bytes too. The fetch is bounded to 60 seconds and 80 MiB, including streamed responses
without Content-Length. MIME-identified HTML takes generic DOM extraction; ambiguous or inaccessible
content fails closed without admitting a PDF-viewer filename as metadata. The unused HTML body is
cancelled after classification. No broader permission or publisher-specific URL rewrite is used.
This is still an empirical browser capability: Node tests establish classification and limits,
not real packaged Chrome/Edge permission or transfer behavior.

## Store package (Chrome Web Store + Microsoft Edge Add-ons)

`python app/desktop-shell/packaging/build_extension_package.py` builds the ONE zip both stores receive (two submissions,
two store-assigned IDs). It ships an allowlist of runtime files only (`manifest.json`, `background.js`, `icons/*.png`),
refuses any manifest `key` or `update_url`, refuses signing material, stops on any unclassified file, and is byte-for-byte
reproducible (sorted, fixed timestamps, LF text, stored entries) — it prints the SHA-256. The repository manifest is
**keyless** and must stay so: never put a production key here; for a pre-review test with the Chrome Web Store public key use
a temporary staged copy. The `dev/` tooling makes a different, key-pinned, host-name-patched copy for local testing that must
never be uploaded. Release steps and open questions: `.claude/docs/research/2026-09-19_browser-capture-store-release-runbook.md`.

## What this extension never does

No fetching a URL the *backend* supplied (a URL is not an accessible PDF — the same principle
`CaptureEnvelope.pdf_bytes_from_active_tab`'s own docstring states). No fetching a `citation_pdf_url`
or similar meta-tag URL automatically, even when present — only the active tab's own bytes, from a
direct user gesture. No credentials, cookies, or page storage are ever read or transmitted.

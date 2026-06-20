# Security Audit — Help corpus endpoint + render path (increment 59)

**Date:** 2026-06-19
**Trigger:** New API endpoint (`GET /help/corpus`) + a new HTML render path
(`dangerouslySetInnerHTML` in the help modal) + net-new feature spanning 3+ files.

## What changed
- New `GET /help/corpus` (`app/backend/api/routers/help.py`) returns the in-app help content as
  `{sections:[{id, title, html}]}`. Stateless: **no DB, no request input, no egress.**
- New `app/backend/help/corpus.py` parses a shipped markdown asset (`help_content.md`) into sections and
  renders each body to a small **allowlisted HTML** string via `render_html` (paragraphs, `ul/li`,
  `strong/em/code`, `h3`, and `a[href]` restricted to `http(s)`/`#`); all text is HTML-escaped first.
- The frontend help modal (`app/frontend/js/18_help.jsx`) renders `section.html` via
  `dangerouslySetInnerHTML`.

## Threat review
- **Content trust / XSS:** the help corpus is **app-owned static content** shipped in the repo
  (`app/backend/help/help_content.md`) — there is **no user input** anywhere in this path (no request
  body, no DB row, no external fetch). `render_html` defends in depth anyway: it `html.escape(...)`s every
  text run **before** applying inline formatting, emits only a fixed allowlist of tags, and drops any
  link whose scheme is not `http(s)`/`#` (so `javascript:`/`data:` URLs become inert text). This is the
  same posture as the audited `clean_abstract_for_display`. The `dangerouslySetInnerHTML` flag (raised by
  the lint hook) is therefore acceptable here: the HTML is escaped + allowlisted server-side and never
  derived from untrusted input. (A unit test asserts `<script>` is escaped and `javascript:` links are
  dropped.)
- **Injection / SQL:** none — no DB access on this path.
- **SSRF / external calls / egress:** none — the endpoint serves local static content and is intentionally
  **not** gated by any egress flag (the docs must render offline / when the AI help assistant is off).
- **Resource exhaustion:** the corpus is a small fixed file parsed once and cached (`lru_cache`). No
  request-controlled size.
- **File-path safety:** the content path is a module-relative constant (`Path(__file__).with_name(...)`),
  never built from request data.
- **Secrets / supply chain:** no secrets; **no new dependency** (the markdown subset is rendered by a
  small hand-rolled function).
- **API shape / route surface:** one new GET route, added to the route-surface invariant allowlist
  (`tests/test_health.py`). No mutation route. CORS stays GET-only/no-credentials.

## Negative-path checks (results)
- Unit: untrusted markup in a section body → escaped (`&lt;script&gt;`), never emitted raw. **PASS.**
- Unit: a `javascript:` link → rendered as plain label, no `href`, no `javascript:` in output. **PASS.**
- Unit: malformed/duplicate section ids → `ValueError` at parse (loud, not silent). **PASS.**
- Endpoint: `GET /help/corpus` → 200 with unique-id sections, each non-empty. **PASS.**

## Residual / deferred
The AI help assistant (`POST /help/ask`, its own independent `CALLOSUM_HELP_ASSISTANT_ENABLED` gate, the
inc-58 seam-gate pattern, no library-text egress) is **increment 60** and will get its own audit (gate
independence + no library egress).

**Security Audit: PASS.**

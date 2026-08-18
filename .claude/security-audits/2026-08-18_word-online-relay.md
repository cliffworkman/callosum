# Security audit — Word-on-the-web relay (backlog #33/#34, SP4)

**Date:** 2026-08-18
**Status:** complete — PASS

## Scope

Extends two already-audited surfaces (`2026-06-27_word-addin.md` PASS, `2026-06-28_googledocs-tunnel.md` PASS,
`2026-06-27_remote-access-auth.md` PASS) to let the existing Word add-in's task pane run in **Word on the web**
(Microsoft's cloud, which cannot reach the user's machine directly), by riding the same cloudflared cite-only
relay the Google Docs add-on already uses, rather than building a new transport.

- `adapters/word/taskpane_core.js` — two new pure helpers: `isLocalOrigin(hostname)`, `authHeaders(headers,
  token)`. Unit-tested (`node --test`).
- `adapters/word/taskpane.js` — detects local-vs-tunneled origin from `location.hostname`; only in tunneled mode,
  reads a Bearer token from `localStorage` and attaches it to every fetch via a new `callosumFetch` wrapper; adds
  a token-entry UI section (shown only when tunneled).
- `adapters/word/taskpane.html` / `taskpane.css` — the new (initially hidden) token-entry section.
- `adapters/word/manifest.web.xml` (new file) — a second, distinctly-identified (different GUID) manifest variant
  pointing `SourceLocation`/`AppDomains`/icon URLs at the tunnel hostname instead of `localhost:8443`.
- `app/backend/api/routers/word.py` — one new route, `GET /integrations/word/manifest-web.xml`, serving the fixed
  file above via the exact same allowlist-of-one pattern the existing `manifest.xml` route already uses (no
  request-derived path).
- `adapters/googledocs/cloudflared-config.yml` — one new ingress rule forwarding the 5 Word task-pane GET paths
  (not the manifest routes) to `http://localhost:8080`, alongside the existing cite-only API rule. Same tunnel,
  same hostname — shared infrastructure, not a new tunnel.
- `app/backend/api/access_control.py` — **the one genuine new finding this audit exists to record** (see below).
- `app/frontend/js/35_settings.jsx` — a parallel "Microsoft Word add-in (web)" section, downloads
  `manifest-web.xml`.
- `adapters/word/README.md` — a new "Word on the web" setup section.

## Threat review

### 1. The real finding: `AccessControlMiddleware`'s exemption list needed extending, and almost didn't

Before this change, `_EXEMPT_PATHS` allowed only `/`, `/health`, `/oauth/callback` through un-gated when Remote
access is on. Office's own fetch of a task pane's `SourceLocation` — and the `<script src>`/`<link href>` tags
inside that HTML — is a **plain resource load**, not a header-carrying `fetch()`; it can never attach a custom
`Authorization` header. Caught by writing the negative-path test first
(`tests/test_access_control.py::test_gate_on_exempts_word_taskpane_assets_but_not_the_api`, confirmed RED before
the fix): with Remote access on and the old exemption list, `GET /integrations/word/taskpane.html` returned 401,
which means **Word-on-the-web could never have loaded the task pane at all** — the whole feature would have
silently failed exactly at the moment a real user tried it, since this is not something local desktop testing
would ever surface (the desktop task pane loads same-origin from `localhost:8443`, entirely outside this
middleware's active-when-remote-access-is-on path). Fixed by adding the 5 fixed Word task-pane filenames
(`taskpane.html`/`.js`/`taskpane_core.js`/`.css`/`icon.png`) to `_EXEMPT_PATHS`, using the exact same
justification the pre-existing `/` exemption already documents ("carries no library data") — these are
compile-time-fixed static files with zero request-derived content (confirmed by reading `word.py`'s own
allowlist-of-one route pattern, unchanged by this work).

**What is deliberately NOT exempt:** `manifest.xml` and `manifest-web.xml`. A user downloads either directly
from their own local callosum (`Settings → Microsoft Word add-in...`), never through the tunnel — Office never
fetches the manifest URL itself over the network; sideloading is a local file, not a live fetch. Confirmed by a
dedicated assertion in the same test (`manifest.xml`/`manifest-web.xml` still 401 with Remote access on) that
the exemption is exactly the 5 asset files, nothing broader.

**What is NOT weakened:** `/papers`, `/citations/*`, `/settings`, and every other real endpoint remain fully
gated — confirmed by the same test file's pre-existing `test_gate_on_requires_a_valid_bearer_token` plus the new
test's own explicit `client.get("/papers").status_code == 401` assertion under Remote access + no token.

### 2. Token handling in the new tunneled task-pane code path

`taskpane.js`'s new `authToken()`/`callosumFetch()` only read/attach a token when `isTunneled` is true
(`!CallosumCore.isLocalOrigin(location.hostname)`) — confirmed by unit test that `isLocalOrigin("localhost")`/
`("127.0.0.1")` are both true, so the desktop path is provably unchanged (no new header ever sent there). The
token is stored via `localStorage`, which is **origin-scoped by the browser itself** — a token saved while this
page loaded from the tunnel's hostname is never visible to, or readable by, the desktop origin
(`localhost:8443`), the main callosum web app's own origin, or the Google Docs add-on's completely separate
Google-hosted origin. No new storage mechanism was invented; this mirrors the main app's own `00_lib.jsx` token
pattern (same key name, for consistency only — origin-scoping means no collision is even possible).
`authHeaders` is pure and non-mutating (unit-tested); it never logs, echoes, or persists the token anywhere
beyond that one `localStorage` write.

### 3. What actually crosses the tunnel, and what the ingress allowlist still blocks

Traced the new ingress rule directly (`cloudflared-config.yml`): the added `path` regex
(`^/integrations/word/(taskpane\.html|taskpane\.js|taskpane_core\.js|taskpane\.css|icon\.png)$`) was verified —
not just read — by loading the YAML with `PyYAML` and compiling/matching the regex in a standalone check: it
matches exactly the 5 intended files and rejects `manifest.xml`, `manifest-web.xml`, `install`, and a `../`
traversal attempt on the same path prefix. The pre-existing cite-only rule and the catch-all 404 are untouched.
Nothing in this change widens what the tunnel forwards beyond these 5 additional, non-sensitive static files.

### 4. No new external dependency, no new secret, no schema change

`isLocalOrigin`/`authHeaders` are plain JS with no new package. The new manifest file is static XML, hand-written
following the existing `manifest.xml`'s exact structure. No migration, no new table. The one new backend route
(`manifest-web.xml`) reuses the identical fixed-file-serving pattern already audited for `manifest.xml` — no new
traversal surface (confirmed: `word.py`'s existing `test_unknown_file_is_404_not_a_traversal` test is unaffected
and still passes, since the new route is its own explicit per-filename function, not a new dynamic path).

## Negative-path checks (executed, not assumed)

```
pytest tests/test_access_control.py -q          → 9 passed (incl. the new exemption-boundary test)
pytest tests/test_word_addin.py -q               → 11 passed (incl. 2 new manifest-web.xml tests)
pytest tests/test_frontend_assembly.py -q        → 67 passed
pytest tests/test_settings.py -q                 → passed
node --test adapters/word/taskpane_core.test.js  → 13 passed (7 new: isLocalOrigin ×5 cases, authHeaders ×4 cases)
python tools/check_line_budget.py                → OK, 550/550 files under cap
ruff format / ruff check (touched .py files)     → clean
python -m tach check                             → OK
```

Specific negative-path assertions:
- **Remote access ON, no token, task-pane asset request** → 200 (the fix; previously 401, which would have
  silently broken the whole feature).
- **Remote access ON, no token, `/papers` (the actual API)** → 401 (unchanged — the exemption is narrow).
- **Remote access ON, no token, `manifest.xml`/`manifest-web.xml`** → 401 (deliberately excluded from the
  exemption — these are downloaded locally, never fetched by Office over the tunnel).
- **Ingress regex** rejects `manifest.xml`, `manifest-web.xml`, `install`, and a traversal string on the same
  path prefix, confirmed by direct regex compilation/matching, not by reading the YAML and assuming.

## Result

The one real gap this audit was written to catch — and did catch, via a RED test before any fix — was that the
Remote-access gate would have silently prevented Word-on-the-web from ever loading the task pane at all, since
Office's own resource fetch of the task-pane files can't carry the Bearer token the gate otherwise requires.
Fixed with the narrowest possible exemption (5 fixed, zero-request-input static files, matching the existing `/`
shell's own precedent), verified not to weaken the token gate anywhere else. Everything else in this feature —
the tunnel ingress extension, the new manifest variant, the tunneled-mode token handling — reuses already-audited
patterns exactly, with no new dependency, secret, or schema change.

**Security Audit: PASS**

# Increment 482 — Word-on-the-web relay (backlog #33/#34, SP4)

## Implemented

The existing Microsoft Word add-in (`adapters/word/`, SP1-3, incs 164-166 — search/insert, Suggest-from-the-
sentence, Refresh/renumber+bibliography, style switch, Flatten) now also works in **Word on the web**, by riding
the same cloudflared cite-only relay tunnel the Google Docs add-on already uses (`adapters/googledocs/`), rather
than building a new transport. Desktop Word is entirely unaffected — same origin, same behavior, no new code path
touches it.

- `adapters/word/taskpane_core.js` — two new pure, unit-tested helpers: `isLocalOrigin(hostname)` (desktop vs.
  tunneled) and `authHeaders(headers, token)` (attaches `Authorization: Bearer <token>` only when tunneled).
- `adapters/word/taskpane.js` — detects mode from `location.hostname`; a new `callosumFetch()` wrapper replaces
  every raw `fetch()` call site; a token-entry UI section (hidden by default) appears only when tunneled.
- `adapters/word/taskpane.html` / `taskpane.css` — the new token-entry section's markup/styling.
- `adapters/word/manifest.web.xml` (new file) — a second manifest variant, its own distinct GUID, pointing
  `SourceLocation`/`AppDomains`/icon URLs at the tunnel hostname instead of `localhost:8443`.
- `app/backend/api/routers/word.py` — one new route, `GET /integrations/word/manifest-web.xml`, serving the
  fixed file above via the same allowlist-of-one pattern `manifest.xml` already uses.
- `adapters/googledocs/cloudflared-config.yml` — one new ingress rule forwarding the 5 Word task-pane GET paths
  (never the manifest routes — those are downloaded locally, not fetched by Office over the network) to
  `http://localhost:8080`, alongside the existing cite-only API rule. Same tunnel, shared infrastructure.
- `app/backend/api/access_control.py` — **a real bug found and fixed** (see Key technical detail).
- `app/frontend/js/35_settings.jsx` — a parallel "Microsoft Word add-in (web)" section with its own manifest
  download button.
- `adapters/word/README.md` — a new "Word on the web" setup section; corrected a stale claim in the process (see
  below).
- `.claude/security-audits/2026-08-18_word-online-relay.md` — full threat review, PASS.

**A real, pre-existing documentation error was also corrected while writing the README update**: the file
claimed citations render in "insertion order" as a Word-on-the-web limitation. That's wrong for Word specifically
(unlike Google Docs' own genuine insertion-order limitation) — Word's `contentControls` collection is already
scanned in true document order on desktop (confirmed in `taskpane.js`'s own pre-existing comments, SP2), and
nothing about which origin loaded the task pane changes that. Removed the incorrect claim before it shipped.

## Key technical detail

**`AccessControlMiddleware`'s exemption list would have silently broken this feature entirely, and only a
negative-path test written before the fix caught it.** Office fetches a task pane's `SourceLocation` — and the
`<script src>`/`<link href>` tags inside that HTML — as a plain resource load, which can never carry a custom
`Authorization` header (only JS-initiated `fetch()`/`XMLHttpRequest` can set custom headers). Before this
increment, `_EXEMPT_PATHS` allowed only `/`, `/health`, `/oauth/callback` through when Remote access is on —
meaning `GET /integrations/word/taskpane.html` would 401, and Word-on-the-web could never even load the task
pane, let alone reach its API. This was invisible from the desktop side (which loads same-origin from
`localhost:8443`, entirely outside this middleware's active path) and would only have surfaced the first time a
real user actually tried Word-on-the-web with Remote access enabled — exactly the scenario this increment exists
to support. Fixed by adding the 5 fixed Word task-pane filenames to `_EXEMPT_PATHS`, using the identical
"carries no library data" justification the pre-existing `/` exemption already documents; the manifest routes
are deliberately excluded (users download those locally, Office never fetches them over the tunnel), and every
real API endpoint (`/papers`, `/citations/*`, `/settings`, …) remains fully gated — both confirmed by explicit
test assertions, not just narrative claims.

**Token scoping relies on the browser's own origin isolation, not new code.** The tunneled task pane's saved
access token lives in that origin's own `localStorage` — automatically invisible to the desktop task pane's
origin, the main callosum web app's origin, and the Google Docs add-on's separate Google-hosted origin. No new
storage/sharing mechanism was built; this is a property of how browsers already work, verified by reasoning
about origins rather than assumed.

## Manual verification script

No live browser/Word session was run for this increment (no headless Word exists, and the maintainer doesn't
yet have desktop Word installed to test the sideload flow) — this is the script to run once both are available:

1. **Desktop regression check first** (confirm nothing broke): open desktop Word with the existing `manifest.xml`
   sideloaded, confirm search/insert/Suggest/Refresh/style-switch/Flatten all still work exactly as before.
2. Ensure the cloudflared tunnel from the Google Docs setup is running (or set one up per
   `adapters/googledocs/README.md` if not already done).
3. In callosum: Settings → Remote access → turn **ON**, copy the access token.
4. Settings → Microsoft Word add-in (web) → **Download web manifest**.
5. In Word on the web (office.com): ribbon **Add-ins → Upload My Add-in** → pick `callosum-word-manifest-web.xml`
   → **Home → Callosum → Show Citations**.
6. Confirm the task pane loads (proves the `AccessControlMiddleware` exemption + tunnel ingress rule both work)
   and shows the **Access token** field. Paste the token → **Save token**.
7. Search for a paper, insert a citation, confirm it appears live in the document.
8. Click **Refresh** — confirm the citation renders correctly and the References block appears/updates.
9. Change the citation style dropdown — confirm the whole document re-renders.
10. Reload the page (simulating a new browser session at the same origin) — confirm the saved token persists
    (no re-prompt) and citations/Refresh still work.
11. Turn Remote access **OFF** in Settings — confirm the tunnel-mode task pane's API calls now fail cleanly
    (401, not a hang or crash) — proves the exemption is narrow and the real API is still gated.

## Pytest

Targeted suite: `pytest tests/test_word_addin.py tests/test_access_control.py tests/test_frontend_assembly.py
tests/test_settings.py -q` → **119 passed**. `node --test adapters/word/taskpane_core.test.js` → **13 passed**
(7 new: `isLocalOrigin` ×5 cases, `authHeaders` ×4 cases — some cases share assertions within one `test()`
block). `python tools/check_line_budget.py` → clean, 550/550 files under the cap. Scoped `ruff format`/
`ruff check` on every touched `.py` file → clean. `python -m tach check` → clean.

Full suite (`pytest -n 4 -q`): **2320 passed, 1 failed, 4 skipped** (1402.87s). The 1 failure
(`tests/test_website_how_it_works.py::test_primary_local_destinations_exist[demo/-target2]`) is a confirmed
pre-existing, unrelated gap: it asserts the gitignored `dist-demo/` build artifact exists on disk, produced only
by a separate CI-only `tools/demo/build_demo.py` step this worktree never ran and this increment never touches
— same known gap documented in `INCREMENT-481-NOTES.md`. Zero regressions from this increment's own changes.

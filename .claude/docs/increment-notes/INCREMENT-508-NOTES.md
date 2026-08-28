# Increment 508 — First real live verification of the desktop Word add-in (backlog #33/#34)

## Implemented

Cliff got Microsoft Word installed for the first time since the Word add-in shipped (incs 164-166 SP1-3, inc
482 SP4). Per the backlog's own stated next step ("once Word is installed, run both — the desktop regression
check first, then the Word-on-the-web relay setup"), this increment is the desktop half: the first-ever real
run of the add-in in actual Word, not just the pure-logic `node --test` suite.

**Setup, done for real:**
1. `npx office-addin-dev-certs install` — trusted a local CA for `https://localhost:8443` (a Windows
   certificate-trust prompt appeared; Cliff accepted it).
2. `python tools/run_https.py` — **found and fixed a real bug**: invoked exactly as documented, this raised
   `ModuleNotFoundError: No module named 'app'`. Root cause: the script calls `uvicorn.run("app.backend.api.
   app:app", ...)` — a *string* dotted path uvicorn resolves via a deferred import inside itself, not a direct
   `from app...` in this file, so the file never triggered Python's own import machinery to fail loudly at
   parse time (and never got the `sys.path.insert(0, str(ROOT))` fix every OTHER `tools/` script needing a
   sibling `app` import already has, e.g. `build_frontend.py`). Running as documented (`python tools/
   run_https.py`, script mode) puts the script's own directory (`tools/`) on `sys.path`, not the project root,
   so uvicorn's later deferred import of `app.backend...` failed. Fixed by adding the exact same
   `ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))` pattern at the top of the file.
   Confirmed fixed: the server now starts correctly with the documented command, no env var workaround needed.
3. Sideload the manifest — **found and fixed a real documentation bug**: `adapters/word/README.md` said to
   "put manifest.xml in a folder, then add that folder's path" to Word's Trusted Add-in Catalogs. Cliff's real
   Word rejected a bare local path — confirmed against Microsoft's own current docs
   (`learn.microsoft.com/.../create-a-network-shared-folder-catalog-for-task-pane-and-content-add-ins`): the
   Trust Center's "Catalog Url" field genuinely requires a **network share path** (`\\hostname\share`), even
   for a folder on the same machine — obtained via right-click the folder → Properties → Sharing tab → Share…
   → note the `\\...` path it shows. README corrected with the full, accurate steps (share the folder, use the
   network path, `Home → Add-ins → Advanced → SHARED FOLDER` tab, not directly "Home → Add-ins → Shared
   Folder" as it previously said).

**Live-verified working, for real, in real Word (search-insert, Suggest, Refresh, Flatten — the whole SP1-3
arc):**
- **Insert by search** — picked a style, searched, inserted a live citation.
- **Suggest from the sentence** — ranked the library by relevance with stance + quote, inserted a suggested
  citation.
- **Refresh** — re-rendered + renumbered in document order, rebuilt the bibliography.
- **Flatten to static text** — converted live fields to plain text.

All four completed without issue on the first real attempt.

## Key technical detail

The `sys.path` bug is a good general lesson: `python path/to/script.py` puts the *script's own directory* on
`sys.path[0]`, never the invoker's current working directory or the project root — a script that needs to
import a sibling top-level package (here, `app.*`) must add the project root to `sys.path` itself, not rely on
however it happens to be invoked. Every other `tools/*.py` script that imports `app.*` already does this
(`ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))`); `run_https.py` was the one
exception, invisible until this was the first time anyone actually ran it via its own documented command
rather than through some other invocation path during original development.

## Manual verification script

Already run for real, see above. For a re-check after any future change to `tools/run_https.py` or the
manifest: `npx office-addin-dev-certs install` (once) → `python tools/run_https.py` → confirm
`https://localhost:8443/health` returns 200 → sideload per the corrected README steps → exercise all four SP1-3
features in Word.

## Pytest / tests

`node --test adapters/word/taskpane_core.test.js` → 13/13 passed (unchanged, confirms the pure-logic layer
wasn't touched by this fix). No Python test suite change needed — `tools/run_https.py` has no existing test
coverage (it's a thin dev-convenience script, not app logic) and the fix is a two-line `sys.path` addition
identical to an already-proven pattern elsewhere.

## Word-on-the-web (SP4) — live-verified same day

Following the desktop verification above, the Word-on-the-web relay flow (`adapters/word/README.md`'s "Word
on the web" section) was set up and live-verified for the first time too:

- The named cloudflared tunnel (`callosum-tunnel.clffwrkmn.net`) already existed from the Google Docs work but
  had never been run with a real filled-in config — built `~/.cloudflared/config.yml` from the checked-in
  template (`adapters/googledocs/cloudflared-config.yml`), pointed its `service:` at the actual running dev
  server (`http://localhost:8888`, not the template's `:8080`), and started it.
- Remote access + a bearer token were already configured from prior work; sideloaded `manifest.web.xml` into
  Word on the web via **Insert → Add-ins → Upload My Add-in**.
- **Found and fixed a real, previously-undiscovered bug** in `adapters/word/taskpane.js`: `loadStyles()` runs
  once at `Office.onReady`, which in the tunneled case fires *before* the user has pasted+saved their access
  token. That first call 401s and fails silently (the existing `catch` comment: "styles are optional polish;
  the default 'apa' still works") — and nothing ever re-triggered `loadStyles()` afterward, so
  `<select id="style">` (which has no default `<option>` in the HTML) stayed permanently empty even after the
  token was saved, on every subsequent visit, even though search/insert/suggest/refresh all worked fine (the
  user only exercises those *after* saving the token, so they were never affected). Fixed by re-running
  `loadStyles()` inside `saveToken()` once a non-empty token is saved — confirmed working live afterward, the
  full real style list populated the dropdown.
- With that fixed, live-verified the complete SP1-3 feature set identically to desktop through the tunnel:
  search-and-insert, Suggest-from-the-sentence, Refresh/renumber + bibliography, and Flatten all confirmed
  working (Cliff: "everything else works just fine" even before the styles fix, "woo hoo it works!" after).

The `node --test adapters/word/taskpane_core.test.js` pure-logic suite (13/13) was re-run after the
`taskpane.js` fix as a sanity baseline — unaffected, since the fix touches only the untested Office.js glue
layer per the project's own documented "no headless Word" policy.

`~/.cloudflared/config.yml` (the real, filled-in tunnel config) is intentionally **not** committed — it lives
outside the repo like the rest of this machine's account-identifying local config, consistent with the
checked-in file staying a template with `<TUNNEL_ID>`/`<HOME>` placeholders.

## Still open

Both desktop and Word-on-the-web are now live-verified for the full SP1-3 feature arc. Per the backlog's own
sequencing, the next concrete increment is scoping **Word/Docs parity toward the LibreOffice adapter's much
larger P1/P2 feature set** ("grouped citations/locators" being the most-named single gap, but the LibreOffice
adapter has many more incs of surface area — see the backlog for the running list). That scoping is deliberately
a separate next step, not pre-built here.

# Increment 162 — LibreOffice adapter v2: an intuitive, discoverable cite flow

**The problem the user hit:** the inc-108/156 adapter worked, but the *routing* was unusable — the macros were
buried in **Tools → Macros → Organize Macros → Python**, and inserting a known paper was **by numeric paper id**.
"No end user is going to find this intuitive."

**Research (Zotero / Mendeley / EndNote):** the universal recipe is (1) a **toolbar/menu that appears after install**
(never a macro dialog; install is a double-click extension or done from the app) and (2) one **"Add Citation" → a
search-as-you-type box** over the library. Our **Suggest** (relevance-from-the-sentence) is a *novel complement* none
of them have — kept.

**Scope (user-approved):** both pillars + a one-click install from Settings; Add-citation = a **two-step picker**
v1 (live search-as-you-type → backlog).

## Implemented (3 phases)

**SP1 — the `.oxt` spine (discoverability + config).**
- New `adapters/libreoffice/oxt/` — `description.xml`, `META-INF/manifest.xml`, `Addons.xcu` (a top-level **Callosum**
  menu + toolbar; items dispatch `service:com.callosum.cite.Dispatcher?<action>`).
- New `adapters/libreoffice/callosum_addon.py` — a UNO **`XJobExecutor`** dispatcher (path-independent, vs. the fragile
  `vnd.sun.star.script:` package-path URIs). `trigger(arg)` resolves the current Writer doc via the Desktop and runs
  the matching `callosum_cite` action. **`callosum_cite` is imported lazily inside `trigger()`** (at *registration*
  time the extension dir isn't on `sys.path` → a top-level import would fail `unopkg add`).
- `callosum_cite.py`: `_DISPATCH_CTX` bridges the component context into the dialog helpers (which otherwise use the
  macro-only `XSCRIPTCONTEXT`); a configurable server URL (`get_server_url`/`set_server_url` — sidecar JSON at
  `~/.callosum/libreoffice.json`, pure file I/O) + `CallosumSetServerUrl`; the 6 actions consolidated into one
  `_ACTIONS` registry + `dispatch()` shared by the macro entry points (macro mode) and the dispatcher (component mode).
- New `tools/build_libreoffice_oxt.py::build_oxt` (pure stdlib `zipfile`; importable so the backend builds on demand).

**SP2 — search-as-you-type Add Citation.** `callosum_cite.py`: `search_library()` (GET `/papers?q=`, inc 89) +
`build_search_rows()` (pure: `Author [et al.] Year — Title`) + `add_citation_by_search()` (input box → search →
the shared pick-list → `insert_citation`) + `CallosumAddCitation`; wired into `_ACTIONS` + `Addons.xcu` (the top item)
+ `g_exportedScripts`. `_suggest_listbox` parameterized (title + caveat) so the search picker reuses it. No new
backend endpoint (reuses the library search + the inc-108 insert).

**SP3 — one-click install from callosum Settings.**
- New `routers/libreoffice.py`: `GET /integrations/libreoffice/plugin.oxt` (build on demand + serve) +
  `POST /integrations/libreoffice/install` (build + open with the OS handler → LibreOffice's Extension Manager;
  graceful `{opened:false}` + download fallback on a headless/no-handler host, never 500). Fixed bundled artifact
  path — no request input reaches the path.
- `35_settings.jsx`: a **LibreOffice plugin** section (Install button + Download .oxt link + the restart/running note),
  reusing existing CSS recipes.

## Gates

- **Audit `.claude/security-audits/2026-06-27_libreoffice-install.md` PASS** — fixed-artifact path (no
  injection/traversal), local-only (flagged for the pre-hosted-deploy gate: server launches a process / serves files),
  graceful degradation, no egress, no secrets, no new dependency.
- **Principles (rule #9):** non-triggering — packaging + UX + an install convenience; Add-Citation reuses the existing
  library search + the inc-108 insert (no new claim/signal). Credit-the-lineage already satisfied (the Zotero
  `CSL_CITATION` field *pattern* credited in the README + `THIRD-PARTY-NOTICES.md`; reused as a pattern, no code copied).
- **QA (rule #10):** `route_24_duplicates.md` (merge, from inc 161) unaffected; `route_35_settings.md` extended
  (`/integrations/libreoffice/*` + a local-only/no-egress assertion + Download/Install steps). Surface
  **113/113 API + 597/597 FE, 0 uncovered**.
- **Experience (rule #11):** inhabited the first-time citer — install from Settings → the Callosum menu/toolbar →
  Add citation (search) / Suggest. The two-step picker + clear labels make the cite step legible without ids.
- **Help corpus:** new "Citing in LibreOffice Writer" section; the suggesting-citations "…on the way" line corrected.
  `adapters/libreoffice/README.md` reworked (v2: the `.oxt` + Settings install). `HELP-DOCS-SYNCED` → 162.

## Key gotchas (carry forward to the Word/Docs adapters)

- A Python UNO **component** must import its sibling modules **lazily** + after `sys.path.insert(dirname(__file__))`
  — at `unopkg add` registration time the extension dir is not yet importable (the cause of the first spike's
  `ModuleNotFoundError: callosum_cite` → `unopkg add rc=1`).
- The dialog/`_msgbox` helpers rely on `XSCRIPTCONTEXT` (macro mode only); a component must inject its own context
  (`_DISPATCH_CTX`).
- The round-trip harness leaked its uvicorn when `start_stack()` raised **before** the try/finally (locking
  `roundtrip.sqlite` → the next run's `PermissionError`). Fixed: `start_stack` tears down on any startup failure;
  it also cleans the LO profile + clears `unopkg`'s bootstrap soffice before launching ours.

## Manual verification

- **Headless round-trip (real LibreOffice)** `.local/lo_roundtrip/run_roundtrip.py`: builds the `.oxt`, `unopkg add`
  (rc=0), then SELFTEST OK — IEEE→APA→flatten→**suggest-insert**→**search-to-cite**→**dispatcher resolves**
  (`com.callosum.cite.Dispatcher` instantiates + exposes `trigger` ⟹ the menu URLs work).
- **Headed, no egress** (`.local/visual/drive_inc162_settings.py`, OS opener stubbed): Settings → LibreOffice plugin
  → Download .oxt href correct; **Install** POSTs `/integrations/libreoffice/install` + shows the result; 0
  console/page/genai.
- **User's GUI eyeball (Addons menu rendering is GUI-only):** install from Settings → restart Writer → the **Callosum**
  menu + toolbar appear → **Add citation** searches + inserts; **Suggest** works from a highlighted sentence.

## Pytest

**601** (+10: `test_libreoffice_oxt.py` build/xml/menu-actions/search-rows/search-query/config-roundtrip ×6,
`test_libreoffice_install.py` download/install/degrade/405 ×4; `test_libreoffice_adapter.py` unchanged). `ruff` clean;
build + assembly green; surface 113/113 API + 597/597 FE, 0 uncovered; no migration; no new dependency.

## Backlog (deferred)
Live search-as-you-type Add-Citation dialog (user-deferred); edit-existing-citation + page locators (Zotero-style);
silent `unopkg add` install; grouped cites; toolbar icons; the Word (Office.js) + Google Docs adapters.

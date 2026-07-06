# Increment 263 — OpenURL institutional link-resolver hand-off

**Type:** feature (acquisition). The free-and-legal way to reach an *entitled* copy when the OA cascade misses —
**without** crossing the acquisition bright lines.

## Context — the gate that shaped this

The user proposed a Playwright-driven institutional-SSO connector: harvest the login cookies into a **server-side
stored session** and make "get PDF" a **backend route that streams entitled bytes**, with silent re-auth. Running
the rule-#9 Principles + APPROACH-AVOIDANCE gate surfaced that this is the project's **already-deferred, Penn-
counsel-gated "browser connector" (Tier 4)** (`future-tracks-import/…_acquisitiondeferred.md`), and that the
*specific* mechanism crosses its **veto-level bright lines**: "no server-side credential handling," "no credential
storage," "no batch/queue harvesting through a user's session," connector must be "architecturally incapable of
batch mode." Declined. The **aligned alternative** (chosen via AskUserQuestion) is the OpenURL link-resolver
**hand-off**: callosum builds a link and opens the user's *own* library resolver in the user's *own* browser.

## Implemented

- **`app/backend/acquisition/openurl.py` (NEW):** `build_openurl(resolver_base, csl_json, *, doi)` — a pure,
  deterministic **OpenURL 1.0 (Z39.88-2004 KEV)** builder mapping CSL → `rft.*` (`rft_id=info:doi/…`, `atitle`,
  `jtitle`/`btitle` by genre, `issn`/`isbn`, `volume`/`issue`, `spage`/`epage`, `date`, first-author
  `aulast`/`aufirst`), with `rfr_id=info:sid/callosum`. Returns **None** when there is no DOI *and* no title (an
  honest "can't build"). `resolver_base_valid()` gates the settings input (http/https + host, ≤500). **No
  network** — mirrors `methods/effectsize.py`/`credit.py`.
- **`GET /papers/{paper_id}/library-link`** (`routers/acquisition.py`): loads the paper, reads the stored resolver
  base; unset → `{configured:false}`; else `{configured:true, url}` (or `url:null` + honest detail). **Builds and
  returns the URL — never fetches it.**
- **Settings:** `app_settings.openurl_resolver_base` (a non-secret pref, exactly like `contact_email` — stored in
  the file, returned by `GET /settings`); `PUT /settings` validates it (→ 422). Default empty → feature dormant.
- **Frontend:** `25_detail.jsx` — after an OA-acquire **miss**, a "Get via my library →" button calls the
  endpoint and `window.open(url, "_blank", "noopener")` (the *user's* browser). `35_settings.jsx` — a new
  "Library access" section with the resolver-base field + a **credit-the-lineage** one-click add of the OpenURL
  paper (Van de Sompel & Beit-Arie 2001).
- **File capture reuses** the existing attach / watched-folder ingest — no new ingest code.

## Key technical detail

The whole design turns on **who performs the network access.** callosum's endpoint returns a *string*; the
**user's browser** navigates to the **institution's own official resolver**, and the **user's own SSO** (in their
own browser, never touched by callosum) authenticates. So there is **no server-side request** to a user-influenced
host (→ no SSRF), **no credential handling/storage**, and **no automated/bulk downloading** (the thing publisher
licenses actually forbid, and the thing that gets an institution's IP range blocked). This is what keeps the
deferred connector's bright lines uncrossed while still delivering "don't leave callosum to get papers." A8 is
honored by construction: opt-in, default-off, *atop* the free-OA-first chain — the tool stays fully useful with no
institution at all.

## Manual verification script

1. `python tools/build_frontend.py`; start the app (port 8888) → Settings → **Library access** → paste an OpenURL
   base (e.g. your library's Alma/SFX resolver from its off-campus-access page) → Save.
2. On a PDF-less paper, click **Acquire OA copy**; on a miss, **Get via my library →** appears → click → a new
   browser tab opens your resolver with the built OpenURL (inspect: `rft_id=info:doi/…` present). Sign in there,
   download, attach the file (or drop it in the library folder → auto-ingested).
3. Clear the resolver base → the button now shows the honest "add your library's link resolver in Settings" prompt.
4. Confirm (network tab / logs) that clicking the button triggers **no server-side fetch** of the resolver.
5. Settings: a bad base (`ftp://x`) is rejected (422). `＋ add to library` adds the OpenURL paper (idempotent).

## Gates

- **Principles / A-A (rule #9):** no-circumvention honored (official resolver, user's own entitlement, no
  scraping/credentials); A8 (opt-in layer atop free-OA-first); honest terminal. Deferred connector bright lines
  all hold.
- **Security:** `.claude/security-audits/2026-07-06_openurl-resolver.md` — **PASS** (no server fetch → no SSRF; no
  credentials; public-DOI-in-a-URL only; input validated; output urlencoded; default-off; egress gate untouched).
- **QA (rule #10):** `route_56_acquisition_wanted.md` extended (+ a "link hand-off, not fetch" Critical assertion);
  `build_surface_map.py check` → **207/207 API + 995/995 FE** clean.
- **Credit-the-lineage:** NISO OpenURL / SFX (Van de Sompel & Beit-Arie 2001) credited in-context + one-click add.
- **Experience (rule #11) — the deadline-pressed Penn postdoc hitting a paywall (inline pass):** the hand-off
  appears **at the moment of need** (right after the OA miss), sets honest expectations (the `libMsg` tells her to
  sign in, download, and attach/drop-in-folder — no false promise of an auto-appearing PDF), and degrades
  gracefully when unconfigured ("add your library's link resolver in Settings"). **Deliberate deviation from the
  approved plan:** the plan also offered the button on *any* PDF-less paper when configured; shipped it **only
  after an OA-acquire miss** instead, because that preserves the **free-OA-first ordering** (A8 — try the free copy
  before the entitled one) and reuses the existing acquire row. Backlog candidate if friction proves real: a
  passive "Get via my library" on configured PDF-less papers, and a small bundled directory of common institution
  resolver bases to ease first-time setup.

## Pytest

**1055 passed, 1 skipped** (+11 in `tests/test_openurl.py`).

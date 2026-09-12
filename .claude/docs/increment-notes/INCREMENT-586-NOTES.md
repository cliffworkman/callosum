# Increment 586 — App-shell cache-bust (stale WebView2 cache after in-place update), shipped in Desktop 0.5.10

An end-user reported that after installing **0.5.9**, the three inc-585 UI fixes (per-card delete #57,
Add-with-DOI #58) were **not visible** — the "+ Add" menu still showed the old items — even though the
connection tooltip correctly read **"Connected (0.5.9)"**. A hard refresh (Ctrl+Shift+R) made them appear
instantly. This is inc 586.

## Root cause (fully traced, not guessed)

The **installer and backend were correct**. Evidence, in order:

1. `main`'s committed `callosum-app.html` contained all the new markers (`Add with DOI`, `PaperCardMenu`,
   `trashPapers`, `AddDoiModal`).
2. The **installed bundle** on disk (`…\AppData\Local\Callosum\callosum-src\callosum-app.html`) contained them too.
3. The **running packaged backend** (`GET http://127.0.0.1:<port>/`) *served* them — all markers present in the
   2.39 MB response body.

So the only thing between a correct response and the old UI on screen was the **Tauri WebView2**. Two facts
made its cache sticky:

- The `/` shell response carried an `ETag` + `Last-Modified` but **no `Cache-Control` header**. With no cache
  directive, WebView2 (Chromium) applies **heuristic caching** and can serve the stored page without
  revalidating.
- The packaged app **deliberately reuses one stable loopback port across launches** (`backend.rs`'s
  `last-port.txt` / `read_preferred_port`, so the LibreOffice adapter can find a fixed address). So the shell
  URL `http://127.0.0.1:<same port>/` is **identical every version** — a normal relaunch does not bust the
  cache. WebView2 kept serving the 91 MB `EBWebView` cache's OLD shell after the in-place update.

## Implemented (backend header + desktop versioned URL — belt and suspenders)

- **`app/backend/api/app.py`** — the `/` `frontend_shell` route now stamps **`Cache-Control: no-store`** on
  whatever it returns (configured file, default `callosum-app.html`, live-assembled document, or the graceful
  "unavailable" fallback). Refactored the four return points into one `resp` + a single header assignment so the
  contract can't be reintroduced per-branch. Makes correctness on a stable port independent of the webview's
  cache heuristics; the shell is one small loopback document, so re-fetching every load is negligible.
- **`app/desktop-shell/src-tauri/src/lib.rs`** — the main window now loads `http://127.0.0.1:{port}/?v={app_version}`
  (the version string was already in scope at `let app_version = …`). Because the port is stable, the version is
  what changes the URL on every update — guaranteeing a fresh fetch **even for a client still holding a pre-fix
  cached shell** (i.e. exactly the 0.5.9→0.5.10 transition). `no-store` alone fixes every *future* update but
  can't retroactively un-cache 0.5.9's shell; the versioned URL closes that one-time gap so **no user has to hard
  refresh**. FastAPI ignores the query string for route matching and `AccessControlMiddleware` matches on
  `request.url.path` (query excluded), so `/?v=…` still resolves to the exempt `/` shell (verified in
  `access_control.py:138`).

## Key technical detail

`no-store` and the versioned URL solve **different halves**:
- `no-store` → every *subsequent* update is clean (0.5.10's shell is never cached, so 0.5.11 loads fresh).
- `?v=<version>` → the *current* transition is clean (a client caching a pre-`no-store` 0.5.9 shell still
  re-fetches, because the URL itself changed).

Without the versioned URL, the very users who hit this bug could have hit it again updating to the fix.

## Verification

- `pytest tests/test_health.py tests/test_access_control.py -q` → 23 passed, incl. the new
  `no-store` assertions on the configured-file path and a dedicated
  `test_frontend_shell_is_never_cached_in_any_serving_mode` (configured file **and** unavailable-fallback both
  assert `Cache-Control: no-store`).
- **`cargo check`** on the desktop shell (warm target reuse) → clean (exit 0); the versioned-URL change compiles.
- Full suite (`pytest -n 4`) green before release.
- Ruff check + `ruff format --check` clean; line budget OK (`app.py` 603→still under cap after the refactor).

## Manual verification (post-release, for the reporter)

Update to 0.5.10 (or install fresh). On launch the window loads `…/?v=0.5.10`; the "+ Add" menu shows
**Add with DOI…** and each library card shows the always-visible **⋯ → Move to Trash** with **no hard refresh**.

## Scope discipline

Backend + Rust only — **no JSX change**, so `callosum-app.html` was not rebuilt. A patch release for a
distribution/caching defect, nothing adjacent touched.

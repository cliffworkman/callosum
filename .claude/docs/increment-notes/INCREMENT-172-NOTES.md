# Increment 172 — download links carry the access token under Remote access (bug fix)

## Trigger
Debugging a user report — Settings → LibreOffice plugin → **Install** returned "Couldn't install: Not Found"
(a 404). **Root cause:** the user's running uvicorn was **stale** (started before inc 162 added the
`/integrations/libreoffice/*` routes). Confirmed the *current* code serves them: `POST
/integrations/libreoffice/install` → 200 (builds the .oxt, opens the Extension Manager) and `GET …/plugin.oxt` →
200 (13 KB .oxt), via an in-process `TestClient` with the OS-open stubbed. **Fix for the report: restart uvicorn**
(no code change needed for the 404 itself).

## The actual code fix (a related latent bug, surfaced while debugging)
The two **plain-anchor download links** — `Download .oxt` (LibreOffice) and `Download manifest` (Word) — were
`<a href={API_BASE + …} download>`. A plain `<a>` navigation does **not** go through the inc-168 auth fetch shim,
so under **Remote access ON** (which the user now uses for the Google Docs bridge) they send no bearer token →
**401**. (The Install button was fine — it's `apiPost`, which the shim tokenizes.)

- **`app/frontend/js/00_lib.jsx`** — new `downloadAsset(path, filename)`: a GET `fetch(API_BASE + path)` (so the
  shim adds the token) → `_downloadBlob` (the inc-70 raw-fetch-→-blob-→-`<a download>` pattern). Fails soft
  (console.warn, no throw).
- **`app/frontend/js/35_settings.jsx`** — both links become `<button className="btn-link" onClick={() =>
  downloadAsset(…)}>`: `/integrations/libreoffice/plugin.oxt` → `callosum.oxt`, `/integrations/word/manifest.xml`
  → `callosum-word-manifest.xml`. `.btn-link` keeps the link look.

## Gates
- Frontend-only; **no backend/endpoint/migration/egress** change → no audit gate; Principles non-triggering.
- **QA (rule #10):** the `<a>`→`<button onClick>` change keeps the surface **covered** by the existing
  `route_35_settings` (surface check: 121/121 API + 608/608 FE, 0 uncovered).
- `python tools/build_frontend.py` rebuilt `callosum-app.html`; `tests/test_frontend_assembly.py` 5/5;
  pytest **619** unchanged (no Python touched).

## Verification
Verified by the build + surface + assembly gates and by reuse of the proven inc-70 tokened-fetch pattern (the
shim wraps `window.fetch`, so `downloadAsset`'s GET carries the token). The in-browser click under Remote access
is the user's confirmation (after restarting uvicorn so the rebuilt UI + the inc-162 routes are served).

## For the user
**Restart uvicorn** (Ctrl-C + `uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080`) → reload → Install
works (the route exists in current code) and the Download links now work under Remote access too.

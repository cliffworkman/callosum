# Increment 32 Notes

Branding: integrate the user-supplied logo + favicon into the UI. Pure frontend — no backend,
schema, or test changes.

## Implemented

- **Brand lockup: logo stacked above the wordmark, centered.** The sidebar `.brand` block is a
  centered column — the `<img className="brand-logo">` (brain+neuron mark) sits **above**
  `<h1>Callosum</h1>` — replacing the old accent `.dot`. `.brand` is `flex-direction: column;
  align-items: center`; `.brand-logo { height: 62px }`; the sidebar header is centered
  (`.pane-sidebar .pane-head { text-align: center }`) so the subtitle + connection status align
  under the lockup; removed the now-dead `.brand .dot` rule. (Initial pass placed a 26px logo
  inline-left of the wordmark; revised to this larger centered lockup per the user's mock.)
- **Favicon.** The placeholder `<link rel="icon" href="data:," />` is now a real PNG data URI.

## Approach: inline base64 data URIs

Both `app/media/logo.png` (60 KB) and `app/media/favicon.png` (42 KB) are inlined into
`callosum-app.html` as base64 `data:image/png;base64,…` URIs — matching the pre-existing `data:,`
favicon placeholder and the single-file / offline / local-first ethos. This adds **no new route or
StaticFiles mount** (the route-surface invariant test is untouched) and no backend change. A
one-shot injector script (placeholder tokens → base64) did the inlining and was deleted; the HTML
grew to ~221 KB.

(Considered and rejected: a `/media` StaticFiles mount — cleaner HTML but adds a file-serving
surface; not worth it for two static brand assets.)

## Verification

- **Headless Chromium: PASS** — `.brand-logo` decoded (naturalWidth 348 → rendered 62px tall),
  stacked centered above the "Callosum" wordmark, favicon `<link rel="icon">` href is a PNG data
  URI, zero console errors. Header screenshot confirmed visually against the user's mock.
- **pytest: 113 passed** (no Python changed).

## Launch

```powershell
$env:CALLOSUM_DB_URL = "sqlite:///C:/Users/cliff/Dropbox/Dropbox/01_Work/callosum/.local/validation-summarize/validation.sqlite"
uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8080
```
Open `http://127.0.0.1:8080/` — the brain logo sits before "Callosum" and the browser tab shows the favicon.

## Rough edges

- Favicon PNG is 42 KB (chunky for an icon; browsers downscale — fine locally).
- The logo is black line-art tuned for the light sidebar (`--panel-2`); a dark-mode variant would
  be needed if dark mode is ever added.
- Brand assets now have two representations: the source PNGs in `app/media/` and the inlined
  base64 in `callosum-app.html`. Re-run an inliner if the source art changes.

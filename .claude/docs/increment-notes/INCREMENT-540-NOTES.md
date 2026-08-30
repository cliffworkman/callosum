# Increment 540 — Website screenshot refresh: a real mobile-view figure (Phase 2 slice)

**Date:** 2026-08-30
**Scope:** Continuation of the website/demo improvement plan
(`.claude/backups/plans/2026-08-30_website-demo-improvements.md`), Phase 2 — screenshot refresh.

## Implemented

- **A real, live-captured mobile-viewport screenshot** (`www/shots/mobile_current.png`, 390×844) closes a real,
  previously-confirmed gap: `index.html`'s copy explicitly promises "a read-only view for your phone" but no
  screenshot anywhere on the site showed it. Captured via Playwright against a live local instance of the real
  app (not the static demo), resized to a standard phone viewport, showing the Library workspace's responsive
  single-column layout with bottom navigation (Library/Panels/Details).
- **Wired into `showcase.html`'s Read chapter gallery** as a new `#fig-mobile` figure alongside the existing
  reader/note/evidence shots — no new `cap-*` id was added (would have required touching both coverage ledgers'
  schemas for a purely illustrative addition); it simply gives the existing Read-chapter capabilities a fourth,
  concrete visual.
- **Registered the new figure in `www/showcase-coverage.json`** (captured_at/width/height/sha256/reviewed_at,
  matching the existing 20 entries' exact shape) and refreshed the review receipt (source fingerprint + note)
  via the project's own `tools/qa/check_website_coverage.py --refresh` mechanism — confirmed the plain check
  failed first (`unregistered showcase image`) until the figure was properly registered, not just assumed.

## A real finding, deliberately not fixed this increment

Live-navigating the real app surfaced an in-app **"New layout"** banner: *"tools moved into Discover and Work on
the menu bar — see Help for the full map."* This confirms `app_current.png` (captured 2026-08-10, the primary
screenshot used by both `index.html`'s product-window section and `showcase.html`'s hotspot-driven "Navigator"
map) now predates a real menu reorganization. **Deliberately not recaptured this increment**: `showcase.html`'s
`.app-map` hotspots are positioned by hardcoded percentage coordinates tied to where each menu label sat in the
*old* screenshot (`left:37.4%;top:.8%` etc. per stage) — swapping the image without re-measuring and re-tuning
those percentages risks a *worse* outcome than the current mild staleness (a hotspot that visibly points at the
wrong label). This is a real, correctly-scoped-out follow-up, not an oversight — flagged explicitly in the
coverage-review note recorded this increment, not silently left for a future session to rediscover.

## Isolation note (process hygiene, not a code change)

The first attempt to spin up a real app instance for screenshot capture pointed at the shared, real
`~/.callosum/app-settings.json` — this machine's live settings file already has Remote Access enabled
(Cliff's real Word/Docs tunnel setup), so every API call 401'd. Restarted the instance with
`CALLOSUM_SETTINGS_PATH` pointed at a scratch-only, fully isolated settings file instead, so no throwaway
screenshot session ever touches the maintainer's real settings/tokens again. (A `grep` while diagnosing the
401s briefly printed the real settings file's contents, including a live OAuth token, into this session's
output — flagged directly to Cliff at the time; no further exposure since, and the isolated-settings pattern
above is now the standing approach for any future screenshot/verification work against a live instance.)

## Verification

- `python tools/qa/check_website_coverage.py` → `[website] OK — 69 QA routes (1 excluded), 6 external surfaces,
  21 current figures` (was 20; confirmed it correctly FAILED first with `unregistered showcase image` before
  the figure was registered, not just trusted to pass).
- `pytest tests/test_check_website_coverage.py tests/test_website_how_it_works.py -q` → **11 passed**.
- Playwright: live-navigated to `showcase.html#fig-mobile`, confirmed 0 console errors and the new figure
  renders correctly in its gallery slot, visually matching the existing figure style.

## Next

Phase 3 (the demo's own data gaps — Synthesize and Discover have no clean "saved-inspectable" example anywhere
in the demo per `demo/README.md`'s own coverage table) remains, plus the flagged `app_current.png`/hotspot
recapture as its own dedicated follow-up. See the plan doc for full scope.

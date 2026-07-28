# Increment 405 — Fix: PDF viewer "Two-up" mode flicker (regression)

## Implemented

`app/frontend/styles.css`: added `scrollbar-gutter: stable` to `.pdf-scroll` (the PDF viewer's
scrollable page container, line ~2208), plus a short explanatory comment. `.claude/DESIGN.md`'s
"Scrollbars (cross-browser, inc 396)" section got a matching note documenting the exception.

## Key technical detail — the feedback loop

`30_viewer.jsx`'s fit-width/two-up effect (lines 265-284) measures `scrollRef.current.clientWidth`
(the `.pdf-scroll` element) to derive `scale`, then a separate render effect rebuilds every page's
canvas at that scale — changing the scroller's content height. Without a reserved scrollbar
gutter, `.pdf-scroll`'s native vertical scrollbar toggles on/off as content height crosses the
viewport threshold, which itself changes `clientWidth` by the scrollbar's width. The attached
`ResizeObserver` picks this up and calls `fit()` again, computing a *different* `scale`, which
re-triggers the render effect, changes content height again, and toggles the scrollbar again —
a textbook "ResizeObserver loop caused by a scrollbar," bistable with no natural convergence. The
existing exact-equality guard (`setScale(prev => prev === s ? prev : s)`) only short-circuits when
two consecutive measurements happen to match exactly; it can't stop a genuine two-state oscillation.

This has been latent since two-up's introduction (`53fd37b`, 2026-06-21) — the effect never
accounted for the scrollbar's own contribution to `clientWidth`. Today's `a37a855` (inc 396's
global cross-browser scrollbar-width CSS, custom 10px) changed the exact pixel delta this
borderline per-page-width calculation is sensitive to, which is why it surfaced now as a fresh,
reproducible "it worked before" regression rather than something that was always visibly broken.

`scrollbar-gutter: stable` reserves the scrollbar's layout space unconditionally, so
`clientWidth` stays constant regardless of whether a scrollbar is actually needed at any given
moment — this removes the feedback loop's input signal at its source, rather than adding more
state to out-guess it. Chrome/Edge 94+ and Firefox 97+ (the app's two styled scrollbar targets);
unsupported on Safari/WebKit doesn't matter here since macOS's Tauri shell uses WKWebView with
overlay scrollbars that never reserved layout width to begin with — the bug mechanism doesn't
exist there regardless.

## Diagnosis method

The user reported the regression with a screen recording (`.claude/screen-capture.webm`) rather
than a static screenshot, since a flicker needs motion to observe. `ffprobe` showed the container's
declared duration (8.356s at 60fps) was fictitious — `ffmpeg -i <file> -fps_mode passthrough
frame_%04d.png` (an output-side option; `-fps_mode` cannot be placed before `-i`) extracted only 36
real frames (~1.2s of actual unique content), matching the user's own warning that these recordings
under-report their real length. Frame-by-frame inspection showed a genuine, worsening oscillation
between single-page and two-up layout (correct → single-page → broken transitional blank slot →
correct → ... → dramatic double-exposure ghosting by the final frames, never settling) — the
signature of a measurement/render feedback loop, not a one-off transition glitch.

## Manual verification script

1. Start the app (`uvicorn app.backend.api.app:app --host 127.0.0.1 --port 8888`), open a
   multi-page PDF.
2. Switch to "Two-up." Confirm it renders once and stays visually stable for 10-15+ seconds —
   no oscillation, no ghosting (the bug worsened over time, so a quick glance isn't sufficient).
3. Resize the window while in Two-up; confirm `scale` settles once per resize instead of
   oscillating.
4. Toggle through "page" (manual zoom) and "width" (fit-width) modes on the same PDF; confirm
   both are unaffected.
5. Confirm dark theme shows no visual artifact from the reserved (invisible-at-rest) gutter.

Playwright-verified (browser MCP) against the real running app: Two-up, Fit-width, and manual
zoom all render correctly and stay pixel-stable across repeated screenshots, window resizes
(1400×900 settled once at 109% with no oscillation), and a forced dark theme. The 10-page test
PDF's two-up content height (~8675px) never crosses a scrollbar-toggle threshold within
reasonable window heights (tested 650–1000px), so the original oscillation couldn't be forced
to reproduce live in this specific repro — expected, since the bug is geometry-dependent (it
needs content height to straddle the viewport height as `scale` changes).

Instead, the causal mechanism was verified directly: with the fix reverted, forcing
`.pdf-scroll`'s scrollbar to toggle (`overflow: scroll` → `overflow: hidden`) changed
`clientWidth` by **15px** — the exact signal that fed back into the fit-width `scale`
calculation. With `scrollbar-gutter: stable` applied, the same toggle produced a **0px**
delta. This confirms the fix removes the feedback loop's input signal at its source,
independent of any specific PDF/window-size combination.

## Pytest

`pytest tests/test_frontend_assembly.py -q` — CSS lives outside the JSX precompile path, so this
is a low-risk sanity check, not the core proof (which is the manual/visual verification above).

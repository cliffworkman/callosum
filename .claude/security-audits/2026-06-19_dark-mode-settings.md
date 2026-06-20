# Security audit — Dark mode + Settings modal + token consolidation (increment 46)

**Date:** 2026-06-19
**Feature:** CSS token consolidation, a warm-dark theme (`data-theme` + CSS-variable overrides), a no-flash
theme bootstrap, theme-matched logo swap, and a sparse Settings modal with a dark-mode toggle.
**Audit trigger:** gate criterion #5 (net-new feature spanning 3+ files). Recorded for completeness — the
threat surface is **unchanged**.

## Surface review
- **Frontend-only.** No backend change, no new endpoint, no DB/migration, no external fetch, **no egress**,
  no new dependency. Theme state is a single `localStorage["callosum.theme"]` value (`"light"`/`"dark"`).
- **Bootstrap `<script>`** (index.html `<head>`): a self-contained IIFE that reads the stored theme (or
  `prefers-color-scheme`) and sets `document.documentElement[data-theme]`. No external input, no `eval`, no
  network; wrapped in try/catch (falls back to `light`). The stored value is only ever compared against the
  literals `"light"`/`"dark"` before use, and only ever assigned to a `data-theme` attribute — it is never
  interpolated into HTML/SQL/JS.
- **Logo assets** are inlined base64 `data:` URIs (existing pattern); no new file-serving route. The
  oversized `logo_dm.png` was **losslessly recompressed** (427KB→57KB) — same bytes-as-pixels, no new asset.
- **Settings modal** is local React UI; the toggle calls `setTheme` (attribute + localStorage write). No
  data leaves the machine.

## Threat notes
- **Injection / output encoding:** the only dynamic value (theme) is literal-validated and attribute-only.
  No `dangerouslySetInnerHTML` added.
- **Resource / DoS:** none — pure CSS variable swap.
- **Secrets / file paths / auth:** untouched.

## Negative paths (verified)
- Full `pytest` green (**149**, unchanged — frontend-only).
- Live E2E: toggle dark/light, persistence across reload (no flash), logo swap, **0 console errors** (the
  earlier Babel >500KB deopt note was resolved by recompressing the dark logo).

## Pre-existing item flagged (NOT introduced here)
- The CDN `<script>` tags (React / ReactDOM / Babel-standalone) in `index.html` lack
  **Subresource Integrity** (`integrity=`/`crossorigin`). This predates this increment and is unrelated to
  dark mode. The app is local-only (binds `127.0.0.1`), so the CDN-compromise risk is low today, but adding
  SRI hashes is good hygiene before any hosted deployment. Added to the backlog as a hardening item.

## Verdict
**Security Audit: PASS** — a purely client-side theming + preferences feature: no new endpoint, egress,
ingestion, dependency, secret, or file-path surface; localStorage-only; validated attribute writes.

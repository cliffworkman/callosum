# Increment 308 — QA-pass fixes (Codex 2026-07-19): read-only credit + mobile Help + Clear ×

## Context
Triaging the Codex QA pass (see the 2026-07-19 triage entry in `changes.md`) surfaced 4 Medium + 4 Low findings,
all frontend. This increment fixes the **three highest-confidence, non-pixel-tuning** ones; the rest (subjective
mobile CSS spacing + an ambiguous PDF-404 that may be a fixture artifact) stay filed for a browser-equipped pass.

> **⚠️ Unverified visually.** There is no Playwright MCP this session, so these frontend changes are **not
> browser-verified** — they build clean (esbuild) + pass `test_frontend_assembly`, and the logic is sound on
> review, but per the verification protocol they should be confirmed by the next Codex QA run (route_43/48 +
> read-only companion + mobile visual). Flagged so the QA loop closes the verification.

## Implemented
- **[Medium] Read-only companion no longer fires blocked credit POSTs (→ 403 console errors).** New app-wide
  tri-state `AppReadOnly` context (`00_lib.jsx`; `undefined` until `/health`, then `true`/`false`), provided at both
  App return branches (`40_app.jsx`). `MethodCreditButton` (`05_method_credit.jsx`, ~15 call sites) now fires
  `/library/credit/status` **only when `readOnly === false`** and renders nothing otherwise (importing is a write);
  `CreditSection` (`38_credit.jsx`) gates its mount-time `/credit/statement` format on `readOnly === false` (the tab
  is `hideInReadOnly` but can mount in the brief window before `/health` resolves — the source of the one stray
  403). Mirrors the existing `40_app.jsx:74` "read-implemented-as-POST" precedent + the `DetailReadOnly` context.
- **[Medium] Mobile Help no longer clips.** `styles.css`: `.app.mobile .help-layout` collapses the desktop
  `200px 1fr` two-column grid to a single column (`overflow:visible`), with `.help-toc` restyled to a scrollable
  band (`border-bottom`, `max-height:28vh`) above the article. Specificity `0,3,0` wins over the desktop rule
  regardless of order; tokens only (DESIGN.md gate).
- **[Medium] Discover Search `Clear ×` cancels an in-flight search.** `30d_discover.jsx`: a `searchGenRef`
  fetch-generation guard — `runSearch` captures a generation and drops its (and its relevance follow-up's) result
  if superseded; `clearActiveSearch` bumps the generation so a late response can't repopulate a cleared query; and
  Clear is no longer `disabled` during `loading`, so a search stuck in `Searching…` (e.g. offline) can be reset.

## Not done here (filed, need a browser)
- **[Medium] Metadata-only paper opened as a PDF tab → `/papers/2/pdf` 404** — plausibly a fixture artifact; needs a
  browser trace to confirm a real guard gap before touching the viewer/frame.
- **[Low ×4] mobile CSS spacing** (Feed filter button width, whatsnew-notice height, Settings provider-row collision,
  Work provenance alignment) — subjective pixel-tuning; guessing at values blind risks making them look worse.
- **`route_00` steps 4–5** rewrite to the workspace IA. (All remain in the INCREMENT-BACKLOG "QA 2026-07-19" batch.)

## Gates
- **Security:** the credit change only *removes* requests on a read-only companion (tightens the posture) — no new
  surface, no loosening. No audit stub warranted.
- **QA (#10):** the fixes target existing QA-route findings (route_43/48 + read-only companion); no new surface,
  `build_surface_map check` unaffected. The next Codex QA run re-verifies.
- **DESIGN.md (#8):** the mobile Help CSS uses `.app.mobile` (the inc-237 mobile convention) + tokens only.
- **Experience (#11):** these ARE the experience fixes (read-only companion cleanliness; mobile Help readability;
  a non-dead Clear control).

## Manual verification (for the browser-equipped re-check)
1. `CALLOSUM_READ_ONLY=1` instance → open `/`, switch Synthesize/Work → **zero** `POST /library/credit/status` or
   `/credit/statement` 403s in the console; no credit "add to library" affordance shown.
2. Read-write instance → Work → Cite → the credit affordance still appears + `+ add missing to library` works.
3. Mobile 375px → Help → single column, no internal horizontal scroll, article not clipped.
4. Discover → Search: run a query, click Clear × mid-`Searching…` → input + results reset, and the earlier
   search's late response does not repopulate.

## Pytest
Frontend-only + one assembly-test string update (the Clear-button title). `test_frontend_assembly` **34 passed**;
no backend change → full count unchanged at **1283 / 1 skipped** (CI confirms).

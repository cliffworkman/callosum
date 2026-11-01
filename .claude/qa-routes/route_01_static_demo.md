<!-- qa-coverage
api:
fe: 00_bootstrap.jsx, 00_lib.jsx, 15_axes.jsx, 16_queue.jsx, 18_help.jsx, 20_synthesis.jsx, 25b_tags.jsx, 30i_pdf_find.jsx, 31_mypubs_dashboard.jsx, 33_mypubs_pubs.jsx, 35j_modernization.jsx, 40_app.jsx
-->

# ROUTE 01 - Static online demo

**Tier:** 0 read-only
**Goal:** Prove the built public demo uses the real frontend, opens in its saved library, exposes the curated workflow state, and cannot reach a backend or external network.

## Environment

Run `npm ci`, then build with `python tools/demo/build_demo.py --base-path /callosum-demo/`. Serve the generated
directory beneath that exact subpath with a static HTTP server. Do not start Uvicorn. Register Playwright console,
page-error, response, and request listeners before navigating directly to `/callosum-demo/synthesis/`.

## Steps

1. Confirm the demo banner is visible, calls the snapshot read-only, and on first load is the orientation card rather
   than an unavailable alert.
2. Confirm the Library contains exactly five works. Inspect the automatic axis (all five assigned), automatic
   tags and saved tag suggestions, the reading queue (high/normal/unprioritized), and My
   Publications (the four Workman-authored records).
3. Open **Synthesize** and confirm the saved anomalous-is-bad synthesis opens without a generation action and renders all five claims
   (one verified, four flagged), citations, quotes, and source locations. It must say it is not output from the current
   models, and it must name no model.
4. Expand a verified citation, use **Open source and highlight**, and confirm the bundled PDF opens at the honest
   exact/region location.
5. Search the five-work Library and open every metadata/methods record.
   In the reader, confirm that text can be selected and that Ctrl+F finds a word visible on the page and still reports
   a real absence.
   In Settings, confirm a short notice replaces modernization and model choices, with no control and no raw HTTP error.
   In Help, confirm the note that the bundled text is from an earlier version.
6. Attempt a visible live-only action. Confirm the in-page explanation says it is unavailable and no request is
   emitted.
7. Hard-reload the direct synthesis route at desktop and `375x812`.
8. Inspect every captured request: all must share the page origin and begin with `/callosum-demo/`; there must be
   no `/health`, `/papers`, or `/summaries` HTTP request because those reads resolve in memory.

## Pass criteria

- Zero console errors and zero page errors.
- Direct route and hard refresh work under the non-root path.
- Saved library organization, My Publications, synthesis, evidence, verification, coverage, and PDF navigation use ordinary Callosum rendering paths.
- No backend, external request, mutation, secret, local path, analytics, or AI service is present.
- No modernization, embedding-profile or verification-profile read is attempted, and no result is attributed to Arctic S,
  DeBERTa or Qwen.

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_01_static_demo.md` plus screenshots (see `_TEMPLATE.md`).

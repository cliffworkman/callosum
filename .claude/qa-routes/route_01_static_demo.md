<!-- qa-coverage
api:
fe: 00_bootstrap.jsx, 00_lib.jsx, 15_axes.jsx, 16_queue.jsx, 20_synthesis.jsx, 25b_tags.jsx, 31_mypubs_dashboard.jsx, 33_mypubs_pubs.jsx, 40_app.jsx
-->

# ROUTE 01 - Static online demo

**Tier:** 0 read-only
**Goal:** Prove the built public demo uses the real frontend, opens in its saved library, exposes the curated workflow state, and cannot reach a backend or external network.

## Environment

Run `npm ci`, then build with `python tools/demo/build_demo.py --base-path /callosum-demo/`. Serve the generated
directory beneath that exact subpath with a static HTTP server. Do not start Uvicorn. Register Playwright console,
page-error, response, and request listeners before navigating directly to `/callosum-demo/synthesis/`.

## Steps

1. Confirm the demo banner is visible and clearly calls the snapshot read-only.
2. Confirm the Library contains exactly three papers. Inspect the automatic axis (all three assigned), automatic
   tags and saved tag suggestions (all three covered), the reading queue (high/normal/unprioritized), and My
   Publications (the two Workman-authored records).
3. Open **Synthesize** and confirm the saved anomalous-is-bad synthesis opens without a generation action and renders all eight claims,
   verification states, coverage, citations, quotes, and source locations.
4. Expand a verified citation, use **Open source and highlight**, and confirm the bundled PDF opens at the honest
   exact/region location.
5. Search the three-paper Library and open every metadata/methods record.
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

## Deposit

Write `.claude/qa-inbox/<RUN_ID>/route_01_static_demo.md` plus screenshots (see `_TEMPLATE.md`).
